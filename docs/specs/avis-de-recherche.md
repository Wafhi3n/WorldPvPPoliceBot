# Avis de recherche : qui farme la guilde

> État : **brouillon** · 2026-10-30 · Idée de la guilde (Belledame, Atlânce), proposition du user ; la façon
> de compter vient de l'agent, acceptée par le « ok go » du user. **Rien n'est codé. Le seuil et la sortie du
> tableau attendent le user et Atlânce ; le code attend le lancement (4/11).**

## Le problème

Un joueur revient tuer les guildiens soir après soir. Chaque appel fait sa carte, et les cartes s'effacent au
bout de 24 heures : personne ne voit que c'est toujours le même, ni ne peut dire qui le chasser.

## Ce qu'on veut

- **Un tableau de chasse sur Discord** : le salon forum `wanted` (catégorie Commissariat), un post par joueur
  recherché, où les membres lisent sans écrire. Il dit le nom complet, la classe, la race si elle est connue,
  le nombre de morts, les victimes, les zones et la dernière fois.
- **Il se remplit tout seul** : le bot compte les morts par joueur à partir des appels ; passé un seuil, il
  ouvre le post et l'annonce une fois dans `#alerte-pvp`, à `pvp-police`.
- **Les officiers décident aussi** : une commande Discord ajoute ou retire un wanted (une personne, ou une
  guilde entière, écrite à la main).
- Le post suit : chaque nouvelle mort met le compteur à jour, sans nouvelle mention.

## Ce qu'on NE fait PAS

- **Pas de récap en jeu dans cette version** : rien ne redescend de Discord vers le jeu (S4 de
  `appel-sans-pont-discord.md` côté addon ; un bot est refusé dans le salon relié, code 20062). Une liste en jeu
  serait un autre chantier, partagée entre addons, et sans les wanted posés par commande.
- **Pas de comptage dans l'addon** : chaque copie ne voit que les morts de son joueur, et ne peut rien publier
  sans un clic.
- **Pas de commande en jeu** : ce serait une ligne dans le salon relié, que tout guildien peut écrire ; le bot
  n'a aucun moyen d'y reconnaître un officier.
- **Pas de post automatique sur une guilde** tant que la guilde du tueur n'est pas lisible (M15).
- **Pas de morts sans appel** : ce qui n'a pas fait de ligne n'existe pas pour le bot.
- **Pas de royaume** affiché (règle du user).

## Cas particuliers

- **Un même appel cite plusieurs tueurs, ou se met à jour** : une mort se compte une fois par joueur. La ligne
  donne le total des morts de l'appel : le bot compte ce qui s'ajoute, jamais le total à chaque ligne.
- **Le prénom seul** (une ligne d'avant D22, un récap sans nom de famille) : pas compté pour le seuil, deux
  joueurs seraient mélangés.
- **Fausse ligne** : un guildien peut écrire un `SOS` à la main. Exiger plusieurs victimes réduit le risque sans
  le supprimer ; le retrait par commande le répare.
- **Retiré, puis il recommence** : à trancher (Q3).
- **Le bot perd ses compteurs** : sous le seuil, ils ne vivent que sur le volume `/app/state`. Sans volume, le
  compte repart de zéro à chaque déploiement. Les posts ouverts, eux, se relisent sur Discord.
- **Un post à la main sur un joueur inconnu du bot** : il existe sans compteur, le premier appel le rejoint.
- **Le forum n'existe pas, ou le bot n'y a pas droit** : le journal le dit, les alertes continuent.

## Décisions

- **W1** (user, 2026-10-30) — Salon relié pour les données, `#alerte-pvp` et le rôle `pvp-police` pour
  l'alerte, forum `wanted` pour le tableau.
- **W2** (user, « ok go » sur la proposition de l'agent) — **Le bot compte**, pas l'addon. L'idée de départ du
  user (« l'addon va conserver les stats ») est écartée pour la raison ci-dessus.
- **W3** (même accord) — **Le nom complet dans la ligne** (D22 de `appel-a-l-aide.md`), fait d'abord.
- **W4** (même accord) — **Commandes Discord**, réservées à un rôle Discord : le jeu ne dit pas à Discord qui est
  officier. Le lien d'invitation change (portée `applications.commands`), et un bot déjà invité doit l'être à
  nouveau.
- **W5** (même accord) — **Ordre** : la bascule et l'alerte d'abord, le nom complet, puis le wanted après le
  lancement, quand de vraies morts permettront de régler le seuil.

## Questions ouvertes (au user et à Atlânce)

- **Q1 — Le seuil.** Proposé : 5 morts, sur au moins 2 guildiens, en 7 jours, réglable.
- **Q2 — La sortie du tableau.** Proposé : le post se ferme après 30 jours sans nouvelle mort, ou sur
  `/wanted retirer`.
- **Q3 — Retiré à la main, puis il recommence.** Proposé : le seuil repart de zéro à partir du retrait.
- **Q4 — Quel rôle Discord** a droit aux commandes ? Proposé : un rôle réglé par son nom, `BOT_WANTED_ROLE`.

## Mesures

- **M14** (`appel-a-l-aide.md`) — Le récap donne-t-il le nom complet sur Forever ? Sinon, pas de seuil.
- **M15** — La guilde et la race d'un tueur : `GetPlayerInfoByGUID` rend la race (source Forever et PTR, pas
  mesuré) ; la guilde, seulement avec une unité sous la main, peut-être jamais pendant une mort.
- **M16** — Le bot dans un forum : créer un post, le modifier, le fermer, avec quels droits. À essayer sur `wanted`.

## Critères d'acceptation

1. [test] Une suite de lignes (mises à jour, plusieurs tueurs, deux victimes) donne le bon compte par joueur ;
   rejouer une ligne n'ajoute rien ; un prénom seul ne compte pas.
2. [test] Le seuil franchi ouvre UN post et UNE annonce ; une mort de plus met à jour sans mention.
3. [test] Un redémarrage garde les compteurs (avec volume) et rejoint les posts ouverts.
4. [human] Sur Ost Ardent : un joueur tue assez de guildiens, le post apparaît dans `wanted`, l'annonce dans
   `#alerte-pvp`, une seule mention. Témoin : une carte d'appel ordinaire, qui n'ouvre aucun post.
5. [human] Un membre sans le rôle voit `/wanted ajouter` refusé ; un officier l'exécute et le post apparaît ;
   `/wanted retirer` le ferme.

## Renvois

- Addon : `WorldPvPPolice/docs/specs/appel-a-l-aide.md` (D15, D22, M14 ; sa ligne « Pas de liste d'ennemis »
  est à revoir quand ce brouillon sera validé) et `appel-sans-pont-discord.md` (S4).
- Ici : `alertes-pvp.md`, `bot-autonome.md`.

## Plan (2026-10-30) — volatile, meurt quand c'est fait

- **T1** — Le nom complet : fait sur `feat/wpp-nom-tueur` (addon, outillage) et `feat/nom-tueur` (bot).
- **T2** — M14 et M16 au lancement ; le user et Atlânce tranchent Q1 à Q4.
- **T3** — Le compte par joueur, sur le volume (critères 1, 3).
- **T4** — Le forum et l'annonce (critère 2, puis 4).
- **T5** — Les commandes Discord et le nouveau lien (critère 5), guide FR/EN.
