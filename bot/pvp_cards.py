"""Les cartes d'appel à l'aide dans #alertes-pvp : UNE carte par ZONE en cours, qui porte un ou plusieurs
appels (spec alertes-pvp.md, P4, P8, P10 à P12 ; décisions du user du 2026-10-28 : « si deux joueurs sont
morts sur la même map, utiliser la même card », « le but c'est que la guilde joue ensemble »).

Un appel = un guildien et son numéro (`#SOS<n>`) : ses morts, ses tueurs, son message, qui arrive vers
lui, son point sur la carte de la zone, son état (en cours, réglé, sans nouvelles). Une carte = une
zone (`m<uiMapID>`) : elle est en cours tant qu'un de ses appels l'est, verte quand TOUS sont réglés,
grise sinon. Un appel n'est jamais sur deux cartes. Le rendu Discord (et sa relecture après un
redémarrage) vit dans pvp_embed.py.

Les textes venus d'un joueur (zone, message, noms des tueurs) sont ÉCHAPPÉS une fois, à la lecture de la
ligne, et gardés tels quels : une carte relue ne s'échappe pas deux fois. Prénoms et répondants restent
bruts (clés), échappés à l'affichage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import discord

from . import labels
from .pvp_line import PvpLine

EXPIRY = 30 * 60   # s sans ligne SOS : l'appel est sans nouvelles (P8 ; D11 de l'addon, 30 min depuis le 2026-10-28)
MAX_CALLS = 20     # appels au plus sur une carte (un embed a 25 champs) ; au-delà, une autre carte

ACTIVE, SETTLED, EXPIRED = "active", "settled", "expired"
# Les jetons de classe que l'addon écrit (D15) ; leurs noms affichés vivent dans labels.py, par langue.
CLASS_TOKENS = ("WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID",
                "DEATHKNIGHT", "MONK", "DEMONHUNTER", "EVOKER")

Key = tuple[str, int]


def key(who: str, n: int) -> Key:
    return who.casefold(), int(n)


def escape(text: str) -> str:
    """Un texte de joueur sans mise en forme ni mention (critère 2)."""
    return discord.utils.escape_mentions(discord.utils.escape_markdown(text))


def unescape(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text)


@dataclass
class Call:
    caller: str                 # le prénom de la ligne, brut (clé et pied)
    n: int
    map: int | None = None      # la zone de sa dernière ligne (une autre que celle de la carte : pas de point)
    zone: str = ""              # textes affichés, déjà échappés
    x: float | None = None
    y: float | None = None
    deaths: int = 1
    killers: str = ""
    msg: str = ""
    en_route: list[str] = field(default_factory=list)   # noms bruts
    status: str = ACTIVE
    updated_at: float = 0.0     # heure (s, Discord) de sa dernière ligne SOS

    @property
    def key(self) -> Key:
        return key(self.caller, self.n)


@dataclass
class Card:
    map: int | None             # la zone de la carte (celle de son 1er appel)
    zone: str = ""              # son nom, échappé
    calls: list[Call] = field(default_factory=list)
    message: object = None      # la carte publiée (discord.Message), quand on l'a

    @property
    def status(self) -> str:
        states = {c.status for c in self.calls}
        if ACTIVE in states:
            return ACTIVE
        return SETTLED if states == {SETTLED} else EXPIRED

    @property
    def updated_at(self) -> float:
        return max((c.updated_at for c in self.calls), default=0.0)

    def call(self, k: Key) -> Call | None:
        return next((c for c in self.calls if c.key == k), None)


def _killers(line: PvpLine) -> str:
    """Les tueurs en texte, classes dans la langue du bot (un jeton inconnu reste tel quel)."""
    classes = labels.text()["classes"]
    return ", ".join(escape(k.name) + (f" ({classes.get(k.cls, k.cls)})" if k.cls else "") for k in line.killers)


def update_call(call: Call, line: PvpLine, at: float) -> None:
    """Une ligne SOS : l'appel suit la dernière ligne telle quelle (zone, point, tueurs, message ; P4)."""
    call.map, call.zone, call.x, call.y = line.map, escape(line.zone or ""), line.x, line.y
    call.deaths, call.killers, call.msg = line.deaths, _killers(line), escape(line.msg or "")
    call.status, call.updated_at = ACTIVE, at


def call_from_line(line: PvpLine, at: float) -> Call:
    call = Call(line.who, line.n)
    update_call(call, line, at)
    return call


def open_card(line: PvpLine, at: float) -> Card:
    """La carte d'une zone, ouverte par son 1er appel."""
    return Card(line.map, escape(line.zone or ""), [call_from_line(line, at)])


def join(card: Card, line: PvpLine, at: float) -> Call:
    """Un nouvel appel rejoint la carte de sa zone (P10). Un ancien appel au même numéro sur cette carte
    (sans nouvelles, un autre poste repart du même numéro) est remplacé : un appel n'y est qu'une fois."""
    card.calls = [c for c in card.calls if c.key != key(line.who, line.n)]
    call = call_from_line(line, at)
    card.calls.append(call)
    return call


def add_responder(call: Call, name: str) -> bool:
    """Un « j'arrive » : un nom n'apparaît qu'une fois. Ne prolonge pas l'appel (comme l'addon)."""
    if name.casefold() in (r.casefold() for r in call.en_route):
        return False
    call.en_route.append(name)
    return True


def is_live(call: Call, at: float) -> bool:
    """L'appel est-il encore en cours à l'heure `at` ?"""
    return call.status == ACTIVE and at - call.updated_at < EXPIRY


def expire(card: Card, now: float) -> bool:
    """Les appels sans ligne SOS depuis 30 minutes passent « sans nouvelles ». Rend True si l'un y passe."""
    changed = False
    for call in card.calls:
        if call.status == ACTIVE and now - call.updated_at >= EXPIRY:
            call.status, changed = EXPIRED, True
    return changed


def next_expiry(card: Card) -> float | None:
    """L'heure où le prochain appel en cours de la carte passera « sans nouvelles »."""
    times = [c.updated_at + EXPIRY for c in card.calls if c.status == ACTIVE]
    return min(times) if times else None
