"""Le rendu d'une carte de zone en « embed » Discord, et sa relecture après un redémarrage (P7, P10, P12).

Une carte porte TOUT ce qu'il faut pour la reprendre (rien n'est stocké ailleurs) :
- le pied, lu par la machine : `m<uiMapID> · <Prénom>#<n> · <Prénom>#<n>@<autre zone>` (prénoms bruts) ;
- un champ « Zone », puis un champ par appel, dans l'ordre du pied :
    nom   : « Palrien — appel n°8 » (+ « · réglé » ou « · sans nouvelles »)
    texte : « Où : (39.8, 55.4) · Morts : 2 », « Tueurs : … », « > message », « En route : … »,
            puis l'heure de sa dernière ligne `<t:…:R>` (l'heure relative de Discord, relue telle quelle).
Le titre : « Palrien appelle à l'aide ! » pour un joueur, « 2 guildiens appellent à l'aide » au-delà.
Les libellés sont ceux de la langue du bot (labels.py, A5) : ci-dessus, le français. La relecture accepte
toutes les langues ; le pied n'en a aucune.
"""

from __future__ import annotations

import datetime as dt
import re

import discord

from . import labels
from .labels import READER
from .pvp_cards import ACTIVE, EXPIRED, SETTLED, Call, Card, escape, unescape

COLORS = {ACTIVE: 0xC0392B, SETTLED: 0x2E8B57, EXPIRED: 0x7F8C8D}
FIELD_MAX = 1024

_FOOTER = re.compile(r"m(\d+|-)((?: · \S+#\d+(?:@\d+)?)+)")
_KEY = re.compile(r" · (\S+)#(\d+)(?:@(\d+))?")
_POINT = re.compile(r"(?:(.*) )?\((\d+\.\d), (\d+\.\d)\)")
_TIME = re.compile(r"<t:(\d+):R>")


def title(card: Card) -> str:
    t = labels.text()
    players = {c.key[0] for c in card.calls}      # des joueurs : un appel réglé et son rappel font un seul guildien
    if len(players) == 1:
        return t["one"].format(caller=escape(card.calls[-1].caller))
    return t["many"].format(n=len(players))


def _where(call: Call, card: Card) -> str:
    other = call.map != card.map
    if call.x is not None and call.y is not None:
        point = f"({call.x * 100:.1f}, {call.y * 100:.1f})"
        return f"{call.zone} {point}" if other and call.zone else point
    return call.zone if other and call.zone else labels.text()["zone_only"]


def _call_name(call: Call) -> str:
    t = labels.text()
    state = t["state"].get(call.status)
    return f"{escape(call.caller)} — " + t["call"].format(n=call.n) + (f" · {state}" if state else "")


def _call_value(call: Call, card: Card) -> str:
    t = labels.text()
    lines = [t["where"].format(where=_where(call, card), deaths=call.deaths)]
    if call.killers:
        lines.append(t["killers"] + call.killers)
    if call.msg:
        lines.append(f"> {call.msg}")
    lines.append(t["en_route"] + (", ".join(escape(r) for r in call.en_route) or t["nobody"]))
    lines.append(f"<t:{int(call.updated_at)}:R>")
    return "\n".join(lines)[:FIELD_MAX]


def footer(card: Card) -> str:
    keys = "".join(f" · {c.caller}#{c.n}" + (f"@{c.map}" if c.map is not None and c.map != card.map else "")
                   for c in card.calls)
    return f"m{card.map if card.map is not None else '-'}{keys}"


def to_embed(card: Card, image: str | None = None) -> discord.Embed:
    """La carte ; `image` = nom du fichier joint qui porte la carte de la zone (pvp_map), s'il y en a un."""
    t = labels.text()
    embed = discord.Embed(title=title(card), description=t["status"][card.status], color=COLORS[card.status],
                          timestamp=dt.datetime.fromtimestamp(card.updated_at, tz=dt.timezone.utc))
    embed.add_field(name=t["zone"], value=card.zone or "?", inline=False)
    for call in card.calls:
        embed.add_field(name=_call_name(call), value=_call_value(call, card), inline=False)
    embed.set_footer(text=footer(card))
    if image:
        embed.set_image(url=f"attachment://{image}")
    return embed


def _after(line: str, prefixes: tuple[str, ...]) -> str | None:
    """Le texte après le libellé de la ligne (« Tueurs : », « Killers: »…), ou None s'il n'en a aucun."""
    prefix = next((p for p in prefixes if line.startswith(p)), None)
    return line[len(prefix):] if prefix is not None else None


def _read_call(caller: str, n: int, other_map, card: Card, f) -> Call:
    call = Call(caller, n, map=int(other_map) if other_map else card.map)
    call.status = READER.call_state(f.name or "") or ACTIVE
    for line in (f.value or "").split("\n"):
        if (w := READER.where_line(line)):
            where, call.deaths = w
            p = _POINT.fullmatch(where)
            if p:
                call.zone = p.group(1) or (card.zone if not other_map else "")
                call.x, call.y = float(p.group(2)) / 100, float(p.group(3)) / 100
            else:
                call.zone = card.zone if where in READER.zone_only else where
        elif (killers := _after(line, READER.killers)) is not None:
            call.killers = killers
        elif line.startswith("> "):
            call.msg = line[2:]
        elif (going := _after(line, READER.en_route)) is not None:
            call.en_route = [] if going in READER.nobody else [unescape(r) for r in going.split(", ")]
        elif (t := _TIME.fullmatch(line)):
            call.updated_at = float(t.group(1))
    return call


def from_embed(embed) -> Card | None:
    """Relit une de nos cartes (après un redémarrage) ; None si ce n'en est pas une."""
    m = _FOOTER.fullmatch(getattr(embed.footer, "text", None) or "")
    fields = list(embed.fields)
    if not m or not fields or fields[0].name not in READER.zone:
        return None
    keys = _KEY.findall(m.group(2))
    if len(fields) != len(keys) + 1:
        return None
    card = Card(None if m.group(1) == "-" else int(m.group(1)), fields[0].value if fields[0].value != "?" else "")
    card.calls = [_read_call(caller, int(n), other, card, f) for (caller, n, other), f in zip(keys, fields[1:])]
    return card
