"""L'image de la carte d'un appel (phase 2 de la spec alertes-pvp.md) : un point là où l'appelant est
mort, sur l'image de sa zone. Le point se place en fractions de l'image ; le nom du fichier porte la
carte et le point (une carte relue après un redémarrage redessine son image) ; rien sans coordonnées
ni sans image pour cette zone ; l'image part avec la carte et suit ses mises à jour."""

import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from bot.pvp_cards import Card, from_embed, to_embed
from bot.pvp_map import MAPS_DIR, file_name, load_index, parse_name, render
from tests.test_pvp_relay import Channel, Raw, make

AT_CENTER = "SOS Gnomi Testzone (50.0, 50.0) #SOS3 m7 d1"
ZONE_ONLY = "SOS Gnomi Testzone #SOS3 m7 d2"


def fake_maps(directory: Path) -> dict:
    Image.new("RGB", (200, 100), (240, 230, 200)).save(directory / "zone.png")
    (directory / "maps.json").write_text(json.dumps({"7": {"file": "zone.png"}, "8": {"file": "absente.png"}}),
                                         encoding="utf-8")
    return load_index(directory)


class Render(unittest.TestCase):
    # Pas de cartes livrées dans ce dépôt (public au lancement : les images sont de Blizzard). Elles
    # viendront de wago.tools à la demande (tâche T3 de la spec bot-autonome.md).
    def test_aucune_image_de_blizzard_dans_le_depot(self):
        self.assertFalse(list(MAPS_DIR.glob("*.webp")) + list(MAPS_DIR.glob("*.png")),
                         "dépôt public : aucune image du jeu versionnée")

    def test_le_point_au_bon_endroit(self):
        with tempfile.TemporaryDirectory() as d:
            index = fake_maps(Path(d))
            self.assertEqual(sorted(index), [7], "une entrée sans son image est ignorée")
            data, name = render(index, 7, 0.25, 0.5)
        self.assertEqual(name, "sos-m7-250-500.jpg")
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual((image.format, image.size), ("JPEG", (200, 100)))
            r, g, b = image.getpixel((50 + 8, 50))   # dans le rouge, hors du cœur clair
            self.assertTrue(r > 150 and g < 90 and b < 90, (r, g, b))
            self.assertEqual(image.getpixel((150, 50))[:2], image.getpixel((150, 20))[:2], "le reste intact")

    def test_rien_a_dessiner(self):
        with tempfile.TemporaryDirectory() as d:
            index = fake_maps(Path(d))
            self.assertIsNone(render(index, 7, None, None), "zone seule (D14)")
            self.assertIsNone(render(index, 99, 0.5, 0.5), "pas d'image pour cette zone")

    def test_le_nom_porte_le_point(self):
        self.assertEqual(file_name(50, 0.397, 0.554), "sos-m50-397-554.jpg")
        url = "https://cdn.discordapp.com/attachments/1/2/sos-m50-397-554.jpg?ex=6720&is=671f&hm=abc"
        self.assertEqual(parse_name(url), (50, 0.397, 0.554))
        self.assertIsNone(parse_name("attachment://autre.png"))


class OnTheCard(unittest.TestCase):
    def test_image_dans_l_embed_et_relue(self):
        card = Card("Gnomi", 3, map=50, x=0.397, y=0.554)
        embed = to_embed(card, "sos-m50-397-554.jpg")
        self.assertEqual(embed.image.url, "attachment://sos-m50-397-554.jpg")
        back = from_embed(embed)
        self.assertEqual((back.map, back.x, back.y), (50, 0.397, 0.554))
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
        self.assertEqual([f.filename for f in posted.files], ["sos-m7-500-500.jpg"])
        self.assertEqual(posted.embeds[0].image.url, "attachment://sos-m7-500-500.jpg")


if __name__ == "__main__":
    unittest.main()
