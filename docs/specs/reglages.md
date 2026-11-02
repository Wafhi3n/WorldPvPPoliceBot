# Réglages par commande : `/setup`

> Statut : codé, jamais vu sur Discord (critères 5 à 8) · Demandé par le user le 2026-11-02 (« un /setup au lieu de Coolify », et le faire avant le lancement du 4/11) ; le reste posé par l'agent, à reconfirmer. Remplace A3 de `bot-autonome.md` sur un point : le lien d'invitation porte maintenant les commandes.

## Le problème

Chaque salon, chaque rôle passe par une variable d'hébergement : ouvrir Coolify, copier un id, redéployer. Une guilde qui héberge son bot paie ça à chaque changement, et une variable vaut pour tous ses serveurs alors qu'un id n'en désigne qu'un.

## Ce qu'on veut

`/setup`, pour les administrateurs : poser le salon des cartes, le rôle mentionné et la catégorie du guide depuis Discord, serveur par serveur, sans redéployer. `/setup voir` montre chaque réglage, d'où il vient, et ce qui manque.

## Ce qu'on ne fait PAS

- **La liste des protecteurs** : ses intents sont privilégiés, et décidés au démarrage. Un réglage posé par commande les allumerait au redémarrage suivant : sur un portail où ils sont éteints, Discord refuserait la connexion, **cartes d'appel comprises**. Elle reste sur l'hébergement.
- **Le jeton, `BOT_MODE`, la langue, les images de zone** : un secret, un garde-fou, et ce qui ne change pas d'un serveur à l'autre.
- **Le salon relié** : il se reconnaît à ses messages du jeu.
- **Toucher à la logique des cartes** : seul le choix du salon et du rôle change.

## Cas particuliers

- **La variable posée, un seul serveur** : comme avant, sans rien refaire. Pas de rattrapage ailleurs que `DISCORD_CHANNEL_ID`, rien de créé.
- **La variable posée, un second serveur** : **changement** ; ses lignes allaient jusqu'ici dans le salon de la variable. Il a maintenant le sien : celui de `/setup`, sinon trouvé ou créé par son nom à sa première ligne (`BOT_INSTALLER=non` l'empêche). Au démarrage, il n'est pas installé pour rien.
- **La variable du salon sans celle du rôle** : **changement** ; le rôle est maintenant trouvé par son nom, sans être créé. Avant, plus personne ne sonnait, sans aucune trace (carte vue sans mention le 2026-11-02).
- **Un salon posé par commande puis supprimé** : rien n'est créé, la ligne brute reste, le journal et `/setup voir` le disent.
- **Changer de salon** : les nouvelles cartes vont dans le nouveau. Les cartes en cours finissent dans l'ancien, et ses cartes finies ne s'effacent plus toutes seules : à supprimer à la main.
- **Un bot démarré sans salon, réglé ensuite** : il marche dès la commande, nettoyage compris.
- **`@everyone` comme rôle** : refusé, tout le serveur sonnerait à chaque appel. **Un rôle géré** : refusé. **Un rôle pas mentionnable** : gardé, et la réponse donne le geste.
- **Un non-administrateur à qui un serveur a ouvert la commande** : refusé par le bot.
- **`BOT_MODE=journal`** : `/setup` n'écrit que dans son fichier, et le guide n'est pas publié.
- **Un fichier de réglages illisible** : mis de côté, retour aux variables, et le journal le dit.
- **Une variable dont l'élément est sur un autre serveur** : rien à régler ici, ni au journal, ni dans `/setup voir`.
- **Deux bots avec `/setup`** : Discord affiche le nom de chacun ; les guides le disent.

## Décisions

- **G1** (user, 2026-11-02) — Un `/setup` plutôt que Coolify ; tout de suite, avant le lancement.
- **A1** (agent, à reconfirmer) — Réservé au propriétaire et aux administrateurs, relu à chaque geste.
- **A2** (agent, à reconfirmer) — La commande l'emporte, la variable reste le secours.
- **A3** (agent) — La liste des protecteurs reste sur l'hébergement : aucun réglage posé par commande ne doit pouvoir empêcher le bot de démarrer.
- **A4** (agent) — Une variable ne vaut que pour le serveur de son salon, comme sur Guild Manager Bot.
- **A5** (agent) — Les noms des commandes restent en français, comme les valeurs des réglages ; les réponses suivent `BOT_LANGUE`.

## Contrat

`state/reglages.json` garde, par serveur : `pvp_channel`, `pvp_role`, `guide_category` (des ids). Le fichier porte un numéro de version et s'écrit de façon atomique.

## Critères d'acceptation

1. [test] La commande l'emporte, sur son serveur seulement ; effacer revient à la variable ; un fichier illisible est mis de côté. → `tests/test_setup.py`
2. [test] La variable sur un seul serveur marche comme avant ; deux serveurs lisent chacun leur salon et leur rôle ; changer de salon vaut sans redémarrer. → `tests/test_setup.py`
3. [test] Un non-admin est refusé à chaque commande ; `@everyone` et un rôle géré sont refusés ; Discord ne propose que le bon type de salon ; la liste des protecteurs n'y est pas. → `tests/test_setup.py`
4. [test] Le guide cite exactement les commandes de `/setup`. → `tests/test_guide.py`
5. [humain] Après le redéploiement et le lien rouvert, `/setup voir` montre les réglages actuels avec l'origine « variable », et un appel fait toujours sa carte, avec sa mention, sans rien refaire. Observateur : le user, sur Discord.
6. [humain] `/setup salon-alertes` : l'appel suivant va dans le nouveau salon, sans redéployer. Observateur : le user, sur Discord.
7. [humain] `/setup categorie-guide` publie le salon `world-pvp-police` tout de suite ; un redéploiement n'y ajoute rien. Observateur : le user, sur Discord.
8. [humain] Un compte qui n'est pas administrateur ne voit pas `/setup`. Observateur : le user, sur Discord.

## Renvois

- `guide.md`, `bot-autonome.md`, `alertes-pvp.md`.
