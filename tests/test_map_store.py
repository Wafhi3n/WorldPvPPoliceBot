"""Les cartes de zone téléchargées à la demande sur wago.tools (bot-autonome.md, A4 ; critère 5), devant un
faux wago.tools : une zone ne se télécharge qu'une fois (cache), au dernier build du produit, dans la
langue voulue, carte explorée ; une requête par seconde au plus ; une panne ou une image illisible = pas
d'image, sans erreur, nouvel essai plus tard ; et la carte d'appel porte l'image."""

import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from bot.map_store import RETRY_AFTER, MapStore
from tests.test_pvp_relay import SOS1, Channel, Raw, make


def png(size=(1002, 668)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 180, 120)).save(out, format="PNG")
    return out.getvalue()


class FakeWago:
    def __init__(self, broken=False, garbage=False):
        self.urls, self.broken, self.garbage = [], broken, garbage

    def __call__(self, url):
        self.urls.append(url)
        if self.broken:
            raise OSError("wago.tools injoignable")
        if "/api/builds/" in url:
            return json.dumps({"product": "wowf", "version": "1.60.1.70658"}).encode()
        return b"pas une image" if self.garbage else png()


class Clock:
    def __init__(self):
        self.t, self.slept = 1000.0, []

    def __call__(self):
        return self.t

    async def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


def store(directory, wago, clock):
    return MapStore(Path(directory), "wowf", "frFR", fetch=wago, clock=clock, sleep=clock.sleep)


class Download(unittest.TestCase):
    def test_une_fois_au_dernier_build(self):
        with tempfile.TemporaryDirectory() as d:
            wago, clock = FakeWago(), Clock()
            maps = store(d, wago, clock)

            async def go():
                return await maps.path(1434), await maps.path(1434), await maps.path(1411)
            first, again, other = asyncio.run(go())
            self.assertTrue(first.exists() and again == first and other.exists())
            self.assertEqual(wago.urls, [
                "https://wago.tools/api/builds/wowf/latest",
                "https://wago.tools/api/map/1434?version=1.60.1.70658&locale=frFR&explored=1",
                "https://wago.tools/api/map/1411?version=1.60.1.70658&locale=frFR&explored=1",
            ], "le build une fois ; chaque zone une fois ; explored=1 (sans valeur : ignoré)")
            self.assertEqual(len(maps), 2)
            self.assertEqual(clock.slept, [1.0, 1.0], "une requête par seconde au plus")

    def test_panne_et_image_illisible(self):
        with tempfile.TemporaryDirectory() as d:
            for wago in (FakeWago(broken=True), FakeWago(garbage=True)):
                clock = Clock()
                maps = store(d, wago, clock)
                self.assertIsNone(asyncio.run(maps.path(50)), "pas d'image, sans erreur")
                calls = len(wago.urls)
                self.assertIsNone(asyncio.run(maps.path(50)))
                self.assertEqual(len(wago.urls), calls, "pas de nouvel essai tout de suite")
                clock.t += RETRY_AFTER
                asyncio.run(maps.path(50))
                self.assertGreater(len(wago.urls), calls, "nouvel essai 10 minutes plus tard")
                self.assertEqual(len(maps), 0, "rien d'illisible dans le cache")

    def test_pas_de_zone(self):
        with tempfile.TemporaryDirectory() as d:
            wago = FakeWago()
            self.assertIsNone(asyncio.run(store(d, wago, Clock()).path(None)))
            self.assertEqual(wago.urls, [])


class OnTheCard(unittest.TestCase):
    def test_la_carte_d_appel_porte_l_image(self):
        with tempfile.TemporaryDirectory() as d:
            channel = Channel()
            relay, _ = make(channel, maps=store(d, FakeWago(), Clock()))
            asyncio.run(relay.handle(Raw(SOS1)))
        posted = channel.sent[0]
        self.assertEqual([f.filename for f in posted.files], ["sos-m1429.jpg"])
        self.assertEqual(posted.embeds[0].image.url, "attachment://sos-m1429.jpg")

    def test_zone_seule_rien_n_est_telecharge(self):
        with tempfile.TemporaryDirectory() as d:
            wago = FakeWago()
            relay, _ = make(Channel(), maps=store(d, wago, Clock()))
            asyncio.run(relay.handle(Raw("SOS Gnomi Duskwood #SOS2 m10 d1")))
        self.assertEqual(wago.urls, [], "sans coordonnées, pas de point : pas de téléchargement")


if __name__ == "__main__":
    unittest.main()
