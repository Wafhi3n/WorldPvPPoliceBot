# Hosting World PvP Police Bot

*[Version française](hebergement.md)*

This guide is for whoever sets the bot up for their guild. Allow half an hour the first time. Each guild
hosts its own bot: there is no shared instance to invite.

## How it works

When a guild member is killed by a player and calls for help with the **World PvP Police Guild** addon,
the addon writes a line in the guild's Discord stream, and the game posts it in the Discord channel
linked to the guild. The bot reads that line and turns it into a card in `#alertes-pvp`: who is calling,
where, how many deaths, the killers, their message, who is on the way, and the zone map with a dot. It
pings the `pvp-police` role, then keeps the card updated until the call ends.

## What you need

- **The guild linked to a Discord server, with Discord chat kept separate.** The guild master or an
  officer, in game: Guild & Communities (`J`), right-click the guild, guild settings, then Discord
  settings. Link the server and the channel there, and tick the box that **keeps Discord chat separate**
  from guild chat. Without that box, the addon treats the guild as not linked and writes nothing to
  Discord.
- **The World PvP Police Guild addon** for your guild members. A member whose Battle.net account isn't
  linked to Discord: their call still goes out in game, but it hasn't been checked yet whether it
  reaches Discord.
- **A Discord server** you can invite a bot to.
- **A machine that stays on**: a server with Docker (Coolify, or plain Docker), or a PC that stays on.

## 1. Create the Discord application

1. At <https://discord.com/developers/applications>, **New Application**. The name is what members will
   see on the cards (for example "World PvP Police").
2. **Bot** tab:
   - **Reset Token**, then copy the token: Discord shows it only once. It's the bot's password. It never
     goes in a message, an issue, a screenshot or a commit.
   - Under **Privileged Gateway Intents**, turn on **Message Content Intent**. Without it the bot can't
     read the text of the in-game lines, and it refuses to start (`PrivilegedIntentsRequired`).
   - Untick **Public Bot**, so only you can invite it. If Discord refuses, first set the **Installation**
     tab, *Install Link*, to *None*.
3. **General Information** tab: note the **Application ID**.

A bot that reads message content can join up to 100 servers without verification by Discord. That's
plenty for a guild, and it's why each guild runs its own.

## 2. Invite the bot

Open this link with `APPLICATION_ID` replaced by yours, and pick the guild's server:

```
https://discord.com/oauth2/authorize?client_id=APPLICATION_ID&scope=bot&permissions=268561424
```

The bot also writes this link to its log on every start (`lien d'invitation du bot : …`).

| Permission | What for |
|---|---|
| View Channels, Read Message History | read the in-game lines in the linked channel; read its own cards back after a restart |
| Send Messages, Embed Links, Attach Files | post the cards and the zone map |
| Manage Messages | delete the raw line from the linked channel once its card is made |
| Manage Channels, Manage Roles | create `#alertes-pvp` and the `pvp-police` role if they don't exist |

**The channel linked to the game often has its own permissions.** Check that the bot has View Channel,
Read Message History and Manage Messages there: a deny set on the channel beats the invite link. Without
Manage Messages, the card is still made, but the raw line stays. The bot never writes in that channel
(Discord won't let a bot post in a channel linked to the game), and it doesn't need to.

**If `#alertes-pvp` or `pvp-police` already exist**, the bot finds them by name and leaves their
permissions alone:

- in `#alertes-pvp`, it must be able to send messages, embed links and attach files;
- the `pvp-police` role must be mentionable. If it isn't, the bot makes it mentionable, as long as that
  role sits below the bot's own role (Server Settings, Roles: drag the bot's role above it).

If it creates them itself, `#alertes-pvp` is read-only for members (they read and react, only the bot
writes), and `pvp-police` is mentionable, below the bot's role.

## 3. Run the bot

### With Coolify

1. **New Resource**, then the bot's repository (*Public Repository*, or *Private Repository with GitHub
   App* for your own copy), branch `main`.
2. **Build Pack: Dockerfile.** No domain: the bot listens on no port, it calls Discord. If Coolify insists
   on an exposed port, keep the suggested value and turn off the *health check*.
3. **Environment Variables**: `DISCORD_TOKEN` (tick *secret*) and `BOT_MODE` = `journal`. Nothing else
   is required.
4. **Persistent Storage** (recommended): a volume mounted on `/app/state`, for the `bot.log` log and the
   zone map cache. Without it, maps are downloaded again after each redeploy; nothing vital lives there.
5. **Deploy**, then read the service logs (step 4).

### With Docker

```sh
git clone <repository URL> WorldPvPPoliceBot
cd WorldPvPPoliceBot
cp .env.example .env            # then type the token after DISCORD_TOKEN=, without quotes
docker build -t worldpvppolicebot .
docker run -d --name worldpvppolicebot --restart unless-stopped \
  --env-file .env -v worldpvppolicebot-state:/app/state worldpvppolicebot
docker logs -f worldpvppolicebot
```

To change a setting: edit `.env`, then `docker rm -f worldpvppolicebot` and run the `docker run`
command again.

### On a PC

With Python 3.13 (the version in the Docker image and the one the tests run on; older versions haven't
been tried). On Windows, in PowerShell:

```powershell
git clone <repository URL> WorldPvPPoliceBot
cd WorldPvPPoliceBot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env     # then type the token after DISCORD_TOKEN=
.\.venv\Scripts\python.exe -m bot
```

On Linux or macOS: `python3 -m venv .venv`, then `.venv/bin/python -m pip install --upgrade pip`,
`.venv/bin/python -m pip install -r requirements.txt` and `.venv/bin/python -m bot`. (A fresh
environment can come with an old pip; an up-to-date one no longer trusts a certificate authority that
was pulled in October 2026.) The bot runs as long as the window stays open; its log is `bot.log`, next
to the code.

## 4. First run: look before it acts

By default (`BOT_MODE=journal`), the bot connects and logs what it sees, without creating or posting
anything. The log is in French; it should start with:

```
connecté : World PvP Police#1234 ; mode journal ; serveurs : Your server (…)
lien d'invitation du bot : https://discord.com/oauth2/authorize?…
```

Then make a call in game (or wait for the next one). This line should show up ("message du jeu" = "game
message"):

```
message du jeu dans #your-linked-channel : id=… content='…'
```

If it doesn't, see troubleshooting below. If it does, set `BOT_MODE` to `repondre` and restart the bot.
On start, it finds or creates what it's missing:

```
installation sur Your server : #alertes-pvp créé (lecture seule pour les membres)
installation sur Your server : rôle pvp-police créé (mentionnable)
```

The next call gets its card. So does the test call, if it's less than 30 minutes old: on start, the bot
catches up on the call lines still sitting in the linked channel, role ping included.

## 5. Let members take the role

The bot creates the `pvp-police` role but gives it to nobody. On a Community server, add a question to
the server's Onboarding (for example "Get pinged for PvP calls for help?") with an answer that grants
`pvp-police`. Members then find it under **Channels & Roles**, at the top of the channel list. On a
server that isn't a Community server, a moderator hands out the role.

## What the bot does

- **One card per zone.** Two guild members calling in the same zone share the card: one line and one
  dot (with their name) each.
- **One ping per card**, when it opens: a second call in the same zone updates the card without pinging
  the role again.
- The card follows the call: deaths, message, "on my way", "settled".
- **Red** while a call is open, **green** once every call is settled, **grey** when the last open call
  went 30 minutes without news.
- The raw line is deleted from the linked channel once the card is made (`BOT_SUPPRIMER`).
- A finished card is deleted from `#alertes-pvp` 24 hours later (`BOT_GARDER_HEURES`). The bot never
  touches other messages in that channel.
- After a stop, it picks its open cards back up and catches up on the lines that came in meanwhile
  (those from the last 30 minutes).
- It only reads and edits its own cards: another bot's cards in the same channel are left alone.
- One bot can serve several servers: each gets its own `#alertes-pvp`.
- **The cards are in French for now.** An English version is planned. The settings keep their French
  values (`oui` / `non` = yes / no, `journal`, `repondre`).

## Settings

All optional except the token. In `.env`, or as environment variables (Coolify, Docker).

| Variable | Default | What it does |
|---|---|---|
| `DISCORD_TOKEN` | — | the bot's token (required) |
| `BOT_MODE` | `journal` | `journal`: log only; `repondre`: make the cards |
| `DISCORD_PVP_CHANNEL_NAME` | `alertes-pvp` | the cards channel, found or created by this name |
| `DISCORD_PVP_ROLE_NAME` | `pvp-police` | the role to ping, found or created by this name |
| `BOT_INSTALLER` | `oui` | `non`: never create a channel or a role |
| `DISCORD_CHANNEL_ID` | empty | force the linked channel (otherwise found by its in-game messages) |
| `DISCORD_PVP_CHANNEL_ID` | empty | force the cards channel (the bot then serves one server only) |
| `DISCORD_PVP_ROLE_ID` | empty | force the role to ping |
| `BOT_SUPPRIMER` | `oui` | delete the raw line from the linked channel |
| `BOT_GARDER_HEURES` | `24` | hours before a finished card is deleted (`0`: never) |
| `BOT_CARTES` | `oui` | `non`: cards without a zone map |
| `BOT_CARTES_PRODUIT` | `wowf` | `wowf`: WoW: Forever; `wowt`: Retail PTR; `wow`: Retail |
| `BOT_CARTES_LANGUE` | `frFR` | language of the names on the map (`enUS`, `deDE`, `esES`…) |
| `BOT_LOG` | `bot.log` | log file (`/app/state/bot.log` in the image) |
| `BOT_STATE` | `state` | map cache folder (`/app/state` in the image) |

## Troubleshooting

| The log says, or you see | Cause and fix |
|---|---|
| `PrivilegedIntentsRequired` on start | Message Content Intent isn't on (step 1). |
| `salon … INTROUVABLE` | a forced id (`DISCORD_CHANNEL_ID`, `DISCORD_PVP_CHANNEL_ID`) the bot can't see: not invited, or not allowed to view that channel. |
| no `message du jeu` line after a call | the bot can't see the linked channel (its permissions), the guild doesn't keep Discord chat separate, or the call didn't reach Discord (in game, "Ton appel" shows how the sending went). |
| `message du jeu` logged, but no card | `BOT_MODE` is still `journal`. |
| `pas de #alertes-pvp et pas le droit de gérer les salons` ("no #alertes-pvp and no right to manage channels") | invite the bot again with the step 2 link, or create the channel yourself. |
| `rôle pvp-police pas mentionnable, et le bot ne peut pas y toucher` ("role not mentionable, and the bot can't touch it") | make the role mentionable, or drag the bot's role above it. |
| `suppression refusée` ("deletion refused"), the raw line stays | the bot lacks Manage Messages on the linked channel. |
| `carte de zone … pas téléchargée` ("zone map not downloaded") | wago.tools unreachable: the card goes out without a map, retried 10 minutes later. `BOT_CARTES=non` to do without. |

## Updating

- **Coolify**: *Redeploy*.
- **Docker**: `git pull`, `docker build -t worldpvppolicebot .`, then `docker rm -f worldpvppolicebot` and
  the `docker run` command.
- **PC**: `git pull`, `pip install -r requirements.txt` in the `.venv`, and start it again.

## What the bot reads and keeps

- It only handles messages posted by the game in the linked channel; it ignores everything else.
- Its log keeps those lines as they are (caller's name, zone, message).
- It only talks to Discord and [wago.tools](https://wago.tools), for the zone maps. No player data goes
  to wago.tools: only the zone number, the game and the language.
- No game image is stored in this repository or in the Docker image.
