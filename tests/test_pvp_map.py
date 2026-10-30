"""L'image de la carte d'une zone (phase 2 et P10 de la spec alertes-pvp.md) : un point par guildien qui y
appelle, son prénom à côté, sur l'image de sa zone. Le point se place en fractions de l'image ; rien sans
point ni sans image pour cette zone ; l'image part avec la carte et suit ses mises à jour."""

import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from bot.pvp_cards import open_card
from bot.pvp_embed import from_embed, to_embed
from bot.pvp_line import parse
from bot.pvp_map import MAPS_DIR, file_name, load_index, render
from tests.test_pvp_relay import Channel, Raw, make

AT_CENTER = "SOS Gnomi Testzone (50.0, 50.0) #SOS3 m7 d1"
ZONE_ONLY = "SOS Gnomi Testzone #SOS3 m7 d2"


def fake_maps(directory: Path) -> dict:
    Image.new("RGB", (400, 200), (240, 230, 200)).save(directory / "zone.png")
    (directory / "maps.json").write_text(json.dumps({"7": {"file": "zone.png"}, "8": {"file": "absente.png"}}),
                                         encoding="utf-8")
    return load_index(directory)


def red(pixel):
    r, g, b = pixel
    return r > 150 and g < 90 and b < 90


class Render(unittest.TestCase):
    # Pas de cartes livrées dans ce dépôt (public au lancement : les images sont de Blizzard). Elles
    # viennent de wago.tools à la demande (map_store.py).
    def test_aucune_image_de_blizzard_dans_le_depot(self):
        self.assertFalse(list(MAPS_DIR.glob("*.webp")) + list(MAPS_DIR.glob("*.png")),
                         "dépôt public : aucune image du jeu versionnée")

    def test_le_point_au_bon_endroit(self):
        with tempfile.TemporaryDirectory() as d:
            index = fake_maps(Path(d))
            self.assertEqual(sorted(index), [7], "une entrée sans son image est ignorée")
            data, name = render(index, 7, [(0.25, 0.5, "")])
        self.assertEqual(name, file_name(7))
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual((image.format, image.size), ("JPEG", (400, 200)))
            self.assertTrue(red(image.getpixel((100 + 8, 100))), "dans le rouge, hors du cœur clair")
            self.assertEqual(image.getpixel((300, 100))[:2], image.getpixel((300, 20))[:2], "le reste intact")

    def test_un_point_par_appelant_et_son_prenom(self):
        with tempfile.TemporaryDirectory() as d:
            data, _ = render(fake_maps(Path(d)), 7, [(0.2, 0.3, "Gnomi"), (0.7, 0.7, "Bob")])
        with Image.open(io.BytesIO(data)) as image:
            self.assertTrue(red(image.getpixel((80 + 8, 60))) and red(image.getpixel((280 + 8, 140))), "deux points")
            label = [image.getpixel((x, 60)) for x in range(98, 140)]
            self.assertTrue(any(min(p) > 220 for p in label) and any(max(p) < 60 for p in label),
                            "le prénom à côté du point : blanc cerné de noir")

    def test_deux_points_qui_se_touchent_gardent_leurs_deux_prenoms(self):
        # Vu au PTR le 2026-10-30 : Palrien (39.8, 55.6) et Boomaz (39.9, 55.7), un seul prénom lisible.
        def label_rows(points):
            with tempfile.TemporaryDirectory() as d:
                data, _ = render(fake_maps(Path(d)), 7, points)
            with Image.open(io.BytesIO(data)) as image:
                return {y for y in range(70, 130) if any(min(image.getpixel((x, y))) > 220 for x in range(222, 300))}
        one = label_rows([(0.5, 0.5, "Gnomi")])
        two = label_rows([(0.5, 0.5, "Gnomi"), (0.502, 0.502, "Bob")])
        self.assertTrue(one and min(one) < 100 < max(one), "seul : le prénom centré sur le point")
        self.assertTrue(any(y < 96 for y in two) and any(y > 104 for y in two), "deux lignes, l'une au-dessus de l'autre")
        self.assertGreater(max(two) - min(two), 20, "sur deux lignes, pas superposés")

    def test_deux_points_eloignes_ne_s_empilent_pas(self):
        with tempfile.TemporaryDirectory() as d:
            data, _ = render(fake_maps(Path(d)), 7, [(0.25, 0.3, "Gnomi"), (0.25, 0.7, "Bob")])
        with Image.open(io.BytesIO(data)) as image:
            for y in (60, 140):
                self.assertTrue(any(min(image.getpixel((x, y))) > 220 for x in range(120, 160)), "chacun à hauteur de son point")

    def test_rien_a_dessiner(self):
        with tempfile.TemporaryDirectory() as d:
            index = fake_maps(Path(d))
            self.assertIsNone(render(index, 7, [(None, None, "Zed")]), "zone seule (D14)")
            self.assertIsNone(render(index, 99, [(0.5, 0.5, "Bob")]), "pas d'image pour cette zone")
            self.assertIsNone(render(index, 7, []), "aucun appel")


class OnTheCard(unittest.TestCase):
    def test_image_dans_l_embed_et_points_relus(self):
        card = open_card(parse("SOS Gnomi Strangleronce (39.7, 55.4) #SOS3 m50 d1"), 0.0)
        embed = to_embed(card, file_name(50))
        self.assertEqual(embed.image.url, "attachment://sos-m50.jpg")
        back = from_embed(embed).calls[0]
        self.assertEqual((back.map, round(back.x, 3), round(back.y, 3)), (50, 0.397, 0.554),
                         "les points se relisent dans la carte : l'image se redessine après un redémarrage")
        self.assertIsNone(to_embed(card).image.url, "sans image : pas d'image dans l'embed")

    def test_l_image_part_et_suit_la_carte(self):
        with tempfile.TemporaryDirectory() as d:
            channel = Channel()
            relay, _ = make(channel, maps=fake_maps(Path(d)))

            async def go():
                await relay.handle(Raw(AT_CENTER))
                await relay.handle(Raw(ZONE_ONLY))
            asyncio.run(go())
        posted = channel.sent[0]
        self.assertEqual(len(channel.sent), 1)
        self.assertEqual(posted.embeds[0].image.url, None, "zone seule ensuite : plus d'image dans l'embed")
        self.assertEqual(posted.files, [], "et la vieille image est retirée du message")

    def test_l_image_a_la_publication(self):
        with tempfile.TemporaryDirectory() as d:
            channel = Channel()
            relay, _ = make(channel, maps=fake_maps(Path(d)))
            asyncio.run(relay.handle(Raw(AT_CENTER)))
        posted = channel.sent[0]
        self.assertEqual([f.filename for f in posted.files], ["sos-m7.jpg"])
        self.assertEqual(posted.embeds[0].image.url, "attachment://sos-m7.jpg")


if __name__ == "__main__":
    unittest.main()
