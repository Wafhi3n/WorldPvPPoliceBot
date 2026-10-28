"""Plusieurs serveurs (bot-autonome.md, A1-A2 ; critères 3 et 4) : chaque serveur a ses cartes dans SON
salon des cartes, installé à la première ligne ; un même appelant au même numéro sur deux serveurs fait
deux cartes ; au démarrage, le salon relié est retrouvé à ses messages du jeu et ses lignes ratées sont
rattrapées, sans toucher aux autres salons ni lire ceux que le bot ne peut pas relire."""

import asyncio
import datetime as dt
import unittest
from types import SimpleNamespace

from bot.pvp import PvpRelay
from tests.fakes import HIDDEN, FakeGuild, Source
from tests.test_pvp_relay import BOT, OMW, SOS1, Raw, never

T0 = 100000.0


def ago(seconds):
    return dt.datetime.fromtimestamp(T0 - seconds, tz=dt.timezone.utc)


def relay_for(*guilds):
    log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)
    client = SimpleNamespace(get_channel=lambda _id: None, user=BOT, guilds=list(guilds))
    conf = SimpleNamespace(pvp_channel_id=None, pvp_role_id=None, channel_id=None, install=True,
                           pvp_channel_name="alertes-pvp", pvp_role_name="pvp-police", delete_relayed=True)
    return PvpRelay(client, conf, log, clock=lambda: T0, sleep=never, maps={})


def line(content, guild, created_at=None):
    raw = Raw(content, created_at=created_at)
    raw.guild = guild
    return raw


def alerts_of(guild):
    return next(c for c in guild.text_channels if c.name == "alertes-pvp")


class TwoServers(unittest.TestCase):
    def test_chacun_ses_cartes(self):
        a, b = FakeGuild(500, "Ost"), FakeGuild(600, "Autre")
        relay = relay_for(a, b)

        async def go():
            await relay.handle(line(SOS1, a))
            await relay.handle(line(SOS1, b))            # même appelant, même numéro, autre serveur
            await relay.handle(line(OMW, a))
        asyncio.run(go())
        self.assertEqual((len(alerts_of(a).sent), len(alerts_of(b).sent)), (1, 1), "une carte par serveur")
        self.assertEqual(alerts_of(a).sent[0].call.en_route, ["Gnomette"], "le « j'arrive » de A va à la carte de A")
        self.assertEqual(alerts_of(b).sent[0].call.en_route, [], "jamais à celle de B")
        self.assertEqual((a.created.count(("salon", "alertes-pvp")), b.created.count(("salon", "alertes-pvp"))), (1, 1),
                         "chaque serveur s'installe une fois")

    def test_un_serveur_sans_droit_n_a_pas_de_cartes(self):
        a = FakeGuild(500, "Ost", manage_channels=False)
        relay = relay_for(a)
        raw = line(SOS1, a)
        self.assertTrue(asyncio.run(relay.handle(raw)))
        self.assertFalse(raw.deleted, "pas de carte : la ligne brute reste")


class Discovery(unittest.TestCase):
    def test_le_salon_relie_retrouve_au_demarrage(self):
        missed, typed = line(SOS1, None, ago(600)), Raw("salut", from_game=False, created_at=ago(500))
        relayed = Source("g", [missed, typed])
        general = Source("general", [Raw("on y va ?", from_game=False, created_at=ago(300))])
        hidden = Source("officiers", [line(SOS1.replace("#SOS7", "#SOS9"), None, ago(200))], perms=HIDDEN)
        guild = FakeGuild(500, "Ost", channels=[general, relayed, hidden])
        missed.guild = guild
        relay = relay_for(guild)
        asyncio.run(relay.start())
        alerts = alerts_of(guild)
        self.assertEqual(len(alerts.sent), 1, "la ligne ratée du salon relié a sa carte")
        self.assertTrue(missed.deleted and not typed.deleted, "elle quitte le salon relié ; la discussion reste")
        self.assertEqual(hidden.read, 0, "un salon que le bot ne peut pas relire n'est pas lu")
        self.assertEqual(general.read, 1, "les autres salons sont lus, rien n'y est touché")


if __name__ == "__main__":
    unittest.main()
