"""Les libellés des cartes d'appel, en français ou en anglais (A5 de docs/specs/bot-autonome.md).

Une langue par bot (`BOT_LANGUE`), posée une fois au démarrage par `use`. La relecture d'une carte
(pvp_embed.from_embed) accepte TOUTES les langues : une carte écrite avant un changement de langue se relit,
et sa prochaine mise à jour l'écrit dans la nouvelle (les classes des tueurs, gardées en texte, n'y passent
qu'à la ligne SOS suivante). Le pied de la carte, lu par la machine, ne dépend d'aucune langue. Le journal
du bot reste en français.

Clés de `status` et `state` : les états de pvp_cards (ACTIVE, SETTLED, EXPIRED), en clair pour ne pas
importer pvp_cards (qui importe ce module) ; un test vérifie qu'ils concordent.
"""

from __future__ import annotations

import re
from contextlib import contextmanager

LANGS = {
    "fr": {
        "one": "{caller} appelle à l'aide !",
        "many": "{n} guildiens appellent à l'aide",
        "status": {"active": "**En cours**", "settled": "**Réglé**", "expired": "**Terminé, sans nouvelles**"},
        "state": {"settled": "réglé", "expired": "sans nouvelles"},
        "zone": "Zone",
        "call": "appel n°{n}",
        "where": "Où : {where} · Morts : {deaths}",
        "killers": "Tueurs : ",
        "en_route": "En route : ",
        "nobody": "personne pour l'instant",
        "zone_only": "zone seule",
        "protectors_title": "Protecteurs de ",
        "protectors_one": "**{online}** connecté sur {total}",
        "protectors_many": "**{online}** connectés sur {total}",
        "classes": {"WARRIOR": "Guerrier", "PALADIN": "Paladin", "HUNTER": "Chasseur", "ROGUE": "Voleur",
                    "PRIEST": "Prêtre", "SHAMAN": "Chaman", "MAGE": "Mage", "WARLOCK": "Démoniste",
                    "DRUID": "Druide", "DEATHKNIGHT": "Chevalier de la mort", "MONK": "Moine",
                    "DEMONHUNTER": "Chasseur de démons", "EVOKER": "Évocateur"},
    },
    "en": {
        "one": "{caller} is calling for help!",
        "many": "{n} guild members are calling for help",
        "status": {"active": "**Ongoing**", "settled": "**Settled**", "expired": "**Over, no news**"},
        "state": {"settled": "settled", "expired": "no news"},
        "zone": "Zone",
        "call": "call #{n}",
        "where": "Where: {where} · Deaths: {deaths}",
        "killers": "Killers: ",
        "en_route": "On the way: ",
        "nobody": "nobody yet",
        "zone_only": "zone only",
        "protectors_title": "Protectors of ",
        "protectors_one": "**{online}** online out of {total}",
        "protectors_many": "**{online}** online out of {total}",
        "classes": {"WARRIOR": "Warrior", "PALADIN": "Paladin", "HUNTER": "Hunter", "ROGUE": "Rogue",
                    "PRIEST": "Priest", "SHAMAN": "Shaman", "MAGE": "Mage", "WARLOCK": "Warlock",
                    "DRUID": "Druid", "DEATHKNIGHT": "Death Knight", "MONK": "Monk",
                    "DEMONHUNTER": "Demon Hunter", "EVOKER": "Evoker"},
    },
}
MAP_LOCALES = {"fr": "frFR", "en": "enUS"}   # la langue des noms sur l'image de zone, sauf BOT_CARTES_LANGUE

_current = "fr"


def use(lang: str) -> None:
    global _current
    if lang not in LANGS:
        raise ValueError(f"langue inconnue : {lang!r}")
    _current = lang


def text() -> dict:
    """Les libellés de la langue du bot."""
    return LANGS[_current]


@contextmanager
def using(lang: str):
    """Une autre langue le temps d'un bloc (tests)."""
    old = _current
    use(lang)
    try:
        yield
    finally:
        use(old)


def _pattern(template: str, groups: dict[str, str]) -> str:
    """Un libellé à trous (`{deaths}`…) en expression régulière : le texte tel quel, les trous en groupes."""
    return "".join(groups[p[1:-1]] if p.startswith("{") else re.escape(p)
                   for p in re.split(r"(\{\w+\})", template) if p)


class Reader:
    """Ce qu'il faut pour relire une carte écrite dans N'IMPORTE QUELLE langue."""

    def __init__(self) -> None:
        all_ = LANGS.values()
        self.zone = {t["zone"] for t in all_}
        self.nobody = {t["nobody"] for t in all_}
        self.zone_only = {t["zone_only"] for t in all_}
        self.killers = tuple(t["killers"] for t in all_)
        self.en_route = tuple(t["en_route"] for t in all_)
        self.state = {label: state for t in all_ for state, label in t["state"].items()}
        states = "|".join(re.escape(s) for s in self.state)
        self.names = [re.compile(r".* — " + _pattern(t["call"], {"n": r"\d+"}) + rf"(?: · ({states}))?")
                      for t in all_]
        self.where = [re.compile(_pattern(t["where"], {"where": "(.*)", "deaths": r"(\d+)"})) for t in all_]

    def call_state(self, name: str) -> str | None:
        """L'état écrit dans le nom du champ d'un appel (« réglé », « no news »…), ou None : en cours."""
        for pattern in self.names:
            if (m := pattern.fullmatch(name)):
                return self.state.get(m.group(1)) if m.group(1) else None
        return None

    def where_line(self, line: str):
        """(lieu, morts) d'une ligne « Où : … · Morts : … », dans n'importe quelle langue ; None sinon."""
        for pattern in self.where:
            if (m := pattern.fullmatch(line)):
                return m.group(1), int(m.group(2))
        return None


READER = Reader()
