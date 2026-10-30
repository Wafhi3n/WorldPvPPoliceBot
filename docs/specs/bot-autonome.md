# Un bot PvP autonome, que chaque guilde peut héberger

> État : **validée** le 2026-10-28 · Demande du user, mise en forme par l'agent · Décisions D1 à D6 du
> user (2026-10-28) ; A1 à A6 proposées par l'agent, **validées par le user le même jour** (« oui je
> valide »). La spec des cartes elles-mêmes
> (lecture des lignes, carte, mise à jour, mention, effacement, rattrapage) reste
> `docs/specs/alertes-pvp.md`, venue de CraftingOrderBot avec le code.

## Le problème

Les cartes d'appel de World PvP Police vivent aujourd'hui dans CraftingOrderBot, le bot privé des
commandes de Crafting Order (COC), avec ses données et ses réglages propres à une guilde. Une autre
guilde qui voudrait l'addon et ses cartes Discord ne peut rien en faire : il faudrait lui donner tout le
bot des commandes. Et au lancement, le user doit encore créer `#alertes-pvp`, le rôle et recopier trois
identifiants dans Coolify.

## Ce qu'on veut

- **Un bot à part**, World PvP Police Bot, dans son propre dépôt, que n'importe quelle guilde peut
  héberger (Docker, Coolify, ou un PC), avec un guide en français et en anglais.
- **Le moins de réglages possible** : un jeton, un lien d'invitation que le bot écrit lui-même ; il
  trouve ou crée sur le serveur ce dont il a besoin (`#alertes-pvp`, le rôle à mentionner, ses droits).
- **Plusieurs serveurs** si on l'invite sur plusieurs : chaque serveur a ses cartes dans son propre
  `#alertes-pvp`.
- **Les cartes de zone** téléchargées à la demande sur wago.tools (jamais d'image du jeu dans le dépôt).
- **Le bot des commandes** ne garde que les commandes de COC.

## Ce qu'on NE fait PAS

- **Pas d'instance publique** partagée par tout le monde : le contenu des messages est un « intent »
  privilégié de Discord ; au-delà de 100 serveurs, il faudrait la vérification de Discord. Chaque guilde
  héberge son bot (D2) ; plusieurs serveurs par bot restent possibles en dessous de cette limite.
- **Pas de bouton pour prendre le rôle** : les membres passent par « Salons et rôles » de la
  communauté Discord (D6).
- **Pas d'image de Blizzard dans le dépôt**, ni dans l'image Docker (D5).
- **Pas de commandes de COC** dans ce bot.

## Cas particuliers

- **Deux modules PvP sur le même salon relié** (pendant la bascule) : chaque appel ferait deux cartes et
  deux mentions. Interdit par l'ordre de la bascule (A6).
- **Le bot n'a pas le droit de créer un salon ou un rôle** : il le dit dans son journal, avec le lien
  d'invitation qui donne les bons droits, et continue sans cartes sur ce serveur.
- **Un rôle `pvp-police` au-dessus du rôle du bot** : Discord lui interdit d'y toucher (le rendre
  mentionnable) ; il le dit. S'il le crée lui-même, il est en dessous.
- **Le salon relié n'a reçu aucune ligne du jeu depuis longtemps** : rien à découvrir au démarrage ;
  il est reconnu à la première ligne du jeu qui arrive (A2).
- **wago.tools injoignable** : la carte part sans image ; nouvel essai à l'appel suivant (A4).

## Décisions

- **D1** (user, 2026-10-28, « il faudrait peut-être dissocier le bot PvP du bot de commande au cas où
  on veut partager ») — **Deux bots** : World PvP Police Bot pour les appels, CraftingOrderBot pour les
  commandes. Revoit **P5** de `alertes-pvp.md` (un seul bot) : la crainte de P5 (deux bots qui se
  marchent dessus dans le salon relié) ne tient pas, chacun ne lit et n'efface que SES lignes (le lecteur
  PvP refuse les `WTB … #CO<n>`, le lecteur de commandes ignore les `SOS`/`OMW`/`END` : testé des deux
  côtés).
- **D2** (user, 2026-10-28, « il faut que les gens puissent héberger leur propre bot ») — **Chaque
  guilde héberge le sien.**
- **D3** (user, 2026-10-28) — Nom **WorldPvPPoliceBot** ; licence **MIT**.
- **D4** (user, 2026-10-28) — Dépôt GitHub **privé**, rendu public **avec l'addon, au lancement** (après
  l'avoir vu sur Forever) ; README et guide **en français et en anglais**.
- **D5** (agent, découle de D4) — Aucune image du jeu versionnée : cartes de zone à la demande.
- **D6** (user, 2026-10-28) — Le rôle se prend par « Salons et rôles » de la communauté Discord ; le bot
  le crée (mentionnable), il ne le distribue pas.
- **A1** (agent, validée par le user le 2026-10-28) — **Le bot crée ce qui manque**, sur le serveur du salon relié, au
  démarrage : `#alertes-pvp` (nom réglable), en lecture seule pour les membres (ils lisent et
  réagissent, seul le bot écrit) ; le rôle `pvp-police` (nom réglable), mentionnable. Un identifiant
  mis dans la configuration reste prioritaire sur le nom.
- **A2** (agent, validée par le user le 2026-10-28) — **Le salon relié se reconnaît tout seul** : seuls les salons reliés au jeu
  reçoivent des messages du jeu (`is_from_game`). Au démarrage, le bot relit les derniers messages des
  salons qu'il peut lire (borné) pour retrouver le salon relié de chaque serveur, puis rattrape les
  lignes ratées ; en direct, une ligne d'appel venue du jeu dans un salon le désigne. `DISCORD_CHANNEL_ID`
  reste possible pour forcer un salon. Raison : sur Coolify, `/app/state` n'est pas un volume
  persistant (mesuré le 2026-10-10) ; rien de vital ne doit dépendre d'un fichier.
- **A3** (agent, validée par le user le 2026-10-28) — **Les droits** : le bot écrit dans son journal son lien d'invitation avec
  exactement voir, écrire, intégrer des liens, **joindre des fichiers** (l'image de la carte), lire
  l'historique, gérer les messages (effacer la ligne brute), gérer les salons et gérer les rôles (A1).
- **A4** (agent, validée par le user le 2026-10-28) — **Cartes de zone à la demande** : à la première ligne d'une zone, le bot
  télécharge `/api/map/{uiMapID}?version=<dernier build>&locale=<langue>&explored=1` sur wago.tools
  (dernier build du produit par `/api/builds/{produit}/latest`, produit `wowf` par défaut, `wowt` pour le
  PTR de Retail ; langue `frFR` par défaut), une requête par seconde au plus, dans son cache (`BOT_STATE`).
- **A5** (agent, validée par le user le 2026-10-28) — **Langue des cartes Discord** : le français d'aujourd'hui ; les libellés
  de la carte passent dans une table de traduction (anglais en plus) choisie par une variable.
- **A6** (agent, validée par le user le 2026-10-28) — **L'ordre de la bascule** depuis CraftingOrderBot :
  1. le nouveau bot tourne en `BOT_MODE=journal` (il regarde, ne fait rien) ;
  2. dans UNE même fenêtre de redéploiement, le user vide `DISCORD_PVP_CHANNEL_ID` de CraftingOrderBot
     (son module PvP s'éteint : critère 5 de `alertes-pvp.md`) et passe le nouveau en `repondre` ;
  3. ensuite seulement, le module PvP est retiré du code de CraftingOrderBot (en gardant le test qui
     prouve qu'il ignore une ligne `SOS`).

## Critères d'acceptation

1. [test] Les modules repris de CraftingOrderBot gardent leurs tests verts (critères 1 à 6, 9 de
   `alertes-pvp.md`) dans ce dépôt, sans rien importer du bot des commandes.
2. [test] Sur un faux serveur sans `#alertes-pvp` ni rôle, le bot les crée : le salon en lecture seule
   pour `@everyone`, écriture et fichiers pour lui ; le rôle mentionnable ; un identifiant configuré
   empêche toute création ; sans le droit, rien n'est créé et le journal le dit.
3. [test] Deux faux serveurs : une ligne d'appel du salon relié de l'un fait sa carte dans le
   `#alertes-pvp` de l'un, jamais de l'autre.
4. [test] Le salon relié est retrouvé au démarrage par ses messages du jeu, puis ses lignes ratées
   rattrapées ; un salon sans message du jeu n'est jamais pris pour le salon relié.
5. [test] La carte de zone se télécharge une fois (cache), au dernier build du produit ; wago.tools en
   panne = carte sans image, sans erreur.
6. [check] Aucune image (`.webp`, `.png`) versionnée ; l'image Docker ne copie que `bot/`.
7. [human] Sur le serveur de test du user : le bot invité par son lien, sans aucun identifiant dans sa
   configuration hors le jeton, **retrouve** `#alertes-pvp` et `pvp-police` (ils existent déjà sur Ost
   Ardent : la création ne s'y voit pas ; elle se voit sur un serveur neuf, ou en renommant le salon), et
   un appel en jeu y fait sa carte avec l'image de la zone. Témoin : la carte du bot des commandes d'avant
   la bascule.
8. [human] Après la bascule : un appel = UNE carte, UNE mention ; une commande de COC suit son chemin
   habituel dans `#commandes`.

## Contrat

- **Entrée** : le format de ligne de la spec de l'addon (`SOS`, `OMW`, `END`), inchangé
  (`docs/specs/alertes-pvp.md`, « Contrat »).
- **Configuration** (variables d'environnement, mêmes noms que l'ancien module pour la bascule) :
  `DISCORD_TOKEN` ; facultatifs `DISCORD_CHANNEL_ID`, `DISCORD_PVP_CHANNEL_ID`, `DISCORD_PVP_ROLE_ID`
  (prioritaires sur les noms), `BOT_MODE` (`journal` par défaut), `BOT_SUPPRIMER` (`oui` par défaut),
  `BOT_LOG`, `BOT_STATE` ; `DISCORD_PVP_CHANNEL_NAME` (`alertes-pvp`), `DISCORD_PVP_ROLE_NAME`
  (`pvp-police`), `BOT_INSTALLER` (`oui` : le droit de créer ce qui manque) ; `BOT_CARTES` (`oui`),
  `BOT_CARTES_PRODUIT` (`wowf`), `BOT_CARTES_LANGUE` (selon `BOT_LANGUE` : `frFR` ou `enUS`) ;
  `BOT_GARDER_HEURES` (`24`, 0 = jamais : P13) ; `BOT_LANGUE` (`fr` par défaut, ou `en` : A5).

## Renvois

- `docs/specs/alertes-pvp.md` : les cartes (P1-P9 ; P5 revue par D1).
- Addon : `WorldPvPPolice/docs/specs/appel-a-l-aide.md` (format de ligne, D11 à 30 minutes).
- wago.tools : `https://wago.tools/apis` (`/api/map`, `/api/builds/{produit}/latest`).

## Plan (2026-10-28) — volatile, meurt quand c'est fait

- **T1** — Dépôt, modules repris (`bot/pvp*.py`, `bot/game.py`), config et point d'entrée à un seul
  serveur, comme aujourd'hui ; tests verts (critère 1). FAIT le 2026-10-28 (53 tests).
- **T2** — Plusieurs serveurs, salon relié reconnu, installation par nom (critères 2 à 4). FAIT le
  2026-10-28 : `bot/install.py` (salon et rôle trouvés ou créés), `PvpRelay` par serveur (cartes et
  minuteurs rangés par serveur ; avec `DISCORD_PVP_CHANNEL_ID`, un seul serveur comme avant), sans salon
  imposé le bot écoute tous les salons et ne retient que les lignes d'appel venues du jeu ; au démarrage
  il relit les salons qu'il peut relire (pas les autres) pour rattraper. 62 tests ; 5 règles cassées :
  attrapées. Jamais vu sur Discord.
- **T3** — Cartes de zone à la demande (critère 5). FAIT le 2026-10-28 : `bot/map_store.py` (dernier
  build par `/api/builds/{produit}/latest`, carte par `/api/map/{id}?…&explored=1`, cache dans
  `BOT_STATE/cartes`, une requête par seconde, hors de la boucle du bot ; panne = pas d'image, nouvel
  essai 10 min plus tard) ; essai réel : Strangleronce de Forever 70658 en français, 1002×668. 68 tests ;
  4 règles cassées : attrapées.
- **T3 bis** — Une carte par zone et le salon qui se vide (P10 à P13 de `alertes-pvp.md`, user
  2026-10-28). FAIT le 2026-10-28 : `pvp_cards.py` (une carte = une zone, plusieurs appels ; verte quand
  tous sont réglés, grise sinon), `pvp_embed.py` (un champ par appel, pied `m<zone> · Prénom#n …`, relu
  après un redémarrage), `pvp_map.py` (un point par appelant, son prénom à côté), `pvp.py` (rejoindre la
  carte en cours de la zone, une mention par carte, cartes relues à la 1re rencontre d'un serveur,
  nettoyage toutes les heures, `BOT_GARDER_HEURES`). Trouvé en codant et corrigé : une carte restée
  « en cours » pendant l'arrêt, au même appel qu'une plus récente, n'était jamais grisée ni effacée.
  81 tests ; 7 règles cassées : attrapées. Rendu vérifié sur la vraie carte de Forever (deux prénoms).
- **T4** — README complet et guide d'hébergement FR/EN (application Discord, lien d'invitation, Docker,
  Coolify). FAIT le 2026-10-28 : `docs/hebergement.md` et `docs/hosting.md` (prérequis en jeu : chat
  Discord séparé ; intent « Message Content » ; `journal` puis `repondre` ; permissions du salon relié et
  d'un `#alertes-pvp` existant ; dépannage par les lignes du journal). Le lien d'invitation n'a plus que
  la portée `bot` (`invite_link`), et un test épingle le même entier de droits dans les deux guides.
  Adresse du dépôt laissée en blanc (`<adresse du dépôt>`) : il n'existe pas encore sur GitHub. Pas
  essayé : `docker build` (Docker Desktop éteint sur le fixe) ; Coolify le construira à la bascule.
- **T4 bis** — A5 : les libellés des cartes en français ou en anglais. FAIT le 2026-10-29 :
  `bot/labels.py` (une table par langue, classes des tueurs comprises), `BOT_LANGUE` (`fr` par défaut,
  `en`) ; les noms sur l'image de zone suivent la langue sauf `BOT_CARTES_LANGUE` (vide dans
  `.env.example`). La relecture d'une carte accepte TOUTES les langues : un changement de langue pendant
  une carte en cours ne perd rien, la carte est réécrite dans la nouvelle à sa mise à jour suivante ;
  accepté : les classes des tueurs, gardées en texte, n'y passent qu'à la ligne `SOS` suivante. Le pied
  ne dépend d'aucune langue ; le journal et les noms par défaut du salon et du rôle restent en français.
  Le français d'avant est épinglé au caractère près (`tests/cartes_fr.json`, relevé avant la table).
  97 tests ; 4 règles cassées : attrapées.
- **T4 ter** — Le journal en `repondre` (T3 de `appel-sans-pont-discord.md`, côté addon). FAIT le
  2026-10-30 : seules les lignes d'appel y restent ; en chat fusionné, tout le chat de guilde arrive dans le
  salon relié. Le guide suit, avec ce que la 1re installation réelle a appris (clé de déploiement, variables
  à créer à la main, identifiant collé à la place du jeton).
- **T5** — Bascule (A6), puis retrait du module PvP de CraftingOrderBot ; critères 7 et 8. Avant la
  bascule : relire les permissions du NOUVEAU bot dans le `#alertes-pvp` existant (il le retrouve par
  son nom et ne règle pas ses permissions : envoyer, intégrer des liens, joindre des fichiers). Les cartes
  de CraftingOrderBot déjà dans ce salon ne sont ni relues ni rejointes (le bot ne lit que les siennes ;
  `test_la_carte_d_un_autre_bot_jamais_rejointe`).
