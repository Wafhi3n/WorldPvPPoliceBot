# World PvP Police Bot

When a guild member calls for help from the game, with the World PvP Police Guild addon, the bot turns it into a card on Discord. It has no commands: everything is set where it's hosted.

## The call card

The line the addon writes in the channel linked to the guild becomes a card in the alerts channel: who's calling, where, how many deaths, the killers, their message, who's on the way, and the zone map with a dot.

- **One card per zone**: two guild members calling in the same zone share it.
- **One ping per card**, of the `pvp-police` role, when it opens: a second call in the zone updates the card without pinging the role again.
- **Red** while a call is open, **green** once all are settled, **grey** after 30 minutes without news.
- The raw line leaves the linked channel once the card is made.
- A finished card is deleted 24 hours later. The bot never touches other messages in that channel.
- After a stop, it picks its open cards back up and catches up on the calls from the last 30 minutes.

## Taking the role

The bot gives the `pvp-police` role to nobody: members take it under "Channels & Roles". For the ping to ring, the role must be mentionable.

## The protectors list

If its channel is set, the bot keeps a single message there: the role holders who are online, and their total. "Online" means online on Discord: the bot can't see the game. Idle and Do Not Disturb count; invisible counts as offline. Nobody gets notified by these @s.

## Settings where it's hosted

- `BOT_MODE`: `journal` logs and does nothing, `repondre` makes the cards
- `DISCORD_PVP_CHANNEL_ID`: the cards channel
- `DISCORD_PVP_ROLE_ID`: the role to ping
- `DISCORD_PVP_PROTECTORS_CHANNEL_ID`: the protectors list channel; turn on Server Members Intent and Presence Intent on the Discord portal before setting it
- `DISCORD_GUIDE_CATEGORY_ID`: the category where the bot posts this guide, updated on every deployment

## If nothing arrives

A call line that doesn't show up in the linked channel doesn't come from the bot: check "Ton appel" in the addon. If it shows up without a card: the bot is in `journal`, or lacks its permissions in the alerts channel. Its log says so.
