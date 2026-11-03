# Cartes « mercenaire » : appeler un tank ou un soigneur

> État : **brouillon** · Idée du user le 2026-11-03. R1 à R4 tranchées par lui (dans la spec de l'addon),
> puis B1 (salon à part) et les noms des rôles le même jour ; B2 à B7 proposées par l'agent, **à confirmer**. Rien de codé. La ligne lue ici est définie par la spec de
> l'addon, qui fait foi : `F:\AddonDevellopement\WorldPvPPolice\docs\specs\mercenaires.md`.

## Le problème

L'addon World PvP Police va savoir écrire dans le fil Discord de la guilde « je cherche un tank, ou un
soigneur ». Ceux qui veulent être appelés portent un rôle `Tank Mercenaire` ou `Heal Mercenaire`, pris
dans « Salons et rôles » comme `pvp-police`. Sans ce chantier, le bot ignore ces lignes : la ligne
brute reste dans le salon relié et personne ne sonne.

## Ce qu'on veut

1. **Une ligne `LFM` venue du jeu** devient une carte dans un salon dédié, `#mercenaires` par défaut.
   Le salon est trouvé ou créé par son nom, comme celui des alertes ; on peut aussi le régler avec
   `/setup salon-mercenaires` ou `DISCORD_MERC_CHANNEL_ID` (B1).
2. **La carte mentionne les rôles demandés** : `TANK` donne `@Tank Mercenaire`, `HEAL` donne
   `@Heal Mercenaire`, et les deux s'il le faut. On peut régler chaque rôle avec `/setup role-tank`,
   `/setup role-heal`, ou par les variables `DISCORD_TANK_ROLE_ID` / `_NAME` et `DISCORD_HEAL_ROLE_ID`
   / `_NAME` (B2). Noms cherchés par défaut : `Tank Mercenaire` et `Heal Mercenaire`, casse ignorée.
3. **La carte dit** : qui cherche (« Gnomi Ombrelune cherche un tank »), où (la zone de la ligne), le
   message, comment répondre (« En jeu : /w Gnomi Ombrelune », forme exacte selon MR1 de l'addon) et
   l'heure (celle de Discord).
4. **Le même appel revient** (même `#LFM<n>` moins de 30 minutes après sa **dernière** ligne) : la
   carte est modifiée, sans nouvelle mention. **`END … #LFM<n>`** : la carte passe en gris, « Trouvé ».
   **30 minutes sans ligne** de cet appel : elle passe en gris, « Expiré ». L'addon compte avec la même
   horloge. Une carte finie s'efface au bout de
   `BOT_GARDER_HEURES`, comme une carte d'appel PvP (P13).
5. **La ligne brute est effacée** du salon relié une fois la carte faite (`BOT_SUPPRIMER=oui`). Elle
   reste si la carte n'a pas pu se faire.

## Ce qu'on NE fait PAS

- **Pas d'image de zone**, et pas de carte par zone (P10 est propre aux appels PvP) : une carte par
  appel.
- **Pas de liste des mercenaires connectés** : la liste des protecteurs reste celle de `pvp-police`.
- **Pas de réponse sur Discord** (bouton, réaction) : le mercenaire chuchote en jeu (R4).
- **Pas de message privé** aux porteurs du rôle : la mention suffit.
- **Jamais `@everyone` ni `@here`**, jamais une mention tirée du texte du joueur : seuls les rôles
  réglés sont autorisés dans `allowed_mentions`.
- **Rien sur une ligne tapée sur Discord** : seulement les lignes venues du jeu.

## Cas particuliers

- **Un rôle absent** (aucun réglage, et aucun rôle de ce nom, casse ignorée) : il n'est **jamais
  créé** (B3). La carte part sans mention de ce rôle, et le journal comme `/setup voir` le disent.
- **Le même `#LFM<n>` avec d'autres rôles** (l'addon ne le fait pas, R8) : mise à jour ; la carte prend
  les rôles de la ligne, et un rôle pas encore mentionné sonne une fois (B5 s'applique).
- **Une mise à jour à la limite des 30 minutes** (envoyée à 29:59, reçue à 30:01) : elle devient un
  nouvel appel et une 2e carte, sans mention grâce à B5 ; la 1re expire seule.
- **Un rôle pas mentionnable** : la carte part, la mention ne sonne pas, et `/setup voir` donne le geste.
- **Le salon des mercenaires absent**, sans droit de le créer : la ligne brute reste.
- **Un même appelant qui rouvre un appel** (changement de rôles, R8 de l'addon) : un rôle déjà mentionné
  pour lui il y a moins de 10 minutes ne re-sonne pas ; seul le rôle nouveau sonne (B5).
- **`END` d'un appel inconnu** (le bot a redémarré entre-temps) : la carte est cherchée dans
  l'historique du salon, comme pour une carte PvP ; introuvable, la ligne est effacée sans rien faire.
- **Une ligne `LFM` refusée par la lecture** : rien n'est publié, la ligne brute reste.
- **`BOT_MODE=journal`** : on écrit seulement dans le journal, comme pour les appels PvP.
- **Le bot d'avant ce chantier**, et CraftingOrderBot : ils ignorent `LFM`, la ligne brute reste
  lisible. Le déploiement du bot et celui de l'addon se font dans n'importe quel ordre.
- **`/setup effacer`** accepte les trois nouveaux réglages.
- **Le fichier de réglages d'avant** : il se relit tel quel, puisque les nouveaux champs sont
  facultatifs et que `VERSION` ne bouge pas.

## Décisions

- **R1 à R4** (user, 2026-11-03) : voir la spec de l'addon. En bref : ici, dans World PvP Police ;
  `Tank Mercenaire` et `Heal Mercenaire` ; le mercenaire chuchote.
- **B1** (user, 2026-11-03) : **un salon à part**, `#mercenaires`, dans la ligne de P2 de
  `alertes-pvp.md` (un salon par sorte de sortie).
- **B2** (agent, à confirmer) : **un rôle par sorte d'appel**, avec ses réglages. Le `pvp_role`
  d'aujourd'hui ne change pas.
- **B3** (agent, à confirmer) : un rôle de mercenaire n'est **jamais créé** par le bot, il est trouvé
  par son nom (casse ignorée) ou réglé. Le user les crée dans « Salons et rôles » (R2) ; un nom un
  peu différent (`heal-mercenaire` avec un tiret, au lieu de `Heal Mercenaire`) ferait sinon un doublon, et un bot public ne doit
  pas poser sur le serveur d'une autre guilde des rôles qu'elle n'a pas demandés. C'est un écart
  voulu avec `pvp-police`, qui reste créé comme avant.
- **B4** (agent, à confirmer) : une mention seulement à la création de la carte (R7 de l'addon).
- **B5** (agent, à confirmer) : 10 minutes entre deux mentions du même rôle pour le même appelant.
- **B6** (agent, à confirmer) : 30 minutes de vie après la dernière ligne, comme un appel PvP, et
  comme l'addon le compte (R10).
- **B7** (agent) : le guide FR/EN (`bot/guide/`) décrit les nouveaux réglages dans la même branche ;
  son garde-fou (les tests) l'exige déjà pour une commande.

## Critères d'acceptation

1. [test] Les trois exemples du contrat de l'addon sont relus avec les mêmes champs, et figés comme
   ceux des SOS. → `tests/`
2. [test] Une ligne `LFM` n'est jamais lue comme un SOS, un OMW ou un END d'appel PvP, et l'inverse
   non plus.
3. [test] Nouvelle carte : la mention porte exactement les rôles demandés. Mise à jour : aucune
   mention, et l'horloge repart. `END` : carte grise. 30 minutes après la dernière ligne : carte grise
   « Expiré ». Un rôle absent : aucune création, carte sans sa mention.
4. [test] Un deuxième appel du même appelant pour le même rôle en moins de 10 minutes ne mentionne pas.
5. [test] `allowed_mentions` ne laisse passer que les rôles réglés, même si le message contient `@everyone`.
6. [test] Dans CraftingOrderBot, une ligne `LFM` est ignorée (même témoin que pour les SOS).
7. [test] Le garde-fou du guide : les nouvelles commandes de `/setup` y figurent en FR et en EN.
8. [human] Sur Discord : la carte arrive dans `#mercenaires` et le téléphone d'un porteur de
   `Tank Mercenaire` sonne. Témoin : une carte SOS du même jour. Observateur : le user.
9. [human] `/setup role-tank` puis `/setup voir` : on voit le rôle et d'où il vient. Observateur : le user.

## Contrat

Les lignes (copie ; c'est la spec de l'addon qui fait foi) :

```
LFM <Nom> <Rôles> <Zone> #LFM<n>[ : <message>]
END <Nom> #LFM<n>
```

`<Nom>` : `Prénom_Nom`, à relire avec une espace. `<Rôles>` : `TANK`, `HEAL`, `TANK,HEAL`. `<Zone>`
vaut `-` quand l'addon n'a pas pu la lire.

Les réglages par serveur gagnent trois champs facultatifs : `merc_channel`, `tank_role` et
`heal_role` (secours : `DISCORD_MERC_CHANNEL_ID`, `DISCORD_TANK_ROLE_ID`, `DISCORD_HEAL_ROLE_ID`). La
`VERSION` du fichier reste 1.

## Renvois

- `docs/specs/alertes-pvp.md` (P2 un salon par sorte, P13 nettoyage, heure de Discord),
  `docs/specs/reglages.md` (`/setup`), `docs/specs/guide.md`.
- GuildManagerBot compte `TANK` et `HEAL` par leur nom exact : les rôles de mercenaire ne comptent pas
  dans son #roster.

## Plan (2026-11-03) : provisoire, à supprimer une fois fait

Rien n'entre dans `main` avant que la bascule du lancement (4/11) soit faite et vue.

- **T3a** : lecture `LFM` / `END #LFM` (`bot/pvp_line.py` ou un module voisin), critères 1 et 2.
- **T3b** : cartes, mentions, expiration, nettoyage ; critères 3 à 5.
- **T3c** : `/setup` (trois réglages), `/setup voir`, guide FR/EN ; critères 7 et 9.
- **T3d** : le témoin dans CraftingOrderBot (sa propre branche), critère 6.
