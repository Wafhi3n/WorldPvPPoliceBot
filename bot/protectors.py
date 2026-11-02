"""La liste des protecteurs (docs/specs/protecteurs.md) : dans un salon désigné par son id, un seul message tenu à
jour, les porteurs du rôle qui sont connectés. « Connecté » veut dire en ligne sur Discord : le bot ne voit pas le jeu.

Éteinte sans `DISCORD_PVP_PROTECTORS_CHANNEL_ID` : les deux intents privilégiés qu'elle demande ne sont alors pas
demandés. Le salon est public, des gens y parlent : l'id du message est gardé dans BOT_STATE, sinon le message
s'enfoncerait et un redémarrage le doublerait. Sans volume, l'historique sert de secours.
"""

from __future__ import annotations

import asyncio
import json
import logging

import discord

from .install import find_role
from .labels import LANGS, text
from .settings import Settings

DELAY = 5               # secondes entre le premier changement et l'écriture
HISTORY = 1000          # messages relus dans le salon pour y retrouver la liste, si l'id gardé ne sert pas
MAX_DESCRIPTION = 4096  # la limite de Discord
RESERVE = 10            # la place du « +N » de fin
COLOR = 0x3B82F6
NO_MENTION = discord.AllowedMentions.none()
TITLES = tuple(t["protectors_title"] for t in LANGS.values())


def came_or_left(before, after) -> bool:
    """Un membre vient de passer en ligne ou hors ligne. Discord signale aussi chaque jeu lancé et chaque passage
    en absent : rien de tout ça ne change la liste."""
    return (before.status == discord.Status.offline) != (after.status == discord.Status.offline)


def describe(online: list, total: int) -> str:
    """Le nombre, puis les @ par ordre alphabétique ; ceux qui ne tiennent plus deviennent `+N`."""
    labels = text()
    head = labels["protectors_many" if len(online) > 1 else "protectors_one"].format(online=len(online), total=total)
    names, room = [], MAX_DESCRIPTION - len(head) - RESERVE
    for member in online:
        room -= len(member.mention) + 1
        if room < 0:
            break
        names.append(member.mention)
    rest = len(online) - len(names)
    line = " ".join(names) + (f" +{rest}" if rest else "")
    return f"{head}\n{line}" if line else head


def to_embed(online: list, total: int, server_name: str) -> discord.Embed:
    return discord.Embed(title=text()["protectors_title"] + server_name, description=describe(online, total), color=COLOR)


def same(message, card: discord.Embed) -> bool:
    """Ce que la liste affiche : un embed relu sur Discord porte d'autres clés que celui qu'on vient de construire."""
    return bool(message.embeds) and (message.embeds[0].title, message.embeds[0].description) == (card.title, card.description)


class Protectors:
    def __init__(self, client, conf, log: logging.Logger, delay: float = DELAY, settings: Settings | None = None):
        self.client, self.conf, self.log, self.delay = client, conf, log, delay
        self.settings = settings or Settings(conf)
        self.path = conf.state_dir / "protecteurs.json"
        self.message = None
        self.lock = asyncio.Lock()
        self.pending = False        # la fenêtre est ouverte
        self.tasks: set[asyncio.Task] = set()

    @property
    def enabled(self) -> bool:
        return bool(self.conf.protectors_channel_id)

    def _channel(self):
        """Parmi les salons texte des serveurs du bot : ni une catégorie, ni un vocal."""
        wanted = self.conf.protectors_channel_id
        return next((c for g in self.client.guilds for c in g.text_channels if c.id == wanted), None) if wanted else None

    def _role(self, guild):
        role_id = self.settings.get(guild.id, "pvp_role")     # le même rôle que les cartes
        role = guild.get_role(role_id) if role_id else None
        return role or find_role(guild, self.conf.pvp_role_name)

    # ===== Quand =====

    def schedule(self, guild) -> None:
        """Un changement sur ce serveur : ouvre la fenêtre, ou rejoint celle qui est ouverte."""
        channel = self._channel()
        if channel is None or channel.guild.id != guild.id or self.pending:
            return
        self.pending = True
        task = asyncio.create_task(self._later())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _later(self) -> None:
        await asyncio.sleep(self.delay)
        self.pending = False        # avant le calcul : un changement pendant l'écriture rouvre la fenêtre
        await self.refresh()

    def listen(self) -> None:
        """Ce qui peut changer la liste. Sans les intents, Discord n'envoie pas les événements des membres."""
        client = self.client

        @client.event
        async def on_presence_update(before, after) -> None:
            if came_or_left(before, after):
                self.schedule(after.guild)

        @client.event
        async def on_member_update(before, after) -> None:
            if before.roles != after.roles:
                self.schedule(after.guild)

        @client.event
        async def on_member_join(member) -> None:
            self.schedule(member.guild)

        @client.event
        async def on_raw_member_remove(payload) -> None:
            guild = client.get_guild(payload.guild_id)
            if guild is not None:
                self.schedule(guild)

        @client.event
        async def on_guild_role_create(role) -> None:
            self.schedule(role.guild)

        @client.event
        async def on_guild_role_update(before, after) -> None:
            if before.name != after.name:
                self.schedule(after.guild)

        @client.event
        async def on_guild_role_delete(role) -> None:
            self.schedule(role.guild)

    # ===== Quoi =====

    async def refresh(self) -> None:
        """Sous le verrou : un démarrage et une fenêtre ne publient pas chacun un message."""
        async with self.lock:
            try:
                await self._refresh()
            except discord.DiscordException as err:
                self.log.warning("liste des protecteurs pas mise à jour : %s", err)

    async def _refresh(self) -> None:
        channel = self._channel()
        if channel is None:
            self.log.warning("salon %s introuvable parmi les salons texte du bot : pas de liste des protecteurs",
                             self.conf.protectors_channel_id)
            return
        guild = channel.guild
        if not guild.chunked:
            await guild.chunk()
        role = self._role(guild)
        if role is None:    # un réglage faux n'efface pas une liste déjà affichée
            self.log.warning("sur %s, ni DISCORD_PVP_ROLE_ID ni le rôle %s : pas de liste des protecteurs", guild.name,
                             self.conf.pvp_role_name)
            return
        holders = [m for m in guild.members if role in m.roles and not m.bot]
        online = sorted((m for m in holders if m.status != discord.Status.offline), key=lambda m: m.display_name.casefold())
        self.log.info("protecteurs de %s : %d connectés sur %d", guild.name, len(online), len(holders))
        if self.conf.mode == "repondre":
            await self._publish(channel, to_embed(online, len(holders), guild.name))

    # ===== Le message =====

    async def _publish(self, channel, card: discord.Embed) -> None:
        message = self.message or await self._find(channel)
        if message is not None:
            self.message = message
            if same(message, card):
                return
            try:
                self.message = await message.edit(embed=card, allowed_mentions=NO_MENTION)
                return
            except discord.NotFound:    # le message a été supprimé : on en poste un autre
                self.message = None
        self.message = await channel.send(embed=card, allowed_mentions=NO_MENTION)
        self._remember(self.message)
        self.log.info("liste des protecteurs publiée dans #%s", channel.name)

    def _ours(self, message) -> bool:
        """Notre liste, dans n'importe quelle langue, jamais une carte d'appel si le salon est le même."""
        return (getattr(message.author, "id", None) == getattr(self.client.user, "id", None) and bool(message.embeds)
                and (message.embeds[0].title or "").startswith(TITLES))

    async def _find(self, channel):
        """Par l'id gardé, puis dans l'historique. Sans le droit de relire, Discord refuse et rien n'est publié :
        chaque redémarrage ferait sinon un doublon."""
        saved = self._saved()
        if saved:
            try:
                message = await channel.fetch_message(saved)
                if self._ours(message):
                    return message
            except discord.NotFound:
                pass
        async for message in channel.history(limit=HISTORY):
            if self._ours(message):
                self._remember(message)
                return message
        return None

    def _saved(self) -> int | None:
        try:
            return int(json.loads(self.path.read_text(encoding="utf-8"))["message_id"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _remember(self, message) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"message_id": message.id}), encoding="utf-8")
        except OSError as err:      # sans le fichier, l'historique sert de secours
            self.log.warning("id de la liste des protecteurs pas gardé (%s) : %s", self.path, err)
