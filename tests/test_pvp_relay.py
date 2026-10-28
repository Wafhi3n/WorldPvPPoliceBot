"""Le relais des appels PvP (spec alertes-pvp.md, B-T3 ; critères 2, 3, 5, 6) devant un faux salon :
une carte par appel, éditée au fil des lignes ; le rôle mentionné une fois ; éteint sans salon ; la ligne
brute gardée si la carte n'est pas faite ; les cartes retrouvées après un redémarrage ; 30 minutes sans
ligne SOS ; deux lignes qui se croisent ne font jamais deux cartes."""

import asyncio
import unittest
from types import SimpleNamespace

import discord

from bot.pvp import PvpRelay
from bot.pvp_cards import ACTIVE, EXPIRED, EXPIRY, SETTLED, Card, from_embed, to_embed

WOW_APP = 1384671873593512078
BOT = SimpleNamespace(id=1)
PLAYER = SimpleNamespace(id=9, bot=False)
SOS1 = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d1 kXyz cROGUE : 3 voleurs au pont"
SOS3 = "SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d3 kXyz cROGUE : 3 voleurs au pont"
OMW = "OMW Gnomette > Gnomi #SOS7"
END = "END Gnomi #SOS7"


class Raw:
    """Une ligne du salon relié (identifiant unique, heure de Discord facultative)."""
    count = 0

    def __init__(self, content, from_game=True, created_at=None):
        Raw.count += 1
        self.content, self.id, self.deleted, self.author = content, 100 + Raw.count, False, PLAYER
        self.application_id = WOW_APP if from_game else None
        self.created_at = created_at

    async def delete(self):
        self.deleted = True


class Posted:
    """Un message du bot dans #alertes-pvp."""
    def __init__(self, content, embed, mentions, files=()):
        self.author, self.content, self.embeds, self.mentions, self.edits = BOT, content, [embed], mentions, []
        self.files = list(files)

    async def edit(self, embed=None, attachments=None, allowed_mentions=None):
        self.embeds = [embed]
        self.edits.append(allowed_mentions)
        if attachments is not None:
            self.files = list(attachments)

    @property
    def card(self):
        return from_embed(self.embeds[0])


class Channel:
    name = "alertes-pvp"

    def __init__(self, fail=False):
        self.sent, self.older, self.fail = [], [], fail

    async def send(self, content=None, embed=None, files=(), allowed_mentions=None):
        await asyncio.sleep(0)   # rend la main : une autre ligne peut arriver pendant l'envoi
        if self.fail:
            raise discord.DiscordException("refusé")
        message = Posted(content, embed, allowed_mentions, files)
        self.sent.append(message)
        return message

    def history(self, limit=100):
        async def gen():
            for m in (list(reversed(self.sent)) + self.older)[:limit]:
                yield m
        return gen()


async def never(_delay):
    await asyncio.Event().wait()


def make(channel, role=None, delete=True, pvp=True, maps=None, source=None):
    """Le relais devant `channel` (#alertes-pvp, id 77) et `source` (le salon relié, id 66)."""
    log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)
    client = SimpleNamespace(get_channel=lambda cid: source if cid == 66 else channel, user=BOT)
    conf = SimpleNamespace(pvp_channel_id=77 if pvp else None, pvp_role_id=role, delete_relayed=delete,
                           channel_id=66)
    clock = {"now": 100000.0}
    return PvpRelay(client, conf, log, clock=lambda: clock["now"], sleep=never, maps={} if maps is None else maps), clock


def run(relay, *contents):
    async def go():
        raws = [Raw(c) for c in contents]
        for raw in raws:
            await relay.handle(raw)
        return raws
    return asyncio.run(go())


class OneCard(unittest.TestCase):
    def test_un_appel_une_carte(self):
        channel = Channel()
        relay, _ = make(channel)
        raws = run(relay, SOS1, OMW, SOS3, END)
        self.assertEqual(len(channel.sent), 1, "critère 3 : une seule carte")
        card = channel.sent[0]
        self.assertEqual(len(card.edits), 3, "éditée trois fois")
        final = card.card
        self.assertEqual((final.deaths, final.en_route, final.status), (3, ["Gnomette"], SETTLED))
        self.assertTrue(all(r.deleted for r in raws), "les lignes brutes quittent le salon relié (P3)")

    def test_omw_en_double(self):
        channel = Channel()
        relay, _ = make(channel)
        run(relay, SOS1, OMW, OMW)
        self.assertEqual(channel.sent[0].card.en_route, ["Gnomette"])


class Mentions(unittest.TestCase):
    def test_le_role_seul_a_la_publication(self):
        channel = Channel()
        relay, _ = make(channel, role=555)
        run(relay, "SOS Gnomi Duskwood #SOS2 m10 d1 : @everyone <@&123456789012345678>", OMW.replace("7", "2"))
        card = channel.sent[0]
        self.assertEqual(card.content, "<@&555>", "le texte du joueur ne va jamais dans le contenu")
        self.assertFalse(card.mentions.everyone)
        self.assertFalse(card.mentions.users)
        self.assertEqual([r.id for r in card.mentions.roles], [555])
        self.assertTrue(card.edits and all(m.roles is False and m.everyone is False for m in card.edits),
                        "une modification ne mentionne personne")

    def test_sans_role_aucune_mention(self):
        channel = Channel()
        relay, _ = make(channel)
        run(relay, SOS1)
        self.assertIsNone(channel.sent[0].content)
        self.assertIs(channel.sent[0].mentions.roles, False)


class Paths(unittest.TestCase):
    def test_eteint_sans_salon(self):
        channel = Channel()
        relay, _ = make(channel, pvp=False)
        raw = Raw(SOS1)
        self.assertFalse(asyncio.run(relay.handle(raw)), "critère 5 : chemin habituel")
        self.assertFalse(raw.deleted)
        self.assertEqual(channel.sent, [])

    def test_envoi_en_echec_la_ligne_reste(self):
        relay, _ = make(Channel(fail=True))
        raw = Raw(SOS1)
        self.assertTrue(asyncio.run(relay.handle(raw)))
        self.assertFalse(raw.deleted, "critère 6 : la ligne brute est gardée")

    def test_pas_un_appel(self):
        relay, _ = make(Channel())
        for raw in (Raw("SOS quelqu'un ?"), Raw(SOS1, from_game=False)):
            self.assertFalse(asyncio.run(relay.handle(raw)), raw.content)
            self.assertFalse(raw.deleted)

    def test_omw_d_un_appel_inconnu(self):
        channel = Channel()
        relay, _ = make(channel)
        raw = run(relay, OMW)[0]
        self.assertEqual(channel.sent, [])
        self.assertTrue(raw.deleted, "ignoré, ligne brute supprimée quand même")


class Restart(unittest.TestCase):
    def test_carte_retrouvee_sans_nouvelle_mention(self):
        channel = Channel()
        first, _ = make(channel, role=555)
        run(first, SOS1)
        second, _ = make(channel, role=555)        # le bot redémarre : plus rien en mémoire
        run(second, SOS3, OMW)
        self.assertEqual(len(channel.sent), 1, "pas de 2e carte ni de 2e mention")
        final = channel.sent[0].card
        self.assertEqual((final.deaths, final.en_route), (3, ["Gnomette"]))

    def test_reprise_au_demarrage(self):
        channel = Channel()
        old, recent, done = (Posted(None, to_embed(Card("Vieux", 1, updated_at=100000.0 - EXPIRY - 5)), None),
                             Posted(None, to_embed(Card("Neuf", 2, updated_at=100000.0 - 60)), None),
                             Posted(None, to_embed(Card("Fini", 3, status=SETTLED, updated_at=0.0)), None))
        channel.older = [recent, old, done]
        relay, _ = make(channel)
        asyncio.run(relay.start())
        self.assertEqual(old.card.status, EXPIRED, "plus de 30 minutes : au gris")
        self.assertEqual((recent.edits, recent.card.status), ([], ACTIVE))
        self.assertIn((None, "neuf", 2), relay.cards, "une carte récente reprend son compte à rebours")
        self.assertEqual(done.edits, [], "une carte réglée n'est pas touchée")


class Time(unittest.TestCase):
    def test_trente_minutes_sans_ligne(self):
        channel = Channel()
        relay, clock = make(channel)

        async def go():
            await relay.handle(Raw(SOS1))
            clock["now"] += EXPIRY - 1
            await relay.expire_due()
            before = channel.sent[0].card.status
            clock["now"] += 1
            await relay.expire_due()
            return before
        self.assertEqual(asyncio.run(go()), ACTIVE)
        self.assertEqual(channel.sent[0].card.status, EXPIRED, "critère 4")

    def test_meme_numero_apres_trente_minutes(self):
        channel = Channel()
        relay, clock = make(channel)

        async def go():
            await relay.handle(Raw(SOS1))
            clock["now"] += EXPIRY
            await relay.handle(Raw(SOS1))
        asyncio.run(go())
        self.assertEqual(len(channel.sent), 2, "un autre poste repart du même numéro : nouvel appel")
        self.assertEqual(channel.sent[0].card.status, EXPIRED)
        self.assertEqual(channel.sent[1].card.status, ACTIVE)

    def test_deux_lignes_qui_se_croisent(self):
        channel = Channel()
        relay, _ = make(channel)

        async def go():
            await asyncio.gather(relay.handle(Raw(SOS1)), relay.handle(Raw(SOS3)))
        asyncio.run(go())
        self.assertEqual(len(channel.sent), 1, "jamais deux cartes pour un appel")
        self.assertEqual(channel.sent[0].card.deaths, 3)


if __name__ == "__main__":
    unittest.main()
