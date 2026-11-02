"""Le guide du bot (docs/specs/guide.md) : éteint par défaut, publié à chaque démarrage sans doublon, et il ne cite que des réglages qui
existent."""

import asyncio
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord
from discord import app_commands

from bot.config import Config
from bot.guide import CHANNEL, MAX_MESSAGE, Guide, load, split
from bot.labels import LANGS
from bot.settings import Settings
from bot.setup_commands import SetupGroup

BOT, OTHER, CATEGORY = SimpleNamespace(id=1), SimpleNamespace(id=2), 700
ALL = SimpleNamespace(view_channel=True, manage_channels=True, send_messages=True, read_message_history=True)
CONFIG = Path(__file__).resolve().parent.parent / "bot" / "config.py"


class Message:
    def __init__(self, author, content):
        self.author, self.content, self.edits, self.deleted = author, content, 0, False

    async def edit(self, content=None, allowed_mentions=None):
        self.content, self.edits = content, self.edits + 1

    async def delete(self):
        self.deleted = True


class Channel:
    def __init__(self, name):
        self.name, self.messages, self.sent, self.allowed_mentions, self.denied = name, [], 0, None, False

    def history(self, limit=100, oldest_first=None):
        async def gen():
            if self.denied:
                raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "refusé")
            for message in [m for m in self.messages if not m.deleted][:limit]:
                yield message
        return gen()

    async def send(self, content, allowed_mentions=None):
        self.messages.append(Message(BOT, content))
        self.sent, self.allowed_mentions = self.sent + 1, allowed_mentions


class Category:
    def __init__(self, guild):
        self.id, self.name, self.guild, self.text_channels, self.rights = CATEGORY, "Guides des bots", guild, [], ALL

    def permissions_for(self, _member):
        return self.rights


class Guild:
    def __init__(self):
        self.id, self.name = 500, "Ost"
        self.me, self.created, self.categories = SimpleNamespace(id=1), [], []

    async def create_text_channel(self, name, category=None, reason=None):
        channel = Channel(name)
        category.text_channels.append(channel)
        self.created.append(name)
        return channel


class Base(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        (self.folder / "fr.md").write_text("Texte.", encoding="utf-8")
        (self.folder / "en.md").write_text("Text.", encoding="utf-8")
        self.guild = Guild()
        self.category = Category(self.guild)
        self.guild.categories = [self.category]
        self.warnings = []
        self.log = SimpleNamespace(warning=lambda *a: self.warnings.append(a))

    def guide(self, category_id=CATEGORY, mode="repondre", language="fr"):
        conf = Config(token="x", guide_category_id=category_id, mode=mode, language=language)
        return Guide(SimpleNamespace(user=BOT, guilds=[self.guild]), conf, self.log, self.folder)

    def publish(self, **kwargs):
        asyncio.run(self.guide(**kwargs).publish())

    @property
    def channel(self):
        return self.category.text_channels[0]


class Publish(Base):
    def test_eteint_sans_la_variable(self):
        self.publish(category_id=None)
        self.assertEqual((self.guild.created, self.warnings), ([], []))

    def test_rien_en_journal(self):
        self.publish(mode="journal")
        self.assertEqual(self.guild.created, [])

    def test_son_salon_et_son_texte(self):
        self.publish()
        self.assertEqual(self.guild.created, [CHANNEL])
        self.assertEqual(self.channel.messages[0].content, "Texte.")
        self.assertEqual(self.channel.allowed_mentions.users, discord.AllowedMentions.none().users)

    def test_dans_la_langue_du_bot(self):
        self.publish(language="en")
        self.assertEqual(self.channel.messages[0].content, "Text.")

    def test_un_redemarrage_ne_double_rien(self):
        self.publish()
        self.publish()
        self.assertEqual((self.guild.created, self.channel.sent, self.channel.messages[0].edits), ([CHANNEL], 1, 0))

    def test_un_texte_change_modifie_le_message(self):
        self.publish()
        (self.folder / "fr.md").write_text("Nouveau.", encoding="utf-8")
        self.publish()
        self.assertEqual((self.channel.sent, self.channel.messages[0].content), (1, "Nouveau."))

    def test_un_guide_raccourci_retire_ses_messages_en_trop(self):
        self.publish()
        extra = Message(BOT, "En trop.")
        self.channel.messages.append(extra)
        self.publish()
        self.assertTrue(extra.deleted)

    def test_le_message_d_un_autre_n_est_jamais_touche(self):
        self.publish()
        note = Message(OTHER, "Une note.")
        self.channel.messages.append(note)
        self.publish()
        self.assertEqual((note.edits, note.deleted), (0, False))

    def test_une_categorie_introuvable_est_dite(self):
        self.publish(category_id=123)
        self.assertEqual((self.guild.created, len(self.warnings)), ([], 1))

    def test_chaque_droit_manquant_est_dit_sans_rien_tenter(self):
        for right in ("view_channel", "manage_channels", "send_messages", "read_message_history"):
            self.warnings.clear()
            self.category.rights = SimpleNamespace(**{**vars(ALL), right: False})
            with self.subTest(right):
                self.publish()
                self.assertEqual((self.guild.created, len(self.warnings)), ([], 1))

    def test_un_refus_de_discord_n_arrete_pas_le_bot(self):
        self.publish()
        self.channel.denied = True
        self.publish()
        self.assertIn("guide pas mis à jour", self.warnings[0][0])


class Split(unittest.TestCase):
    def test_coupe_entre_deux_paragraphes(self):
        self.assertEqual(split("a" * 8 + "\n\n" + "b" * 8, limit=10), ["a" * 8, "b" * 8])

    def test_une_ligne_trop_longue_se_coupe_sans_rien_perdre(self):
        chunks = split("a" * 25, limit=10)
        self.assertEqual("".join(chunks), "a" * 25)
        self.assertLessEqual(max(map(len, chunks)), 10)


class RealGuide(unittest.TestCase):
    """Le garde-fou : les vrais textes, tels qu'ils partent dans l'image."""

    def test_une_version_par_langue_et_chaque_message_tient(self):
        for language in LANGS:
            with self.subTest(language):
                self.assertLessEqual(max(map(len, load(language))), MAX_MESSAGE)

    def test_le_guide_ne_cite_que_des_reglages_qui_existent(self):
        known = set(re.findall(r"(?:BOT|DISCORD)_[A-Z_]+", CONFIG.read_text(encoding="utf-8")))
        for language in LANGS:
            for name in re.findall(r"(?:BOT|DISCORD)_[A-Z_]+", "\n".join(load(language))):
                self.assertIn(name, known, f"{name} : à corriger dans bot/guide/{language}.md")

    def test_chaque_commande_est_dans_le_guide_et_le_guide_ne_cite_qu_elles(self):
        client = discord.Client(intents=discord.Intents.none())
        tree = app_commands.CommandTree(client)
        tree.add_command(SetupGroup(Settings(Config(token="x")), None, None, None, SimpleNamespace()))
        names = {command.name for command in tree.get_commands()[0].commands}
        for language in LANGS:
            found = set(re.findall(r"/setup ([a-z-]+)", "\n".join(load(language))))
            self.assertEqual(found, names, f"à corriger dans bot/guide/{language}.md")

    def test_les_deux_langues_citent_les_memes_reglages(self):
        names = [set(re.findall(r"(?:BOT|DISCORD)_[A-Z_]+", "\n".join(load(language)))) for language in LANGS]
        self.assertEqual(names[0], names[1], "un réglage ajouté à une seule langue")


if __name__ == "__main__":
    unittest.main()
