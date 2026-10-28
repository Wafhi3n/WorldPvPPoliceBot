"""Les appels à l'aide de World PvP Police : une ligne `SOS`/`OMW`/`END` venue du jeu dans le salon relié
met à jour LA carte de sa zone dans #alertes-pvp (spec alertes-pvp.md, B-T3, P10 à P13).

- Une carte par ZONE en cours (P10) : un appel dont la zone a déjà une carte en cours la rejoint ; un
  appel n'est jamais sur deux cartes, et jamais deux cartes pour une même zone en cours (P12).
- Le rôle n'est mentionné qu'à la PUBLICATION d'une carte (P6, P11), jamais à une modification ni pour
  un 2e appelant, jamais `@everyone` ; le texte des joueurs ne va que dans l'embed (critère 2).
- Plusieurs serveurs (bot-autonome.md, A1-A2) : chaque serveur a ses cartes dans SON salon des cartes,
  trouvé ou créé par son nom (`install.py`) ; avec `DISCORD_PVP_CHANNEL_ID`, un seul serveur.
- La ligne brute quitte le salon relié (`BOT_SUPPRIMER=oui`, P3) seulement si la carte est faite ;
  un envoi en échec la GARDE (critère 6).
- Rien n'est gardé d'un démarrage à l'autre : à la 1re rencontre d'un serveur, ses cartes en cours sont
  relues dans ses derniers messages (`_sweep`) ; au démarrage, les lignes ratées pendant l'arrêt (encore
  dans le salon relié) sont rattrapées.
- Le salon se vide tout seul (P13) : une carte finie depuis `BOT_GARDER_HEURES` (24 h) est effacée.
- Une ligne à la fois (verrou). L'heure est celle de DISCORD (`created_at`), pas celle du serveur du bot
  (qui retardait de 114 s le 2026-10-28) ; l'écart est appris des messages qui arrivent.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import logging
import time
from collections import deque

import discord

from .game import delete_relayed, is_from_game
from .install import Server, install
from .pvp_cards import (ACTIVE, EXPIRY, MAX_CALLS, SETTLED, Card, add_responder, expire, is_live, join, key,
                        next_expiry, open_card, update_call)
from .pvp_embed import from_embed, to_embed
from .pvp_line import PvpLine, parse
from .pvp_map import load_index, render

HISTORY = 200        # messages relus dans #alertes-pvp (les cartes) ou dans le salon relié (le rattrapage)
CLEAN_EVERY = 3600   # s entre deux nettoyages du salon des cartes


class PvpRelay:
    def __init__(self, client, conf, log: logging.Logger, clock=time.time, sleep=asyncio.sleep, maps=None):
        self.client, self.conf, self.log, self.clock, self.sleep = client, conf, log, clock, sleep
        self.maps = load_index() if maps is None else maps   # uiMapID → image, ou un magasin (map_store)
        self.servers: dict = {}            # id du serveur (None : un seul, configuré) → Server
        self.cards: dict = {}              # (serveur, appelant, numéro) → Card (plusieurs clés, une carte)
        self.lock = asyncio.Lock()
        self.timers: dict = {}             # id(carte) → minuteur de son prochain appel sans nouvelles
        self.tasks: set = set()
        self.offset = 0.0                  # heure de Discord - heure du serveur, apprise des messages reçus
        self.done: deque = deque(maxlen=500)   # ids des lignes déjà traitées (direct ET rattrapage)

    def now(self) -> float:
        """L'heure de Discord, autant qu'on la connaît."""
        return self.clock() + self.offset

    def _time(self, message, live: bool) -> float:
        """L'heure d'une ligne : celle de Discord ; une ligne qui arrive en direct règle l'écart."""
        created = getattr(message, "created_at", None)
        if created is None:
            return self.now()
        at = created.timestamp()
        if live:
            self.offset = at - self.clock()
        return at

    # ===== L'image =====

    async def _map_file(self, map_id):
        """L'image de la zone : un index (uiMapID → fichier) ou un magasin qui télécharge à la demande."""
        if hasattr(self.maps, "path"):
            return await self.maps.path(map_id)
        return self.maps.get(map_id)

    async def _art(self, card: Card) -> tuple[discord.Embed, list]:
        """L'embed de la carte et ses pièces jointes : l'image de la zone avec un point par appelant de
        cette zone, redessinée à chaque envoi ; aucune pièce jointe sans point (zone seule, autre zone)."""
        points = [(c.x, c.y, c.caller) for c in card.calls if c.map == card.map and c.x is not None]
        path = await self._map_file(card.map) if points else None
        art = render({card.map: path}, card.map, points) if path is not None else None
        if art is None:
            return to_embed(card), []
        data, name = art
        return to_embed(card, name), [discord.File(io.BytesIO(data), filename=name)]

    # ===== Les serveurs =====

    @property
    def configured(self) -> bool:
        """Un seul serveur, aux identifiants configurés (le mode du module d'origine)."""
        return bool(getattr(self.conf, "pvp_channel_id", None))

    @property
    def enabled(self) -> bool:
        return self.configured or bool(getattr(self.conf, "install", False))

    def _gid(self, guild):
        return None if self.configured else getattr(guild, "id", None)

    async def _server(self, guild) -> Server | None:
        """Le salon des cartes et le rôle du serveur de ce message : configurés, déjà connus, ou installés
        (trouvés ou créés par leur nom), puis ses cartes en cours relues. Appelée SOUS le verrou : un
        serveur ne s'installe et ne se relit qu'une fois."""
        gid = self._gid(guild)
        if gid in self.servers:
            return self.servers[gid]
        server = None
        if self.configured:
            channel = self.client.get_channel(self.conf.pvp_channel_id)
            server = Server(None, channel, getattr(self.conf, "pvp_role_id", None)) if channel else None
        elif guild is not None:
            server = await install(guild, self.conf.pvp_channel_name, self.conf.pvp_role_name, self.log)
        if server is None:
            self.log.warning("pas de salon des cartes pour %s", getattr(guild, "name", "ce serveur"))
            return None
        self.servers[gid] = server
        await self._sweep(server)
        return server

    # ===== Les cartes en mémoire =====

    def _remember(self, server: Server, card: Card) -> None:
        for call in card.calls:
            self.cards[(server.guild_id,) + call.key] = card

    def _forget(self, card: Card) -> None:
        for k in [k for k, c in self.cards.items() if c is card]:
            del self.cards[k]
        timer = self.timers.pop(id(card), None)
        if timer is not None:
            timer.cancel()

    def _known(self, server: Server) -> list[Card]:
        seen, out = set(), []
        for k, card in self.cards.items():
            if k[0] == server.guild_id and id(card) not in seen:
                seen.add(id(card))
                out.append(card)
        return out

    async def _zone_card(self, server: Server, map_id, at: float) -> Card | None:
        """La carte EN COURS de cette zone sur ce serveur, s'il y en a une (P10) ; une carte dont les appels
        ont tous dépassé 30 minutes passe d'abord au gris."""
        found = None
        for card in self._known(server):
            if card.map != map_id:
                continue
            if expire(card, at):
                await self._edit(card)
            if card.status == ACTIVE and len(card.calls) < MAX_CALLS and (found is None or card.updated_at > found.updated_at):
                found = card
        return found

    # ===== Une ligne =====

    async def handle(self, message, live: bool = True) -> bool:
        """True si le message est une ligne de l'addon (traitée, réussie ou non, ou déjà traitée) ;
        False sinon. `live` : arrivée en direct (False : rattrapage au démarrage)."""
        if not (self.enabled and is_from_game(message)):
            return False
        line = parse(message.content)
        if line is None:
            if (message.content or "")[:4] in ("SOS ", "OMW ", "END "):
                self.log.info("ligne %s pas lue comme un appel (format)", message.id)
            return False
        if message.id in self.done:   # vue par le rattrapage ET en direct : une seule fois
            return True
        self.done.append(message.id)
        at = self._time(message, live)
        async with self.lock:
            server = await self._server(getattr(message, "guild", None))
            done = server is not None and await self._apply(server, line, at)
        if done and self.conf.delete_relayed:
            await delete_relayed([message], self.log)
        elif not done:
            self.log.warning("appel #SOS%d de %s : carte pas faite, ligne gardée dans le salon relié",
                             line.n, line.caller_name)
        return True

    async def _apply(self, server: Server, line: PvpLine, at: float) -> bool:
        """La ligne, arrivée à l'heure `at` (Discord), appliquée à la carte de son appel ou de sa zone."""
        k = key(line.caller_name, line.n)
        card = self.cards.get((server.guild_id,) + k)
        call = card.call(k) if card is not None else None
        if line.kind == "SOS":
            if call is not None and is_live(call, at):          # l'appel suit, même s'il change de zone
                update_call(call, line, at)
                self._arm(card)
                return await self._edit(card)
            if card is not None and expire(card, at):           # l'ancien appel au même numéro se fige
                await self._edit(card)
            zone = await self._zone_card(server, line.map, at)
            if zone is None:
                return await self._open(server, line, at)
            join(zone, line, at)                                # P10 : la même carte, sans nouvelle mention
            self._remember(server, zone)
            self._arm(zone)
            return await self._edit(zone)
        if call is None:   # OMW / END d'un appel inconnu : ignoré, ligne brute supprimée quand même
            self.log.info("%s #SOS%d de %s : carte introuvable", line.kind, line.n, line.caller_name)
            return True
        if line.kind == "OMW":
            if not add_responder(call, line.who):
                return True
        else:
            call.status = SETTLED
        return await self._edit(card)

    async def _open(self, server: Server, line: PvpLine, at: float) -> bool:
        """Une zone sans carte en cours : une nouvelle carte, avec la mention du rôle."""
        card = open_card(line, at)
        role = server.role_id
        mentions = (discord.AllowedMentions(everyone=False, users=False, roles=[discord.Object(id=role)])
                    if role else discord.AllowedMentions.none())
        embed, files = await self._art(card)
        try:
            card.message = await server.alerts.send(content=f"<@&{role}>" if role else None, embed=embed,
                                                    files=files, allowed_mentions=mentions)
        except discord.DiscordException as err:
            self.log.warning("carte de l'appel #SOS%d de %s refusée : %s", line.n, line.caller_name, err)
            return False
        self._remember(server, card)
        self._arm(card)
        self.log.info("appel #SOS%d de %s : carte de la zone %s publiée", line.n, line.caller_name, line.map)
        return True

    async def _edit(self, card: Card) -> bool:
        # `attachments` remplace celles de la carte : la nouvelle image, ou aucune (sinon une vieille image
        # resterait affichée sous la carte, détachée de l'embed).
        embed, files = await self._art(card)
        try:
            await card.message.edit(embed=embed, attachments=files, allowed_mentions=discord.AllowedMentions.none())
        except discord.DiscordException as err:
            self.log.warning("carte de la zone %s pas modifiée : %s", card.map, err)
            return False
        self.log.info("carte de la zone %s mise à jour (%d appel(s), %s)", card.map, len(card.calls), card.status)
        return True

    def _read(self, message) -> Card | None:
        if getattr(message.author, "id", None) != getattr(self.client.user, "id", None) or not message.embeds:
            return None
        card = from_embed(message.embeds[0])
        if card is not None:
            card.message = message
        return card

    # ===== Le temps =====

    def _arm(self, card: Card) -> None:
        """Le compte à rebours du prochain appel de la carte qui passera « sans nouvelles »."""
        old = self.timers.pop(id(card), None)
        if old is not None:
            old.cancel()
        due = next_expiry(card)
        if due is None:
            return
        task = asyncio.create_task(self._later(max(0.0, due - self.now())))
        self.timers[id(card)] = task
        task.add_done_callback(lambda t, k=id(card): self.timers.pop(k, None) if self.timers.get(k) is t else None)

    async def _later(self, delay: float) -> None:
        await self.sleep(delay)
        await self.expire_due()

    async def expire_due(self) -> None:
        """Les appels sans ligne depuis 30 minutes passent « sans nouvelles » ; les cartes finies depuis
        longtemps sont oubliées (elles restent dans le salon jusqu'au nettoyage)."""
        async with self.lock:
            now = self.now()
            for card in {id(c): c for c in self.cards.values()}.values():
                if expire(card, now):
                    await self._edit(card)
                if card.status == ACTIVE:
                    self._arm(card)
                elif now - card.updated_at >= 2 * EXPIRY:
                    self._forget(card)

    # ===== Le démarrage, le nettoyage =====

    async def _sweep(self, server: Server) -> None:
        """Les cartes encore en cours des derniers messages du salon des cartes reviennent en mémoire et
        reprennent leur compte à rebours, ou passent au gris si leurs appels ont plus de 30 minutes. Sous
        le verrou (appelée par `_server`)."""
        now = self.now()
        async for message in server.alerts.history(limit=HISTORY):
            card = self._read(message)
            if card is None or card.status != ACTIVE:
                continue
            # Une carte restée « en cours » pendant l'arrêt passe au gris dans TOUS les cas (sinon elle le
            # resterait pour toujours, et le nettoyage ne l'effacerait jamais) ; seule la plus récente d'un
            # même appel revient en mémoire.
            if expire(card, now):
                await self._edit(card)
            if card.status == ACTIVE and not any((server.guild_id,) + c.key in self.cards for c in card.calls):
                self._remember(server, card)
                self._arm(card)

    async def clean(self) -> int:
        """P13 : efface les cartes finies (réglées ou sans nouvelles) depuis `BOT_GARDER_HEURES` heures.
        Jamais une carte en cours, jamais le message d'un autre. Rend le nombre de cartes effacées."""
        hours = getattr(self.conf, "keep_hours", 24)
        if not hours:
            return 0
        removed, now = 0, self.now()
        for server in list(self.servers.values()):
            async for message in server.alerts.history(limit=HISTORY):
                card = self._read(message)
                ended = getattr(message, "edited_at", None) or getattr(message, "created_at", None)
                if card is None or card.status == ACTIVE or ended is None or now - ended.timestamp() < hours * 3600:
                    continue
                try:
                    await message.delete()
                except discord.DiscordException as err:
                    self.log.warning("carte finie %s pas effacée : %s", getattr(message, "id", "?"), err)
                    continue
                for known in [c for c in self.cards.values() if c.message is message]:
                    self._forget(known)
                removed += 1
        if removed:
            self.log.info("nettoyage : %d carte(s) finie(s) depuis plus de %d h effacée(s)", removed, hours)
        return removed

    async def _clean_loop(self) -> None:
        while True:
            try:
                await self.clean()
            except discord.DiscordException as err:
                self.log.warning("nettoyage interrompu : %s", err)
            await self.sleep(CLEAN_EVERY)

    def _sources(self, guild, server: Server) -> list:
        """Où lire les lignes ratées : le salon relié configuré ; sinon, sur ce serveur, tous les salons
        que le bot peut relire sauf celui des cartes (seul un salon relié porte des messages du jeu)."""
        forced = getattr(self.conf, "channel_id", None)
        if forced:
            channel = self.client.get_channel(forced)
            return [channel] if channel is not None else []
        if guild is None:
            return []
        out = []
        for channel in guild.text_channels:
            perms = channel.permissions_for(guild.me)
            if channel is not server.alerts and perms.view_channel and perms.read_message_history:
                out.append(channel)
        return out

    async def catch_up(self, guild=None, server: Server | None = None) -> int:
        """Au démarrage : les lignes d'appel venues du jeu, des 30 dernières minutes, encore dans le
        salon relié sont celles qu'on a ratées pendant l'arrêt (une ligne traitée en est effacée) : on
        les traite dans l'ordre, chacune à son heure. Sans effacement (`BOT_SUPPRIMER=non`), on ne sait
        pas lesquelles l'ont déjà été : rien. Rend le nombre de lignes reprises."""
        if not (self.enabled and self.conf.delete_relayed):
            return 0
        if server is None:
            async with self.lock:
                server = await self._server(guild)
            if server is None:
                return 0
        since = dt.datetime.fromtimestamp(self.now() - EXPIRY, tz=dt.timezone.utc)
        caught = 0
        for source in self._sources(guild, server):
            async for message in source.history(limit=HISTORY, after=since, oldest_first=True):
                if await self.handle(message, live=False):
                    caught += 1
        if caught:
            self.log.info("rattrapage : %d ligne(s) d'appel ratée(s) pendant l'arrêt, reprise(s)", caught)
        return caught

    async def start(self) -> None:
        """Au démarrage, pour chaque serveur : installation et cartes en cours relues, lignes ratées
        rattrapées ; puis le nettoyage, toutes les heures."""
        guilds = [None] if self.configured else list(getattr(self.client, "guilds", []))
        for guild in guilds:
            async with self.lock:
                server = await self._server(guild)
            if server is not None:
                await self.catch_up(guild, server)
        task = asyncio.create_task(self._clean_loop())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
