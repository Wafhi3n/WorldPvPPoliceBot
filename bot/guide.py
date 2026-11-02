"""Le guide du bot pour les administrateurs (docs/specs/guide.md) : à chaque démarrage, le bot publie le texte de son dépôt dans un
salon de la catégorie réglée. Un changement du bot et de son guide part donc au même déploiement. Ses messages sont modifiés, pas
doublés, et il ne touche jamais à un message qui n'est pas le sien.

Éteint sans `/setup categorie-guide` ni `DISCORD_GUIDE_CATEGORY_ID`. La catégorie, et qui la voit, restent à l'admin : le bot n'y
pose aucun droit.
"""

from __future__ import annotations

import logging
from pathlib import Path

import discord

from .settings import Settings

FOLDER = Path(__file__).resolve().parent / "guide"
CHANNEL = "world-pvp-police"
MAX_MESSAGE = 2000      # la limite de Discord
HISTORY = 50            # messages relus dans le salon du guide
RIGHTS = ("view_channel", "manage_channels", "send_messages", "read_message_history")
REASON = "World PvP Police Bot : son guide, pour les administrateurs"
NO_MENTION = discord.AllowedMentions.none()


def split(text: str, limit: int = MAX_MESSAGE) -> list[str]:
    """Le texte en messages, coupés entre deux paragraphes, sinon entre deux lignes, et en dernier recours n'importe où."""
    chunks, current = [], ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in text.strip().split("\n\n"):
        if len(current) + len(paragraph) + 2 > limit:
            flush()
        if len(paragraph) <= limit:
            current += paragraph + "\n\n"
            continue
        for line in paragraph.split("\n"):
            if len(current) + len(line) + 1 > limit:
                flush()
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current += line + "\n"
        flush()
    flush()
    return chunks


def load(language: str, folder: Path = FOLDER) -> list[str]:
    return split((folder / f"{language}.md").read_text(encoding="utf-8"))


class Guide:
    def __init__(self, client, conf, log: logging.Logger, folder: Path = FOLDER, settings: Settings | None = None):
        self.client, self.conf, self.log, self.folder = client, conf, log, folder
        self.settings = settings or Settings(conf)

    @property
    def active(self) -> bool:
        return self.conf.mode == "repondre"

    def category(self, guild):
        """La catégorie de ce serveur : une variable vaut pour tous les serveurs, et n'en désigne qu'un."""
        wanted = self.settings.get(guild.id, "guide_category")
        return next((c for c in guild.categories if c.id == wanted), None)

    async def publish(self) -> None:
        """Au démarrage, le guide à jour sur chaque serveur réglé. Le journal dit ce qui l'empêche ; les cartes n'en dépendent pas."""
        if not self.active:
            return
        wanted = self.settings.env("guide_category")
        guilds = self.client.guilds
        if wanted is not None and not any(c.id == wanted for g in guilds for c in g.categories):
            self.log.warning("guide : la catégorie %s n'est sur aucun serveur du bot (DISCORD_GUIDE_CATEGORY_ID)", wanted)
        for guild in guilds:
            if self.category(guild) is not None or self.settings.stored(guild.id, "guide_category") is not None:
                await self.publish_in(guild)

    async def publish_in(self, guild) -> str | None:
        """Le guide à jour sur ce serveur ; rend ce qui l'empêche (`gone`, `rights`, `failed`), ou None."""
        category = self.category(guild)
        if category is None:
            self.log.warning("guide sur %s : la catégorie réglée n'existe plus (/setup categorie-guide)", guild.name)
            return "gone"
        rights = category.permissions_for(guild.me)
        if not all(getattr(rights, right) for right in RIGHTS):
            self.log.warning("guide : il manque au bot, dans la catégorie %s : voir les salons, gérer les salons, envoyer des "
                             "messages ou lire l'historique", category.name)
            return "rights"
        try:
            channel = next((c for c in category.text_channels if c.name == CHANNEL), None)
            if channel is None:
                channel = await guild.create_text_channel(CHANNEL, category=category, reason=REASON)
            await self._post(channel, load(self.conf.language, self.folder))
        except discord.DiscordException as err:
            self.log.warning("guide pas mis à jour : %s", err)
            return "failed"
        return None

    async def _post(self, channel, chunks: list[str]) -> None:
        mine = [message async for message in channel.history(limit=HISTORY, oldest_first=True)
                if message.author.id == self.client.user.id]
        for message, chunk in zip(mine, chunks):
            if message.content != chunk:
                await message.edit(content=chunk, allowed_mentions=NO_MENTION)
        for chunk in chunks[len(mine):]:
            await channel.send(chunk, allowed_mentions=NO_MENTION)
        for message in mine[len(chunks):]:
            await message.delete()
