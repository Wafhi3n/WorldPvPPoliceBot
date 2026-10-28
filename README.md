# World PvP Police Bot

*(English below)*

Bot Discord compagnon de l'addon WoW **World PvP Police Guild** : quand un guildien est tué par un
joueur et appelle à l'aide, la ligne que l'addon écrit dans le salon Discord relié à la guilde devient
une carte lisible dans `#alertes-pvp` (qui appelle, où, combien de morts, les tueurs, qui arrive, la
carte de la zone avec un point), mise à jour au fil de l'appel.

Chaque guilde peut héberger son propre bot. Le guide d'hébergement complet arrive (spec
`docs/specs/bot-autonome.md`, tâche T4). En attendant :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # puis y taper le jeton et les identifiants
.\.venv\Scripts\python.exe -m bot
python -m unittest discover -s tests -t .
```

Licence MIT. Aucune image de Blizzard dans ce dépôt : les cartes de zone se téléchargent à la demande
sur [wago.tools](https://wago.tools).

---

## English

Discord companion bot for the WoW addon **World PvP Police Guild**: when a guild member is killed by a
player and calls for help, the line the addon writes in the guild's linked Discord channel becomes a
readable card in `#alertes-pvp` (who calls, where, deaths, killers, who is coming, the zone map with a
dot), updated as the call goes on.

Each guild can host its own bot. A full self-hosting guide is coming (task T4 of
`docs/specs/bot-autonome.md`). MIT licensed. No Blizzard images in this repository: zone maps are
fetched on demand from [wago.tools](https://wago.tools).
