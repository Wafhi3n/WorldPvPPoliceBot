# World PvP Police Bot

*(English below)*

Bot Discord compagnon de l'addon WoW **World PvP Police Guild**. Quand un guildien est tué par un joueur
et appelle à l'aide, la ligne que l'addon écrit dans le salon Discord relié à la guilde devient une carte
dans `#alertes-pvp` : qui appelle, où, combien de morts, les tueurs, son message, qui arrive, et l'image
de la zone avec un point. Le rôle `pvp-police` est mentionné, et la carte suit l'appel jusqu'au bout.
Deux guildiens qui appellent dans la même zone partagent la même carte.

Chaque guilde héberge son propre bot (Coolify, Docker ou un PC) : **[guide d'hébergement](docs/hebergement.md)**.
Cartes en français ou en anglais (`BOT_LANGUE=en`).

## Développer

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

Ce que le bot doit faire, et pourquoi : `docs/specs/alertes-pvp.md` (les cartes) et
`docs/specs/bot-autonome.md` (un bot par guilde, installation, cartes de zone).

Licence MIT. Aucune image de Blizzard dans ce dépôt : les cartes de zone se téléchargent à la demande
sur [wago.tools](https://wago.tools).

---

## English

Discord companion bot for the WoW addon **World PvP Police Guild**. When a guild member is killed by a
player and calls for help, the line the addon writes in the guild's linked Discord channel becomes a card
in `#alertes-pvp`: who is calling, where, how many deaths, the killers, their message, who is on the way,
and the zone map with a dot. The `pvp-police` role gets pinged, and the card follows the call to the end.
Two guild members calling in the same zone share one card.

Each guild hosts its own bot (Coolify, Docker or a PC): **[hosting guide](docs/hosting.md)**. The cards
come in French or English (`BOT_LANGUE=en`); the log is in French.

Development: same commands as above. The specs (in French) are in `docs/specs/`. MIT licensed. No
Blizzard images in this repository: zone maps are fetched on demand from [wago.tools](https://wago.tools).
