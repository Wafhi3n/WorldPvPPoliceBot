"""Les appels à l'aide de World PvP Police : une ligne `SOS`/`OMW`/`END` venue du jeu dans le salon relié
devient UNE carte dans #alertes-pvp, mise à jour au fil des lignes (spec alertes-pvp.md, B-T3).

- Plusieurs serveurs (bot-autonome.md, A1-A2) : chaque serveur a ses cartes dans SON salon des cartes,
  trouvé ou créé par son nom (`install.py`) ; avec `DISCORD_PVP_CHANNEL_ID`, un seul serveur, comme le
  module d'origine de CraftingOrderBot.
- Une ligne que la lecture refuse n'est pas un appel (un guildien qui tape « SOS » en jeu).
- La ligne brute quitte le salon relié (`BOT_SUPPRIMER=oui`, P3) seulement si la carte est faite ;
  un envoi en échec la GARDE (critère 6).
- Le rôle P6 n'est mentionné qu'à la PUBLICATION d'une carte, jamais à une modification, jamais
  `@everyone` ; le texte des joueurs ne va que dans l'embed (critère 2).
- Rien n'est gardé d'un démarrage à l'autre : une carte se retrouve dans les derniers messages du bot,
  et au démarrage (`start`) les cartes encore en cours reprennent, puis les lignes ratées pendant
  l'arrêt (encore dans le salon relié, retrouvé à ses messages du jeu) sont rattrapées.
- Une ligne à la fois (verrou) : un SOS et un OMW qui se croisent ne font jamais deux cartes, et un
  serveur ne s'installe qu'une fois.
- L'heure d'une ligne est celle de DISCORD (`created_at`), pas celle du serveur du bot (qui retardait de
  114 s le 2026-10-28) ; l'écart est appris des messages qui arrivent.
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
from .pvp_cards import (ACTIVE, EXPIRY, SETTLED, Card, add_responder, expire, from_embed, from_line, key,
                        to_embed, update)
from .pvp_line import PvpLine, parse
from .pvp_map import load_index, render

HISTORY = 200   # messages relus dans #alertes-pvp (une carte) ou dans le salon relié (le rattrapage)


class PvpRelay:
    def __init__(self, client, conf, log: logging.Logger, clock=time.time, sleep=asyncio.sleep, maps=None):
        self.client, self.conf, self.log, self.clock, self.sleep = client, conf, log, clock, sleep
        self.maps = load_index() if maps is None else maps   # uiMapID → image de la carte (phase 2)
        self.servers: dict = {}            # id du serveur (None : un seul, configuré) → Server
        self.cards: dict = {}              # (serveur, appelant, numéro) → Card
        self.lock = asyncio.Lock()
        self.timers: dict = {}
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

    def _art(self, card: Card) -> tuple[discord.Embed, list]:
        """L'embed de la carte et ses pièces jointes : l'image de la zone avec le point, redessinée à
        chaque envoi (le point a pu bouger) ; aucune pièce jointe sans image (zone seule, carte inconnue)."""
        art = render(self.maps, card.map, card.x, card.y)
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
        (trouvés ou créés par leur nom). Appelée sous le verrou : un serveur ne s'installe qu'une fois."""
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
        return server

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
        """La ligne, arrivée à l'heure `at` (Discord), appliquée à sa carte sur ce serveur."""
        card = await self._find(server, key(line.caller_name, line.n))
        if line.kind == "SOS":
            if card is None or at - card.updated_at >= EXPIRY:
                return await self._open(server, card, line, at)
            update(card, line, at)
            self._arm(server, card)
        elif card is None:   # OMW / END d'un appel introuvable : ignoré, ligne brute supprimée quand même
            self.log.info("%s #SOS%d de %s : carte introuvable", line.kind, line.n, line.caller_name)
            return True
        elif line.kind == "OMW":
            if not add_responder(card, line.who):
                return True
        else:
            card.status = SETTLED
        return await self._edit(card)

    async def _open(self, server: Server, old: Card | None, line: PvpLine, at: float) -> bool:
        """Un nouvel appel : une nouvelle carte, avec la mention du rôle. La carte d'un vieil appel au
        même numéro (plus de 30 minutes, autre poste) passe au gris si elle ne l'était pas."""
        if old is not None and expire(old, max(at, self.now())):
            await self._edit(old)
        card = from_line(line, at)
        role = server.role_id
        mentions = (discord.AllowedMentions(everyone=False, users=False, roles=[discord.Object(id=role)])
                    if role else discord.AllowedMentions.none())
        embed, files = self._art(card)
        try:
            card.message = await server.alerts.send(content=f"<@&{role}>" if role else None, embed=embed,
                                                    files=files, allowed_mentions=mentions)
        except discord.DiscordException as err:
            self.log.warning("carte de l'appel #SOS%d de %s refusée : %s", card.n, card.caller, err)
            return False
        self.cards[(server.guild_id,) + card.key] = card
        self._arm(server, card)
        self.log.info("appel #SOS%d de %s : carte publiée", card.n, card.caller)
        return True

    async def _edit(self, card: Card) -> bool:
        # `attachments` remplace celles de la carte : la nouvelle image, ou aucune (sinon une vieille image
        # resterait affichée sous la carte, détachée de l'embed).
        embed, files = self._art(card)
        try:
            await card.message.edit(embed=embed, attachments=files, allowed_mentions=discord.AllowedMentions.none())
        except discord.DiscordException as err:
            self.log.warning("carte de l'appel #SOS%d de %s pas modifiée : %s", card.n, card.caller, err)
            return False
        self.log.info("appel #SOS%d de %s : carte mise à jour (%s)", card.n, card.caller, card.status)
        return True

    async def _find(self, server: Server, k) -> Card | None:
        """La carte de la clé sur ce serveur : en mémoire, sinon la plus récente de ses derniers messages."""
        mem = (server.guild_id,) + k
        if mem in self.cards:
            return self.cards[mem]
        async for message in server.alerts.history(limit=HISTORY):
            card = self._read(message)
            if card is not None and card.key == k:
                self.cards[mem] = card
                return card
        return None

    def _read(self, message) -> Card | None:
        if getattr(message.author, "id", None) != getattr(self.client.user, "id", None) or not message.embeds:
            return None
        card = from_embed(message.embeds[0])
        if card is not None:
            card.message = message
        return card

    # ===== Le temps =====

    def _arm(self, server: Server, card: Card) -> None:
        """Le compte à rebours de la carte (30 minutes après sa dernière ligne SOS)."""
        mem = (server.guild_id,) + card.key
        old = self.timers.pop(mem, None)
        if old is not None:
            old.cancel()
        delay = max(0.0, card.updated_at + EXPIRY - self.now())
        task = asyncio.create_task(self._later(delay))
        self.timers[mem] = task
        task.add_done_callback(lambda t, k=mem: self.timers.pop(k, None) if self.timers.get(k) is t else None)

    async def _later(self, delay: float) -> None:
        await self.sleep(delay)
        await self.expire_due()

    async def expire_due(self) -> None:
        """Passe au gris les cartes sans ligne depuis 30 minutes, et oublie les cartes finies."""
        async with self.lock:
            now = self.now()
            for k, card in list(self.cards.items()):
                if expire(card, now):
                    await self._edit(card)
                if card.status != ACTIVE and now - card.updated_at >= 2 * EXPIRY:
                    del self.cards[k]

    # ===== Le démarrage =====

    async def sweep(self, server: Server) -> None:
        """Les cartes encore en cours des derniers messages du salon des cartes reprennent leur compte à
        rebours, ou passent au gris si leur dernière ligne a plus de 30 minutes."""
        async with self.lock:
            now = self.now()
            async for message in server.alerts.history(limit=HISTORY):
                card = self._read(message)
                mem = None if card is None else (server.guild_id,) + card.key
                if card is None or card.status != ACTIVE or mem in self.cards:
                    continue
                if expire(card, now):
                    await self._edit(card)
                else:
                    self.cards[mem] = card
                    self._arm(server, card)

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
        """Au démarrage, pour chaque serveur : installation, cartes en cours reprises, lignes ratées."""
        guilds = [None] if self.configured else list(getattr(self.client, "guilds", []))
        for guild in guilds:
            async with self.lock:
                server = await self._server(guild)
            if server is None:
                continue
            await self.sweep(server)
            await self.catch_up(guild, server)
