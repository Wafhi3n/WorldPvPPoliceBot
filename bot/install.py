"""L'installation du bot sur un serveur Discord (A1 de docs/specs/bot-autonome.md, validée par le user le
2026-10-28) : le salon des cartes et le rôle à mentionner, trouvés par leur NOM, ou créés s'ils manquent.

- `#alertes-pvp` (nom réglable) est créé en lecture seule pour les membres : ils lisent et réagissent,
  seul le bot écrit (avec les fichiers : l'image de la carte de zone).
- Le rôle `pvp-police` (nom réglable) est créé MENTIONNABLE : sans ça, la mention d'un bot ne sonne pas.
  Les membres le prennent par « Salons et rôles » de la communauté Discord (D6) : le bot ne le distribue
  pas. Discord interdit à un bot de toucher un rôle placé au-dessus du sien : il le dit.
- Sans le droit de créer, rien n'est créé : le journal le dit, et ce serveur n'a pas de cartes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

REASON = "World PvP Police Bot : installation (salon des cartes d'appel, rôle à mentionner)"


@dataclass
class Server:
    """Où vont les cartes d'un serveur, et qui elles mentionnent."""
    guild_id: int | None
    alerts: object               # le salon des cartes (discord.TextChannel)
    role_id: int | None = None   # le rôle mentionné à un nouvel appel (None : aucune mention)


def find_channel(guild, name: str):
    return next((c for c in guild.text_channels if c.name == name), None)


def find_role(guild, name: str):
    return next((r for r in guild.roles if r.name.casefold() == name.casefold()), None)


async def _alerts(guild, name: str, log: logging.Logger):
    channel = find_channel(guild, name)
    if channel is not None:
        log.info("installation sur %s : #%s retrouvé", guild.name, channel.name)
        return channel
    if not guild.me.guild_permissions.manage_channels:
        log.warning("installation sur %s : pas de #%s et pas le droit de gérer les salons : aucune carte ici",
                    guild.name, name)
        return None
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False, add_reactions=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True,
                                              attach_files=True, read_message_history=True),
    }
    try:
        channel = await guild.create_text_channel(name, overwrites=overwrites, reason=REASON)
    except discord.DiscordException as err:
        log.warning("installation sur %s : #%s pas créé (%s) : aucune carte ici", guild.name, name, err)
        return None
    log.info("installation sur %s : #%s créé (lecture seule pour les membres)", guild.name, channel.name)
    return channel


async def _role(guild, name: str, log: logging.Logger):
    role, can = find_role(guild, name), guild.me.guild_permissions.manage_roles
    try:
        if role is None and can:
            role = await guild.create_role(name=name, mentionable=True, reason=REASON)
            log.info("installation sur %s : rôle %s créé (mentionnable)", guild.name, role.name)
        elif role is not None and not role.mentionable and can and role < guild.me.top_role:
            await role.edit(mentionable=True, reason=REASON)
            log.info("installation sur %s : rôle %s rendu mentionnable", guild.name, role.name)
        elif role is not None and not role.mentionable:
            log.warning("installation sur %s : rôle %s pas mentionnable, et le bot ne peut pas y toucher : "
                        "la mention ne sonnera pas", guild.name, role.name)
        elif role is None:
            log.warning("installation sur %s : pas de rôle %s et pas le droit de gérer les rôles : aucune mention",
                        guild.name, name)
    except discord.DiscordException as err:
        log.warning("installation sur %s : rôle %s pas réglé (%s)", guild.name, name, err)
    return role


async def install(guild, channel_name: str, role_name: str, log: logging.Logger, role_id: int | None = None) -> Server | None:
    """Le salon des cartes et le rôle de ce serveur, trouvés ou créés ; None sans salon des cartes. Avec un rôle déjà réglé
    (`role_id`), aucun rôle n'est cherché ni créé."""
    alerts = await _alerts(guild, channel_name, log)
    if alerts is None:
        return None
    if role_id is not None:
        return Server(guild.id, alerts, role_id)
    role = await _role(guild, role_name, log)
    return Server(guild.id, alerts, role.id if role is not None else None)
