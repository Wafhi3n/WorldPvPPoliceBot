"""Ce que le bot sait d'un message du salon relié au jeu (repris de CraftingOrderBot, bot/relay.py).

Un salon Discord relié à une guilde de WoW reçoit les messages du jeu sous le nom du compte Discord du
joueur. Mesuré le 2026-10-10 : un message relayé par le jeu porte `application_id` = 1384671873593512078
(l'application du jeu) et `flags` = 65536 ; un message tapé sur Discord n'a ni l'un ni l'autre. Un bot
ne peut PAS écrire dans ce salon (erreur 20062, même administrateur) mais peut y SUPPRIMER, avec le
droit « Gérer les messages » (mesuré le 2026-10-10 19:08).
"""

from __future__ import annotations

import logging

import discord


def is_from_game(message) -> bool:
    """Le message vient-il du jeu (badge manette) ? Un bot qui répond à une commande porte aussi un
    `application_id` : on écarte les bots."""
    author = getattr(message, "author", None)
    return bool(getattr(message, "application_id", None)) and not getattr(author, "bot", True)


async def delete_relayed(messages: list, log: logging.Logger) -> None:
    """Supprime du salon relié les lignes déjà traitées (elles disparaissent aussi du fil Discord en jeu)."""
    for message in messages:
        try:
            await message.delete()
            log.info("ligne d'origine %s supprimée du salon relié", message.id)
        except discord.HTTPException as err:
            log.warning("suppression refusée pour %s : %s (code %s)", message.id, err, getattr(err, "code", "?"))
