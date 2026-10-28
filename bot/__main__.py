"""World PvP Police Bot : `python -m bot` depuis le dépôt (ou l'image Docker).

Mode `journal` (par défaut) : le bot note dans son journal chaque message du salon relié, et ne fait
rien d'autre. C'est le premier lancement, et la BASCULE depuis le module PvP de CraftingOrderBot :
jamais deux modules PvP sur le même salon relié (chaque appel ferait deux cartes et deux mentions ;
ordre de la bascule dans docs/specs/bot-autonome.md). Mode `repondre` : les cartes d'appel (bot/pvp.py).
"""

from __future__ import annotations

import asyncio
import logging
import sys

import discord

from . import config as cfg
from .game import is_from_game
from .map_store import MapStore
from .pvp import PvpRelay

# Ce que le bot doit pouvoir faire (A3) : lire le salon relié et y effacer les lignes traitées, écrire ses
# cartes avec leur image dans #alertes-pvp, y relire ses cartes après un redémarrage, et créer ce salon
# et le rôle à mentionner s'ils manquent (A1).
PERMISSIONS = discord.Permissions(view_channel=True, send_messages=True, embed_links=True, attach_files=True,
                                  read_message_history=True, manage_messages=True, manage_channels=True,
                                  manage_roles=True)


def invite_link(application_id: int) -> str:
    """Le lien d'invitation : la portée `bot` seule (aucune commande slash) et les droits ci-dessus. Le guide
    d'hébergement (docs/hebergement.md, docs/hosting.md) en recopie l'entier des droits."""
    return discord.utils.oauth_url(application_id, permissions=PERMISSIONS, scopes=("bot",))


def setup_logging(log_file) -> logging.Logger:
    """Journal dans `log_file` (BOT_LOG) ET sur la sortie standard (`docker logs` en conteneur)."""
    log = logging.getLogger("bot")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


def raw(message: discord.Message) -> str:
    """Tout ce qu'on sait d'un message, sauf ses pièces jointes : de quoi régler la lecture."""
    author = message.author
    return (f"id={message.id} author={author!s} bot={author.bot} application_id={message.application_id} "
            f"flags={message.flags.value} content={message.content!r}")


def diagnose(client: discord.Client, channel_id: int, log: logging.Logger) -> None:
    """Au démarrage : le bot voit-il le salon, et avec quels droits ? Un salon qu'il ne voit pas ne lui
    envoie aucun message, sans autre erreur : on journalise alors le lien d'invitation."""
    channel = client.get_channel(channel_id)
    if channel is None:
        servers = ", ".join(f"{g.name} ({g.id})" for g in client.guilds) or "aucun"
        log.warning("salon %s INTROUVABLE pour le bot (pas invité, ou pas le droit de le voir) ; serveurs : %s",
                    channel_id, servers)
        log.warning("lien d'invitation du bot : %s", invite_link(client.application_id))
        return
    perms = channel.permissions_for(channel.guild.me)
    log.info("salon #%s sur %s : voir=%s lire_historique=%s envoyer=%s liens=%s fichiers=%s gerer_messages=%s",
             channel.name, channel.guild.name, perms.view_channel, perms.read_message_history, perms.send_messages,
             perms.embed_links, perms.attach_files, perms.manage_messages)


def main() -> None:
    conf = cfg.load()
    conf.state_dir.mkdir(parents=True, exist_ok=True)
    log = setup_logging(conf.log_file)
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    maps = MapStore(conf.state_dir / "cartes", conf.maps_product, conf.maps_locale, log=log) if conf.maps else {}
    pvp = PvpRelay(client, conf, log, maps=maps)
    started: set[asyncio.Task] = set()

    @client.event
    async def on_ready() -> None:
        servers = ", ".join(f"{g.name} ({g.id})" for g in client.guilds) or "aucun"
        log.info("connecté : %s ; mode %s ; serveurs : %s", client.user, conf.mode, servers)
        log.info("cartes de zone : %s", f"wago.tools, {conf.maps_product}, {conf.maps_locale}, {len(maps)} en cache"
                 if conf.maps else "éteintes (BOT_CARTES=non)")
        log.info("lien d'invitation du bot : %s", invite_link(client.application_id))
        for channel_id in (conf.channel_id, conf.pvp_channel_id):
            if channel_id:
                diagnose(client, channel_id, log)
        if not pvp.enabled:
            log.warning("ni DISCORD_PVP_CHANNEL_ID ni BOT_INSTALLER=oui : aucune carte d'appel ne sera faite")
        elif conf.mode == "repondre":   # installation, cartes en cours reprises, lignes ratées rattrapées
            task = asyncio.create_task(pvp.start())
            started.add(task)
            task.add_done_callback(started.discard)

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author == client.user:
            return
        if conf.channel_id and message.channel.id != conf.channel_id:
            return
        if not is_from_game(message):   # sans salon imposé, le bot voit tout le serveur : il ne note que le jeu
            return
        log.info("message du jeu dans #%s : %s", getattr(message.channel, "name", "?"), raw(message))
        if conf.mode == "repondre":
            await pvp.handle(message)

    client.run(conf.token, log_handler=None)


if __name__ == "__main__":
    main()
