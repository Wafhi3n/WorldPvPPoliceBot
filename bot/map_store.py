"""Les cartes de zone, téléchargées À LA DEMANDE sur wago.tools (A4 de docs/specs/bot-autonome.md, validée
par le user le 2026-10-28). Aucune image du jeu n'est versionnée : ce dépôt devient public (D4, D5).

La première fois qu'un appel arrive d'une zone, le bot demande à wago.tools la carte du jeu de cette zone,
entièrement explorée, dans la langue voulue : `/api/map/{uiMapID}?version=<dernier build>&locale=<langue>
&explored=1` (`explored` SANS valeur est ignoré : mesuré le 2026-10-28). Le dernier build du produit
vient de `/api/builds/{produit}/latest` (`wowf` = Forever, `wowt` = PTR de Retail), relu toutes les 6
heures. L'image (PNG, la toile du jeu, 1002×668) est gardée dans le cache (`BOT_STATE`) : une zone ne se
télécharge qu'une fois. Politesse : une requête par seconde au plus, un en-tête qui dit qui on est.
wago.tools injoignable ou image illisible : pas d'image pour cette carte, nouvel essai 10 minutes plus
tard ; jamais d'erreur qui remonte.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import time
import urllib.request
from pathlib import Path

from PIL import Image

SITE = "https://wago.tools"
AGENT = "WorldPvPPoliceBot (bot de guilde World PvP Police ; cartes de zone, une requete par seconde)"
BUILD_TTL = 6 * 3600     # s avant de relire le dernier build du produit
RETRY_AFTER = 10 * 60    # s avant de retenter une zone dont le téléchargement a échoué


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


class MapStore:
    """uiMapID → le fichier de la carte de zone, téléchargé au besoin."""

    def __init__(self, cache_dir: Path, product: str = "wowf", locale: str = "frFR", fetch=http_get,
                 clock=time.monotonic, sleep=asyncio.sleep, delay: float = 1.0, log: logging.Logger | None = None):
        self.dir, self.product, self.locale = Path(cache_dir), product, locale
        self.fetch, self.clock, self.sleep, self.delay = fetch, clock, sleep, delay
        self.log = log or logging.getLogger("bot")
        self.failed: dict[int, float] = {}
        self.build: str | None = None
        self.build_at = 0.0
        self.last: float | None = None
        self.lock = asyncio.Lock()

    def file(self, map_id: int) -> Path:
        return self.dir / f"{self.product}-{self.locale}-{map_id}.png"

    def __len__(self) -> int:
        return len(list(self.dir.glob(f"{self.product}-{self.locale}-*.png"))) if self.dir.exists() else 0

    async def _get(self, url: str) -> bytes:
        """Une requête, au plus une par seconde, hors de la boucle du bot (elle ne le fige pas)."""
        async with self.lock:
            if self.last is not None:
                wait = self.delay - (self.clock() - self.last)
                if wait > 0:
                    await self.sleep(wait)
            try:
                return await asyncio.to_thread(self.fetch, url)
            finally:
                self.last = self.clock()

    async def _version(self) -> str:
        if self.build and self.clock() - self.build_at < BUILD_TTL:
            return self.build
        data = json.loads(await self._get(f"{SITE}/api/builds/{self.product}/latest"))
        self.build, self.build_at = str(data["version"]), self.clock()
        return self.build

    async def path(self, map_id) -> Path | None:
        """Le fichier de la carte de cette zone, téléchargé s'il manque ; None si impossible."""
        if not isinstance(map_id, int):
            return None
        f = self.file(map_id)
        if f.exists():
            return f
        failed = self.failed.get(map_id)
        if failed is not None and self.clock() - failed < RETRY_AFTER:
            return None
        try:
            version = await self._version()
            data = await self._get(f"{SITE}/api/map/{map_id}?version={version}&locale={self.locale}&explored=1")
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            self.dir.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        except (OSError, ValueError, KeyError) as err:   # réseau, réponse illisible, image invalide
            self.failed[map_id] = self.clock()
            self.log.warning("carte de zone %s pas téléchargée (%s) : pas d'image, nouvel essai dans 10 min",
                             map_id, err)
            return None
        self.failed.pop(map_id, None)
        self.log.info("carte de zone %s téléchargée (%s %s, %s)", map_id, self.product, version, self.locale)
        return f
