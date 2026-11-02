# World PvP Police Bot

Quand un guildien appelle à l'aide depuis le jeu, avec l'addon World PvP Police Guild, le bot en fait une carte sur Discord.

## Régler le bot : `/setup`

Réservé aux administrateurs. Si plusieurs bots proposent `/setup`, Discord affiche le nom de chacun : prends celui de World PvP Police. Commence par `/setup voir` : il montre chaque réglage et ce qui manque.

- `/setup salon-alertes` : le salon des cartes
- `/setup role` : le rôle mentionné à chaque nouvelle carte, et listé comme protecteurs
- `/setup categorie-guide` : la catégorie où publier ce guide
- `/setup effacer` : oublie un réglage posé ici, et revient à celui de l'hébergement

## La carte d'appel

La ligne que l'addon écrit dans le salon relié à la guilde devient une carte dans le salon des alertes : qui appelle, où, combien de morts, les tueurs, son message, qui arrive, et l'image de la zone avec un point.

- **Une carte par zone** : deux guildiens qui appellent dans la même zone la partagent.
- **Une mention par carte**, du rôle `pvp-police`, à son ouverture : un 2e appel dans la zone met la carte à jour sans refaire sonner le rôle.
- **Rouge** tant qu'un appel est en cours, **verte** quand tous sont réglés, **grise** après 30 minutes sans nouvelles.
- La ligne brute quitte le salon relié une fois la carte faite.
- Une carte finie est effacée 24 heures plus tard. Le bot ne touche jamais aux autres messages du salon.
- Après un arrêt, il reprend ses cartes en cours et rattrape les appels des 30 dernières minutes.

## Prendre le rôle

Le bot ne donne le rôle `pvp-police` à personne : les membres le prennent dans « Salons et rôles ». Pour que la mention sonne, le rôle doit être mentionnable.

## La liste des protecteurs

Si son salon est réglé, le bot y tient un seul message : les porteurs du rôle connectés, et leur total. « Connecté » veut dire en ligne sur Discord : le bot ne voit pas le jeu. Absent et Ne pas déranger comptent ; invisible compte comme hors ligne. Personne n'est notifié par ces @.

## Réglages sur l'hébergement

- `BOT_MODE` : `journal` note sans rien faire, `repondre` fait les cartes
- `DISCORD_PVP_PROTECTORS_CHANNEL_ID` : le salon de la liste des protecteurs ; il demande d'allumer Server Members Intent et Presence Intent sur le portail Discord, avant de la poser
- `DISCORD_PVP_CHANNEL_ID`, `DISCORD_PVP_ROLE_ID`, `DISCORD_GUIDE_CATEGORY_ID` : les mêmes réglages que `/setup`, qui l'emporte

## Si rien n'arrive

Une ligne d'appel qui n'apparaît pas dans le salon relié ne vient pas du bot : regarde « Ton appel » dans l'addon. Si elle apparaît sans carte : le bot est en `journal`, ou il n'a pas ses droits dans le salon des alertes. Son journal le dit.
