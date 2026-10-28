"""Récupère les cartes de zone DU JEU sur wago.tools et les range dans data/maps/ (phase 2 des alertes
PvP, demande du user le 2026-10-28 : « moyen d'extraire celles du jeu ? »).

Pourquoi wago.tools : il lit les fichiers et les tables du jeu build par build, Forever compris
(produit `wowf`, 1.60.1.x). Son API documentée (https://wago.tools/apis) rend une carte toute faite :
`/api/map/{uiMapID}?version=…&explored=1` = la toile du jeu (1002×668) avec ses surcouches
d'exploration, en PNG ; `locale=frFR` donne les noms en français (essayé le 2026-10-28 ; `explored`
seul, sans valeur, est ignoré). Au pixel près : le point d'une ligne SOS (fractions) y tombe juste
sans calage. Clé = uiMapID, celui que porte la ligne (`m<id>`).

Les zones par défaut viennent de la table UiMap du build (export CSV de wago.tools) : type 3 (zone,
villes comprises) sous Kalimdor (1414) et les Royaumes de l'Est (1415), avec leur nom dans la langue.

Politesse : une requête par seconde (--delay), un en-tête qui dit qui on est, un cache (.cache/maps/,
jamais versionné) : relancer ne retélécharge rien.

Usage :
    python tools/fetch_maps.py --version 1.60.1.70658                 # zones de Kalimdor et des Royaumes de l'Est
    python tools/fetch_maps.py --version 12.1.7.70493 --maps 50       # quelques cartes (PTR de Retail)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://wago.tools"
AGENT = "CraftingOrderBot-cartes/1.0 (cartes de zone pour un bot de guilde, usage personnel)"
CONTINENTS = ("1414", "1415")   # Kalimdor, Royaumes de l'Est (ids de Forever et de la Classic)
ZONE = "3"                      # UiMap.Type : une zone (les villes aussi)


def zones(table_csv: str, continents=CONTINENTS) -> list[tuple[int, str]]:
    """(uiMapID, nom) des zones des continents, d'après la table UiMap du build."""
    rows = csv.DictReader(io.StringIO(table_csv))
    return [(int(r["ID"]), r["Name_lang"]) for r in rows if r["Type"] == ZONE and r["ParentUiMapID"] in continents]


def map_path(map_id: int, version: str, locale: str) -> str:
    """L'adresse de l'API qui rend la carte entièrement explorée."""
    return f"/api/map/{map_id}?version={version}&locale={locale}&explored=1"


def client_name(version: str) -> str:
    return "Forever" if version.startswith("1.60.") else ("Retail" if int(version.split(".")[0]) >= 10 else "Classic")


def merge_index(index: dict, entries: dict) -> dict:
    """L'index avec les nouvelles entrées (par uiMapID), les autres gardées, trié par numéro."""
    merged = {**index, **entries}
    notes = {k: v for k, v in merged.items() if not k.isdigit()}
    return {**notes, **dict(sorted(((k, v) for k, v in merged.items() if k.isdigit()), key=lambda kv: int(kv[0])))}


class Wago:
    """Les requêtes vers wago.tools : en cache, espacées, identifiées."""

    def __init__(self, cache: Path, delay: float):
        self.cache, self.delay = cache, delay
        cache.mkdir(parents=True, exist_ok=True)

    def get(self, path: str, name: str) -> bytes:
        f = self.cache / name
        if f.exists():
            return f.read_bytes()
        time.sleep(self.delay)
        req = urllib.request.Request(SITE + path, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        f.write_bytes(data)
        return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", required=True, help="build du jeu sur wago.tools, ex. 1.60.1.70658")
    ap.add_argument("--locale", default="frFR")
    ap.add_argument("--maps", help="uiMapID séparés par des virgules (défaut : les zones des deux continents)")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "maps")
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "maps")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args(argv)
    wago = Wago(args.cache, args.delay)
    table = wago.get(f"/db2/UiMap/csv?build={args.version}&locale={args.locale}",
                     f"UiMap-{args.version}-{args.locale}.csv").decode("utf-8")
    names = {r["ID"]: r["Name_lang"] for r in csv.DictReader(io.StringIO(table))}
    wanted = ([(int(m), names.get(m.strip(), "?")) for m in args.maps.split(",")] if args.maps else zones(table))
    index_file = args.out / "maps.json"
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {}
    entries, failed = {}, []
    for n, (map_id, name) in enumerate(wanted, 1):
        try:
            data = wago.get(map_path(map_id, args.version, args.locale), f"map-{map_id}-{args.version}-{args.locale}.png")
            image = Image.open(io.BytesIO(data)).convert("RGB")
        except OSError as err:
            failed.append(map_id)
            print(f"{n:3}/{len(wanted)} {map_id} {name} : ÉCHEC {err}", flush=True)
            continue
        image.save(args.out / f"{map_id}.webp", quality=85, method=6)
        entries[str(map_id)] = {"file": f"{map_id}.webp", "zone": name,
                                "client": f"{client_name(args.version)} {args.version} (jeu, wago.tools, {args.locale})"}
        print(f"{n:3}/{len(wanted)} {map_id} {name} : {image.size[0]}×{image.size[1]}", flush=True)
    index_file.write_text(json.dumps(merge_index(index, entries), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entries)} carte(s) écrite(s), {len(failed)} en échec {failed or ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
