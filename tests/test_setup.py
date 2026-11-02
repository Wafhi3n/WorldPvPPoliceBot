"""Les réglages par `/setup` (docs/specs/reglages.md) : la commande l'emporte sur la variable, chaque serveur lit les siens, seul un
administrateur les change, et une variable déjà posée sur un seul serveur marche comme avant : ce sont les cartes d'appel."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import discord
from discord import app_commands

from bot import labels
from bot.config import Config
from bot.guide import Guide
from bot.install import Server
from bot.protectors import Protectors
from bot.pvp import PvpRelay
from bot.settings import Settings
from bot.setup_commands import SetupGroup
from tests.fakes import FakeGuild, FakeRole
from tests.test_pvp_relay import BOT, SOS1, Channel, Raw, never

GUILD, OTHER = 500, 600
T0 = 100000.0
ALL = SimpleNamespace(view_channel=True, manage_channels=True, send_messages=True, embed_links=True, attach_files=True,
                      read_message_history=True)


def conf(**kwargs):
    values = dict(token="x", mode="repondre", pvp_channel_name="alertes-pvp", pvp_role_name="pvp-police", install=True,
                  delete_relayed=True)
    return Config(**{**values, **kwargs})


def channel(channel_id, guild=None, name="cartes"):
    found = Channel()
    found.id, found.name, found.mention = channel_id, name, f"<#{channel_id}>"
    found.permissions_for = lambda _member: ALL
    if guild is not None:
        found.guild = guild
        guild.text_channels.append(found)
    return found


def relay_of(config, settings, guilds, channels=()):
    log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)
    by_id = {c.id: c for c in channels}
    client = SimpleNamespace(get_channel=by_id.get, user=BOT, guilds=list(guilds))
    return PvpRelay(client, config, log, clock=lambda: T0, sleep=never, maps={}, settings=settings)


def line(guild, content=SOS1):
    raw = Raw(content)
    raw.guild = guild
    return raw


def role(role_id, name="police", mentionable=True, managed=False, default=False):
    made = SimpleNamespace(id=role_id, name=name, mention=f"<@&{role_id}>", mentionable=mentionable, managed=managed)
    made.is_default = lambda: default
    return made


class Base(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.path = self.folder / "reglages.json"
        self.warnings = []
        self.log = SimpleNamespace(info=lambda *a: None, warning=lambda *a: self.warnings.append(a))


class Store(Base):
    def test_la_variable_quand_rien_n_est_pose(self):
        settings = Settings(conf(pvp_role_id=7), self.path, self.log)
        self.assertEqual((settings.get(GUILD, "pvp_role"), settings.origin(GUILD, "pvp_role")), (7, "variable"))
        self.assertIsNone(settings.origin(GUILD, "pvp_channel"))

    def test_la_commande_l_emporte_sur_ce_serveur_seulement(self):
        settings = Settings(conf(pvp_role_id=7), self.path, self.log)
        settings.put(GUILD, "pvp_role", 8)
        self.assertEqual((settings.get(GUILD, "pvp_role"), settings.origin(GUILD, "pvp_role")), (8, "command"))
        self.assertEqual(settings.get(OTHER, "pvp_role"), 7)

    def test_effacer_revient_a_la_variable(self):
        settings = Settings(conf(pvp_role_id=7), self.path, self.log)
        settings.put(GUILD, "pvp_role", 8)
        self.assertTrue(settings.clear(GUILD, "pvp_role"))
        self.assertEqual(settings.get(GUILD, "pvp_role"), 7)
        self.assertFalse(settings.clear(GUILD, "pvp_role"), "plus rien à oublier")

    def test_un_reglage_survit_au_redemarrage(self):
        Settings(conf(), self.path, self.log).put(GUILD, "pvp_channel", 9)
        self.assertEqual(Settings(conf(), self.path, self.log).get(GUILD, "pvp_channel"), 9)

    def test_une_ecriture_ratee_ne_change_rien(self):
        settings = Settings(conf(), self.path, self.log)
        with mock.patch("bot.settings.os.replace", side_effect=OSError("disque")), self.assertRaises(OSError):
            settings.put(GUILD, "pvp_role", 8)
        self.assertIsNone(settings.get(GUILD, "pvp_role"))

    def test_un_fichier_illisible_est_mis_de_cote_et_dit(self):
        for content in ("{abîmé", json.dumps({"version": 99, "servers": {}}),
                        json.dumps({"version": 1, "servers": {"1": {"pvp_role": "oups"}}}),
                        json.dumps({"version": 1, "servers": {"1": {"protectors_channel": 5}}})):
            self.warnings.clear()
            self.path.write_text(content, encoding="utf-8")
            with self.subTest(content):
                self.assertEqual(Settings(conf(), self.path, self.log).count(), 0)
                self.assertEqual(len(self.warnings), 1)


class VariableAsToday(Base):
    """Le service d'aujourd'hui : DISCORD_PVP_CHANNEL_ID et un serveur. Rien ne doit changer pour les cartes."""

    def setUp(self):
        super().setUp()
        self.guild = FakeGuild(GUILD, "Ost", roles=[FakeRole(55, "police", 1, True)])
        self.alerts = channel(900, self.guild)
        self.config = conf(pvp_channel_id=900, pvp_role_id=55)
        self.relay = relay_of(self.config, Settings(self.config), [self.guild], [self.alerts])

    def test_la_carte_va_dans_le_salon_de_la_variable_avec_son_role(self):
        asyncio.run(self.relay.handle(line(self.guild)))
        self.assertEqual(len(self.alerts.sent), 1)
        self.assertEqual(self.alerts.sent[0].content, "<@&55>")
        self.assertEqual(self.guild.created, [], "rien n'est créé")

    def test_au_demarrage_rien_n_est_cree_et_les_autres_salons_ne_sont_pas_relus(self):
        other = channel(901, self.guild, "general")
        other.read = 0
        real = other.history

        def counted(*a, **k):
            other.read += 1
            return real(*a, **k)
        other.history = counted
        asyncio.run(self.relay.start())
        self.assertEqual((self.guild.created, other.read), ([], 0), "sans DISCORD_CHANNEL_ID, pas de rattrapage : comme avant")

    def test_un_message_sans_serveur_connu_garde_le_salon_de_la_variable(self):
        asyncio.run(self.relay.handle(Raw(SOS1)))
        self.assertEqual(len(self.alerts.sent), 1)

    def test_sans_role_regle_il_est_trouve_par_son_nom(self):
        self.guild.roles.append(FakeRole(66, "pvp-police", 1, True))
        config = conf(pvp_channel_id=900)
        relay = relay_of(config, Settings(config), [self.guild], [self.alerts])
        asyncio.run(relay.handle(line(self.guild)))
        self.assertEqual(self.alerts.sent[0].content, "<@&66>", "la variable du salon seule ne faisait plus sonner personne")


class TwoServers(Base):
    def test_un_autre_serveur_a_son_salon_et_non_celui_de_la_variable(self):
        here, there = FakeGuild(GUILD, "Ost"), FakeGuild(OTHER, "Autre")
        alerts = channel(900, here)
        config = conf(pvp_channel_id=900)
        relay = relay_of(config, Settings(config), [here, there], [alerts])
        asyncio.run(relay.handle(line(there)))
        self.assertEqual(alerts.sent, [], "le salon de la variable n'est pas à ce serveur")
        self.assertIn(("salon", "alertes-pvp"), there.created)

    def test_le_role_de_la_variable_ne_deborde_pas_sur_un_autre_serveur(self):
        here, there = FakeGuild(GUILD, "Ost", roles=[FakeRole(55, "police", 1, True)]), FakeGuild(OTHER, "Autre")
        theirs = FakeRole(66, "pvp-police", 1, True)
        there.roles.append(theirs)
        alerts = channel(900, here)
        config = conf(pvp_channel_id=900, pvp_role_id=55)
        relay = relay_of(config, Settings(config), [here, there], [alerts])
        asyncio.run(relay.handle(line(there)))
        created = next(c for c in there.text_channels if c.name == "alertes-pvp")
        self.assertEqual(created.sent[0].content, "<@&66>", "le rôle de l'autre serveur ferait une mention morte")

    def test_le_role_de_la_variable_absent_d_ici_le_nom_est_cree_a_l_installation(self):
        here, there = FakeGuild(GUILD, "Ost", roles=[FakeRole(55, "police", 1, True)]), FakeGuild(OTHER, "Autre")
        alerts = channel(900, here)
        config = conf(pvp_channel_id=900, pvp_role_id=55)
        asyncio.run(relay_of(config, Settings(config), [here, there], [alerts]).handle(line(there)))
        self.assertIn(("rôle", "pvp-police"), there.created)

    def test_au_demarrage_un_serveur_sans_reglage_ne_s_installe_pas_a_cote_de_la_variable(self):
        here, there = FakeGuild(GUILD, "Ost"), FakeGuild(OTHER, "Autre")
        alerts = channel(900, here)
        config = conf(pvp_channel_id=900)
        asyncio.run(relay_of(config, Settings(config), [here, there], [alerts]).start())
        self.assertEqual(there.created, [])

    def test_chaque_serveur_lit_son_reglage(self):
        one, two = FakeGuild(GUILD, "Ost"), FakeGuild(OTHER, "Autre")
        first, second = channel(901, one), channel(902, two)
        config = conf()
        settings = Settings(config, self.path, self.log)
        settings.put(GUILD, "pvp_channel", 901)
        settings.put(GUILD, "pvp_role", 71)
        settings.put(OTHER, "pvp_channel", 902)
        settings.put(OTHER, "pvp_role", 72)
        relay = relay_of(config, settings, [one, two])

        async def go():
            await relay.handle(line(one))
            await relay.handle(line(two))
        asyncio.run(go())
        self.assertEqual((first.sent[0].content, second.sent[0].content), ("<@&71>", "<@&72>"))
        self.assertEqual((one.created, two.created), ([], []), "rien n'est créé")


class Moved(Base):
    def setUp(self):
        super().setUp()
        self.guild = FakeGuild(GUILD, "Ost")
        self.first, self.second = channel(901, self.guild, "ancien"), channel(902, self.guild, "nouveau")
        self.config = conf()
        self.settings = Settings(self.config, self.path, self.log)

    def test_la_commande_l_emporte_sur_la_variable(self):
        config = conf(pvp_channel_id=901)
        settings = Settings(config, self.path, self.log)
        settings.put(GUILD, "pvp_channel", 902)
        asyncio.run(relay_of(config, settings, [self.guild], [self.first]).handle(line(self.guild)))
        self.assertEqual((len(self.first.sent), len(self.second.sent)), (0, 1))

    def test_changer_de_salon_vaut_sans_redemarrer(self):
        self.settings.put(GUILD, "pvp_channel", 901)
        relay = relay_of(self.config, self.settings, [self.guild])

        async def go():
            await relay.handle(line(self.guild))
            self.settings.put(GUILD, "pvp_channel", 902)
            await relay.moved(self.guild)
            await relay.handle(line(self.guild, SOS1.replace("#SOS7", "#SOS8").replace("Gnomette", "Autre")))
            relay.cleaning.cancel()
        asyncio.run(go())
        self.assertEqual(relay.servers[GUILD].alerts, self.second)

    def test_un_salon_pose_puis_supprime_ne_cree_rien_et_garde_la_ligne(self):
        self.settings.put(GUILD, "pvp_channel", 999)
        relay = relay_of(self.config, self.settings, [self.guild])
        raw = line(self.guild)
        asyncio.run(relay.handle(raw))
        self.assertEqual(self.guild.created, [])
        self.assertFalse(raw.deleted, "pas de carte : la ligne brute reste")

    def test_un_bot_sans_rien_d_autre_marche_des_la_commande(self):
        config = conf(install=False)
        settings = Settings(config, self.path, self.log)
        relay = relay_of(config, settings, [self.guild])
        self.assertFalse(relay.enabled)
        settings.put(GUILD, "pvp_channel", 901)
        self.assertTrue(relay.enabled)
        self.assertTrue(asyncio.run(relay.handle(line(self.guild))))
        self.assertEqual(len(self.first.sent), 1)

    def test_avec_install_non_un_serveur_sans_reglage_n_installe_rien(self):
        config = conf(install=False)
        settings = Settings(config, self.path, self.log)
        settings.put(OTHER, "pvp_channel", 1)
        asyncio.run(relay_of(config, settings, [self.guild]).handle(line(self.guild)))
        self.assertEqual(self.guild.created, [])

    def test_le_nettoyage_ne_part_qu_une_fois(self):
        relay = relay_of(self.config, self.settings, [self.guild])

        async def go():
            await relay.moved(self.guild)
            first = relay.cleaning
            await relay.moved(self.guild)
            self.assertIs(relay.cleaning, first)
            first.cancel()
        asyncio.run(go())


class ProtectorsRole(Base):
    def test_la_liste_lit_le_role_pose_pour_son_serveur(self):
        police, posted = role(1, "pvp-police"), role(2, "autre")
        guild = SimpleNamespace(id=GUILD, roles=[police, posted], get_role={1: police, 2: posted}.get)
        config = conf()
        settings = Settings(config, self.path, self.log)
        board = Protectors(SimpleNamespace(guilds=[]), config, self.log, delay=0, settings=settings)
        self.assertIs(board._role(guild), police, "par son nom")
        settings.put(GUILD, "pvp_role", 2)
        self.assertIs(board._role(guild), posted, "le même rôle que les cartes")


class FakeInteraction:
    def __init__(self, guild, user):
        self.guild, self.user, self.deferred, self.sent = guild, user, False, []
        self.response = SimpleNamespace(defer=self._defer)
        self.followup = SimpleNamespace(send=self._send)

    async def _defer(self, ephemeral=False):
        self.deferred = ephemeral

    async def _send(self, answer, ephemeral=False, allowed_mentions=None):
        self.sent.append(SimpleNamespace(text=answer, ephemeral=ephemeral, allowed_mentions=allowed_mentions))

    @property
    def reply(self):
        return self.sent[-1].text


class Group(Base):
    def setUp(self):
        super().setUp()
        self.config = conf()
        self.settings = Settings(self.config, self.path, self.log)
        self.moves, self.published, self.outcome = [], [], None
        self.alerts = channel(900)
        self.category = SimpleNamespace(id=700, name="Guides", permissions_for=lambda _m: ALL)
        self.role = role(800)
        self.guild = SimpleNamespace(id=GUILD, name="Ost", owner_id=1, me=SimpleNamespace(id=99), text_channels=[self.alerts],
                                     get_role={800: self.role}.get)
        relay = SimpleNamespace(moved=self.moved)
        guide = SimpleNamespace(active=True, publish_in=self.publish_in, category=self.find_category)
        self.group = SetupGroup(self.settings, relay, guide, lambda: "LIEN", self.log)
        self.admin = SimpleNamespace(id=9, guild_permissions=SimpleNamespace(administrator=True))
        self.plain = SimpleNamespace(id=2, guild_permissions=SimpleNamespace(administrator=False))

    async def moved(self, guild):
        self.moves.append(guild.id)

    async def publish_in(self, guild):
        self.published.append(guild.id)
        return self.outcome

    def find_category(self, guild):
        return self.category if self.settings.get(guild.id, "guide_category") == 700 else None

    def call(self, command, *args, user=None):
        interaction = FakeInteraction(self.guild, user or self.admin)
        asyncio.run(command.callback(self.group, interaction, *args))
        return interaction

    def test_un_non_admin_est_refuse_a_chaque_commande(self):
        cases = ((self.group.alerts, self.alerts), (self.group.role, self.role), (self.group.guide_category, self.category),
                 (self.group.forget, app_commands.Choice(name="x", value="pvp_role")), (self.group.show,))
        for command, *args in cases:
            with self.subTest(command.name):
                self.assertEqual(self.call(command, *args, user=self.plain).reply, "Réservé aux administrateurs.")
        self.assertEqual((self.settings.count(), self.moves), (0, []))

    def test_le_proprietaire_sans_administrateur_passe(self):
        owner = SimpleNamespace(id=1, guild_permissions=SimpleNamespace(administrator=False))
        self.call(self.group.role, self.role, user=owner)
        self.assertEqual(self.settings.get(GUILD, "pvp_role"), 800)

    def test_les_reponses_sont_privees_et_ne_notifient_personne(self):
        sent = self.call(self.group.role, self.role).sent[0]
        self.assertTrue(sent.ephemeral)
        self.assertEqual((sent.allowed_mentions.users, sent.allowed_mentions.roles), (False, False))

    def test_salon_alertes_vaut_tout_de_suite(self):
        reply = self.call(self.group.alerts, self.alerts).reply
        self.assertEqual((self.settings.get(GUILD, "pvp_channel"), self.moves), (900, [GUILD]))
        self.assertIn("Celles de l'ancien salon y restent", reply)

    def test_salon_alertes_nomme_le_droit_manquant_mais_garde_le_reglage(self):
        self.alerts.permissions_for = lambda _m: SimpleNamespace(**{**vars(ALL), "attach_files": False})
        self.assertIn("joindre des fichiers", self.call(self.group.alerts, self.alerts).reply)
        self.assertEqual(self.settings.get(GUILD, "pvp_channel"), 900)

    def test_everyone_est_refuse(self):
        reply = self.call(self.group.role, role(GUILD, "@everyone", default=True)).reply
        self.assertIn("tout le serveur sonnerait", reply)
        self.assertIsNone(self.settings.get(GUILD, "pvp_role"))

    def test_un_role_gere_est_refuse(self):
        self.call(self.group.role, role(3, "bot", managed=True))
        self.assertIsNone(self.settings.get(GUILD, "pvp_role"))

    def test_un_role_pas_mentionnable_est_garde_et_donne_le_geste(self):
        self.assertIn("pas mentionnable", self.call(self.group.role, role(4, mentionable=False)).reply)
        self.assertEqual(self.settings.get(GUILD, "pvp_role"), 4)

    def test_categorie_guide_publie_tout_de_suite(self):
        self.assertIn("publié dans Guides", self.call(self.group.guide_category, self.category).reply)
        self.assertEqual(self.published, [GUILD])

    def test_categorie_guide_dit_ce_qui_l_empeche(self):
        self.outcome = "rights"
        self.assertIn("il manque au bot", self.call(self.group.guide_category, self.category).reply)
        self.assertEqual(self.settings.get(GUILD, "guide_category"), 700)
        self.outcome = "failed"
        self.assertIn("Discord a refusé", self.call(self.group.guide_category, self.category).reply)

    def test_categorie_guide_en_journal_ne_publie_rien(self):
        self.group.guide.active = False
        self.assertIn("repondre", self.call(self.group.guide_category, self.category).reply)
        self.assertEqual(self.published, [])

    def test_une_ecriture_ratee_est_dite_et_ne_change_rien(self):
        with mock.patch.object(self.settings, "_write", side_effect=OSError("disque")):
            for command, arg in ((self.group.alerts, self.alerts), (self.group.role, self.role),
                                 (self.group.guide_category, self.category)):
                with self.subTest(command.name):
                    self.assertIn("**pas** enregistré", self.call(command, arg).reply)
        self.assertEqual((self.settings.count(), self.moves, self.published), (0, [], []))

    def test_effacer(self):
        self.settings.put(GUILD, "pvp_channel", 900)
        choice = app_commands.Choice(name="x", value="pvp_channel")
        self.assertIn("oublié", self.call(self.group.forget, choice).reply)
        self.assertEqual(self.moves, [GUILD])
        self.assertIn("n'était pas posé", self.call(self.group.forget, choice).reply)

    def test_voir_rien_de_regle(self):
        answer = self.call(self.group.show).reply
        self.assertIn("Salon des cartes : `#alertes-pvp`, par son nom", answer)
        self.assertIn("Rôle mentionné : `pvp-police`, par son nom", answer)
        self.assertIn("Catégorie du guide : pas réglé", answer)
        self.assertIn("Mode : repondre", answer)
        self.assertNotIn("À régler", answer)

    def test_voir_dit_l_origine(self):
        self.settings.conf.pvp_channel_id = 900
        self.settings.conf.protectors_channel_id = 901
        self.settings.put(GUILD, "pvp_role", 800)
        answer = self.call(self.group.show).reply
        self.assertIn("Salon des cartes : <#900> (variable)", answer)
        self.assertIn("Rôle mentionné : <@&800> (commande)", answer)
        self.assertIn("Liste des protecteurs : <#901> (variable)", answer)

    def test_voir_rassemble_ce_qui_manque_et_donne_le_lien(self):
        self.settings.put(GUILD, "pvp_channel", 123)
        self.settings.put(GUILD, "pvp_role", 124)
        self.settings.put(GUILD, "guide_category", 125)
        answer = self.call(self.group.show).reply
        for wanted in ("**À régler**", "`/setup salon-alertes`", "`/setup role`", "`/setup categorie-guide`", "LIEN"):
            self.assertIn(wanted, answer)

    def test_une_variable_d_un_autre_serveur_n_est_pas_a_regler_ici(self):
        self.settings.conf.pvp_channel_id = 123
        self.settings.conf.pvp_role_id = 124
        self.settings.conf.guide_category_id = 125
        self.assertNotIn("À régler", self.call(self.group.show).reply)

    def test_en_anglais(self):
        with labels.using("en"):
            answer = self.call(self.group.show).reply
            self.assertIn("Cards channel: `#alertes-pvp`, by name", answer)
            self.assertEqual(self.call(self.group.show, user=self.plain).reply, "Administrators only.")


class GuidePerServer(Base):
    def setUp(self):
        super().setUp()
        self.docs = self.folder / "guide"
        self.docs.mkdir()
        (self.docs / "fr.md").write_text("Texte.", encoding="utf-8")

    def guild(self, guild_id, category_id):
        made = SimpleNamespace(id=guild_id, name=str(guild_id), me=SimpleNamespace(id=1), created=[])
        category = SimpleNamespace(id=category_id, name="Guides", guild=made, text_channels=[], permissions_for=lambda _m: ALL)
        made.categories = [category]

        async def create(name, category=None, reason=None):
            created = Channel()
            created.name, created.history, created.posts = name, self.no_history, []

            async def send(content, allowed_mentions=None):
                created.posts.append(content)
            created.send = send
            category.text_channels.append(created)
            made.created.append(name)
            return created
        made.create_text_channel = create
        return made

    def no_history(self, limit=100, oldest_first=None):
        async def gen():
            return
            yield
        return gen()

    def test_chaque_serveur_a_sa_categorie(self):
        one, two, three = self.guild(GUILD, 701), self.guild(OTHER, 702), self.guild(700, 703)
        config = conf()
        settings = Settings(config, self.path, self.log)
        settings.put(GUILD, "guide_category", 701)
        settings.put(OTHER, "guide_category", 702)
        client = SimpleNamespace(user=BOT, guilds=[one, two, three])
        asyncio.run(Guide(client, config, self.log, self.docs, settings).publish())
        self.assertEqual((len(one.created), len(two.created), three.created), (1, 1, []))

    def test_une_variable_d_un_autre_serveur_ne_dit_rien(self):
        one, two = self.guild(GUILD, 701), self.guild(OTHER, 702)
        config = conf(guide_category_id=701)
        client = SimpleNamespace(user=BOT, guilds=[one, two])
        asyncio.run(Guide(client, config, self.log, self.docs).publish())
        self.assertEqual((len(one.created), two.created, self.warnings), (1, [], []))

    def test_une_categorie_posee_puis_supprimee_se_dit(self):
        one = self.guild(GUILD, 701)
        config = conf()
        settings = Settings(config, self.path, self.log)
        settings.put(GUILD, "guide_category", 999)
        asyncio.run(Guide(SimpleNamespace(user=BOT, guilds=[one]), config, self.log, self.docs, settings).publish())
        self.assertEqual((one.created, len(self.warnings)), ([], 1))


class Schema(unittest.TestCase):
    """Le vrai arbre de commandes de discord.py : ce que Discord recevra."""

    def payload(self):
        client = discord.Client(intents=discord.Intents.none())
        tree = app_commands.CommandTree(client)
        tree.add_command(SetupGroup(Settings(Config(token="x")), None, None, None, SimpleNamespace()))
        return tree.get_commands()[0].to_dict(tree)

    def test_reserve_aux_admins_et_aux_serveurs(self):
        payload = self.payload()
        self.assertEqual(payload["name"], "setup")
        self.assertEqual(int(payload["default_member_permissions"]), discord.Permissions(administrator=True).value)
        self.assertIs(payload["dm_permission"], False)

    def test_discord_ne_propose_que_le_bon_type_de_salon(self):
        options = {o["name"]: o for o in self.payload()["options"]}
        self.assertEqual(set(options), {"salon-alertes", "role", "categorie-guide", "effacer", "voir"})
        self.assertEqual(options["categorie-guide"]["options"][0]["channel_types"], [discord.ChannelType.category.value])
        self.assertIn(discord.ChannelType.text.value, options["salon-alertes"]["options"][0]["channel_types"])

    def test_la_liste_des_protecteurs_n_y_est_pas(self):
        names = {o["name"] for o in self.payload()["options"]}
        self.assertFalse({name for name in names if "protect" in name}, "ses intents couperaient les cartes au redémarrage")


class ServerShape(unittest.TestCase):
    def test_un_serveur_garde_son_id(self):
        self.assertEqual(Server(GUILD, object(), 5).guild_id, GUILD)


if __name__ == "__main__":
    unittest.main()
