"""La carte d'un appel à l'aide dans #alertes-pvp (spec alertes-pvp.md, P4, P7, P8 ; critères 2 à 4).

Une carte « embed » par appel : qui appelle, où, combien de morts, les tueurs, le message, qui arrive,
l'heure de la dernière nouvelle. Elle porte TOUT ce qu'il faut pour la reprendre après un redémarrage
(pied `#SOS<n> · <Perso>`, heure de l'embed = dernière ligne `SOS`) : `from_embed` la relit.

Les textes venus d'un joueur (zone, message, noms) sont ÉCHAPPÉS une fois, à la lecture de la ligne,
et gardés tels quels : une carte relue ne s'échappe pas deux fois. Le pied n'est pas mis en forme par
Discord : il garde le nom brut.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import discord

from .pvp_line import PvpLine
from .pvp_map import parse_name

EXPIRY = 30 * 60   # s sans ligne SOS : la carte passe au gris (P8 ; D11 de l'addon, 30 min depuis le 2026-10-28)

ACTIVE, SETTLED, EXPIRED = "active", "settled", "expired"
STATUS_TEXT = {ACTIVE: "**En cours**", SETTLED: "**Réglé**", EXPIRED: "**Terminé, sans nouvelles**"}
COLORS = {ACTIVE: 0xC0392B, SETTLED: 0x2E8B57, EXPIRED: 0x7F8C8D}
WHERE, DEATHS, KILLERS, EN_ROUTE, LAST = "Où", "Morts", "Tueurs", "En route", "Dernière nouvelle"
NOBODY = "Personne pour l'instant"
CLASSES = {"WARRIOR": "Guerrier", "PALADIN": "Paladin", "HUNTER": "Chasseur", "ROGUE": "Voleur",
           "PRIEST": "Prêtre", "SHAMAN": "Chaman", "MAGE": "Mage", "WARLOCK": "Démoniste", "DRUID": "Druide",
           "DEATHKNIGHT": "Chevalier de la mort", "MONK": "Moine", "DEMONHUNTER": "Chasseur de démons",
           "EVOKER": "Évocateur"}
_FOOTER = re.compile(r"#SOS(\d+) · (\S+)")

Key = tuple[str, int]


def key(who: str, n: int) -> Key:
    return who.casefold(), int(n)


def escape(text: str) -> str:
    """Un texte de joueur sans mise en forme ni mention (critère 2)."""
    return discord.utils.escape_mentions(discord.utils.escape_markdown(text))


def unescape(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text)


@dataclass
class Card:
    caller: str                 # le prénom de la ligne, brut (clé et pied)
    n: int
    where: str = ""             # textes affichés, déjà échappés
    deaths: int = 1
    killers: str = ""
    msg: str = ""
    en_route: list[str] = field(default_factory=list)   # noms bruts
    status: str = ACTIVE
    updated_at: float = 0.0     # heure (s) de la dernière ligne SOS
    map: int | None = None      # uiMapID et point de la dernière ligne : l'image de la carte (phase 2)
    x: float | None = None
    y: float | None = None
    message: object = None      # la carte publiée (discord.Message), quand on l'a

    @property
    def key(self) -> Key:
        return key(self.caller, self.n)


def _where(line: PvpLine) -> str:
    where = escape(line.zone or "")
    if line.x is not None and line.y is not None:
        where += f" ({line.x * 100:.1f}, {line.y * 100:.1f})"
    return where


def _killers(line: PvpLine) -> str:
    return ", ".join(escape(k.name) + (f" ({CLASSES.get(k.cls, k.cls)})" if k.cls else "") for k in line.killers)


def update(card: Card, line: PvpLine, now: float) -> None:
    """Une ligne SOS : la carte suit la dernière ligne telle quelle (zone, tueurs, message ; P4)."""
    card.where, card.deaths, card.killers = _where(line), line.deaths, _killers(line)
    card.msg = escape(line.msg or "")
    card.status, card.updated_at = ACTIVE, now
    card.map, card.x, card.y = line.map, line.x, line.y


def from_line(line: PvpLine, now: float) -> Card:
    card = Card(line.who, line.n)
    update(card, line, now)
    return card


def add_responder(card: Card, name: str) -> bool:
    """Un « j'arrive » : un nom n'apparaît qu'une fois. Ne prolonge pas l'appel (comme l'addon)."""
    if name.casefold() in (r.casefold() for r in card.en_route):
        return False
    card.en_route.append(name)
    return True


def expire(card: Card, now: float) -> bool:
    """30 minutes sans ligne SOS : une carte en cours passe au gris. Rend True si elle y passe."""
    if card.status != ACTIVE or now - card.updated_at < EXPIRY:
        return False
    card.status = EXPIRED
    return True


def to_embed(card: Card, image: str | None = None) -> discord.Embed:
    """La carte ; `image` = nom du fichier joint qui porte la carte de la zone (pvp_map), s'il y en a un."""
    desc = STATUS_TEXT[card.status] + (f"\n> {card.msg}" if card.msg else "")
    embed = discord.Embed(title=f"{escape(card.caller)} appelle à l'aide !", description=desc,
                          color=COLORS[card.status],
                          timestamp=dt.datetime.fromtimestamp(card.updated_at, tz=dt.timezone.utc))
    embed.add_field(name=WHERE, value=card.where or "?", inline=True)
    embed.add_field(name=DEATHS, value=str(card.deaths), inline=True)
    if card.killers:
        embed.add_field(name=KILLERS, value=card.killers, inline=False)
    going = ", ".join(escape(r) for r in card.en_route)
    embed.add_field(name=EN_ROUTE, value=going or NOBODY, inline=False)
    embed.add_field(name=LAST, value=f"<t:{int(card.updated_at)}:R>", inline=False)
    embed.set_footer(text=f"#SOS{card.n} · {card.caller}")
    if image:
        embed.set_image(url=f"attachment://{image}")
    return embed


def from_embed(embed) -> Card | None:
    """Relit une de nos cartes (après un redémarrage) ; None si ce n'en est pas une."""
    m = _FOOTER.fullmatch(getattr(embed.footer, "text", None) or "")
    if not m or embed.timestamp is None:
        return None
    card = Card(m.group(2), int(m.group(1)), updated_at=embed.timestamp.timestamp())
    head, _, msg = (embed.description or "").partition("\n> ")
    card.status = next((s for s, t in STATUS_TEXT.items() if t == head), ACTIVE)
    card.msg = msg
    point = parse_name(getattr(embed.image, "url", None))
    if point:
        card.map, card.x, card.y = point
    for f in embed.fields:
        if f.name == WHERE:
            card.where = f.value
        elif f.name == DEATHS and f.value.isdigit():
            card.deaths = int(f.value)
        elif f.name == KILLERS:
            card.killers = f.value
        elif f.name == EN_ROUTE and f.value != NOBODY:
            card.en_route = [unescape(r) for r in f.value.split(", ")]
    return card
