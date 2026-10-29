"""Les cartes en français ou en anglais (A5 de docs/specs/bot-autonome.md) : le français d'avant inchangé au
caractère près, l'anglais complet, et une carte relue quelle que soit la langue où elle a été écrite (un
hébergeur peut changer de langue pendant qu'une carte est en cours)."""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot import config as cfg
from bot import labels
from bot.pvp_cards import ACTIVE, CLASS_TOKENS, EXPIRED, SETTLED, Call, Card, open_card
from bot.pvp_embed import from_embed, to_embed
from bot.pvp_line import parse
from tests.test_pvp_relay import Channel, Raw, make

HERE = Path(__file__).resolve().parent
THREE = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d3 kXyz,Abc,Def cROGUE,DEATHKNIGHT,- : 3 voleurs au pont"


def zone_card() -> Card:
    """La carte de tests/cartes_fr.json (rendu français relevé AVANT la table des libellés)."""
    return Card(1429, "Forêt d'Elwynn", [
        Call("Gnomi", 7, map=1429, zone="Forêt d'Elwynn", x=0.421, y=0.653, deaths=3, killers="Xyz (Voleur), Abc",
             msg="3 voleurs au pont", en_route=["Gnomette", "Bob"], status=ACTIVE, updated_at=1793000000.0),
        Call("Bob", 2, map=1429, zone="Forêt d'Elwynn", deaths=1, status=SETTLED, updated_at=1793000100.0),
        Call("Zed", 4, map=1411, zone="Durotar", x=0.1, y=0.2, deaths=1, status=EXPIRED, updated_at=1793000200.0),
        Call("Lia", 1, map=1411, zone="Durotar", deaths=2, status=EXPIRED, updated_at=1793000300.0),
    ])


def one_card() -> Card:
    return Card(1429, "Forêt d'Elwynn", [Call("Gnomi", 7, map=1429, zone="Forêt d'Elwynn", x=0.5, y=0.5,
                                              status=SETTLED, updated_at=1793000000.0)])


def dump(card: Card) -> dict:
    e = to_embed(card, image="x.jpg")
    return {"title": e.title, "description": e.description, "color": e.color.value, "footer": e.footer.text,
            "fields": [[f.name, f.value] for f in e.fields]}


def facts(card: Card) -> list:
    """Ce qu'une carte relue doit rendre (le point relu passe par « 42.1 » : arrondi)."""
    def r(v):
        return None if v is None else round(v, 4)
    return [(c.caller, c.n, c.map, c.zone, r(c.x), r(c.y), c.deaths, c.killers, c.msg, c.en_route, c.status,
             c.updated_at) for c in card.calls]


class Table(unittest.TestCase):
    def test_memes_cles_dans_chaque_langue(self):
        fr = labels.LANGS["fr"]
        for lang, t in labels.LANGS.items():
            self.assertEqual(set(t), set(fr), lang)
            self.assertEqual(set(t["status"]), {ACTIVE, SETTLED, EXPIRED}, lang)
            self.assertEqual(set(t["state"]), {SETTLED, EXPIRED}, lang)
            self.assertEqual(set(t["classes"]), set(CLASS_TOKENS), f"{lang} : une classe sans nom")
        self.assertEqual(set(labels.MAP_LOCALES), set(labels.LANGS))

    def test_une_langue_inconnue_refusee(self):
        with self.assertRaises(ValueError):
            labels.use("de")


class French(unittest.TestCase):
    def test_le_francais_d_avant_au_caractere_pres(self):
        before = json.loads((HERE / "cartes_fr.json").read_text(encoding="utf-8"))
        self.assertEqual({"many": dump(zone_card()), "one": dump(one_card())}, before)


class English(unittest.TestCase):
    def setUp(self):
        context = labels.using("en")
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def test_ce_que_montre_la_carte(self):
        embed = to_embed(open_card(parse(THREE), 1000.0))
        self.assertEqual((embed.title, embed.description), ("Gnomi is calling for help!", "**Ongoing**"))
        self.assertEqual([(f.name, f.value) for f in embed.fields], [
            ("Zone", "Forêt d'Elwynn"),
            ("Gnomi — call #7", "Where: (42.1, 65.3) · Deaths: 3\nKillers: Xyz (Rogue), Abc (Death Knight), Def\n"
                                "> 3 voleurs au pont\nOn the way: nobody yet\n<t:1000:R>"),
        ])
        self.assertEqual(embed.footer.text, "m1429 · Gnomi#7", "le pied ne change pas de langue")

    def test_plusieurs_appels_et_leurs_etats(self):
        e = to_embed(zone_card())
        self.assertEqual(e.title, "4 guild members are calling for help")
        self.assertEqual([f.name for f in e.fields[1:]], ["Gnomi — call #7", "Bob — call #2 · settled",
                                                          "Zed — call #4 · no news", "Lia — call #1 · no news"])
        self.assertTrue(e.fields[2].value.startswith("Where: zone only · Deaths: 1\nOn the way: nobody yet"))

    def test_relue(self):
        self.assertEqual(facts(from_embed(to_embed(zone_card()))), facts(zone_card()))

    def test_une_carte_ecrite_en_francais_relue_en_anglais(self):
        with labels.using("fr"):
            french = to_embed(zone_card())
        card = from_embed(french)
        self.assertEqual(facts(card), facts(zone_card()), "rien de perdu au changement de langue")
        value = to_embed(card).fields[1].value
        self.assertTrue(value.startswith("Where: (42.1, 65.3) · Deaths: 3\nKillers: Xyz (Voleur), Abc"),
                        "réécrite en anglais ; les classes des tueurs attendent la prochaine ligne SOS")

    def test_une_carte_ecrite_en_anglais_relue_en_francais(self):
        english = to_embed(zone_card())
        with labels.using("fr"):
            self.assertEqual(facts(from_embed(english)), facts(zone_card()))

    def test_le_relais_publie_en_anglais(self):
        channel = Channel()
        relay, _ = make(channel, role=555)

        async def go():
            await relay.handle(Raw(THREE))
            await relay.handle(Raw("END Gnomi #SOS7"))
        asyncio.run(go())
        embed = channel.sent[0].embeds[0]
        self.assertEqual((embed.title, embed.description), ("Gnomi is calling for help!", "**Settled**"))
        self.assertEqual(embed.fields[1].name, "Gnomi — call #7 · settled")


class Setting(unittest.TestCase):
    def load(self, env):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"DISCORD_TOKEN": "x", **env}, clear=True):
            return cfg.load(Path(d) / "absent.env")

    def test_par_defaut_le_francais(self):
        c = self.load({})
        self.assertEqual((c.language, c.maps_locale), ("fr", "frFR"))

    def test_l_anglais_et_ses_cartes_de_zone(self):
        c = self.load({"BOT_LANGUE": "en"})
        self.assertEqual((c.language, c.maps_locale), ("en", "enUS"), "les noms sur l'image suivent la langue")
        c = self.load({"BOT_LANGUE": "en", "BOT_CARTES_LANGUE": ""})
        self.assertEqual(c.maps_locale, "enUS", "vide (comme dans .env.example) : la langue des cartes")
        c = self.load({"BOT_LANGUE": "en", "BOT_CARTES_LANGUE": "deDE"})
        self.assertEqual(c.maps_locale, "deDE", "imposée, elle l'emporte")

    def test_une_langue_inconnue_refusee(self):
        with self.assertRaises(SystemExit):
            self.load({"BOT_LANGUE": "de"})


if __name__ == "__main__":
    unittest.main()
