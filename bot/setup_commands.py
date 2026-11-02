"""Les commandes `/setup` (docs/specs/reglages.md) : poser sur Discord ce qui passait par une variable. Discord ne propose que le
bon type de salon, ce qui évite un id mal collé. Réservées aux administrateurs, ce que le bot relit à chaque geste : un serveur peut
ouvrir une commande à d'autres rôles, et celles-ci décident qui sonne à chaque appel.

La liste des protecteurs n'en fait pas partie : elle demande des intents privilégiés. Un réglage posé ici les allumerait au
redémarrage suivant, et un portail où ils sont éteints refuserait alors la connexion, cartes d'appel comprises.

Le nom des commandes et leur description restent en français ; les réponses suivent `BOT_LANGUE`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import discord
from discord import app_commands

from .labels import LANGS, text
from .settings import FROM_ENV, Settings

NO_MENTION = discord.AllowedMentions.none()
ALERTS_RIGHTS = ("view_channel", "send_messages", "embed_links", "attach_files", "read_message_history")
GUIDE_RIGHTS = ("view_channel", "manage_channels", "send_messages", "read_message_history")
CHOICES = [app_commands.Choice(name=LANGS["fr"]["setup"]["names"][field], value=field) for field in FROM_ENV]
SHOWN = {"pvp_channel": "<#{}>", "pvp_role": "<@&{}>", "guide_category": "<#{}>"}


class SetupGroup(app_commands.Group):
    def __init__(self, settings: Settings, relay, guide, link: Callable[[], str], log: logging.Logger):
        super().__init__(name="setup", description="Régler le bot sur ce serveur", guild_only=True,
                         default_permissions=discord.Permissions(administrator=True))
        self.settings, self.relay, self.guide, self.link, self.log = settings, relay, guide, link, log

    async def _answer(self, interaction: discord.Interaction, answer: str) -> None:
        await interaction.followup.send(answer, ephemeral=True, allowed_mentions=NO_MENTION)

    async def _allowed(self, interaction: discord.Interaction) -> bool:
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        if user.id == interaction.guild.owner_id or user.guild_permissions.administrator:
            return True
        await self._answer(interaction, text()["setup"]["denied"])
        return False

    def _save(self, interaction: discord.Interaction, field: str, value: int) -> bool:
        try:
            self.settings.put(interaction.guild.id, field, value)
        except OSError as err:
            self.log.warning("réglage %s pas enregistré : %s", field, err)
            return False
        self.log.info("réglage %s posé sur %s par %s : %s", field, interaction.guild.name, interaction.user, value)
        return True

    @app_commands.command(name="salon-alertes", description="Le salon où le bot publie les cartes d'appel")
    @app_commands.describe(salon="Le salon des cartes")
    async def alerts(self, interaction: discord.Interaction, salon: discord.TextChannel) -> None:
        if not await self._allowed(interaction):
            return
        labels = text()["setup"]
        if not self._save(interaction, "pvp_channel", salon.id):
            await self._answer(interaction, labels["not_saved"])
            return
        await self.relay.moved(interaction.guild)
        lines = [labels["alerts_set"].format(channel=salon.mention), *self._channel_problems(interaction.guild)]
        await self._answer(interaction, "\n".join(lines))

    @app_commands.command(name="role", description="Le rôle mentionné à chaque nouvelle carte, et listé comme protecteurs")
    @app_commands.describe(role="Le rôle")
    async def role(self, interaction: discord.Interaction, role: discord.Role) -> None:
        if not await self._allowed(interaction):
            return
        labels = text()["setup"]
        if role.is_default():
            await self._answer(interaction, labels["role_everyone"])
            return
        if role.managed:
            await self._answer(interaction, labels["role_managed"].format(role=role.mention))
            return
        if not self._save(interaction, "pvp_role", role.id):
            await self._answer(interaction, labels["not_saved"])
            return
        await self.relay.moved(interaction.guild)
        lines = [labels["role_set"].format(role=role.mention)]
        if not role.mentionable:    # se répare : le réglage est gardé, et la réponse donne le geste
            lines.append(labels["role_quiet"].format(role=role.mention))
        await self._answer(interaction, "\n".join(lines))

    @app_commands.command(name="categorie-guide", description="La catégorie où le bot publie son guide pour les administrateurs")
    @app_commands.describe(categorie="La catégorie")
    async def guide_category(self, interaction: discord.Interaction, categorie: discord.CategoryChannel) -> None:
        if not await self._allowed(interaction):
            return
        labels = text()["setup"]
        if not self._save(interaction, "guide_category", categorie.id):
            await self._answer(interaction, labels["not_saved"])
            return
        if not self.guide.active:
            await self._answer(interaction, labels["guide_saved"])
            return
        problem = await self.guide.publish_in(interaction.guild)
        key = {None: "guide_set", "rights": "guide_rights"}.get(problem, "guide_failed")
        await self._answer(interaction, labels[key].format(category=categorie.name))

    @app_commands.command(name="effacer", description="Oublier un réglage posé ici, et revenir à celui de l'hébergement")
    @app_commands.describe(reglage="Le réglage à oublier")
    @app_commands.choices(reglage=CHOICES)
    async def forget(self, interaction: discord.Interaction, reglage: app_commands.Choice[str]) -> None:
        if not await self._allowed(interaction):
            return
        labels = text()["setup"]
        try:
            removed = self.settings.clear(interaction.guild.id, reglage.value)
        except OSError as err:
            self.log.warning("réglage %s pas effacé : %s", reglage.value, err)
            await self._answer(interaction, labels["not_saved"])
            return
        if removed:
            await self.relay.moved(interaction.guild)
        name = labels["names"][reglage.value]
        await self._answer(interaction, labels["forgotten" if removed else "not_posted"].format(name=name))

    @app_commands.command(name="voir", description="Les réglages de ce serveur, et ce qui manque")
    async def show(self, interaction: discord.Interaction) -> None:
        if await self._allowed(interaction):
            await self._answer(interaction, self.overview(interaction.guild))

    # ===== Ce qui se voit =====

    def _alerts_channel(self, guild):
        wanted = self.settings.get(guild.id, "pvp_channel")
        return next((c for c in guild.text_channels if c.id == wanted), None)

    def _channel_problems(self, guild) -> list[str]:
        """Une variable vaut pour tous les serveurs : son salon absent d'ici n'est pas un problème, le bot passe par le nom."""
        labels = text()["setup"]
        channel = self._alerts_channel(guild)
        if channel is None:
            return [labels["channel_gone"]] if self.settings.origin(guild.id, "pvp_channel") == "command" else []
        rights = channel.permissions_for(guild.me)
        return [] if all(getattr(rights, right) for right in ALERTS_RIGHTS) else [labels["channel_rights"].format(channel=channel.mention)]

    def _role_problems(self, guild) -> list[str]:
        labels = text()["setup"]
        role_id = self.settings.get(guild.id, "pvp_role")
        if role_id is None:
            return []
        role = guild.get_role(role_id)
        if role is None:
            return [labels["role_gone"]] if self.settings.origin(guild.id, "pvp_role") == "command" else []
        return [labels["role_quiet"].format(role=role.mention)] if not role.mentionable else []

    def _guide_problems(self, guild) -> list[str]:
        labels = text()["setup"]
        category = self.guide.category(guild)
        if category is None:
            return [labels["category_gone"]] if self.settings.origin(guild.id, "guide_category") == "command" else []
        rights = category.permissions_for(guild.me)
        return [] if all(getattr(rights, right) for right in GUIDE_RIGHTS) else [labels["category_rights"].format(category=category.name)]

    def _line(self, guild, field: str, fallback: str) -> str:
        labels = text()["setup"]
        origin = self.settings.origin(guild.id, field)
        name = labels["names"][field] + labels["separator"]
        if origin is None:
            return name + fallback
        return f"{name}{SHOWN[field].format(self.settings.get(guild.id, field))} ({labels['origins'][origin]})"

    def overview(self, guild) -> str:
        labels, conf = text()["setup"], self.settings.conf
        protectors = getattr(conf, "protectors_channel_id", None)
        lines = [self._line(guild, "pvp_channel", labels["by_name"].format(name=f"#{conf.pvp_channel_name}")),
                 self._line(guild, "pvp_role", labels["by_name"].format(name=conf.pvp_role_name)),
                 self._line(guild, "guide_category", labels["unset"]),
                 labels["protectors"] + labels["separator"]
                 + (f"<#{protectors}> ({labels['origins']['variable']})" if protectors else labels["unset"]),
                 labels["mode"].format(mode=conf.mode)]
        problems = [*self._channel_problems(guild), *self._role_problems(guild), *self._guide_problems(guild)]
        if problems:
            lines += ["", labels["to_fix"], *(f"- {problem}" for problem in problems), "", labels["invite"].format(link=self.link())]
        return "\n".join(lines)
