# Héberger World PvP Police Bot

*[English version](hosting.md)*

Ce guide est pour la personne qui installe le bot pour sa guilde. Comptez une demi-heure la première
fois. Chaque guilde héberge son propre bot : il n'y a pas d'instance commune à inviter.

## Comment ça marche

Quand un guildien est tué par un joueur et appelle à l'aide avec l'addon **World PvP Police Guild**,
l'addon écrit une ligne dans le fil Discord de la guilde, et le jeu la publie dans le salon Discord relié
à la guilde. Le bot lit cette ligne et en fait une carte dans `#alertes-pvp` : qui appelle, où, combien
de morts, les tueurs, son message, qui arrive, et l'image de la zone avec un point. Il mentionne le rôle
`pvp-police`, puis met la carte à jour jusqu'à la fin de l'appel.

## Ce qu'il faut

- **La guilde reliée à un serveur Discord, en chat Discord séparé.** Le maître de guilde ou un officier,
  en jeu : Guilde et communautés (`J`), clic droit sur la guilde, réglages de la guilde, puis réglages
  Discord. Il y relie le serveur et le salon, et coche la case qui **sépare le chat Discord** du chat de
  guilde. Sans cette case, l'addon traite la guilde comme non reliée et n'écrit rien sur Discord.
- **L'addon World PvP Police Guild** chez les guildiens. Un guildien dont le compte Battle.net n'est pas
  relié à Discord : son appel part bien en jeu, mais on n'a pas encore vérifié qu'il arrive sur Discord.
- **Un serveur Discord** sur lequel vous pouvez inviter un bot.
- **Une machine allumée en permanence** : un serveur avec Docker (Coolify, ou Docker seul), ou un PC
  qui reste allumé.

## 1. Créer l'application Discord

1. Sur <https://discord.com/developers/applications>, **New Application**. Le nom est celui que les
   membres verront sur les cartes (par exemple « World PvP Police »).
2. Onglet **Bot** :
   - **Reset Token**, puis copiez le jeton : Discord ne l'affiche qu'une fois. C'est le mot de passe du
     bot. Il ne va jamais dans un message, un ticket, une capture d'écran ou un commit.
   - Sous **Privileged Gateway Intents**, activez **Message Content Intent**. Sans lui, le bot ne lit
     pas le texte des lignes du jeu, et il refuse de démarrer (`PrivilegedIntentsRequired`).
   - Décochez **Public Bot**, pour que vous seul puissiez l'inviter. Si Discord refuse, mettez d'abord
     l'onglet **Installation**, *Install Link*, sur *None*.
3. Onglet **General Information** : notez l'**Application ID**.

Un bot qui lit le contenu des messages peut rejoindre jusqu'à 100 serveurs sans vérification par
Discord. C'est largement assez pour une guilde, et c'est la raison pour laquelle chaque guilde a le sien.

## 2. Inviter le bot

Ouvrez ce lien en remplaçant `APPLICATION_ID` par le vôtre, et choisissez le serveur de la guilde :

```
https://discord.com/oauth2/authorize?client_id=APPLICATION_ID&scope=bot&permissions=268561424
```

Le bot écrit aussi ce lien dans son journal à chaque démarrage (`lien d'invitation du bot : …`).

| Droit demandé | Pour quoi faire |
|---|---|
| Voir les salons, Lire l'historique des messages | lire les lignes du jeu dans le salon relié ; relire ses cartes après un redémarrage |
| Envoyer des messages, Intégrer des liens, Joindre des fichiers | publier les cartes et l'image de la zone |
| Gérer les messages | effacer la ligne brute du salon relié une fois sa carte faite |
| Gérer les salons, Gérer les rôles | créer `#alertes-pvp` et le rôle `pvp-police` s'ils n'existent pas |

**Le salon relié au jeu a souvent ses propres permissions.** Vérifiez que le bot y a Voir le salon, Lire
l'historique et Gérer les messages : un refus posé sur le salon l'emporte sur le lien d'invitation. Sans
Gérer les messages, la carte se fait quand même, mais la ligne brute reste. Le bot n'écrit jamais dans
ce salon (Discord refuse qu'un bot écrive dans un salon relié au jeu), il n'en a pas besoin.

**Si `#alertes-pvp` ou `pvp-police` existent déjà**, le bot les retrouve par leur nom et ne touche pas
à leurs permissions :

- dans `#alertes-pvp`, il doit pouvoir envoyer des messages, intégrer des liens et joindre des fichiers ;
- le rôle `pvp-police` doit être mentionnable. S'il ne l'est pas, le bot le rend mentionnable, à
  condition que ce rôle soit sous le sien dans la liste des rôles (Paramètres du serveur, Rôles : glissez
  le rôle du bot au-dessus).

S'il les crée lui-même, `#alertes-pvp` est en lecture seule pour les membres (ils lisent et réagissent,
seul le bot écrit), et `pvp-police` est mentionnable, sous le rôle du bot.

## 3. Lancer le bot

### Avec Coolify

1. **New Resource**, puis le dépôt du bot (*Public Repository*, ou *Private Repository with GitHub App*
   pour votre propre copie), branche `main`.
2. **Build Pack : Dockerfile.** Pas de domaine : le bot n'écoute aucun port, c'est lui qui appelle
   Discord. Si Coolify exige un port exposé, laissez la valeur proposée et désactivez le *health check*.
3. **Environment Variables** : `DISCORD_TOKEN` (cochez *secret*) et `BOT_MODE` = `journal`. Rien
   d'autre n'est obligatoire.
4. **Persistent Storage** (conseillé) : un volume monté sur `/app/state`, pour le journal `bot.log` et
   le cache des images de zone. Sans lui, les images sont retéléchargées après chaque redéploiement ;
   rien de vital n'y est rangé.
5. **Deploy**, puis lisez les logs du service (étape 4).

### Avec Docker

```sh
git clone <adresse du dépôt> WorldPvPPoliceBot
cd WorldPvPPoliceBot
cp .env.example .env            # puis tapez le jeton après DISCORD_TOKEN=, sans guillemets
docker build -t worldpvppolicebot .
docker run -d --name worldpvppolicebot --restart unless-stopped \
  --env-file .env -v worldpvppolicebot-state:/app/state worldpvppolicebot
docker logs -f worldpvppolicebot
```

Pour changer un réglage : modifiez `.env`, puis `docker rm -f worldpvppolicebot` et relancez la
commande `docker run`.

### Sur un PC

Avec Python 3.13 (la version de l'image Docker et des tests ; une version plus ancienne n'a pas été
essayée). Sous Windows, dans PowerShell :

```powershell
git clone <adresse du dépôt> WorldPvPPoliceBot
cd WorldPvPPoliceBot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env     # puis tapez le jeton après DISCORD_TOKEN=
.\.venv\Scripts\python.exe -m bot
```

Sous Linux ou macOS : `python3 -m venv .venv`, puis `.venv/bin/python -m pip install -r requirements.txt`
et `.venv/bin/python -m bot`. Le bot tourne tant que la fenêtre reste ouverte ; son journal est
`bot.log`, à côté du code.

## 4. Premier lancement : regarder avant d'agir

Par défaut (`BOT_MODE=journal`), le bot se connecte et note ce qu'il voit, sans rien créer ni publier.
Le journal doit commencer par :

```
connecté : World PvP Police#1234 ; mode journal ; serveurs : Votre serveur (…)
lien d'invitation du bot : https://discord.com/oauth2/authorize?…
```

Faites ensuite un appel en jeu (ou attendez le prochain). Cette ligne doit apparaître :

```
message du jeu dans #votre-salon-relie : id=… content='…'
```

Si elle n'apparaît pas, voyez le dépannage plus bas. Si elle apparaît, passez `BOT_MODE` à `repondre`
et redémarrez le bot. Au démarrage, il retrouve ou crée ce qui lui manque :

```
installation sur Votre serveur : #alertes-pvp créé (lecture seule pour les membres)
installation sur Votre serveur : rôle pvp-police créé (mentionnable)
```

Le prochain appel fait sa carte.

## 5. Laisser les membres prendre le rôle

Le bot crée le rôle `pvp-police` mais ne le donne à personne. Sur un serveur communautaire, ajoutez dans
l'Onboarding du serveur une question (par exemple « Être prévenu des appels à l'aide PvP ? ») dont une
réponse donne le rôle `pvp-police`. Les membres la retrouvent ensuite dans **Salons et rôles**, en haut de
la liste des salons. Sur un serveur qui n'est pas communautaire, un modérateur donne le rôle à la main.

## Ce que fait le bot

- **Une carte par zone.** Deux guildiens qui appellent dans la même zone partagent la carte : une ligne
  et un point (avec le prénom) chacun.
- **Une mention par carte**, à son ouverture : un 2e appel dans la même zone met la carte à jour sans
  refaire sonner le rôle.
- La carte suit l'appel : morts, message, « J'arrive », « C'est réglé ».
- **Rouge** tant qu'un appel est en cours, **verte** quand tous sont réglés, **grise** quand le dernier
  appel en cours est resté 30 minutes sans nouvelles.
- La ligne brute est effacée du salon relié une fois la carte faite (`BOT_SUPPRIMER`).
- Une carte finie est effacée de `#alertes-pvp` 24 heures plus tard (`BOT_GARDER_HEURES`). Le bot ne
  touche jamais aux autres messages du salon.
- Après un arrêt, il reprend ses cartes en cours et rattrape les lignes arrivées entre-temps.
- Un même bot peut servir plusieurs serveurs : chacun a son `#alertes-pvp`.
- Les cartes sont en français. Une version anglaise est prévue.

## Réglages

Tous facultatifs sauf le jeton. Dans `.env`, ou dans les variables d'environnement (Coolify, Docker).

| Variable | Par défaut | Rôle |
|---|---|---|
| `DISCORD_TOKEN` | — | le jeton du bot (obligatoire) |
| `BOT_MODE` | `journal` | `journal` : note seulement ; `repondre` : fait les cartes |
| `DISCORD_PVP_CHANNEL_NAME` | `alertes-pvp` | le salon des cartes, retrouvé ou créé par ce nom |
| `DISCORD_PVP_ROLE_NAME` | `pvp-police` | le rôle mentionné, retrouvé ou créé par ce nom |
| `BOT_INSTALLER` | `oui` | `non` : ne jamais créer de salon ni de rôle |
| `DISCORD_CHANNEL_ID` | vide | imposer le salon relié (sinon reconnu à ses messages du jeu) |
| `DISCORD_PVP_CHANNEL_ID` | vide | imposer le salon des cartes (le bot ne sert alors qu'un serveur) |
| `DISCORD_PVP_ROLE_ID` | vide | imposer le rôle mentionné |
| `BOT_SUPPRIMER` | `oui` | effacer la ligne brute du salon relié |
| `BOT_GARDER_HEURES` | `24` | délai avant d'effacer une carte finie (`0` : jamais) |
| `BOT_CARTES` | `oui` | `non` : cartes sans image de zone |
| `BOT_CARTES_PRODUIT` | `wowf` | `wowf` : WoW: Forever ; `wowt` : PTR de Retail ; `wow` : Retail |
| `BOT_CARTES_LANGUE` | `frFR` | langue des noms sur l'image (`enUS`, `deDE`, `esES`…) |
| `BOT_LOG` | `bot.log` | fichier du journal (`/app/state/bot.log` dans l'image) |
| `BOT_STATE` | `state` | dossier du cache des images (`/app/state` dans l'image) |

## Dépannage

| Le journal dit, ou vous voyez | Cause et remède |
|---|---|
| `PrivilegedIntentsRequired` au démarrage | Message Content Intent n'est pas activé (étape 1). |
| `salon … INTROUVABLE` | un identifiant imposé (`DISCORD_CHANNEL_ID`, `DISCORD_PVP_CHANNEL_ID`) que le bot ne voit pas : pas invité, ou pas le droit de voir ce salon. |
| aucune ligne `message du jeu` après un appel | le bot ne voit pas le salon relié (ses permissions), la guilde n'est pas en chat Discord séparé, ou l'appel n'a pas atteint Discord (en jeu, « Ton appel » dit où en est l'envoi). |
| `message du jeu` noté, mais aucune carte | `BOT_MODE` est encore à `journal`. |
| `pas de #alertes-pvp et pas le droit de gérer les salons` | réinvitez le bot avec le lien de l'étape 2, ou créez le salon vous-même. |
| `rôle pvp-police pas mentionnable, et le bot ne peut pas y toucher` | rendez le rôle mentionnable, ou glissez le rôle du bot au-dessus. |
| `suppression refusée`, la ligne brute reste | Gérer les messages manque au bot sur le salon relié. |
| `carte de zone … pas téléchargée` | wago.tools injoignable : la carte part sans image, nouvel essai 10 minutes plus tard. `BOT_CARTES=non` pour s'en passer. |

## Mettre à jour

- **Coolify** : *Redeploy*.
- **Docker** : `git pull`, `docker build -t worldpvppolicebot .`, puis `docker rm -f worldpvppolicebot`
  et la commande `docker run`.
- **PC** : `git pull`, `pip install -r requirements.txt` dans le `.venv`, et relancez.

## Ce que le bot lit et garde

- Il ne traite que les messages publiés par le jeu dans le salon relié ; il ignore tous les autres.
- Son journal garde ces lignes telles quelles (nom de l'appelant, zone, message).
- Il ne contacte que Discord et [wago.tools](https://wago.tools), pour les images de zone. Aucune donnée
  de joueur ne part chez wago.tools : seulement le numéro de la zone, le jeu et la langue.
- Aucune image du jeu n'est rangée dans ce dépôt ni dans l'image Docker.
