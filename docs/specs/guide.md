# Le guide du bot, et sa pipeline de déploiement

> Statut : codé, jamais vu sur Discord (critères 4 et 5) · Demandé par le user le 2026-11-02 (le texte à modifier à chaque mise à jour, et une pipeline de déploiement) ; le reste posé par l'agent, à reconfirmer.

## Le problème

Les admins lisent sur Discord comment marche le bot. Un texte rangé ailleurs que dans ce dépôt finit par dire le faux : rien ne force à le changer avec le code. Et redéployer se fait à la main, sans passer par les tests.

## Ce qu'on veut

- **À chaque démarrage, le bot publie son guide** dans un salon de la catégorie réglée (`DISCORD_GUIDE_CATEGORY_ID`) : le code et son texte partent au même déploiement.
- **`tools/deploy.py`, depuis le PC** : vérifie `main`, lance les tests, pousse, demande à Coolify de reconstruire, attend la fin.

## Ce qu'on ne fait PAS

- **Créer la catégorie ou régler ses droits** : c'est à l'admin. Un bot n'a pas à ouvrir ni fermer une catégorie, ce dépôt étant hébergé par d'autres guildes.
- **Une commande** : ce bot n'en a aucune.
- **Une pipeline sur GitHub** : GitHub ne joint pas le Coolify du user, dont le port est fermé vers Internet.

## Cas particuliers

- **Pas de variable** : rien, ni salon, ni avertissement. Une guilde qui met à jour n'a rien à changer.
- **`BOT_MODE=journal`** : rien n'est publié.
- **Un redémarrage** : les messages sont modifiés, pas doublés. **Un guide raccourci** : ses messages en trop partent. **Le message de quelqu'un d'autre** : jamais touché.
- **Catégorie introuvable, droit manquant, refus de Discord** : le journal le dit ; les cartes n'en dépendent pas.
- **Un changement de `BOT_LANGUE`** : le guide passe dans l'autre langue au démarrage suivant.
- **Des tests en échec, une autre branche, un arbre sale, GitHub en avance** : `tools/deploy.py` ne pousse ni ne déploie rien.

## Décisions

- **G1** (user, 2026-11-02) — Le texte suit chaque mise à jour ; une pipeline de déploiement.
- **A1** (agent) — Chaque bot publie son propre guide, plutôt que tout depuis Guild Manager Bot, proposé au user et accepté par son « go ».
- **A2** (agent) — La pipeline part du PC, sur le modèle de `tools/redeploy.py` de CraftingOrderBot.
- **A3** (agent) — Le jeton Coolify reste à « read » + « deploy » : les journaux du bot ne sont pas lus par la pipeline, elle ne voit que l'état du déploiement.

## Critères d'acceptation

1. [test] Éteint sans variable ; publié sans doublon ; texte changé, message modifié ; message d'un autre intact ; chaque droit manquant dit. → `tests/test_guide.py`
2. [test] Chaque message tient dans la limite de Discord ; le guide ne cite que des réglages qui existent, les mêmes dans les deux langues. → `tests/test_guide.py`
3. [test] `tools/deploy.py` : rien n'est poussé si les tests échouent ; le jeton ne sort nulle part. → `tests/test_deploy.py`
4. [humain] Avec la variable et les droits posés, le salon `world-pvp-police` apparaît dans la catégorie ; un redéploiement n'y ajoute rien. Observateur : le user, sur Discord.
5. [humain] `tools/deploy.py` depuis le PC finit en `finished`, et le bot tourne sur le nouveau commit. Observateur : le user, sur Coolify.
