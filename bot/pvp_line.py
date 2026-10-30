"""Les lignes de World PvP Police dans le salon relié (spec docs/specs/alertes-pvp.md, critère 1).

COPIE de `Line.Parse` de l'addon (WorldPvPPolice_Line.lua), qui fait foi : même lecture, mêmes refus.
Trois formes, chacune sur une ligne :

    SOS <Perso> <Zone>[ (<x>, <y>)] #SOS<n> m<uiMapID> d<morts>[ k<T1>,<T2>…][ c<C1>,<C2>…][ : <message>]
    OMW <Répondant> > <Perso> #SOS<n>
    END <Perso> #SOS<n>

Une ligne non lue (autre chose, ou une ligne refusée) rend None : elle suit le chemin habituel du bot.

Pièges du portage (les motifs de Lua ne sont pas des regex Python) : les classes de Lua sont ASCII
(`re.ASCII`, et `[A-Z]` pour `%u`) ; `$` de Python accepte un `\\n` final (`fullmatch` partout) ; `.` de
Lua traverse les retours à la ligne (`re.DOTALL`) ; une liste se découpe sans perdre un élément vide
(`split(",")`, comme `(s .. ","):gmatch("(.-),")`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_F = re.ASCII | re.DOTALL
_KIND = re.compile(r"([A-Z]{3}) ", _F)
_SOS_HEAD = re.compile(r"SOS (\S+) (.*?) #SOS(\d+) m(\d+) d(\d+)(.*)", _F)
_WHERE = re.compile(r"(.*?) \((\d+\.\d), (\d+\.\d)\)", _F)
_K = re.compile(r" k(\S+)(.*)", _F)
_C = re.compile(r" c(\S+)(.*)", _F)
_MSG = re.compile(r" : (.*)", _F)
_BLANK = re.compile(r"\s*", _F)
_OMW = re.compile(r"OMW (\S+) > (\S+) #SOS(\d+)\s*", _F)
_END = re.compile(r"END (\S+) #SOS(\d+)\s*", _F)
_FIRST_WORD = re.compile(r"[^-\s]+", re.ASCII)              # ^([^%-%s]+)
_RESERVED = re.compile(r"[\s\x00-\x1f\x7f|\[\]#:,]", re.ASCII)   # [%s%c|%[%]#:,]
_MSG_BAD = re.compile(r"[\x00-\x1f\x7f|\[\]#]")              # [%c|%[%]#]
_TRAILING = re.compile(r"\s+$", re.ASCII)
_TOKEN = re.compile(r"[A-Z]+", re.ASCII)                     # ^%u+$


@dataclass
class Killer:
    name: str                # le nom le plus complet connu, « Prénom Nom » sur Forever, sans royaume
    cls: str | None = None   # jeton anglais (ROGUE…), None = classe inconnue (`-`)


@dataclass
class PvpLine:
    kind: str                   # "SOS", "OMW" ou "END"
    who: str                    # l'appelant (SOS, END) ; le répondant (OMW)
    n: int                      # numéro d'appel du personnage
    caller: str | None = None   # OMW : l'appelant
    zone: str | None = None
    x: float | None = None      # fractions 0..1 (le texte porte des pourcentages)
    y: float | None = None
    map: int | None = None
    deaths: int | None = None
    killers: list[Killer] = field(default_factory=list)
    msg: str | None = None

    @property
    def caller_name(self) -> str:
        """L'appelant, quelle que soit la forme : la clé d'un appel est (appelant, numéro)."""
        return self.caller if self.kind == "OMW" else self.who


def short_name(name: str) -> str | None:
    """Le premier mot d'un nom, sans royaume ni caractère réservé (shortName de l'addon)."""
    m = _FIRST_WORD.match(name)
    if not m or _RESERVED.search(m.group(0)):
        return None
    return m.group(0)


def _where(where: str):
    """« Zone (42.1, 65.3) » ou « Zone » seule (D14). Une parenthèse restée dans la zone : refusée."""
    m = _WHERE.fullmatch(where)
    zone, x, y = (m.group(1), m.group(2), m.group(3)) if m else (where, None, None)
    if zone == "" or "(" in zone or ")" in zone:
        return None
    if x is None:
        return zone, None, None
    fx, fy = float(x) / 100, float(y) / 100
    if fx > 1 or fy > 1:
        return None
    return zone, fx, fy


def _killer_list(names: str, classes: str | None) -> list[Killer] | None:
    """Deux listes alignées (D15) : autant de classes que de noms, `-` = classe inconnue."""
    names_l = names.split(",")
    classes_l = classes.split(",") if classes is not None else None
    if classes_l is not None and len(classes_l) != len(names_l):
        return None
    out = []
    for i, raw in enumerate(names_l):
        if short_name(raw) != raw:
            return None
        cls = classes_l[i] if classes_l is not None else None
        if cls == "-":
            cls = None
        elif cls is not None and not _TOKEN.fullmatch(cls):
            return None
        out.append(Killer(raw.replace("_", " "), cls))   # D22 de l'addon : `Prénom_Nom` se relit « Prénom Nom »
    return out


def _killers(line: PvpLine, rest: str) -> str | None:
    """Pose les tueurs dans `line` ; rend la suite de la ligne, ou None (un `c` sans `k`, des listes
    mal alignées)."""
    k = _K.fullmatch(rest)
    if k:
        rest = k.group(2)
    c = _C.fullmatch(rest)
    if c:
        rest = c.group(2)
    if not k:
        return None if c else rest
    found = _killer_list(k.group(1), c.group(1) if c else None)
    if found is None:
        return None
    line.killers = found
    return rest


def _sos(text: str) -> PvpLine | None:
    m = _SOS_HEAD.fullmatch(text)
    if not m:
        return None
    where = _where(m.group(2))
    if where is None:
        return None
    line = PvpLine("SOS", m.group(1), int(m.group(3)), zone=where[0], x=where[1], y=where[2],
                   map=int(m.group(4)), deaths=int(m.group(5)))
    rest = _killers(line, m.group(6))
    if rest is None:
        return None
    msg = _MSG.fullmatch(rest)
    if msg:
        # L'addon ôte ces caractères du message : s'il en reste, la ligne n'est pas la sienne.
        if _MSG_BAD.search(msg.group(1)):
            return None
        line.msg, rest = _TRAILING.sub("", msg.group(1)), ""
    if not _BLANK.fullmatch(rest):
        return None
    return line


def parse(text) -> PvpLine | None:
    """Relit une ligne du fil Discord ; None si ce n'en est pas une (une commande de COC, du texte)."""
    if not isinstance(text, str):
        return None
    kind = _KIND.match(text)
    kind = kind.group(1) if kind else None
    if kind == "SOS":
        return _sos(text)
    if kind == "OMW":
        m = _OMW.fullmatch(text)
        if m:
            return PvpLine("OMW", m.group(1), int(m.group(3)), caller=m.group(2))
    elif kind == "END":
        m = _END.fullmatch(text)
        if m:
            return PvpLine("END", m.group(1), int(m.group(2)))
    return None
