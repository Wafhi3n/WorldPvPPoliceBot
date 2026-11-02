"""Le lien d'invitation que le bot journalise, et celui que le guide d'hébergement fait recopier à la main :
même portée, mêmes droits (A3)."""

import unittest
from pathlib import Path

from bot.__main__ import PERMISSIONS, invite_link

ROOT = Path(__file__).resolve().parent.parent


class Invite(unittest.TestCase):
    def test_le_bot_et_ses_commandes(self):
        url = invite_link(123)
        self.assertIn("client_id=123", url)
        self.assertIn("scope=bot+applications.commands&", url, "sans ça, /setup n'apparaît pas sur le serveur")

    def test_droits(self):
        self.assertIn(f"permissions={PERMISSIONS.value}", invite_link(123))
        for name in ("view_channel", "read_message_history", "send_messages", "embed_links", "attach_files",
                     "manage_messages", "manage_channels", "manage_roles"):
            self.assertTrue(getattr(PERMISSIONS, name), name)

    def test_le_guide_recopie_les_memes_droits(self):
        for guide in ("hebergement.md", "hosting.md"):
            text = (ROOT / "docs" / guide).read_text(encoding="utf-8")
            self.assertIn(f"scope=bot+applications.commands&permissions={PERMISSIONS.value}", text, guide)


if __name__ == "__main__":
    unittest.main()
