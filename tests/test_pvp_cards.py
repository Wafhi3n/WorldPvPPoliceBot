"""La carte d'une zone (spec alertes-pvp.md, critères 2, 4, 11, 12, 14 ; P7, P8, P10) : un ou plusieurs
appels, ce qu'elle montre, le texte des joueurs échappé, son état (en cours, verte quand tous ses appels
sont réglés, grise sinon), et sa relecture après un redémarrage (rien n'est stocké ailleurs)."""

import unittest

from bot.pvp_cards import (ACTIVE, EXPIRED, EXPIRY, SETTLED, Call, Card, add_responder, expire, is_live, join,
                           next_expiry, open_card, update_call)
from bot.pvp_embed import COLORS, NOBODY, from_embed, to_embed
from bot.pvp_line import parse

THREE = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d3 kXyz,Abc,Def cROGUE,MAGE,- : 3 voleurs au pont"
BOB = "SOS Bob Forêt d'Elwynn (50.0, 40.0) #SOS2 m1429 d1 kXyz cROGUE"
ZONE_ONLY = "SOS Zed Forêt d'Elwynn #SOS4 m1429 d1"


def fields(embed):
    return [(f.name, f.value) for f in embed.fields]


class OneCall(unittest.TestCase):
    def test_ce_que_montre_la_carte(self):
        embed = to_embed(open_card(parse(THREE), 1000.0))
        self.assertEqual(embed.title, "Gnomi appelle à l'aide !")
        self.assertEqual(embed.description, "**En cours**")
        self.assertEqual(fields(embed)[0], ("Zone", "Forêt d'Elwynn"))
        name, value = fields(embed)[1]
        self.assertEqual(name, "Gnomi — appel n°7")
        self.assertEqual(value.split("\n"), [
            "Où : (42.1, 65.3) · Morts : 3",
            "Tueurs : Xyz (Voleur), Abc (Mage), Def",
            "> 3 voleurs au pont",
            f"En route : {NOBODY}",
            "<t:1000:R>",
        ])
        self.assertEqual(embed.footer.text, "m1429 · Gnomi#7", "le pied : la zone et les appels, relus après un redémarrage")
        self.assertEqual(embed.timestamp.timestamp(), 1000.0)

    def test_texte_des_joueurs_echappe(self):
        card = open_card(parse("SOS Gnomi Duskwood #SOS2 m10 d1 : @everyone **gras** <@&123456789012345678> @here"), 0.0)
        value = to_embed(card).fields[1].value
        for raw in ("@everyone", "@here", "<@&123456789012345678>", "**gras**"):
            self.assertNotIn(raw, value, raw)


class SeveralCalls(unittest.TestCase):
    def test_deux_appelants_une_carte(self):
        card = open_card(parse(THREE), 1000.0)
        join(card, parse(BOB), 1060.0)
        embed = to_embed(card)
        self.assertEqual(embed.title, "2 guildiens appellent à l'aide")
        self.assertEqual([n for n, _ in fields(embed)], ["Zone", "Gnomi — appel n°7", "Bob — appel n°2"])
        self.assertEqual(embed.footer.text, "m1429 · Gnomi#7 · Bob#2")
        self.assertEqual(card.updated_at, 1060.0, "la carte date de sa dernière nouvelle")

    def test_les_etats(self):
        card = open_card(parse(THREE), 0.0)
        bob = join(card, parse(BOB), 60.0)
        card.calls[0].status = SETTLED
        self.assertEqual(card.status, ACTIVE, "l'un réglé, l'autre en cours : la carte est en cours")
        self.assertEqual(to_embed(card).fields[1].name, "Gnomi — appel n°7 · réglé")
        bob.status = SETTLED
        self.assertEqual((card.status, to_embed(card).color.value), (SETTLED, COLORS[SETTLED]), "tous réglés : verte")
        bob.status = ACTIVE
        self.assertTrue(expire(card, 60.0 + EXPIRY))
        self.assertEqual((card.status, bob.status), (EXPIRED, EXPIRED), "le dernier en cours expire : grise")

    def test_trente_minutes_par_appel(self):
        card = open_card(parse(THREE), 0.0)
        join(card, parse(BOB), 600.0)
        self.assertEqual(next_expiry(card), EXPIRY, "le prochain à expirer : Gnomi")
        self.assertTrue(expire(card, EXPIRY))
        self.assertEqual([c.status for c in card.calls], [EXPIRED, ACTIVE], "chacun ses 30 minutes")
        self.assertEqual(card.status, ACTIVE)
        self.assertFalse(is_live(card.calls[0], EXPIRY) or not is_live(card.calls[1], EXPIRY))

    def test_meme_numero_remplace(self):
        card = open_card(parse(THREE), 0.0)
        card.calls[0].status = EXPIRED
        join(card, parse(THREE.replace("d3", "d1")), EXPIRY + 5)
        self.assertEqual([(c.caller, c.deaths, c.status) for c in card.calls], [("Gnomi", 1, ACTIVE)],
                         "un appel n'est qu'une fois sur sa carte")

    def test_en_route_par_appel(self):
        card = open_card(parse(THREE), 0.0)
        bob = join(card, parse(BOB), 1.0)
        self.assertTrue(add_responder(bob, "Gnomette"))
        self.assertFalse(add_responder(bob, "gnomette"), "un nom une seule fois")
        self.assertEqual((card.calls[0].en_route, bob.en_route), ([], ["Gnomette"]))


class Reread(unittest.TestCase):
    def test_une_carte_a_plusieurs_appels_se_relit(self):
        card = open_card(parse(THREE), 1234.0)
        bob = join(card, parse(BOB), 1300.0)
        zed = join(card, parse(ZONE_ONLY), 1400.0)
        add_responder(bob, "Gnomette")
        add_responder(bob, "*Ast*")
        card.calls[0].status = SETTLED
        update_call(zed, parse("SOS Zed Durotar (10.0, 20.0) #SOS4 m1411 d2 : parti à Durotar"), 1500.0)
        back = from_embed(to_embed(card))
        self.assertEqual((back.map, back.zone), (1429, "Forêt d'Elwynn"))
        for mine, read in zip(card.calls, back.calls):
            for attr in ("caller", "n", "map", "deaths", "killers", "msg", "en_route", "status", "updated_at"):
                self.assertEqual(getattr(read, attr), getattr(mine, attr), f"{mine.caller} : {attr}")
            self.assertAlmostEqual(read.x or 0, mine.x or 0)
        self.assertEqual(to_embed(card).footer.text, "m1429 · Gnomi#7 · Bob#2 · Zed#4@1411",
                         "un appel parti dans une autre zone reste sur sa carte, sa zone notée")
        self.assertEqual(back.calls[2].zone, "Durotar")

    def test_zone_seule(self):
        card = open_card(parse(ZONE_ONLY), 0.0)
        self.assertIn("Où : zone seule · Morts : 1", to_embed(card).fields[1].value)
        back = from_embed(to_embed(card)).calls[0]
        self.assertEqual((back.x, back.y, back.zone), (None, None, "Forêt d'Elwynn"))

    def test_un_message_echappe_ne_s_echappe_pas_deux_fois(self):
        card = open_card(parse("SOS Gnomi Duskwood #SOS2 m10 d1 : **gras**"), 0.0)
        self.assertEqual(to_embed(from_embed(to_embed(card))).fields[1].value, to_embed(card).fields[1].value)

    def test_pas_une_carte(self):
        embed = to_embed(Card(1429, "Elwynn", [Call("Gnomi", 1, map=1429)]))
        embed.set_footer(text="#CO12 · Gnomi")
        self.assertIsNone(from_embed(embed))

    def test_pied_et_champs_qui_ne_s_accordent_pas(self):
        embed = to_embed(Card(1429, "Elwynn", [Call("Gnomi", 1, map=1429)]))
        embed.set_footer(text="m1429 · Gnomi#1 · Bob#2")
        self.assertIsNone(from_embed(embed), "deux appels au pied, un seul champ : on ne devine pas")


if __name__ == "__main__":
    unittest.main()
