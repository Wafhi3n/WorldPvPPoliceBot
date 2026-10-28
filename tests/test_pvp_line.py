"""La lecture des lignes de World PvP Police (spec alertes-pvp.md, critère 1) : les six exemples de la
spec de l'addon, figés à l'octet, deux vraies lignes vues sur le PTR de Retail le 2026-10-28, et les
refus de `Line.Parse` (l'addon fait foi). Une commande de Crafting Order n'est pas un appel ; l'inverse
(un appel n'est pas une commande) est tenu par les tests du bot des commandes, CraftingOrderBot."""

import unittest

from bot.pvp_line import Killer, parse

# Les six exemples de la spec de l'addon (« Contrat », Exemples), à l'octet.
EX1 = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d1 kXyz cROGUE : 3 voleurs au pont"
EX2 = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d3 kXyz cROGUE : 3 voleurs au pont"
EX3 = "OMW Gnomette > Gnomi #SOS7"
EX4 = "END Gnomi #SOS7"
EX5 = "SOS Gnomi Forêt d'Elwynn #SOS8 m1429 d1 kXyz cROGUE"
EX6 = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d3 kXyz,Abc,Def cROGUE,MAGE,- : 3 voleurs au pont"
# Vues sur Discord et dans les SavedVariables, PTR de Retail, 2026-10-28.
PTR1 = "SOS Palrien Strangleronce septentrionale (39.9, 55.7) #SOS1 m50 d1 kCamparind cDEATHKNIGHT : test libérer"
PTR2 = ("SOS Palrien Strangleronce septentrionale (39.8, 55.5) #SOS7 m50 d1 kCamparind cDEATHKNIGHT : "
        "ON ME CAMPE ATLANCE SAUVE MOA")


class Examples(unittest.TestCase):
    def test_sos_a_une_mort(self):
        line = parse(EX1)
        self.assertEqual((line.kind, line.who, line.n, line.zone, line.map, line.deaths),
                         ("SOS", "Gnomi", 7, "Forêt d'Elwynn", 1429, 1))
        self.assertAlmostEqual(line.x, 0.421)
        self.assertAlmostEqual(line.y, 0.653)
        self.assertEqual(line.killers, [Killer("Xyz", "ROGUE")])
        self.assertEqual(line.msg, "3 voleurs au pont")
        self.assertEqual(line.caller_name, "Gnomi")

    def test_sos_a_trois_morts(self):
        self.assertEqual(parse(EX2).deaths, 3)

    def test_omw_et_end(self):
        omw, end = parse(EX3), parse(EX4)
        self.assertEqual((omw.kind, omw.who, omw.caller, omw.n, omw.caller_name), ("OMW", "Gnomette", "Gnomi", 7, "Gnomi"))
        self.assertEqual((end.kind, end.who, end.n, end.caller_name), ("END", "Gnomi", 7, "Gnomi"))

    def test_zone_seule(self):
        line = parse(EX5)
        self.assertEqual((line.zone, line.x, line.y, line.n, line.msg), ("Forêt d'Elwynn", None, None, 8, None))

    def test_trois_tueurs_dont_une_classe_inconnue(self):
        line = parse(EX6)
        self.assertEqual(line.killers, [Killer("Xyz", "ROGUE"), Killer("Abc", "MAGE"), Killer("Def", None)])

    def test_lignes_vues_sur_le_ptr(self):
        one, seven = parse(PTR1), parse(PTR2)
        self.assertEqual((one.who, one.zone, one.n, one.map, one.msg),
                         ("Palrien", "Strangleronce septentrionale", 1, 50, "test libérer"))
        self.assertEqual(one.killers, [Killer("Camparind", "DEATHKNIGHT")])
        self.assertEqual((seven.n, seven.msg), (7, "ON ME CAMPE ATLANCE SAUVE MOA"))

    def test_tueurs_sans_classe_connue(self):
        self.assertEqual(parse("SOS Gnomi Duskwood #SOS2 m10 d1 kXyz,Abc").killers, [Killer("Xyz"), Killer("Abc")])


class Refusals(unittest.TestCase):
    def assertRefused(self, text, why):
        self.assertIsNone(parse(text), why)

    def test_listes(self):
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 cROGUE", "un c sans k")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 kXyz,Abc cROGUE", "listes mal alignées")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 kXyz,,Abc", "un nom vide (élément vide gardé)")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 kXyz-Royaume", "un nom avec royaume")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 kXyz crogue", "une classe qui n'est pas un jeton")

    def test_zone_et_coordonnees(self):
        self.assertRefused("SOS Gnomi Duskwood (Est) #SOS2 m10 d1", "une parenthèse dans la zone")
        self.assertRefused("SOS Gnomi Duskwood (142.0, 10.0) #SOS2 m10 d1", "au-delà de 100")
        self.assertRefused("SOS Gnomi Duskwood (42.1) #SOS2 m10 d1", "une seule coordonnée")
        self.assertRefused("SOS Gnomi  #SOS2 m10 d1", "zone vide")

    def test_message_et_queue(self):
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 : au #SOS3", "un # dans le message")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 : [Linen Bandage]", "des crochets dans le message")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 : ligne\nsuivante", "un retour à la ligne dans le message")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 xyz", "une queue inconnue")

    def test_pieges_du_portage(self):
        self.assertRefused("SOS Gnomi Duskwood #SOS٢ m10 d1", "un chiffre non ASCII (%d de Lua)")
        self.assertRefused("SOS Gnomi Duskwood #SOS2 m10 d1 kXyz cRogué", "une classe non ASCII (%u de Lua)")
        self.assertIsNotNone(parse(EX4 + "\n"), "un blanc final est permis (%s*$), comme dans l'addon")

    def test_pas_une_ligne_de_l_addon(self):
        self.assertRefused("SOS quelqu'un ?", "un guildien qui tape SOS en jeu")
        self.assertRefused("WTB [Linen Bandage] x1 @Gnomi Wafhien #CO12", "une commande de COC")
        self.assertRefused("OMW Gnomette Gnomi #SOS7", "OMW sans >")
        self.assertRefused(None, "pas un texte")


if __name__ == "__main__":
    unittest.main()
