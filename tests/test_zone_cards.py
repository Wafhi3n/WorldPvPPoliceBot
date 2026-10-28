"""Une carte par zone et le salon qui se vide (spec alertes-pvp.md, P10 à P13 ; critères 11 à 14 ; demandes
du user le 2026-10-28 : « si deux joueurs sont morts sur la même map, utiliser la même card », « ne pas
mettre deux fois la même carte dans le canal », « un système pour nettoyer le canal »)."""

import asyncio
import datetime as dt
import unittest
from types import SimpleNamespace

from bot.pvp_cards import ACTIVE, EXPIRED, EXPIRY, SETTLED, Call, Card
from bot.pvp_embed import to_embed
from tests.test_pvp_relay import BOT, Channel, Posted, Raw, make

GNOMI = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d1 kXyz cROGUE : 3 voleurs au pont"
BOB = "SOS Bob Forêt d'Elwynn (50.0, 40.0) #SOS2 m1429 d1 kXyz cROGUE : ils sont 4"
ELSEWHERE = "SOS Zed Durotar (10.0, 20.0) #SOS4 m1411 d1"
T0 = 1_793_000_000.0   # une heure réaliste : sous Windows, datetime.fromtimestamp refuse une heure négative


def run(relay, *contents):
    async def go():
        for content in contents:
            await relay.handle(Raw(content))
    asyncio.run(go())


def ago(hours):
    return dt.datetime.fromtimestamp(T0 - hours * 3600, tz=dt.timezone.utc)


class OneCardPerZone(unittest.TestCase):
    def test_deux_appelants_de_la_meme_zone(self):
        channel = Channel()
        relay, _ = make(channel, role=555)
        run(relay, GNOMI, BOB, ELSEWHERE)
        self.assertEqual(len(channel.sent), 2, "Elwynn : une carte pour deux ; Durotar : la sienne")
        elwynn = channel.sent[0]
        self.assertEqual([(c.caller, c.msg) for c in elwynn.card.calls], [("Gnomi", "3 voleurs au pont"),
                                                                           ("Bob", "ils sont 4")])
        self.assertEqual(elwynn.embeds[0].title, "2 guildiens appellent à l'aide")
        self.assertEqual(elwynn.content, "<@&555>", "la mention, à la publication")
        self.assertTrue(elwynn.edits and all(m.roles is False for m in elwynn.edits),
                        "le 2e appelant met la carte à jour sans nouvelle mention (P11)")
        self.assertEqual(channel.sent[1].content, "<@&555>", "une autre zone : une autre carte, sa mention")

    def test_chacun_ses_lignes(self):
        channel = Channel()
        relay, _ = make(channel)
        run(relay, GNOMI, BOB, "OMW Gnomette > Bob #SOS2", "SOS Bob Forêt d'Elwynn (50.0, 40.0) #SOS2 m1429 d3")
        gnomi, bob = channel.sent[0].card.calls
        self.assertEqual((gnomi.en_route, gnomi.deaths), ([], 1), "le « j'arrive » et les morts de Bob ne vont qu'à Bob")
        self.assertEqual((bob.en_route, bob.deaths), (["Gnomette"], 3))

    def test_reglee_quand_tous_le_sont(self):
        channel = Channel()
        relay, _ = make(channel)
        run(relay, GNOMI, BOB, "END Gnomi #SOS7")
        card = channel.sent[0].card
        self.assertEqual(([c.status for c in card.calls], card.status), ([SETTLED, ACTIVE], ACTIVE))
        run(relay, "END Bob #SOS2")
        self.assertEqual(channel.sent[0].card.status, SETTLED, "tous réglés : verte")

    def test_une_zone_reglee_repart_sur_une_nouvelle_carte(self):
        channel = Channel()
        relay, _ = make(channel)
        run(relay, GNOMI, "END Gnomi #SOS7", BOB)
        self.assertEqual(len(channel.sent), 2, "une carte verte n'est plus « en cours » : Bob ouvre la sienne")

    def test_trente_minutes(self):
        channel = Channel()
        relay, clock = make(channel)

        async def go():
            await relay.handle(Raw(GNOMI))
            clock["now"] += EXPIRY - 60
            await relay.handle(Raw(BOB))
            clock["now"] += 60
            await relay.expire_due()
            first = [c.status for c in channel.sent[0].card.calls]
            clock["now"] += EXPIRY
            await relay.expire_due()
            return first
        self.assertEqual(asyncio.run(go()), [EXPIRED, ACTIVE], "Gnomi sans nouvelles, Bob encore en cours")
        self.assertEqual(channel.sent[0].card.status, EXPIRED, "le dernier en cours expire : grise")

    def test_jamais_deux_cartes_pour_une_zone_en_cours(self):
        channel = Channel()
        relay, _ = make(channel)

        async def go():
            await asyncio.gather(relay.handle(Raw(GNOMI)), relay.handle(Raw(BOB)))
        asyncio.run(go())
        self.assertEqual((len(channel.sent), len(channel.sent[0].card.calls)), (1, 2))


class Restart(unittest.TestCase):
    def test_la_carte_de_zone_retrouvee(self):
        channel = Channel()
        first, _ = make(channel, role=555)
        run(first, GNOMI, BOB)
        second, _ = make(channel, role=555)          # le bot redémarre
        run(second, "SOS Zed Forêt d'Elwynn (30.0, 30.0) #SOS9 m1429 d1", "OMW Gnomette > Bob #SOS2")
        self.assertEqual(len(channel.sent), 1, "un 3e appelant de la zone rejoint la carte relue (P12)")
        card = channel.sent[0].card
        self.assertEqual([c.caller for c in card.calls], ["Gnomi", "Bob", "Zed"])
        self.assertEqual(card.calls[1].en_route, ["Gnomette"], "le « j'arrive » trouve Bob sur la carte relue")


def finished(hours_ago, status=SETTLED, author=BOT, map_id=1429):
    card = Card(map_id, "Elwynn", [Call("Gnomi", 1, map=map_id, status=status, updated_at=T0 - hours_ago * 3600)])
    message = Posted(None, to_embed(card), None, created_at=ago(hours_ago + 1), author=author)
    message.edited_at = ago(hours_ago)
    return message


class Clean(unittest.TestCase):
    def test_les_cartes_finies_depuis_24_heures(self):
        old, recent, grey = finished(25), finished(2), finished(30, status=EXPIRED)
        live = finished(0.1, status=ACTIVE)
        stale = finished(30, status=ACTIVE, map_id=1411)        # « en cours » dans le salon, mais vieille de 30 h
        stranger = finished(48, author=SimpleNamespace(id=42))
        channel = Channel()
        channel.older = [old, recent, grey, live, stale, stranger]
        relay, clock = make(channel)
        clock["now"] = T0
        relay.conf.keep_hours = 24
        asyncio.run(relay.start())
        self.assertEqual([m.deleted for m in (old, recent, grey, live, stranger)], [True, False, True, False, False],
                         "finie depuis 24 h : effacée ; récente, en cours ou d'un autre : jamais")
        self.assertEqual((stale.card.status, stale.deleted), (EXPIRED, False),
                         "une carte restée « en cours » passe au gris au démarrage, et attend ses 24 h")

    def test_jamais_une_carte_en_cours(self):
        # Le garde lui-même, sans la relecture du démarrage (qui passe d'abord au gris une carte périmée).
        live = finished(30, status=ACTIVE)
        channel = Channel()
        channel.older = [live]
        relay, clock = make(channel)
        clock["now"] = T0
        relay.conf.keep_hours = 24
        relay.servers[None] = SimpleNamespace(guild_id=None, alerts=channel, role_id=None)
        self.assertEqual((asyncio.run(relay.clean()), live.deleted), (0, False))

    def test_jamais_avec_zero(self):
        old = finished(100)
        channel = Channel()
        channel.older = [old]
        relay, clock = make(channel)
        clock["now"] = T0
        relay.conf.keep_hours = 0
        asyncio.run(relay.start())
        self.assertFalse(old.deleted, "BOT_GARDER_HEURES=0 : le salon garde tout")


if __name__ == "__main__":
    unittest.main()
