"""Le rattrapage au démarrage (user, 2026-10-28) et l'heure de Discord : les lignes d'appel ratées pendant
un arrêt du bot (un redéploiement) sont encore dans le salon relié, puisqu'une ligne traitée en est
effacée ; au démarrage, celles des 30 dernières minutes sont traitées dans l'ordre, chacune à son
heure. Une ligne n'est jamais traitée deux fois (rattrapage puis direct). L'heure d'une ligne est celle
de Discord, pas celle du serveur du bot (qui retardait de 114 s le 2026-10-28)."""

import asyncio
import datetime as dt
import unittest

from bot.pvp_cards import EXPIRY
from tests.test_pvp_relay import OMW, SOS1, Channel, Raw, make

T0 = 100000.0   # l'horloge du serveur dans make()


def ago(seconds):
    return dt.datetime.fromtimestamp(T0 - seconds, tz=dt.timezone.utc)


class Source:
    """Le salon relié : son historique filtré par `after`, du plus ancien au plus récent."""
    def __init__(self, messages):
        self.messages = messages

    def history(self, limit=100, after=None, oldest_first=None):
        async def gen():
            for m in sorted(self.messages, key=lambda m: m.created_at)[:limit]:
                if after is None or m.created_at > after:
                    yield m
        return gen()


class CatchUp(unittest.TestCase):
    def test_les_lignes_ratees_sont_reprises(self):
        sos, chat, omw = (Raw(SOS1, created_at=ago(600)), Raw("SOS quelqu'un ?", created_at=ago(500)),
                          Raw(OMW, created_at=ago(300)))
        old = Raw("SOS Vieux Duskwood #SOS2 m10 d1", created_at=ago(EXPIRY + 60))
        channel = Channel()
        relay, _ = make(channel, source=Source([omw, old, sos, chat]))
        self.assertEqual(asyncio.run(relay.catch_up()), 2)
        self.assertEqual(len(channel.sent), 1, "une seule carte, celle de l'appel raté")
        card = channel.sent[0].card
        self.assertEqual((card.en_route, card.updated_at), (["Gnomette"], T0 - 600),
                         "dans l'ordre, et à l'heure de la ligne (pas du redémarrage)")
        self.assertTrue(sos.deleted and omw.deleted, "les lignes reprises quittent le salon relié")
        self.assertFalse(chat.deleted, "une phrase tapée en jeu reste")
        self.assertFalse(old.deleted, "plus de 30 minutes : pas reprise, pas touchée")

    def test_sans_effacement_rien(self):
        channel = Channel()
        relay, _ = make(channel, delete=False, source=Source([Raw(SOS1, created_at=ago(60))]))
        self.assertEqual(asyncio.run(relay.catch_up()), 0, "sans effacement, une ligne restée peut être traitée")
        self.assertEqual(channel.sent, [])

    def test_jamais_deux_fois(self):
        sos = Raw(SOS1, created_at=ago(30))
        channel = Channel()
        relay, _ = make(channel, source=Source([sos]))

        async def go():
            await relay.catch_up()
            return await relay.handle(sos)          # la même ligne arrive aussi en direct
        self.assertTrue(asyncio.run(go()))
        self.assertEqual((len(channel.sent), channel.sent[0].edits), (1, []), "ni 2e carte ni modification")


class DiscordTime(unittest.TestCase):
    def test_l_heure_de_discord(self):
        channel = Channel()
        relay, clock = make(channel)
        discord_now = dt.datetime.fromtimestamp(T0 + 114, tz=dt.timezone.utc)   # le serveur retarde de 114 s
        asyncio.run(relay.handle(Raw(SOS1, created_at=discord_now)))
        card = channel.sent[0].card
        self.assertEqual(card.updated_at, T0 + 114, "la carte est datée de l'heure de Discord")
        self.assertEqual(relay.offset, 114.0, "l'écart est appris")
        clock["now"] += 60
        self.assertEqual(relay.now(), T0 + 174, "et sert ensuite à compter les 30 minutes")


if __name__ == "__main__":
    unittest.main()
