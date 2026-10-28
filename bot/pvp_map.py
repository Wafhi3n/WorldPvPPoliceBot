"""L'image de la carte d'un appel : la carte de la zone, avec un point là où l'appelant est mort (phase 2
de la spec alertes-pvp.md, demande du user le 2026-10-28).

Une image par carte de zone dans `data/maps/`, indexée par l'uiMapID de la ligne (`maps.json`). L'image
est la toile entière de la carte du monde en jeu : les coordonnées de la ligne (fractions 0..1 de la
carte de zone) donnent le pixel directement, `x * largeur`, `y * hauteur`. Essayé le 2026-10-28 sur
Strangleronce septentrionale (Retail, uiMap 50) avec une mort réelle du PTR (39.7, 55.4) : le point
tombe au sud-est de Grom'gol, à confirmer par le user (il sait où il est mort).

Le nom du fichier porte la carte et le point (`sos-m50-397-554.jpg`, en millièmes) : une carte relue
dans l'historique après un redémarrage sait redessiner son image. Rien sans coordonnées (zone seule),
sans image pour cette carte, ou sans Pillow : la carte d'appel part sans image.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = ROOT / "data" / "maps"
_NAME = re.compile(r"sos-m(\d+)-(\d+)-(\d+)\.jpg")


def load_index(directory: Path = MAPS_DIR) -> dict[int, Path]:
    """uiMapID → image, d'après `maps.json` ; une entrée dont l'image manque est ignorée."""
    try:
        raw = json.loads((directory / "maps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    index = {}
    for key, entry in raw.items():
        if key.isdigit() and isinstance(entry, dict) and (directory / str(entry.get("file", ""))).is_file():
            index[int(key)] = directory / entry["file"]
    return index


def file_name(map_id: int, x: float, y: float) -> str:
    return f"sos-m{map_id}-{round(x * 1000)}-{round(y * 1000)}.jpg"


def parse_name(url: str | None):
    """(uiMapID, x, y) depuis l'adresse de l'image d'une carte publiée, ou None."""
    m = _NAME.search(url or "")
    return (int(m.group(1)), int(m.group(2)) / 1000, int(m.group(3)) / 1000) if m else None


def render(index: dict[int, Path], map_id, x, y) -> tuple[bytes, str] | None:
    """L'image JPEG de la carte avec le point, et son nom ; None s'il n'y a rien à dessiner."""
    if map_id not in index or x is None or y is None:
        return None
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    with Image.open(index[map_id]) as source:
        image = source.convert("RGB")
    width, height = image.size
    px, py = x * width, y * height
    draw = ImageDraw.Draw(image)
    for radius, color in ((15, (255, 255, 255)), (11, (200, 20, 20)), (4, (255, 230, 230))):
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88)
    return out.getvalue(), file_name(map_id, x, y)
