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
from . import labels
from .game import is_from_game
from .map_store import MapStore
from .protectors import Protectors
from .pvp import PvpRelay
from .pvp_line import parse

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


def make_intents(protectors: bool = False) -> discord.Intents:
    """Le texte des lignes du jeu, et, pour la liste des protecteurs seulement, les membres et leur présence. Ces
    intents sont PRIVILÉGIÉS : à allumer sur le portail, sinon la connexion est refusée. Un bot sans cette liste ne
    doit rien avoir à changer en se mettant à jour."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = intents.presences = protectors
    return intents


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


def note(log: logging.Logger, mode: str, message: discord.Message) -> None:
    """Un message du jeu au journal. En `journal`, tout : c'est le but. En `repondre`, les seules lignes
    d'appel : en chat fusionné, tout le chat de guilde arrive ici comme des messages du jeu, et il n'a pas à
    rester dans un journal (critère 6 de appel-sans-pont-discord.md, côté addon)."""
    if mode == "journal" or parse(message.content) is not None:
        log.info("message du jeu dans #%s : %s", getattr(message.channel, "name", "?"), raw(message))


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
    labels.use(conf.language)      # la langue des cartes, une fois pour tout le bot (A5)
    conf.state_dir.mkdir(parents=True, exist_ok=True)
    log = setup_logging(conf.log_file)
    client = discord.Client(intents=make_intents(bool(conf.protectors_channel_id)))
    maps = MapStore(conf.state_dir / "cartes", conf.maps_product, conf.maps_locale, log=log) if conf.maps else {}
    pvp = PvpRelay(client, conf, log, maps=maps)
    protectors = Protectors(client, conf, log)
    protectors.listen()
    started: set[asyncio.Task] = set()

    def launch(work) -> None:
        task = asyncio.create_task(work)
        started.add(task)
        task.add_done_callback(started.discard)

    @client.event
    async def on_ready() -> None:
        servers = ", ".join(f"{g.name} ({g.id})" for g in client.guilds) or "aucun"
        log.info("connecté : %s ; mode %s ; langue des cartes %s ; serveurs : %s", client.user, conf.mode,
                 conf.language, servers)
        log.info("cartes de zone : %s", f"wago.tools, {conf.maps_product}, {conf.maps_locale}, {len(maps)} en cache"
                 if conf.maps else "éteintes (BOT_CARTES=non)")
        log.info("lien d'invitation du bot : %s", invite_link(client.application_id))
        for channel_id in (conf.channel_id, conf.pvp_channel_id, conf.protectors_channel_id):
            if channel_id:
                diagnose(client, channel_id, log)
        if protectors.enabled:
            launch(protectors.refresh())
        if not pvp.enabled:
            log.warning("ni DISCORD_PVP_CHANNEL_ID ni BOT_INSTALLER=oui : aucune carte d'appel ne sera faite")
        elif conf.mode == "repondre":   # installation, cartes en cours reprises, lignes ratées rattrapées
            launch(pvp.start())

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author == client.user:
            return
        if conf.channel_id and message.channel.id != conf.channel_id:
            return
        if not is_from_game(message):   # sans salon imposé, le bot voit tout le serveur : il ne note que le jeu
            return
        note(log, conf.mode, message)
        if conf.mode == "repondre":
            await pvp.handle(message)

    try:
        client.run(conf.token, log_handler=None)
    except discord.PrivilegedIntentsRequired:
        needed = ("« Message Content Intent », « Server Members Intent » et « Presence Intent »"
                  if conf.protectors_channel_id else "« Message Content Intent »")
        log.error("Discord refuse la connexion : allumer %s sur le portail "
                  "(discord.com/developers/applications → l'application → Bot → Privileged Gateway Intents).", needed)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
