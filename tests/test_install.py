"""L'installation sur un serveur (bot-autonome.md, A1 ; critère 2) : le salon des cartes et le rôle,
trouvés par leur nom ou créés ; le salon en lecture seule pour les membres, le rôle mentionnable ; rien
de créé sans le droit ; un rôle au-dessus du bot n'est pas touché."""

import asyncio
import unittest
from types import SimpleNamespace

from bot.install import install
from tests.fakes import FakeGuild, FakeRole, Source

LOG = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)


def run(guild):
    return asyncio.run(install(guild, "alertes-pvp", "pvp-police", LOG))


class Create(unittest.TestCase):
    def test_rien_n_existe_tout_est_cree(self):
        guild = FakeGuild(500, "Ost")
        server = run(guild)
        self.assertEqual(guild.created, [("salon", "alertes-pvp"), ("rôle", "pvp-police")])
        alerts, role = server.alerts, guild.roles[-1]
        everyone, me = alerts.overwrites[guild.default_role], alerts.overwrites[guild.me]
        self.assertIs(everyone.send_messages, False, "les membres ne peuvent pas écrire")
        self.assertIs(everyone.add_reactions, True, "mais peuvent réagir")
        self.assertTrue(me.send_messages and me.attach_files and me.embed_links and me.read_message_history,
                        "le bot écrit, joint l'image de la carte, relit ses cartes")
        self.assertTrue(role.mentionable, "sans ça, la mention d'un bot ne sonne pas")
        self.assertEqual((server.guild_id, server.role_id), (500, role.id))


class Reuse(unittest.TestCase):
    def test_retrouves_par_leur_nom(self):
        existing = Source("alertes-pvp")
        role = FakeRole(77, "PvP-Police", 5, mentionable=False)
        guild = FakeGuild(500, "Ost", channels=[Source("general"), existing], roles=[role])
        server = run(guild)
        self.assertEqual(guild.created, [], "rien de créé")
        self.assertIs(server.alerts, existing)
        self.assertEqual((server.role_id, role.mentionable), (77, True), "le rôle retrouvé est rendu mentionnable")

    def test_un_role_au_dessus_du_bot_n_est_pas_touche(self):
        role = FakeRole(77, "pvp-police", 50, mentionable=False)
        server = run(FakeGuild(500, "Ost", channels=[Source("alertes-pvp")], roles=[role]))
        self.assertEqual((role.edits, server.role_id), ([], 77), "Discord l'interdit : on le dit, sans y toucher")


class Rights(unittest.TestCase):
    def test_sans_le_droit_de_gerer_les_salons(self):
        guild = FakeGuild(500, "Ost", manage_channels=False)
        self.assertIsNone(run(guild), "pas de salon des cartes : pas de cartes sur ce serveur")
        self.assertEqual(guild.created, [])

    def test_sans_le_droit_de_gerer_les_roles(self):
        guild = FakeGuild(500, "Ost", manage_roles=False)
        server = run(guild)
        self.assertEqual((guild.created, server.role_id), ([("salon", "alertes-pvp")], None), "des cartes, sans mention")


if __name__ == "__main__":
    unittest.main()
