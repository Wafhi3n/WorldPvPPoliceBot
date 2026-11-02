"""La liste des protecteurs (docs/specs/protecteurs.md) : les porteurs du rôle qui sont connectés, un seul message,
aucune notification, et un bot sans cette liste qui ne demande aucun intent de plus."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord

from bot import labels
from bot.__main__ import make_intents
from bot.config import Config
from bot.protectors import MAX_DESCRIPTION, Protectors, came_or_left

BOT = SimpleNamespace(id=1)
CHANNEL, ROLE = 900, 800
LOG = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)
ONLINE, OFFLINE = discord.Status.online, discord.Status.offline


def not_found():
    return discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "disparu")


def forbidden():
    return discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "refusé")


class Message:
    def __init__(self, author, card, message_id=None):
        self.id, self.author, self.embeds, self.edits, self.deleted = message_id or id(self), author, [card] if card else [], 0, False
        self.allowed_mentions = None

    async def edit(self, embed=None, allowed_mentions=None):
        if self.deleted:
            raise not_found()
        self.embeds, self.edits, self.allowed_mentions = [embed], self.edits + 1, allowed_mentions
        return self


class Channel:
    def __init__(self, channel_id=CHANNEL, name="caserne"):
        self.id, self.name, self.guild, self.messages, self.sent = channel_id, name, None, [], 0
        self.history_denied, self.allowed_mentions, self.history_reads = False, None, 0

    async def send(self, embed=None, allowed_mentions=None):
        message = Message(BOT, embed)
        self.messages.append(message)
        self.sent, self.allowed_mentions = self.sent + 1, allowed_mentions
        return message

    async def fetch_message(self, message_id):
        for message in self.messages:
            if message.id == message_id and not message.deleted:
                return message
        raise not_found()

    def history(self, limit=100):
        async def gen():
            self.history_reads += 1
            if self.history_denied:
                raise forbidden()
            for message in [m for m in reversed(self.messages) if not m.deleted][:limit]:
                yield message
        return gen()


class Guild:
    def __init__(self, guild_id=500, name="Ost", channels=(), roles=(), members=(), chunked=True):
        self.id, self.name, self.text_channels, self.roles = guild_id, name, list(channels), list(roles)
        self.members, self.chunked, self.chunks = list(members), chunked, 0
        for channel in self.text_channels:
            channel.guild = self

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)

    async def chunk(self):
        self.chunked, self.chunks = True, self.chunks + 1


POLICE = SimpleNamespace(id=ROLE, name="pvp-police", guild=None)
OTHER = SimpleNamespace(id=801, name="autre", guild=None)


def protector(member_id, name="Membre", status=ONLINE, bot=False):
    return SimpleNamespace(id=member_id, display_name=name, status=status, bot=bot, roles=[POLICE],
                           mention=f"<@{member_id}>")


class Base(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.channel = Channel()
        self.guild = Guild(channels=[self.channel], roles=[POLICE, OTHER], members=[protector(2, "Zed"), protector(3, "alba")])

    def conf(self, **kwargs):
        values = dict(token="x", protectors_channel_id=CHANNEL, pvp_role_id=ROLE, mode="repondre", state_dir=Path(self.folder.name))
        return Config(**{**values, **kwargs})

    def board(self, *guilds, **kwargs):
        client = SimpleNamespace(user=BOT, guilds=list(guilds) or [self.guild])
        return Protectors(client, self.conf(**kwargs), LOG, delay=0)

    def shown(self):
        return self.channel.messages[0].embeds[0].description


class WhoIsListed(Base):
    def test_seuls_les_connectes_et_par_ordre_alphabetique(self):
        self.guild.members.append(protector(4, "Hors ligne", OFFLINE))
        asyncio.run(self.board().refresh())
        self.assertEqual(self.shown(), "**2** connectés sur 3\n<@3> <@2>")

    def test_absent_et_ne_pas_deranger_comptent_comme_connectes(self):
        self.guild.members = [protector(2, "A", discord.Status.idle), protector(3, "B", discord.Status.dnd)]
        asyncio.run(self.board().refresh())
        self.assertEqual(self.shown(), "**2** connectés sur 2\n<@2> <@3>")

    def test_sans_le_role_et_les_bots_jamais(self):
        sans = protector(5, "Sans")
        sans.roles = [OTHER]
        self.guild.members += [sans, protector(6, "Robot", bot=True)]
        asyncio.run(self.board().refresh())
        self.assertEqual(self.shown(), "**2** connectés sur 2\n<@3> <@2>")

    def test_personne_de_connecte_la_liste_le_dit(self):
        self.guild.members = [protector(2, status=OFFLINE)]
        asyncio.run(self.board().refresh())
        self.assertEqual(self.shown(), "**0** connecté sur 1")

    def test_le_role_par_son_nom_sans_id(self):
        asyncio.run(self.board(pvp_role_id=None).refresh())
        self.assertEqual(self.channel.sent, 1, "avec un id de salon, le rôle reste trouvé par son nom")

    def test_sans_role_rien_n_est_ecrit(self):
        self.guild.roles = [OTHER]
        asyncio.run(self.board(pvp_role_id=123).refresh())
        self.assertEqual(self.channel.sent, 0, "un réglage faux n'efface pas la liste affichée")

    def test_le_cache_incomplet_est_d_abord_charge(self):
        self.guild.chunked = False
        asyncio.run(self.board().refresh())
        self.assertEqual(self.guild.chunks, 1)

    def test_une_liste_trop_longue_tient_dans_la_limite(self):
        self.guild.members = [protector(10 ** 18 + n, f"M{n:04}") for n in range(400)]
        asyncio.run(self.board().refresh())
        self.assertLessEqual(len(self.shown()), MAX_DESCRIPTION)
        self.assertRegex(self.shown(), r" \+\d+$")

    def test_en_anglais(self):
        with labels.using("en"):
            asyncio.run(self.board().refresh())
        self.assertEqual(self.channel.messages[0].embeds[0].title, "Protectors of Ost")
        self.assertTrue(self.shown().startswith("**2** online out of 2\n"))


class OneMessage(Base):
    def test_aucune_notification_a_l_envoi_et_a_la_modification(self):
        async def scenario(b):
            await b.refresh()
            self.guild.members.append(protector(4, "Nouveau"))
            await b.refresh()
        asyncio.run(scenario(self.board()))
        none = discord.AllowedMentions.none()
        for sent in (self.channel.allowed_mentions, self.channel.messages[0].allowed_mentions):
            self.assertEqual((sent.users, sent.roles, sent.everyone), (none.users, none.roles, none.everyone))

    def test_rien_n_a_change_aucune_ecriture(self):
        async def scenario(b):
            await b.refresh()
            await b.refresh()
        asyncio.run(scenario(self.board()))
        self.assertEqual((self.channel.sent, self.channel.messages[0].edits), (1, 0))

    def test_redemarrer_retrouve_le_meme_message_par_son_id_garde(self):
        async def scenario():
            await self.board().refresh()
            self.channel.messages += [Message(SimpleNamespace(id=9), None) for _ in range(5)]   # on parle dans le salon
            self.guild.members.append(protector(4, "Nouveau"))
            await self.board().refresh()
        asyncio.run(scenario())
        self.assertEqual((self.channel.sent, self.channel.messages[0].edits), (1, 1))
        self.assertEqual(self.channel.history_reads, 1, "la 1re fois seulement : ensuite, l'id gardé suffit")

    def test_sans_id_garde_l_historique_retrouve_le_message(self):
        async def scenario():
            await self.board().refresh()
            (Path(self.folder.name) / "protecteurs.json").unlink()     # pas de volume
            await self.board().refresh()
        asyncio.run(scenario())
        self.assertEqual(self.channel.sent, 1)

    def test_un_id_garde_abime_ne_casse_rien(self):
        (Path(self.folder.name) / "protecteurs.json").write_text("{abîmé", encoding="utf-8")
        asyncio.run(self.board().refresh())
        self.assertEqual(self.channel.sent, 1)

    def test_le_message_supprime_est_republie(self):
        async def scenario(b):
            await b.refresh()
            self.channel.messages[0].deleted = True
            self.guild.members.append(protector(4, "Nouveau"))
            await b.refresh()
        asyncio.run(scenario(self.board()))
        self.assertEqual(self.channel.sent, 2)

    def test_une_carte_d_appel_du_bot_n_est_jamais_reprise(self):
        card = Message(BOT, discord.Embed(title="Untel appelle à l'aide !"))
        self.channel.messages.append(card)
        asyncio.run(self.board().refresh())
        self.assertEqual((card.edits, self.channel.sent), (0, 1))

    def test_la_liste_d_un_autre_bot_n_est_jamais_reprise(self):
        other = Message(SimpleNamespace(id=2), discord.Embed(title="Protecteurs de Ost"))
        self.channel.messages.append(other)
        asyncio.run(self.board().refresh())
        self.assertEqual((other.edits, self.channel.sent), (0, 1))

    def test_une_liste_ecrite_dans_l_autre_langue_est_reprise(self):
        async def scenario():
            with labels.using("en"):
                await self.board().refresh()
            await self.board().refresh()
        asyncio.run(scenario())
        self.assertEqual((self.channel.sent, self.channel.messages[0].edits), (1, 1))
        self.assertEqual(self.channel.messages[0].embeds[0].title, "Protecteurs de Ost")

    def test_sans_droit_de_relire_rien_n_est_publie(self):
        self.channel.history_denied = True
        asyncio.run(self.board().refresh())
        self.assertEqual(self.channel.sent, 0, "sinon chaque redémarrage ferait un doublon")

    def test_en_journal_rien_n_est_ecrit_et_aucun_nom_note(self):
        lines = []
        board = self.board(mode="journal")
        board.log = SimpleNamespace(info=lambda *a: lines.append(a), warning=lambda *a: lines.append(a))
        asyncio.run(board.refresh())
        self.assertEqual(self.channel.sent, 0)
        self.assertEqual(lines, [("protecteurs de %s : %d connectés sur %d", "Ost", 2, 2)])


class Where(Base):
    def test_rien_sans_la_variable(self):
        board = self.board(protectors_channel_id=None)
        self.assertFalse(board.enabled)
        self.assertIsNone(board._channel())

    def test_un_id_qui_n_est_pas_un_salon_texte_du_bot(self):
        warnings = []
        board = self.board(protectors_channel_id=123)
        board.log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: warnings.append(a))
        asyncio.run(board.refresh())
        self.assertEqual((self.channel.sent, len(warnings)), (0, 1))

    def test_rien_sur_un_autre_serveur(self):
        async def scenario(b, other):
            b.schedule(other)
            self.assertEqual(b.tasks, set())
        other = Guild(guild_id=600, channels=[Channel(901)], roles=[POLICE])
        asyncio.run(scenario(self.board(self.guild, other), other))


class When(Base):
    def test_dix_changements_une_seule_ecriture(self):
        async def scenario(b):
            await b.refresh()
            self.guild.members.append(protector(4, "Nouveau"))
            for _ in range(10):
                b.schedule(self.guild)
            await asyncio.gather(*b.tasks)
        asyncio.run(scenario(self.board()))
        self.assertEqual((self.channel.sent, self.channel.messages[0].edits), (1, 1))

    def test_demarrage_et_fenetre_ne_publient_pas_deux_messages(self):
        async def scenario(b):
            b.schedule(self.guild)
            await asyncio.gather(b.refresh(), *b.tasks)
        asyncio.run(scenario(self.board()))
        self.assertEqual(self.channel.sent, 1)

    def test_seuls_l_arrivee_et_le_depart_comptent(self):
        def moved(before, after):
            return came_or_left(SimpleNamespace(status=before), SimpleNamespace(status=after))
        idle, dnd = discord.Status.idle, discord.Status.dnd
        self.assertTrue(moved(OFFLINE, ONLINE) and moved(idle, OFFLINE) and moved(OFFLINE, dnd))
        self.assertFalse(moved(ONLINE, idle) or moved(idle, dnd) or moved(ONLINE, ONLINE), "ni un jeu lancé")

    def events(self, board):
        """Les événements branchés par `listen`, sans vrai client."""
        seen = {}
        board.client.event = lambda f: seen.setdefault(f.__name__, f)
        board.client.get_guild = lambda guild_id: self.guild if guild_id == self.guild.id else None
        board.listen()
        return seen

    def test_les_evenements_ouvrent_la_fenetre(self):
        async def fires(b, handler, *args):
            await handler(*args)
            opened = b.pending
            await asyncio.gather(*b.tasks)
            return opened

        def member(status=ONLINE, roles=()):
            return SimpleNamespace(guild=self.guild, status=status, roles=list(roles))

        role = SimpleNamespace(guild=self.guild, name="x")
        cases = [("on_presence_update", (member(OFFLINE), member()), True),
                 ("on_presence_update", (member(ONLINE), member(discord.Status.idle)), False),
                 ("on_member_update", (member(roles=[OTHER]), member(roles=[POLICE])), True),
                 ("on_member_update", (member(roles=[POLICE]), member(roles=[POLICE])), False),
                 ("on_member_join", (member(),), True),
                 ("on_raw_member_remove", (SimpleNamespace(guild_id=self.guild.id),), True),
                 ("on_raw_member_remove", (SimpleNamespace(guild_id=999),), False),
                 ("on_guild_role_create", (role,), True),
                 ("on_guild_role_delete", (role,), True),
                 ("on_guild_role_update", (role, SimpleNamespace(guild=self.guild, name="y")), True),
                 ("on_guild_role_update", (role, role), False)]
        for name, args, expected in cases:
            board = self.board()
            with self.subTest(name, expected=expected):
                self.assertEqual(asyncio.run(fires(board, self.events(board)[name], *args)), expected)


class Intents(unittest.TestCase):
    def test_sans_la_liste_aucun_intent_de_plus(self):
        intents = make_intents()
        self.assertTrue(intents.message_content)
        self.assertFalse(intents.members or intents.presences, "sinon une guilde qui met à jour ne démarre plus")

    def test_avec_la_liste_les_membres_et_la_presence(self):
        intents = make_intents(protectors=True)
        self.assertTrue(intents.members and intents.presences and intents.message_content)


if __name__ == "__main__":
    unittest.main()
