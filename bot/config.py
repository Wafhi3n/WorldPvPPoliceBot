"""Configuration : le fichier `.env` du dépôt (jamais versionné), puis l'environnement (un conteneur n'a
que l'environnement). Mêmes noms de variables que le module PvP de CraftingOrderBot, pour la bascule.

Le jeton du bot n'est jamais affiché ni journalisé : seule sa présence est vérifiée.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .labels import MAP_LOCALES

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    token: str
    channel_id: int | None = None         # le salon relié imposé (absent : reconnu à ses messages du jeu, A2)
    pvp_channel_id: int | None = None     # #alertes-pvp imposé : UN serveur, comme le module d'origine
    pvp_role_id: int | None = None        # rôle imposé, mentionné à un NOUVEL appel
    pvp_channel_name: str = "alertes-pvp"   # sinon : le salon des cartes, trouvé ou créé par ce nom (A1)
    pvp_role_name: str = "pvp-police"       # et le rôle, trouvé ou créé (mentionnable) par ce nom
    install: bool = True                  # BOT_INSTALLER : le droit de créer ce qui manque
    maps: bool = True                     # BOT_CARTES : l'image de la zone sur la carte (wago.tools, A4)
    maps_product: str = "wowf"            # BOT_CARTES_PRODUIT : wowf = Forever, wowt = PTR de Retail
    maps_locale: str = "frFR"             # BOT_CARTES_LANGUE : la langue des noms sur l'image (sinon : BOT_LANGUE)
    language: str = "fr"                  # BOT_LANGUE : la langue des cartes, fr ou en (A5 ; le journal reste en français)
    delete_relayed: bool = True           # BOT_SUPPRIMER : la ligne brute quitte le salon relié (P3)
    keep_hours: int = 24                  # BOT_GARDER_HEURES : une carte finie est effacée après (0 : jamais, P13)
    mode: str = "journal"                 # « journal » : note ce qui passe ; « repondre » : fait les cartes
    log_file: Path = ROOT / "bot.log"     # BOT_LOG
    state_dir: Path = ROOT / "state"      # BOT_STATE : cache des cartes de zone (un volume en conteneur)

    def __repr__(self) -> str:      # jamais le jeton dans une trace
        return (f"Config(channel_id={self.channel_id}, pvp_channel_id={self.pvp_channel_id}, "
                f"pvp_role_id={self.pvp_role_id}, pvp_channel_name={self.pvp_channel_name!r}, "
                f"pvp_role_name={self.pvp_role_name!r}, install={self.install}, delete_relayed={self.delete_relayed}, "
                f"keep_hours={self.keep_hours}, language={self.language!r}, maps_locale={self.maps_locale!r}, "
                f"mode={self.mode!r}, log_file={str(self.log_file)!r}, state_dir={str(self.state_dir)!r})")


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _optional_id(values: dict[str, str], name: str) -> int | None:
    """Un identifiant Discord facultatif : vide = absent, autre chose qu'un nombre = refusé."""
    value = values.get(name, "").strip()
    if value and not value.isdigit():
        raise SystemExit(f"{name} invalide dans .env.")
    return int(value) if value else None


def _choice(values: dict[str, str], name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = values.get(name, default).strip().lower()
    if value not in allowed:
        raise SystemExit(f"{name} doit valoir {' ou '.join(allowed)}.")
    return value


def _pattern(values: dict[str, str], name: str, default: str, regex: str) -> str:
    value = values.get(name, "").strip() or default
    if not re.fullmatch(regex, value):
        raise SystemExit(f"{name} invalide dans .env : {value!r}.")
    return value


def load(path: Path = ROOT / ".env") -> Config:
    values = _read_env(path)
    values.update({k: v for k, v in os.environ.items() if k.startswith(("DISCORD_", "BOT_"))})
    token = values.get("DISCORD_TOKEN", "")
    if not token:
        raise SystemExit("DISCORD_TOKEN manquant : le taper dans .env (voir .env.example).")
    log = values.get("BOT_LOG", "").strip()
    state = values.get("BOT_STATE", "").strip()
    language = _choice(values, "BOT_LANGUE", "fr", tuple(MAP_LOCALES))
    return Config(token=token, channel_id=_optional_id(values, "DISCORD_CHANNEL_ID"),
                  pvp_channel_id=_optional_id(values, "DISCORD_PVP_CHANNEL_ID"),
                  pvp_role_id=_optional_id(values, "DISCORD_PVP_ROLE_ID"),
                  pvp_channel_name=values.get("DISCORD_PVP_CHANNEL_NAME", "").strip() or "alertes-pvp",
                  pvp_role_name=values.get("DISCORD_PVP_ROLE_NAME", "").strip() or "pvp-police",
                  install=_choice(values, "BOT_INSTALLER", "oui", ("oui", "non")) == "oui",
                  maps=_choice(values, "BOT_CARTES", "oui", ("oui", "non")) == "oui",
                  maps_product=_pattern(values, "BOT_CARTES_PRODUIT", "wowf", r"[a-z0-9_]+"),
                  maps_locale=_pattern(values, "BOT_CARTES_LANGUE", MAP_LOCALES[language], r"[a-z]{2}[A-Z]{2}"),
                  language=language,
                  delete_relayed=_choice(values, "BOT_SUPPRIMER", "oui", ("oui", "non")) == "oui",
                  keep_hours=int(_pattern(values, "BOT_GARDER_HEURES", "24", r"\d{1,4}")),
                  mode=_choice(values, "BOT_MODE", "journal", ("journal", "repondre")),
                  log_file=Path(log) if log else ROOT / "bot.log",
                  state_dir=Path(state) if state else ROOT / "state")
