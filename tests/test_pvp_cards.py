"""La carte d'un appel PvP (spec alertes-pvp.md, critères 2 et 4, P7, P8) : ce qu'elle montre, le texte
des joueurs échappé, sa relecture après un redémarrage (rien n'est stocké ailleurs), et 30 minutes sans
ligne SOS = « terminé, sans nouvelles »."""

import unittest

from bot.pvp_cards import (ACTIVE, EXPIRED, EXPIRY, NOBODY, SETTLED, Card, add_responder, expire, from_embed,
                           from_line, to_embed, update)
from bot.pvp_line import parse

THREE = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d3 kXyz,Abc,Def cROGUE,MAGE,- : 3 voleurs au pont"
ZONE_ONLY = "SOS Gnomi Forêt d'Elwynn #SOS8 m1429 d1 kXyz cROGUE"


def fields(embed):
    return {f.name: f.value for f in embed.fields}


class Content(unittest.TestCase):
    def test_ce_que_montre_la_carte(self):
        embed = to_embed(from_line(parse(THREE), 1000.0))
        f = fields(embed)
        self.assertEqual(embed.title, "Gnomi appelle à l'aide !")
        self.assertEqual(f["Où"], "Forêt d'Elwynn (42.1, 65.3)")
        self.assertEqual(f["Morts"], "3")
        self.assertEqual(f["Tueurs"], "Xyz (Voleur), Abc (Mage), Def", "la classe dans la langue du bot, `-` = sans")
        self.assertEqual(f["En route"], NOBODY)
        self.assertEqual(f["Dernière nouvelle"], "<t:1000:R>", "l'heure relative")
        self.assertIn("> 3 voleurs au pont", embed.description)
        self.assertEqual(embed.footer.text, "#SOS7 · Gnomi", "le pied : la clé, relue après un redémarrage")
        self.assertEqual(embed.timestamp.timestamp(), 1000.0)

    def test_zone_seule_sans_tueur_ni_message(self):
        card = from_line(parse("SOS Gnomi Forêt d'Elwynn #SOS8 m1429 d1"), 0.0)
        f = fields(to_embed(card))
        self.assertEqual(f["Où"], "Forêt d'Elwynn", "zone seule (D14) : sans coordonnées")
        self.assertNotIn("Tueurs", f)
        self.assertEqual(to_embed(card).description, "**En cours**")

    def test_texte_des_joueurs_echappe(self):
        line = parse("SOS Gnomi Duskwood #SOS2 m10 d1 : @everyone **gras** <@&123456789012345678> @here")
        desc = to_embed(from_line(line, 0.0)).description
        for raw in ("@everyone", "@here", "<@&123456789012345678>", "**gras**"):
            self.assertNotIn(raw, desc, raw)
        self.assertIn("\\*\\*gras\\*\\*", desc)


class Life(unittest.TestCase):
    def test_trente_minutes(self):
        self.assertEqual(EXPIRY, 30 * 60, "comme l'addon (D11 révisée par le user le 2026-10-28)")
        card = from_line(parse(ZONE_ONLY), 0.0)
        self.assertFalse(expire(card, EXPIRY - 1))
        self.assertTrue(expire(card, EXPIRY))
        self.assertEqual(card.status, EXPIRED)
        self.assertIn("Terminé, sans nouvelles", to_embed(card).description)
        settled = Card("Gnomi", 1, status=SETTLED)
        self.assertFalse(expire(settled, 10 * EXPIRY), "une carte réglée reste réglée")

    def test_en_route_une_fois_et_mise_a_jour(self):
        card = from_line(parse(ZONE_ONLY), 0.0)
        self.assertTrue(add_responder(card, "Gnomette"))
        self.assertFalse(add_responder(card, "gnomette"), "un nom une seule fois")
        update(card, parse(THREE), 60.0)
        self.assertEqual((card.deaths, card.en_route, card.updated_at), (3, ["Gnomette"], 60.0),
                         "une mise à jour garde ceux qui arrivent")


class Reread(unittest.TestCase):
    def test_une_carte_se_relit_telle_quelle(self):
        card = from_line(parse(THREE), 1234.0)
        add_responder(card, "Gnomette")
        add_responder(card, "Bob")
        back = from_embed(to_embed(card))
        for attr in ("caller", "n", "where", "deaths", "killers", "msg", "en_route", "status", "updated_at"):
            self.assertEqual(getattr(back, attr), getattr(card, attr), attr)

    def test_un_message_echappe_ne_s_echappe_pas_deux_fois(self):
        card = from_line(parse("SOS Gnomi Duskwood #SOS2 m10 d1 : **gras**"), 0.0)
        again = to_embed(from_embed(to_embed(card)))
        self.assertEqual(again.description, to_embed(card).description)

    def test_statuts_relus(self):
        for status in (ACTIVE, SETTLED, EXPIRED):
            self.assertEqual(from_embed(to_embed(Card("Gnomi", 1, status=status))).status, status)

    def test_pas_une_carte(self):
        embed = to_embed(Card("Gnomi", 1))
        embed.set_footer(text="#CO12 · Gnomi")
        self.assertIsNone(from_embed(embed))


if __name__ == "__main__":
    unittest.main()
