"""La configuration : `.env` puis l'environnement (un conteneur n'a que l'environnement), mêmes noms que
le module PvP de CraftingOrderBot (bascule), jeton jamais affiché."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot import config as cfg

BASE = {"DISCORD_TOKEN": "x", "DISCORD_CHANNEL_ID": "123"}


class Load(unittest.TestCase):
    def load(self, env):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, env, clear=True):
            return cfg.load(Path(d) / "absent.env")

    def test_par_defaut(self):
        c = self.load({"DISCORD_TOKEN": "x"})
        self.assertEqual((c.channel_id, c.pvp_channel_id, c.pvp_role_id), (None, None, None),
                         "le jeton suffit : salon relié reconnu, salon des cartes et rôle installés (A1, A2)")
        self.assertEqual((c.pvp_channel_name, c.pvp_role_name, c.install), ("alertes-pvp", "pvp-police", True))
        self.assertEqual((c.mode, c.delete_relayed), ("journal", True), "1er lancement : on regarde ; P3 : on efface")
        self.assertEqual(c.state_dir, cfg.ROOT / "state")

    def test_les_noms(self):
        c = self.load({**BASE, "DISCORD_PVP_CHANNEL_NAME": "sos", "DISCORD_PVP_ROLE_NAME": "Police",
                       "BOT_INSTALLER": "non"})
        self.assertEqual((c.channel_id, c.pvp_channel_name, c.pvp_role_name, c.install), (123, "sos", "Police", False))

    def test_les_variables_du_module_pvp(self):
        c = self.load({**BASE, "DISCORD_PVP_CHANNEL_ID": "789", "DISCORD_PVP_ROLE_ID": "555", "BOT_MODE": "repondre",
                       "BOT_SUPPRIMER": "non", "BOT_STATE": "/app/state"})
        self.assertEqual((c.pvp_channel_id, c.pvp_role_id, c.mode, c.delete_relayed, c.state_dir),
                         (789, 555, "repondre", False, Path("/app/state")))

    def test_les_refus(self):
        for env in ({"DISCORD_CHANNEL_ID": "123"}, {**BASE, "DISCORD_PVP_CHANNEL_ID": "#alertes"},
                    {**BASE, "BOT_MODE": "parler"}, {**BASE, "BOT_SUPPRIMER": "peut-être"},
                    {**BASE, "BOT_INSTALLER": "toujours"}):
            with self.subTest(env=env), self.assertRaises(SystemExit):
                self.load(env)

    def test_le_jeton_n_apparait_jamais(self):
        self.assertNotIn("SECRET-JETON", repr(self.load({**BASE, "DISCORD_TOKEN": "SECRET-JETON"})))


if __name__ == "__main__":
    unittest.main()
