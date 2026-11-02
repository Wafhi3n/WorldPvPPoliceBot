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
  Discord, unless a player types `/wpp fusion on`: their calls are then also written to guild chat, where
  the whole guild sees them, and the bridge carries them to Discord. That path hasn't been checked in game
  yet.
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
     read the text of the in-game lines, and it refuses to start (`Discord refuse la connexion`).
   - Untick **Public Bot**, so only you can invite it. If Discord refuses, first set the **Installation**
     tab, *Install Link*, to *None*.
3. **General Information** tab: note the **Application ID**.

A bot that reads message content can join up to 100 servers without verification by Discord. That's
plenty for a guild, and it's why each guild runs its own.

## 2. Invite the bot

Open this link with `APPLICATION_ID` replaced by yours, and pick the guild's server:

```
https://discord.com/oauth2/authorize?client_id=APPLICATION_ID&scope=bot+applications.commands&permissions=268561424
```

The bot also writes this link to its log on every start (`lien d'invitation du bot : …`). If the bot is already on the server
and `/setup` doesn't show up: open this link again, without kicking it.

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

The cards channel can also be an **announcement channel**, if you created it that way: give the bot the right
to send messages there. The bot doesn't "publish" its cards: server members see them, but a server following
that channel wouldn't receive them. This case hasn't been checked in game yet.

## 3. Run the bot

### With Coolify

1. **New Resource**, then the bot's repository, branch `main`: *Public Repository*, or for your own private
   copy *Private Repository with GitHub App* or *Private Repository with Deploy Key*. With a deploy key: in
   Coolify, **Keys & Tokens**, generate a key; on GitHub, in the repository's **Settings**, **Deploy keys**,
   paste its **public** key without allowing write access (a key works for one repository only); the
   repository address looks like `git@github.com:account/repo.git`.
2. **Build Pack: Dockerfile.** No domain: the bot listens on no port, it calls Discord. If Coolify insists
   on an exposed port, keep the suggested value and turn off the *health check*.
3. **Environment Variables**: Coolify creates none of them, add them yourself: `DISCORD_TOKEN` (the token
   from the **Bot** tab, without quotes; tick *secret*, keep it available at runtime, not at build time),
   `BOT_MODE` = `journal`, and `BOT_LANGUE` = `en` for cards in English. Nothing else is required. After a
   change: **Redeploy**.
4. **Persistent Storage** (recommended): a volume mounted on `/app/state`, for the `bot.log` log, the zone
   map cache and the `/setup` settings. Without it, each redeploy erases those settings, and maps are downloaded again.
   Use a **volume**, not a folder on the server: the bot doesn't run as root, and a folder would probably
   refuse it write access (`PermissionError` on start).
5. **Deploy**, then read the service logs (step 4).

### With Docker

```sh
git clone <repository URL> WorldPvPPoliceBot
cd WorldPvPPoliceBot
cp .env.example .env            # then type the token after DISCORD_TOKEN=, without quotes, and BOT_LANGUE=en
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
Copy-Item .env.example .env     # then type the token after DISCORD_TOKEN=, and BOT_LANGUE=en
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
connecté : World PvP Police#1234 ; mode journal ; langue des cartes en ; serveurs : Your server (…)
lien d'invitation du bot : https://discord.com/oauth2/authorize?…
```

Then make a call in game (or wait for the next one). This line should show up ("message du jeu" = "game
message"):

```
message du jeu dans #your-linked-channel : id=… content='…'
```

In `journal`, every message from the game is logged there: with merged chat, that's all of guild chat. In
`repondre`, only the call lines stay.

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

## 6. Show the protectors who are online (optional)

The role holders are the guild's protectors. In a channel of your choice, the bot can keep a single message listing
those who are online:

```
Protectors of Your server
3 online out of 12
@Someone @Another @Third
```

1. **First**, in the portal's **Bot** tab, *Privileged Gateway Intents*: turn on **Server Members Intent** and **Presence
   Intent**. In that order: without them, Discord refuses the connection and the bot won't start anymore.
2. Create the channel. The bot doesn't create it. It needs View Channel, Send Messages, Embed Links and Read Message
   History there.
3. In Discord, Settings, Advanced, **Developer Mode**; then right-click the channel, **Copy Channel ID**. Put it in
   `DISCORD_PVP_PROTECTORS_CHANNEL_ID`, and redeploy.

The log then says `salon #… : voir=True … envoyer=True`, then `protecteurs de Your server : 3 connectés sur 12`. With
`BOT_MODE=journal`, nothing is posted.

**"Online" means online on Discord**, not in the game: the bot can't see who's playing. Idle and Do Not Disturb count as
online; an invisible member counts as offline, since Discord doesn't tell the bot the difference.

Nobody gets notified by these @s. The role is `DISCORD_PVP_ROLE_ID`, otherwise the one named `DISCORD_PVP_ROLE_NAME`.

If members can write in that channel, the list sinks under their messages: make it read-only if the list has to stay in
view. The bot keeps the message's id in `/app/state` to find it after a restart. Without that volume, it looks through the
last 1000 messages, and posts a new one if it isn't there.

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
- **Cards in English**: set `BOT_LANGUE=en` (the default is French). The log stays in French, and the
  settings keep their French values (`oui` / `non` = yes / no, `journal`, `repondre`).
- The channel and the role keep their French default names. To use others, set
  `DISCORD_PVP_CHANNEL_NAME` (for example `pvp-alerts`) and `DISCORD_PVP_ROLE_NAME` **before the first
  run**: renaming later makes the bot look for, and create, a new channel or role with the new name.

## Settings

All optional except the token. In `.env`, or as environment variables (Coolify, Docker).

| Variable | Default | What it does |
|---|---|---|
| `DISCORD_TOKEN` | — | the bot's token (required) |
| `BOT_MODE` | `journal` | `journal`: log only; `repondre`: make the cards |
| `BOT_LANGUE` | `fr` | the language of the cards: `fr` or `en` |
| `DISCORD_PVP_CHANNEL_NAME` | `alertes-pvp` | the cards channel, found or created by this name |
| `DISCORD_PVP_ROLE_NAME` | `pvp-police` | the role to ping, found or created by this name |
| `BOT_INSTALLER` | `oui` | `non`: never create a channel or a role |
| `DISCORD_CHANNEL_ID` | empty | force the linked channel (otherwise found by its in-game messages) |
| `DISCORD_PVP_CHANNEL_ID` | empty | force the cards channel (the bot then serves one server only) |
| `DISCORD_PVP_ROLE_ID` | empty | force the role to ping |
| `DISCORD_PVP_PROTECTORS_CHANNEL_ID` | empty | the channel of the online protectors list (step 6); empty: no list |
| `DISCORD_GUIDE_CATEGORY_ID` | empty | the category where the guide for administrators is posted (below); empty, and without `/setup`: no guide |
| `BOT_SUPPRIMER` | `oui` | delete the raw line from the linked channel |
| `BOT_GARDER_HEURES` | `24` | hours before a finished card is deleted (`0`: never) |
| `BOT_CARTES` | `oui` | `non`: cards without a zone map |
| `BOT_CARTES_PRODUIT` | `wowf` | `wowf`: WoW: Forever; `wowt`: Retail PTR; `wow`: Retail |
| `BOT_CARTES_LANGUE` | from `BOT_LANGUE` | language of the names on the map (`frFR`, `enUS`, `deDE`, `esES`…) |
| `BOT_LOG` | `bot.log` | log file (`/app/state/bot.log` in the image) |
| `BOT_STATE` | `state` | map cache folder (`/app/state` in the image) |

## Troubleshooting

| The log says, or you see | Cause and fix |
|---|---|
| `DISCORD_TOKEN manquant` ("missing") | the variable doesn't reach the bot: misspelled name, not available at runtime, or no **Redeploy** since. |
| `Improper token has been passed` (401) | that isn't the token: it's in the **Bot** tab, in three parts separated by dots. Not the server ID, the Application ID or the Client Secret. A **Reset Token** also cancels the previous one. |
| `Discord refuse la connexion : allumer …` ("Discord refuses the connection: turn on …") | an intent is off: Message Content Intent (step 1); with the protectors list, also Server Members Intent and Presence Intent (step 6). Or empty `DISCORD_PVP_PROTECTORS_CHANNEL_ID`. |
| `salon … INTROUVABLE` | a forced id (`DISCORD_CHANNEL_ID`, `DISCORD_PVP_CHANNEL_ID`, `DISCORD_PVP_PROTECTORS_CHANNEL_ID`) the bot can't see: not invited, or not allowed to view that channel. |
| `salon … introuvable parmi les salons texte du bot` ("not among the bot's text channels") | `DISCORD_PVP_PROTECTORS_CHANNEL_ID` isn't a text channel on one of the bot's servers: copy the id again (step 6). |
| `ni DISCORD_PVP_ROLE_ID ni le rôle` ("neither … nor the role") | the protectors role isn't on that channel's server: set `DISCORD_PVP_ROLE_ID` or `DISCORD_PVP_ROLE_NAME`. The list already shown stops changing. |
| `liste des protecteurs pas mise à jour` ("protectors list not updated") | Discord refuses: give the bot the step 6 permissions in that channel. |
| no `message du jeu` line after a call | the bot can't see the linked channel (its permissions), the guild doesn't keep Discord chat separate, or the call didn't reach Discord (in game, "Ton appel" shows how the sending went). |
| `message du jeu` logged, but no card | `BOT_MODE` is still `journal`. |
| `pas de #alertes-pvp et pas le droit de gérer les salons` ("no #alertes-pvp and no right to manage channels") | invite the bot again with the step 2 link, or create the channel yourself. |
| `rôle pvp-police pas mentionnable, et le bot ne peut pas y toucher` ("role not mentionable, and the bot can't touch it") | make the role mentionable, or drag the bot's role above it. |
| `suppression refusée` ("deletion refused"), the raw line stays | the bot lacks Manage Messages on the linked channel. |
| `salon … pas relu pour le rattrapage` ("not read for catch-up") | the bot can't read that channel: calls missed during the stop get no card. If it's the linked channel, it needs View Channel and Read Message History, or no call arrives (`/setup voir`). |
| `carte de zone … pas téléchargée` ("zone map not downloaded") | wago.tools unreachable: the card goes out without a map, retried 10 minutes later. `BOT_CARTES=non` to do without. |

## Set up the bot from Discord: `/setup`

The most common settings can also be set by command, without redeploying, and **server by server**. A command wins over the variable,
which stays as the fallback: a service already set up has nothing to redo.

| Command | What it does | Replaces |
|---|---|---|
| `/setup voir` | Shows each setting, where it comes from, and what's missing | |
| `/setup salon-alertes salon` | The cards channel | `DISCORD_PVP_CHANNEL_ID` |
| `/setup role role` | The role to ping, also listed as protectors; `@everyone` and a managed role are refused | `DISCORD_PVP_ROLE_ID` |
| `/setup categorie-guide categorie` | The guide's category (below); it's posted right away | `DISCORD_GUIDE_CATEGORY_ID` |
| `/setup effacer reglage` | Forgets a setting made here, and goes back to the variable | |

Server owner and administrators only, even if another role can see these commands through the Integrations settings. Replies follow
`BOT_LANGUE`; the command names stay in French. If several bots offer `/setup`, Discord shows the name of each.

**When changing channels**, new cards go to the new one. Open cards finish in the old one, and its finished cards no longer delete
themselves: remove them by hand.

**What stays where it's hosted**: the token, `BOT_MODE`, the language, the zone maps, the linked channel, and the protectors list: it
needs privileged intents, and a setting made by command would turn them on at the next restart; on a portal where they're off, the bot
wouldn't start anymore, cards included.

**Variable and several servers**: `DISCORD_PVP_CHANNEL_ID` only counts for that channel's server. Another server of the bot has its own
channel: the `/setup` one, otherwise found or created by name on its first call line (`BOT_INSTALLER=non` to avoid that).

Settings live in `/app/state/reglages.json`: without the volume, a redeploy loses them, and the bot goes back to its variables.

```
INFO réglages : 3 posés par commande (fichier /app/state/reglages.json)
```

## Post a guide for administrators (optional)

On every start, the bot can post a guide to how it works in a `world-pvp-police` channel, in the `BOT_LANGUE` language. Its messages
are edited, not doubled, and it touches no other message.

1. Create a category, and choose who sees it: the bot sets no permissions.
2. In that category, give the bot: View Channels, Manage Channels, Send Messages, Read Message History.
3. `/setup categorie-guide`, or the category's id, alone, in `DISCORD_GUIDE_CATEGORY_ID`. It needs `BOT_MODE=repondre`.

## Updating

- **Coolify**: *Redeploy*. Or, from a PC that can reach Coolify: `python tools/deploy.py`, which checks `main`, runs the tests, pushes
  and redeploys. It reads `.deploy.env` (template `.deploy.env.example`), with a token limited to `read` and `deploy`.
- **Docker**: `git pull`, `docker build -t worldpvppolicebot .`, then `docker rm -f worldpvppolicebot` and
  the `docker run` command.
- **PC**: `git pull`, `pip install -r requirements.txt` in the `.venv`, and start it again.

## What the bot reads and keeps

- It only handles messages posted by the game in the linked channel; it ignores everything else.
- In `repondre`, its log keeps only the call lines, as they are (caller's name, zone, message). In
  `journal`, it keeps every message from the game, so all of guild chat with merged chat.
- It only talks to Discord and [wago.tools](https://wago.tools), for the zone maps. No player data goes
  to wago.tools: only the zone number, the game and the language.
- No game image is stored in this repository or in the Docker image.
- Only with the protectors list, it receives the server's member list and their online status. It keeps none of it: the
  log holds numbers, never a name, and the `protecteurs.json` file holds only the message's id.
