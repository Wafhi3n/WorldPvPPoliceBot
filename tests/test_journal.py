"""Ce que le journal garde d'un message du jeu : en chat fusionné, tout le chat de guilde arrive dans le salon
relié (critère 6 de appel-sans-pont-discord.md, côté addon). En `repondre`, il n'en reste aucune trace."""

import logging
import unittest
from types import SimpleNamespace

from bot.__main__ import note

SOS = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS1 m1429 d1 kXyz cROGUE : au pont"
CHAT = "on fait quoi ce soir ?"


def message(content: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, content=content, channel=SimpleNamespace(name="g"), application_id=2,
                           author=SimpleNamespace(bot=False), flags=SimpleNamespace(value=65536))


class Journal(unittest.TestCase):
    def noted(self, mode: str, content: str) -> str:
        log = logging.getLogger("test-journal")
        with self.assertLogs(log, "INFO") as seen:
            log.info("repère")   # assertLogs échoue sans aucune ligne : celle-ci n'y compte pas
            note(log, mode, message(content))
        return "\n".join(seen.output[1:])

    def test_repondre_note_une_ligne_d_appel(self):
        self.assertIn(SOS, self.noted("repondre", SOS))
        self.assertIn("OMW Krosh > Gnomi #SOS1", self.noted("repondre", "OMW Krosh > Gnomi #SOS1"))
        self.assertIn("END Gnomi #SOS1", self.noted("repondre", "END Gnomi #SOS1"))

    def test_repondre_ne_garde_rien_du_chat_de_guilde(self):
        self.assertEqual(self.noted("repondre", CHAT), "")
        self.assertEqual(self.noted("repondre", "SOS pas une vraie ligne"), "")

    def test_journal_note_tout(self):
        self.assertIn(CHAT, self.noted("journal", CHAT))
        self.assertIn(SOS, self.noted("journal", SOS))
