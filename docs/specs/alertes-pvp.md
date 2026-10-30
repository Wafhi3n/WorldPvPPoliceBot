# Bot Discord : cartes d'appel à l'aide PvP (World PvP Police Guild)

> État : **validée** le 2026-10-27 par le user (P1 à P9) · Demande du user, mise en forme par
> l'agent · Décisions P1 à P4 du user ; P5 à P9 proposées par l'agent, validées par le user le même
> jour. Le 2026-10-27, le user a décidé côté addon la zone seule (sa D14) et plusieurs tueurs (sa
> D15) : la carte et la lecture ci-dessous en tiennent compte (précisions de l'agent, à confirmer par
> le user). **Codé le 2026-10-28** (branche `feat/alertes-pvp` : `bot/pvp_line.py`, `bot/pvp_cards.py`,
> `bot/pvp.py`, critères 1 à 6 en tests), fusionné dans `main` (`e726d52`) et déployé le même jour pour
> un essai sur le Discord de test du user (salon relié #g, guilde du PTR de Retail) : **critères 7 et
> 8 vus le 2026-10-28 13:29-13:34** (carte, ligne brute effacée, mention qui notifie, même carte mise
> à jour) ; pas vu : le passage au gris. À refaire sur Forever avec la nouvelle guilde. Dépend de l'addon
> `WorldPvPPolice` (spec `F:\AddonDevellopement\WorldPvPPolice\docs\specs\appel-a-l-aide.md`, **source
> du format de ligne**), codé et vu sur le PTR de Retail le 2026-10-28, pas encore publié.
>
> **Déménagée le 2026-10-28** de CraftingOrderBot dans ce dépôt, World PvP Police Bot, avec son code
> (décision D1 du user : deux bots). Les mentions de CraftingOrderBot, de `#commandes` et de « ce bot »
> plus bas décrivent l'état d'avant le déménagement ; **P5 (un seul bot) est revue par D1** de
> `docs/specs/bot-autonome.md`, qui porte aussi l'installation par nom, les serveurs multiples et les
> cartes de zone à la demande (aucune image du jeu dans ce dépôt).

## Le problème

Au lancement de WoW: Forever (2026-11-04), la guilde du user part sur le royaume PvP, côté Alliance.
L'addon `WorldPvPPolice` écrira, à la mort d'un guildien tué par un joueur, une ligne d'appel dans le
fil Discord de la guilde :

```
SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d1 kXyz cROGUE : 3 voleurs au pont
```

Lisible, mais en jargon, noyée dans le chat de guilde, et sans notification pour qui n'est pas en
jeu. Le bot sait déjà lire le salon relié et y supprimer (commandes de COC, spec `bot-discord.md`).

## Ce qu'on veut

- **Une carte par appel** dans un salon dédié (`#alertes-pvp`) : qui appelle, la zone et les
  coordonnées (la zone seule quand la ligne n'en a pas), tués par qui (tous les tueurs de la ligne,
  jusqu'à 5, chacun avec sa classe si connue), combien de morts, le message, l'heure (relative), et la
  liste de ceux qui arrivent.
- **La carte se met à jour** au lieu d'en publier une autre : une mort de plus ou un nouveau message
  (`SOS` au même numéro ; depuis D18 de l'addon, 2026-10-28, un appelant en fantôme peut changer son
  message sans mourir : même nombre de morts, autre message), un guildien qui arrive (`OMW`), l'appel réglé (`END`, la carte passe au vert « réglé »),
  ou rien pendant 30 minutes (la carte passe au gris « terminé, sans nouvelles » ; P8). Les 30
  minutes comptent depuis la dernière ligne `SOS` : un « j'arrive » ne prolonge pas l'appel, comme
  dans l'addon (précisé par l'agent en codant, 2026-10-28).
- **La ligne brute disparaît** du salon relié une fois la carte faite (et donc du fil Discord en jeu).
- **Une notification** à ceux qui le veulent : la carte d'un NOUVEL appel mentionne un rôle Discord
  (« @Police », P6) ; une mise à jour ne mentionne personne.

## Ce qu'on NE fait PAS

- **Pas d'image de carte** en v1 (phase 2, voir plus bas).
- **Pas de regroupement d'une minute** comme pour les commandes (B8) : un appel part tout de suite.
- **Rien n'est écrit dans le salon relié** : impossible (erreur 20062, mesuré le 2026-10-10).
- ~~Pas de rattrapage au redémarrage~~ : **revu par le user le 2026-10-28** (« on pourrait pas
  reprendre les messages existants dans le #g et le canal PvP au cas où il y ait un redémarrage ou
  une mise à jour entre temps ? ») : voir « Après un redémarrage ». Les commandes de COC, elles, ne
  sont toujours pas rattrapées (proposé pour plus tard).
- **Pas de réponse aux messages tapés sur Discord** (seulement les lignes venues du jeu, `is_from_game`).
- **Jamais `@everyone` ni `@here`**, jamais une mention venue du texte d'un joueur.
- **Pas de nom de compte Discord** sur la carte : seulement le nom de personnage de la ligne.

## Cas particuliers

- **Ligne mal formée** (une ligne `SOS…` que la lecture refuse) : rien n'est publié, la ligne reste dans
  le salon relié, une entrée au journal.
- **`OMW` ou `END` d'un appel inconnu** (bot redémarré entre-temps) : la carte est cherchée dans les
  200 derniers messages du bot du salon (pied `#SOS<n> · <Perso>`, comme la carte barrée de COC) ;
  introuvable → ignoré, ligne brute supprimée quand même.
- **Même `OMW` deux fois** : un nom n'apparaît qu'une fois dans « en route ».
- **Échec d'envoi ou d'édition** de la carte : la ligne brute est GARDÉE (comme B9).
- **Texte du joueur** (message, noms) : échappé (mise en forme Discord, mentions) ; mentions envoyées
  avec `allowed_mentions` limité au seul rôle P6.
- **Variable `DISCORD_PVP_CHANNEL_ID` absente** : le module PvP est éteint, le bot fait le reste comme
  avant (aucune lecture des lignes `SOS`).
- **Deux persos du même prénom** : clé `Perso + n`, collision acceptée. Sur Forever, un nom complet est
  « Prénom Nom » et la ligne ne porte que le PRÉNOM (contrat de l'addon, 2026-10-27) : deux guildiens
  peuvent le partager, plus souvent qu'entre deux royaumes. Si leurs numéros d'appel se croisent dans
  la même fenêtre de 30 minutes, les deux appels écrivent sur la même carte. Rare dans une guilde ; si
  ça arrive au banc, l'addon peut ajouter une marque d'appelant en fin de ligne (évolution du contrat).
- **Un numéro déjà vu il y a plus de 30 minutes** (même perso, dernière ligne de la carte) : c'est un
  NOUVEL appel, donc une nouvelle carte. Le numéro vit dans les SavedVariables du poste du joueur
  (spec de l'addon, « Données sauvegardées ») : un autre poste, ou une base effacée, repart de
  `#SOS1`. Sans cette fenêtre, un nouvel appel mettrait à jour la carte grise d'un vieux. Un `OMW` ou un
  `END` vise la carte la plus récente de la clé. (Ajouté le 2026-10-27 par l'agent, en codant l'envoi
  de l'addon, T3.)
- **Classe inconnue** (`-` dans la liste `c`, ou pas de `c`) : ce tueur s'affiche sans classe. Un
  jeton inattendu, des listes `k`/`c` de longueurs différentes ou un `c` sans `k` : la ligne est mal
  formée (cas plus haut), comme la lecture de l'addon.
- **Ligne sans coordonnées** (zone seule, D14 de l'addon) : la carte montre la zone sans point ; en
  phase 2, pas d'image pour cet appel. Une mise à jour peut ajouter des coordonnées, ou passer à la
  zone seule d'une autre carte : la carte suit la dernière ligne.
- **Les tueurs changent d'une mise à jour à l'autre** (une équipe qui campe) : la carte montre la liste
  de la dernière ligne, telle quelle (l'addon la tient déjà à jour, les plus récents devant).
- **Après un redémarrage** (un redéploiement Coolify pendant un appel ; proposé par l'agent le
  2026-10-28, à confirmer par le user) : le bot ne garde rien en mémoire d'un démarrage à l'autre,
  mais sa carte porte tout (champs, pied `#SOS<n> · <Perso>`, heure de la dernière ligne). Une ligne
  `SOS`, `OMW` ou `END` d'un appel qu'il n'a pas en mémoire se cherche donc dans ses 200 derniers
  messages de `#alertes-pvp` : un `SOS` met à jour la carte trouvée si sa dernière ligne a moins de 30
  minutes (sinon nouvel appel, nouvelle carte), sans mentionner le rôle une 2e fois. Au démarrage, il
  relit ces mêmes messages : une carte encore « en cours » de plus de 30 minutes passe au gris, une
  plus récente reprend son compte à rebours. **Puis il rattrape les lignes ratées pendant l'arrêt**
  (user, 2026-10-28) : une ligne traitée est effacée du salon relié, donc une ligne `SOS`/`OMW`/`END`
  venue du jeu qui y est encore, et de moins de 30 minutes, a été ratée ; il les traite du plus ancien
  au plus récent, chacune à son heure. Sans effacement (`BOT_SUPPRIMER=non`), rien n'est rattrapé (on
  ne saurait pas lesquelles l'ont déjà été). Une ligne n'est jamais traitée deux fois (rattrapage
  puis arrivée en direct).
- **L'heure d'une ligne** est celle de Discord (`created_at` du message), pas celle du serveur du bot :
  le serveur Coolify retardait de 114 s le 2026-10-28, et la carte datait ses lignes 2 minutes trop
  tôt. L'écart est appris des messages qui arrivent et sert à compter les 30 minutes.
- **Deux lignes en même temps** (un `SOS` et un `OMW` qui se croisent) : traitées l'une après l'autre,
  jamais deux cartes pour un appel.

## Décisions

- **P1** (user, 2026-10-27) — Le bot traite les lignes de l'addon PvP et publie une carte lisible.
- **P2** (user) — Les sorties du bot vont dans des **salons dédiés**, un par sorte (« plusieurs
  canaux dédiés à l'addon ») : `#alertes-pvp` pour les appels, le salon actuel pour les commandes. En
  entrée, un seul salon : celui que la guilde a relié.
- **P3** (user) — La ligne brute est **supprimée** du salon relié (option `BOT_SUPPRIMER=oui`, étendue
  aux lignes `SOS`/`OMW`/`END`).
- **P4** (user) — Morts répétées : **la même carte se met à jour**.
- **P5** (agent, validée par le user le 2026-10-27) — **Le même bot** (CraftingOrderBot), un module de plus : un seul bot
  doit lire et supprimer dans le salon relié, deux bots s'y marcheraient dessus.
- **P6** (agent, validée par le user le 2026-10-27) — **Mention d'un rôle** à la carte d'un nouvel appel :
  `DISCORD_PVP_ROLE_ID`, vide = aucune mention. Le rôle s'attribue par chacun (ou par un officier) :
  celui qui ne veut pas de notification ne le prend pas.
- **P7** (agent, validée par le user le 2026-10-27) — **Une carte « embed »** (titre, champs, couleur) plutôt que du texte :
  le salon `#alertes-pvp` n'est pas relié au jeu, la réserve B5 (embed jamais vu en jeu) ne s'y
  applique pas.
- **P8** (agent, validée par le user le 2026-10-27 ; durée révisée par le user le 2026-10-28 avec la
  D11 de l'addon, « un appel doit vivre 30 min ») — **Expiration à 30 minutes** sans ligne, comme
  l'addon.
- **P9** (agent, validée par le user le 2026-10-27) — **Pas de lien Wowhead** sur une carte d'appel : rien à lier (pas
  d'objet) ; la zone en clair suffit.

## Phase 3 : une carte par zone, et le salon qui se vide (décidé et codé le 2026-10-28, jamais vu sur Discord)

Demandé par le user le 2026-10-28 : « ne pas mettre deux fois la même carte dans le canal, et mettre un
système pour nettoyer le canal ; si deux joueurs sont morts sur la même map, utiliser la même card ».
Raison donnée : « le but c'est que la guilde joue ensemble, donc deux personnes qui font un appel à
l'aide doivent être reliées ».

- **P10** (user) — **Une carte par ZONE en cours** : un appel dont la zone (`m<uiMapID>`) a déjà une
  carte en cours sur ce serveur rejoint cette carte, au lieu d'en ouvrir une autre. « En cours » = au
  moins un de ses appels l'est encore (30 minutes, D11 de l'addon). Pas de critère de distance : même
  zone suffit (choix du user).
- **P11** (user) — **Une seule mention du rôle par carte** : le 1er appel d'une zone mentionne le rôle ;
  un 2e appelant qui rejoint la carte la met à jour sans nouvelle notification.
- **P12** (user) — **Jamais deux fois la même carte dans le salon** : un appel, ou une zone en cours, n'a
  qu'une carte, y compris après un redémarrage (la carte se retrouve dans l'historique, P5 bis) et quand
  deux lignes se croisent (verrou).
- **P13** (user) — **Le salon se vide tout seul** : une carte finie (réglée, ou terminée sans
  nouvelles) est effacée **24 heures** après sa fin ; réglable (`BOT_GARDER_HEURES`, 0 = jamais).
  Le bot n'efface que SES cartes.
- **P14** (user, 2026-10-30, après la carte « 2 guildiens » de Palrien n°13 + n°14 au PTR) — **Un guildien n'a
  qu'un appel en cours** : l'addon n'en ouvre qu'un à la fois, donc une ligne `SOS` sous un autre numéro
  remplace les appels encore en cours de ce guildien, comme `Alert:OnSOS` côté addon (le dernier arrivé
  compte, même avec un numéro plus petit : un autre poste repart de 1). Sur la carte que le nouvel appel
  rejoint, l'ancien disparaît, avec son « en route » ; sur la carte d'une autre zone, il passe « réglé ». Une
  ligne `OMW` ou `END` de l'ancien numéro, arrivée après, est ignorée.
- Précisé par l'agent, à confirmer au banc :
  - **la carte** montre chaque appelant sur sa ligne : prénom, morts, numéro, tueurs, message, qui arrive
    vers lui ; un appel réglé reste affiché « réglé » tant que la carte vit ; la carte passe au vert quand
    TOUS ses appels sont réglés, au gris quand le dernier en cours expire ;
  - **l'image** de la zone porte un point par appelant (le prénom à côté) ; des points qui se touchent
    empilent leurs prénoms en colonne, tous lisibles (vu au PTR le 2026-10-30) ;
  - un `OMW` ou un `END` va à la carte qui contient cet appel (appelant + numéro) ;
  - un appel déjà sur une carte y reste, même si sa ligne suivante vient d'une autre zone (sa position y
    est mise à jour) : jamais un même appel sur deux cartes ;
  - le titre : « Palrien appelle à l'aide ! » pour un joueur, « 2 guildiens appellent à l'aide » au-delà (des
    joueurs, pas des appels : un appel réglé et son rappel font un seul guildien),
    avec le nom de la zone. Ces libellés sont ceux du français ; en anglais (`BOT_LANGUE=en`, A5 de
    `bot-autonome.md`), « Palrien is calling for help! », « call #8 », « Where: … · Deaths: … ».
- Côté addon, le même but (« jouer ensemble ») demande un bouton pour monter un groupe ou un raid avec
  ceux qui répondent : décision de l'addon (sa D21), pas du bot.

11. [test] Deux appelants dans la même zone : UNE carte (un envoi), deux lignes, une mention, une image
    à deux points ; un appel dans une autre zone : une autre carte.
12. [test] `END` de l'un : sa ligne « réglé », la carte toujours en cours ; `END` des deux : verte ; le
    dernier appel en cours qui expire : grise.
13. [test] Une carte finie depuis 24 heures est effacée ; jamais une carte en cours, jamais le message
    d'un autre ; `BOT_GARDER_HEURES=0` : jamais.
14. [test] Après un redémarrage, la carte de zone se relit avec tous ses appels, et un nouvel appel de
    la zone la rejoint (pas de 2e carte).
15. [human] Au banc : deux comptes appellent depuis la même zone ; une carte, deux points, UNE
    notification. Témoin : un 3e appel depuis une autre zone fait sa propre carte.
16. [test] (P14) Le même guildien rappelle : même zone, l'ancien appel disparaît, un seul « C'est réglé »
    rend la carte verte, les autres guildiens restent ; autre zone, l'ancien passe « réglé » ; une ligne
    tardive de l'ancien numéro ne change rien ; pareil après un redémarrage.
17. [human] (P14) Au banc : A appelle, clique « C'est réglé » alors que la ligne de fin ne peut pas partir
    (case « séparer » décochée entre-temps), puis rappelle : la carte n'affiche que le dernier appel, sous
    son prénom, et passe au vert au clic suivant.

## Phase 2 : l'image de la carte (codée le 2026-10-28)

L'idée du user : une image de la zone avec un point sur le cadavre. Demandée le 2026-10-28 (« on
prépare une belle carte aussi si possible »), avec deux images fournies par le user : la carte de
Strangleronce septentrionale de Retail (1000×668, celle du PTR) et celle de Strangleronce vanilla
(1002×668, celle de Forever), « car la carte est différente entre Forever et Retail ».

- **Une image par carte de zone**, dans `data/maps/` du dépôt (privé : images de Blizzard, usage de
  fan), indexée par l'`uiMapID` de la ligne dans `data/maps/maps.json`.
- **Les images sont celles du jeu** (demande du user le 2026-10-28, piste wago.tools trouvée par lui) :
  `tools/fetch_maps.py` les assemble depuis wago.tools, qui sert les fichiers et les tables du jeu
  build par build, Forever compris (`wowf` 1.60.1.x), en français (`locale=frFR`) : la toile
  (1002×668), les tuiles et les surcouches d'exploration (carte entièrement explorée). Les zones par
  défaut = celles de Kalimdor et des Royaumes de l'Est dans la table `UiMap` du build (49 sur Forever
  70658). Confirmé par cette table : Strangleronce = **1434** sur Forever. Une requête par seconde, un
  cache local. Les deux images fournies à la main par le user (wiki, 2026-10-28) sont remplacées.
- **Le point** : l'image est la toile entière de la carte du monde en jeu, donc pixel = `x × largeur`,
  `y × hauteur` (x, y de la ligne en fractions). Un disque rouge cerclé de blanc. **Vu juste** sur une
  vraie mort du PTR (39.8, 55.5), au sud-est de Grom'gol : « le point est au bon endroit » (user,
  2026-10-28, avec l'image du wiki ; une image du jeu est la toile exacte).
- **Dans la carte** : l'image (JPEG) est jointe au message et affichée dans l'embed. Elle est
  redessinée à chaque modification (le point a pu bouger) ; une ligne sans coordonnées (zone seule)
  ou une zone sans image : pas d'image, et une vieille image est retirée.
- **Après un redémarrage** : le nom du fichier porte la carte et le point (`sos-m50-397-554.jpg`, en
  millièmes) ; une carte relue dans l'historique sait redessiner son image.
- Pas d'image tant qu'une zone n'a pas la sienne : une zone de plus = `tools/fetch_maps.py --version
  <build> --maps <id>`. Après une mise à jour du jeu qui change une carte (rare), relancer l'outil
  avec le nouveau build.

9. [test] Le point se place en fractions de l'image ; le nom du fichier porte la carte et le point,
   et se relit ; pas d'image sans coordonnées ni pour une zone inconnue ; l'image part avec la carte
   et une vieille image est retirée quand la ligne n'a plus de coordonnées. → `tests/test_pvp_map.py`
10. [human] Sur Discord, la carte d'un appel montre l'image de la zone avec le point là où le perso
    est mort. Témoin : le user sait où il est mort (et l'a vu sur sa carte en jeu).

## Critères d'acceptation

1. [test] Les six exemples de la spec de l'addon (`SOS` d1, `SOS` d3, `OMW`, `END`, `SOS` en zone
   seule, `SOS` à trois tueurs dont une classe `-`) sont relus en champs exacts ; une ligne
   `WTB … #CO<n>` n'est pas lue comme un appel, une ligne `SOS` pas comme une commande ; `c` sans `k`
   et listes mal alignées sont refusés.
2. [test] Un message avec `@everyone`, `<@&123>`, `**gras**` s'affiche échappé, et l'envoi n'autorise
   aucune mention hors du rôle P6.
3. [test] Une suite `SOS d1` → `OMW` → `SOS d3` → `END` produit UNE carte, éditée trois fois, finale :
   3 morts, 1 en route, « réglé ».
4. [test] Une carte sans ligne pendant 30 minutes passe à « terminé, sans nouvelles ».
5. [test] Sans `DISCORD_PVP_CHANNEL_ID`, une ligne `SOS` ne produit rien et n'est pas supprimée.
6. [test] Envoi de la carte en échec : la ligne brute n'est pas supprimée.
7. [human] Au banc, après le lancement : un appel du compte A fait apparaître sa carte dans
   `#alertes-pvp` en moins de 5 secondes, avec le nom du perso de A ; la ligne brute disparaît du
   salon relié. Témoin : une commande de COC, qui suit son chemin habituel. Observateur : le user.
   La carte nomme TOUS les tueurs de la ligne (avec leur classe) ; une ligne en zone seule donne une
   carte avec la zone et sans coordonnées.
8. [human] Le rôle P6 sonne sur le téléphone d'un membre qui l'a, pas d'un membre qui ne l'a pas.

## Contrat

- **Entrée** : le format de ligne de la spec de l'addon (`SOS`, `OMW`, `END`) fait foi ; ce bot le
  relit sans l'étendre. Les exemples de la spec sont figés dans les tests (critère 1) : une évolution
  de l'addon ajoute des champs en fin de ligne, et un test prouve que l'ancienne forme se lit encore.
  Exception datée : le 2026-10-27, avant tout code des deux côtés, la v1 a reçu les coordonnées
  facultatives et les listes de tueurs ; les exemples d'avant n'ont pas changé d'un octet :

  ```
  SOS Gnomi Forêt d'Elwynn #SOS8 m1429 d1 kXyz cROGUE
  SOS Gnomi Forêt d'Elwynn (42.1, 65.3) #SOS7 m1429 d3 kXyz,Abc,Def cROGUE,MAGE,- : 3 voleurs au pont
  ```

  Lecture : couper la queue au ` #SOS`, puis détacher ` (<x>, <y>)` en fin de zone s'il y est ; une
  parenthèse restée dans la zone = ligne refusée. `k` et `c` : deux listes séparées par des virgules,
  alignées (autant de classes que de noms, `-` = inconnue). Découper sans perdre un élément vide
  (`kXyz,,Abc` doit être refusé, pas lu comme deux noms).
- **Configuration** (Coolify, changée par le user dans l'interface : le jeton read+deploy ne le peut
  pas) : `DISCORD_PVP_CHANNEL_ID` (salon des cartes), `DISCORD_PVP_ROLE_ID` (facultatif). Droits du
  bot sur `#alertes-pvp` : voir, envoyer, intégrer des liens, lire l'historique ; « Gérer les messages »
  sur le salon relié (déjà requis par `BOT_SUPPRIMER`).

## Renvois

- `docs/specs/bot-discord.md` (lecture du salon relié, `is_from_game`, 20062, B5, B8, B9, B10).
- Skill public `wow-addon-dev:wow-forever-api`, `chat-channels-and-communities.md` (ce qu'un bot peut
  et ne peut pas faire dans un salon relié).

## Plan (2026-10-27) — volatile, meurt quand c'est fait

- ~~**B-T1** — `bot/pvp_line.py` : lecture des trois formes (critère 1).~~ Fait le 2026-10-28
  (copie de `Line.Parse` de l'addon ; `tests/test_pvp_line.py`, avec deux vraies lignes du PTR).
- ~~**B-T2** — `bot/pvp_cards.py` : rendu de la carte, échappement, état (2, 3, 4).~~ Fait
  (`tests/test_pvp_cards.py`).
- **B-T3** — ~~Branchement (salon PvP, suppression, rôle) (5, 6)~~ fait dans `bot/pvp.py`, appelé par
  `__main__` avant le chemin habituel (`tests/test_pvp_relay.py`). Déployé le 2026-10-28, critères 7
  et 8 vus sur le Discord de test. Reste : au lancement, les ids de la nouvelle guilde dans Coolify
  (`DISCORD_CHANNEL_ID`, `DISCORD_PVP_CHANNEL_ID`, `DISCORD_PVP_ROLE_ID`), puis les revoir sur Forever.
  Vu en passant : l'horloge du serveur Coolify retardait de 114 s (2026-10-28 13:36) ; la carte datait
  alors ses lignes 2 minutes trop tôt.
