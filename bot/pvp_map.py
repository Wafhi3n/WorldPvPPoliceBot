"""L'image de la carte d'un appel : la carte de la zone, avec un point par guildien qui y appelle, son
prénom à côté (phase 2 et P10 de la spec alertes-pvp.md, demandes du user le 2026-10-28).

L'image est la toile entière de la carte du monde en jeu (1002×668, wago.tools, map_store.py) : les
coordonnées d'une ligne (fractions 0..1 de la carte de zone) donnent le pixel directement,
`x * largeur`, `y * hauteur`. Vu juste au PTR de Retail le 2026-10-28 (« le point est au bon endroit »).

Rien sans point (appels en zone seule), sans image pour cette carte, ou sans Pillow : la carte d'appel
part sans image.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = ROOT / "data" / "maps"
DOT = ((15, (255, 255, 255)), (11, (200, 20, 20)), (4, (255, 230, 230)))


def load_index(directory: Path = MAPS_DIR) -> dict[int, Path]:
    """uiMapID → image, d'après `maps.json` (des cartes posées à la main) ; une entrée sans image est ignorée."""
    try:
        raw = json.loads((directory / "maps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    index = {}
    for k, entry in raw.items():
        if k.isdigit() and isinstance(entry, dict) and (directory / str(entry.get("file", ""))).is_file():
            index[int(k)] = directory / entry["file"]
    return index


def file_name(map_id: int) -> str:
    return f"sos-m{map_id}.jpg"


def _font():
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=16)   # Pillow ≥ 10.1 : une police lisible
    except TypeError:
        return ImageFont.load_default()


def render(index: dict, map_id, points) -> tuple[bytes, str] | None:
    """L'image JPEG de la carte avec un point par (x, y, prénom), et son nom ; None s'il n'y a rien à dessiner."""
    points = [(x, y, label) for x, y, label in points if x is not None and y is not None]
    if not points or index.get(map_id) is None:
        return None
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    with Image.open(index[map_id]) as source:
        image = source.convert("RGB")
    width, height = image.size
    draw, font = ImageDraw.Draw(image), _font()
    for x, y, label in points:
        px, py = x * width, y * height
        for radius, color in DOT:
            draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)
        if label:
            draw.text((px + 18, py), label, fill=(255, 255, 255), font=font, anchor="lm",
                      stroke_width=3, stroke_fill=(0, 0, 0))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88)
    return out.getvalue(), file_name(map_id)
