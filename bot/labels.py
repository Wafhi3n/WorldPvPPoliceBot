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
        "setup": {
            "denied": "Réservé aux administrateurs.",
            "not_saved": "Le réglage n'est **pas** enregistré : le bot ne peut pas écrire son fichier (voir son journal).",
            "alerts_set": "Les nouvelles cartes vont dans {channel}. Celles de l'ancien salon y restent, et ne s'effacent plus "
                          "toutes seules.",
            "role_set": "Les nouvelles cartes mentionnent {role}.",
            "role_everyone": "Pas @everyone : tout le serveur sonnerait à chaque appel.",
            "role_managed": "{role} ne peut pas servir : Discord le gère lui-même.",
            "guide_set": "Le guide est publié dans {category}. Qui le voit dépend des droits de cette catégorie.",
            "guide_saved": "Catégorie enregistrée : le guide sera publié quand le bot sera en `BOT_MODE=repondre`.",
            "guide_rights": "Catégorie enregistrée, mais il manque au bot, dans {category} : voir les salons, gérer les salons, "
                            "envoyer des messages ou lire l'historique. Refaire cette commande après.",
            "guide_failed": "Catégorie enregistrée, mais le guide n'est pas publié : Discord a refusé (voir le journal du bot).",
            "forgotten": "{name} : réglage oublié.",
            "not_posted": "{name} n'était pas posé par commande.",
            "names": {"pvp_channel": "Salon des cartes", "pvp_role": "Rôle mentionné", "guide_category": "Catégorie du guide"},
            "origins": {"command": "commande", "variable": "variable"},
            "unset": "pas réglé",
            "by_name": "`{name}`, par son nom",
            "protectors": "Liste des protecteurs",
            "mode": "Mode : {mode} (`BOT_MODE`, sur l'hébergement)",
            "to_fix": "**À régler**",
            "channel_gone": "Le salon des cartes n'est plus sur ce serveur : `/setup salon-alertes`.",
            "channel_rights": "Il manque au bot dans {channel} : voir le salon, envoyer des messages, intégrer des liens, joindre "
                              "des fichiers ou lire l'historique.",
            "linked_rights": "Il manque au bot dans le salon relié {channel} : voir le salon, lire l'historique ou gérer les "
                             "messages. Sans les deux premiers, aucun appel n'arrive jusqu'au bot.",
            "role_gone": "Le rôle mentionné n'est plus sur ce serveur : `/setup role`.",
            "role_quiet": "{role} n'est pas mentionnable : la mention ne sonnera pas. Le rendre mentionnable dans Paramètres du "
                          "serveur → Rôles.",
            "category_gone": "La catégorie du guide n'est plus sur ce serveur : `/setup categorie-guide`.",
            "category_rights": "Il manque au bot dans la catégorie {category} : voir les salons, gérer les salons, envoyer des "
                                "messages ou lire l'historique.",
            "invite": "Si un droit manque sur tout le serveur, rouvrir le lien d'invitation : {link}",
            "separator": " : ",
        },
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
        "setup": {
            "denied": "Administrators only.",
            "not_saved": "The setting was **not** saved: the bot can't write its file (see its log).",
            "alerts_set": "New cards go to {channel}. Those in the old channel stay there, and no longer delete themselves.",
            "role_set": "New cards ping {role}.",
            "role_everyone": "Not @everyone: the whole server would ring on every call.",
            "role_managed": "{role} can't be used: Discord manages it itself.",
            "guide_set": "The guide is posted in {category}. Who sees it depends on that category's permissions.",
            "guide_saved": "Category saved: the guide will be posted once the bot is in `BOT_MODE=repondre`.",
            "guide_rights": "Category saved, but in {category} the bot lacks: View Channels, Manage Channels, Send Messages or Read "
                            "Message History. Run this command again afterwards.",
            "guide_failed": "Category saved, but the guide wasn't posted: Discord refused (see the bot's log).",
            "forgotten": "{name}: setting forgotten.",
            "not_posted": "{name} wasn't set by command.",
            "names": {"pvp_channel": "Cards channel", "pvp_role": "Role to ping", "guide_category": "Guide category"},
            "origins": {"command": "command", "variable": "variable"},
            "unset": "not set",
            "by_name": "`{name}`, by name",
            "protectors": "Protectors list",
            "mode": "Mode: {mode} (`BOT_MODE`, where it's hosted)",
            "to_fix": "**To fix**",
            "channel_gone": "The cards channel is no longer on this server: `/setup salon-alertes`.",
            "channel_rights": "In {channel} the bot lacks: View Channel, Send Messages, Embed Links, Attach Files or Read Message "
                              "History.",
            "linked_rights": "In the linked channel {channel} the bot lacks: View Channel, Read Message History or Manage Messages. "
                             "Without the first two, no call reaches the bot.",
            "role_gone": "The role to ping is no longer on this server: `/setup role`.",
            "role_quiet": "{role} isn't mentionable: the ping won't ring. Make it mentionable in Server Settings, Roles.",
            "category_gone": "The guide category is no longer on this server: `/setup categorie-guide`.",
            "category_rights": "In the {category} category the bot lacks: View Channels, Manage Channels, Send Messages or Read "
                                "Message History.",
            "invite": "If a permission is missing on the whole server, open the invite link again: {link}",
            "separator": ": ",
        },
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
