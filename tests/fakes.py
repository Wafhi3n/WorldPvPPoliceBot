"""Un faux serveur Discord pour les tests d'installation et de serveurs multiples : salons, rôles, droits
du bot, création de salon et de rôle. Les salons des cartes sont les faux salons de test_pvp_relay."""

from types import SimpleNamespace

from tests.test_pvp_relay import Channel

READ = SimpleNamespace(view_channel=True, read_message_history=True)
HIDDEN = SimpleNamespace(view_channel=False, read_message_history=False)


class FakeRole:
    def __init__(self, role_id, name, position, mentionable=False):
        self.id, self.name, self.position, self.mentionable, self.edits = role_id, name, position, mentionable, []

    def __lt__(self, other):
        return self.position < other.position

    async def edit(self, mentionable=None, reason=None):
        self.mentionable = mentionable
        self.edits.append(mentionable)


class Source:
    """Un salon de texte du serveur : son historique (filtré par `after`) et ce que le bot y peut."""
    def __init__(self, name, messages=(), perms=READ):
        self.name, self.messages, self.perms, self.read = name, list(messages), perms, 0

    def permissions_for(self, _member):
        return self.perms

    def history(self, limit=100, after=None, oldest_first=None):
        self.read += 1

        async def gen():
            for m in sorted(self.messages, key=lambda m: m.created_at)[:limit]:
                if after is None or m.created_at > after:
                    yield m
        return gen()


class FakeMember:
    """Le bot sur le serveur (une clé de dictionnaire, comme un vrai membre : les droits par salon)."""
    def __init__(self, top_role, manage_channels, manage_roles):
        self.id, self.top_role = 1, top_role
        self.guild_permissions = SimpleNamespace(manage_channels=manage_channels, manage_roles=manage_roles)


class FakeGuild:
    def __init__(self, guild_id, name, channels=(), roles=(), manage_channels=True, manage_roles=True):
        self.id, self.name = guild_id, name
        self.text_channels, self.roles = list(channels), list(roles)
        self.default_role = FakeRole(guild_id, "@everyone", 0)
        self.me = FakeMember(FakeRole(guild_id + 1, "bot", 10), manage_channels, manage_roles)
        self.created = []

    async def create_text_channel(self, name, overwrites=None, reason=None):
        channel = Channel()
        channel.name, channel.overwrites = name, overwrites
        channel.permissions_for = lambda _member: READ
        self.text_channels.append(channel)
        self.created.append(("salon", name))
        return channel

    async def create_role(self, name, mentionable=False, reason=None):
        role = FakeRole(self.id + 100 + len(self.roles), name, 1, mentionable)
        self.roles.append(role)
        self.created.append(("rôle", name))
        return role
