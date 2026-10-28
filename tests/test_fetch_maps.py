"""L'outil qui récupère les cartes de zone du jeu sur wago.tools (tools/fetch_maps.py), sans réseau :
choisir les zones dans la table UiMap, l'adresse de l'API, l'index. Les vraies cartes se vérifient à
l'œil et sur une vraie mort (critère 10 de la spec)."""

import unittest

from tools.fetch_maps import client_name, map_path, merge_index, zones

UIMAP = (
    "Name_lang,ID,ParentUiMapID,Flags,System,Type\n"
    "Azeroth,947,0,2304,0,1\n"
    "Durotar,1411,1414,2,0,3\n"
    "Kalimdor,1414,947,0,0,2\n"
    '"Les Tarides",1413,1414,2,0,3\n'
    "Strangleronce,1434,1415,2,0,3\n"
    "Grottes,1500,1413,0,0,6\n"
)


class Choose(unittest.TestCase):
    def test_les_zones_des_deux_continents(self):
        self.assertEqual(zones(UIMAP), [(1411, "Durotar"), (1413, "Les Tarides"), (1434, "Strangleronce")],
                         "ni le continent, ni Azeroth, ni une grotte (type 6)")

    def test_l_adresse_de_la_carte_exploree(self):
        self.assertEqual(map_path(1434, "1.60.1.70658", "frFR"),
                         "/api/map/1434?version=1.60.1.70658&locale=frFR&explored=1",
                         "explored=1 : sans valeur, wago.tools rend la carte non explorée (vu le 2026-10-28)")

    def test_le_client(self):
        self.assertEqual([client_name(v) for v in ("1.60.1.70658", "12.1.7.70493", "1.15.9.70576")],
                         ["Forever", "Retail", "Classic"])


class Index(unittest.TestCase):
    def test_l_index_garde_le_reste(self):
        index = {"_lisez-moi": "x", "50": {"file": "50.webp"}, "1434": {"file": "vieux.webp"}}
        merged = merge_index(index, {"1434": {"file": "1434.webp"}, "1411": {"file": "1411.webp"}})
        self.assertEqual(list(merged), ["_lisez-moi", "50", "1411", "1434"], "notes d'abord, puis par numéro")
        self.assertEqual(merged["1434"]["file"], "1434.webp", "la carte du jeu remplace l'ancienne")


if __name__ == "__main__":
    unittest.main()
