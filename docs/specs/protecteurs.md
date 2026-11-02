# La liste des protecteurs connectés

> État : **codée, jamais vue sur Discord** · 2026-11-02 · D1 à D3 du user ; A1 à A7 posées par l'agent, à reconfirmer.

## Le problème

Quand un guildien appelle à l'aide, personne ne sait d'un coup d'œil qui, parmi les porteurs de `pvp-police`, est là pour
répondre. Il faut ouvrir la liste des membres et filtrer à la main.

## Ce qu'on veut

Dans un salon désigné par son id (`caserne` sur le serveur du user, public), **un seul message** du bot, tenu à jour tout seul :

```
Protecteurs de <serveur>
3 connectés sur 12
@Untel @Unetelle @Machin
```

## Ce qu'on ne fait PAS

- **Dire qui est en jeu** : le bot ne voit que Discord. Le savoir demanderait que l'addon l'envoie : un autre chantier.
- **Notifier** : les @ ne font que nommer.
- **Créer le salon, ou donner le rôle** : l'admin crée le salon, les membres prennent le rôle.
- **Écrire un nom dans le journal** : il garde des nombres.

## Cas limites

- **Absent, Ne pas déranger** : connecté. **Invisible** : hors ligne, Discord ne dit pas la différence au bot.
- **Un jeu lancé, un passage en absent** : la liste ne bouge pas.
- **Un bot portant le rôle** : jamais compté.
- **Personne de connecté** : la liste reste, `0 connecté sur 12`.
- **Plusieurs changements d'affilée** : une écriture par fenêtre de 5 s. **Rien de changé** : aucune écriture.
- **Une liste trop longue pour Discord** : les derniers @ deviennent `+N`.
- **Le bot redémarre** : il retrouve son message par l'id gardé, sinon dans les 1000 derniers messages. Sans droit de relire, il ne publie rien.
- **Le message a été supprimé** : il est republié au prochain changement ou au prochain démarrage.
- **Le rôle est introuvable** : le journal le dit, et la liste affichée ne bouge plus.
- **L'id n'est pas un salon texte d'un serveur du bot** : le journal le dit, pas de liste. Mal collé (autre chose qu'un nombre) : le bot refuse de démarrer.
- **Les autres serveurs du bot** : pas de liste.
- **Le même salon que les cartes** : une carte n'est jamais reprise pour la liste, ni l'inverse, mais la liste s'y enfonce.
- **Intents éteints sur le portail** : le bot refuse de démarrer, et le journal nomme les trois intents.

## Décisions

- **D1 (user, 2026-11-02)** : les porteurs du rôle `pvp-police` (`DISCORD_PVP_ROLE_ID`) sont les protecteurs de la guilde, listés comme le tableau du roster de Guild Manager Bot.
- **D2 (user, 2026-11-02)** : le salon est désigné par une variable d'id ; sur son serveur, `caserne`, public.
- **D3 (user, 2026-11-02)** : seuls les membres connectés sont dans la liste.
- **A1 (agent)** : « connecté » = en ligne sur Discord, comme D9 du roster.
- **A2 (agent)** : le total des porteurs est aussi affiché, pour voir le manque (`3 connectés sur 12`).
- **A3 (agent)** : variable `DISCORD_PVP_PROTECTORS_CHANNEL_ID`. Vide, la liste est éteinte et les deux intents privilégiés ne sont pas demandés : une guilde qui met à jour son bot sans cette liste n'a rien à changer.
- **A4 (agent)** : le rôle est `DISCORD_PVP_ROLE_ID`, sinon celui du nom `DISCORD_PVP_ROLE_NAME`, même avec un id de salon.
- **A5 (agent)** : le salon étant public, le message peut s'enfoncer sous la conversation : son id est gardé dans `BOT_STATE/protecteurs.json`, avec l'historique en secours. Pas d'épingle : le droit manque au lien d'invitation, qu'on ne change pas pour ça.
- **A6 (agent)** : en `BOT_MODE=journal`, rien n'est publié ; seuls les nombres sont notés.
- **A7 (agent)** : le message se reconnaît à son auteur et au début de son titre, dans n'importe quelle langue (`BOT_LANGUE`).

## Critères d'acceptation

1. [test] Seuls les porteurs connectés sont listés, sans bots, par ordre alphabétique, le total à côté ; une liste trop longue tient dans la limite. → `tests/test_protectors.py`
2. [test] Un seul message : dix changements, une écriture ; rien de changé, aucune écriture ; retrouvé après un redémarrage, par l'id gardé ou l'historique ; ni carte d'appel ni message d'un autre bot repris. → `tests/test_protectors.py`
3. [test] Aucune notification, à l'envoi comme à la modification ; aucun nom au journal ; rien de publié en `journal`. → `tests/test_protectors.py`
4. [test] Sans la variable, aucun intent de plus. → `tests/test_protectors.py`
5. [humain] Avec les intents et la variable posés, la liste apparaît dans le salon, une seule. Témoin : la liste des membres de Discord, filtrée sur le rôle. Observateur : le user, sur Discord.
6. [humain] Un porteur du rôle se déconnecte de Discord : il quitte la liste en moins de 10 s, et le total ne bouge pas. Il revient quand il se reconnecte. Observateur : le user, sur Discord.
7. [humain] Les @ s'affichent en pseudos cliquables et non en `<@nombre>`, sur PC et sur téléphone, et personne n'est notifié. Observateur : le user, sur Discord.
8. [humain] Après un redéploiement, il reste un seul message, même après de la conversation dans le salon. Observateur : le user, sur Discord.

## Liens

- Hébergement : `docs/hebergement.md`, `docs/hosting.md`, étape 6.
- Modèle : `bot/board.py` de Guild Manager Bot.
