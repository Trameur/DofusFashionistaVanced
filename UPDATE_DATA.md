# Mettre à jour les données

Depuis le dépôt, avec le Python qui fait déjà tourner les scripts `update_data_*.py` :

```powershell
py update_all.py
```

Le lanceur affiche pour chaque jeu la version locale, celle du client Ankama et
celle réellement importable. Répondre avec les numéros ou noms des versions
(`1,4`, `dofus3,touch`), `changed` pour celles qui ont changé, ou `all` pour les
cinq versions de Dofus. Wakfu est disponible avec `6` ou `wakfu` et reste un
choix explicite, car il est expérimental. Choisir ensuite avec ou sans images
pour chaque version, puis confirmer. Entrée sans sélection quitte le programme.

Les anciens scripts restent utilisables directement ; le lanceur réutilise leurs
étapes et leurs arguments. Le terminal affiche chaque étape avec son titre en
français et sa durée, avec un rappel toutes les 30 secondes pendant une opération
longue. Le numéro d'étape affiché est celui du journal
(`dofus3-05-items-obtainment.log` pour « Dofus 3 | 05 »).

## Commandes

```powershell
py update_all.py --list
py update_all.py --dry-run --versions dofus3,beta --images no
py update_all.py --versions dofus3,touch --images yes --yes
py update_all.py --restore .update-reports\<dossier>
py update_all.py --restore .update-reports\<dossier> --versions beta
py update_all.py --clean-reports
```

`--list` et `--dry-run` consultent les sources sans rien modifier. `--list`
donne aussi la place prise par `.update-reports`. `--dry-run` annonce la taille
et la durée de la sauvegarde des images, la place libre, les bases ouvertes par
un autre programme et un import interrompu à restaurer. `--yes` exige des choix
explicites pour les versions et les images. `--restore` et `--clean-reports` sont
décrits plus bas. Aucun mode ne fait de commit, de push ni de déploiement.

## Déroulement

Avant tout import, le lanceur refuse de partir si une base à remplacer est ouverte
par un autre programme (serveur de développement, DB Browser...) et nomme le
fichier. Sous Windows, une base simplement ouverte suffit à bloquer son
remplacement. Il refuse aussi de partir tant qu'un import arrêté en cours de
route n'a pas été restauré (voir « Arrêt brutal »).

Chaque version est traitée seule, l'une après l'autre :

1. vérification que la source n'a pas changé depuis le choix ;
2. inventaire avant import et sauvegarde de ses fichiers : base, dump,
   `spell_reference`, `spell_states`, `transformed_wakfu.json` pour Wakfu,
   `retro_damage_spells.json` pour Dofus Retro, et les fichiers partagés tels
   qu'ils sont à ce moment (`fashionista_version.py`, `dynamic_translations.py`,
   `dofus_constants*.py`) ;
3. relevé des fichiers JSON suivis par git sous `itemscraper/` (voir
   « Fichiers intermédiaires ») ;
4. import par son script `update_data*.py` ;
5. inventaire après import et contrôle des données.

Si tout passe, l'étiquette de la version dans `fashionista_version.py` et son
entrée dans `.update-reports/state.json` sont écrites tout de suite. Quand un
nouveau patch commence, son entrée `PATCH_TIMELINE` est ajoutée et le terminal
le dit. Pour Dofus Touch et Dofus Retro, les repères `WATCHED_*` du même fichier
(paquet de ressources Touch, build, langues et empreinte des images Retro) prennent
les valeurs de la source importée, pour que `itemscraper/check_game_versions.py`
compare la même chose que le lanceur. L'empreinte des images Retro ne change que si
les images ont été importées. Si l'import ou le contrôle échoue, seule cette version est restaurée et
le lanceur passe à la suivante. Si cette restauration reste incomplète (fichier
bloqué), le lanceur s'arrête : les versions suivantes sont marquées `NON LANCÉ`
avec la cause, et les tests ne sont pas lancés. Ctrl+C restaure la version en
cours puis s'arrête.

Les étapes réseau (téléchargements, miroir, scraping, `data/sets`, `data/spells`,
images) sont relancées une fois après 20 secondes si elles échouent ; le journal
de la première tentative est gardé à côté (`.essai-1.log`). Une étape qui dépasse
son délai n'est pas relancée. Les autres étapes ne sont jamais relancées.

## Images

Si au moins une version télécharge des images, les dossiers d'images de
`fashionsite/chardata/static` sont sauvegardés une fois au début. La copie de
`staticfiles` n'est pas sauvegardée : elle n'est pas lue en local et
`collectstatic` la refait au déploiement. Avant cette sauvegarde, le lanceur
vérifie que le disque a 1,2 fois sa taille de libre, sinon il refuse de partir et
donne les deux chiffres.

Quand une version échoue, seules les images qui étaient lisibles avant elle et
qui sont devenues absentes ou illisibles sont remises depuis cette sauvegarde.
Les images nouvelles ou mises à jour restent en place : elles viennent des
sources d'Ankama. Les images des versions non choisies sont contrôlées de la même
façon à la fin.

## Fichiers intermédiaires

Les imports réécrivent des fichiers JSON suivis par git sous `itemscraper/`
(`transformed_equipment.json`, `all_*.json`, `touch_raw/`...). Avant chaque
version, le lanceur copie ceux qui étaient déjà modifiés localement et note la
taille et la date de tous les autres. Quand la version est restaurée, chaque
fichier qu'elle a changé revient : depuis la copie s'il était déjà modifié, sinon
par `git checkout HEAD -- <fichier>`. Un fichier changé ensuite par une version
suivante est gardé et listé. Les fichiers de code (`.py`) ne sont jamais touchés,
pour ne pas perdre une modification faite pendant l'import.

## Contrôles après les imports

Lancés seulement si au moins une version a été importée et qu'aucune restauration
n'est incomplète :

1. génération réelle d'un Iop terre niveau 50 dans chaque version de Dofus (et
   contrôles du solveur Wakfu si Wakfu est choisi). Si une version importée ne
   peut plus générer de build, ses données sont restaurées, puis la génération
   est relancée une fois : ce qui échoue encore est à revoir ;
2. contrôle des données d'armes (`check_version_weapon_data.py`) ;
3. suite Django complète avec `--settings=fashionsite.settings_test`.

Un échec des deux derniers ne restaure rien : les données restent, le statut
devient `IMPORTÉ, TESTS À REVOIR`, le terminal donne le nombre de tests en échec
et les trois premiers, et le récapitulatif les liste tous avec le journal. Un
contrôle en échec sans test nommé affiche son erreur. Les attentes des tests ne
sont jamais modifiées automatiquement : à l'humain de dire si c'est un changement
du jeu ou un défaut d'import.

## Ce qui est vérifié

- Dofus 3, Dofus 3 Beta et Dofus 2 : le tag de l'API d'objets doit disposer de
  son archive de sorts et de langues. Un client Ankama plus récent est signalé à
  part.
- Dofus Touch : build du jeu lu dans `window.buildVersion` du client de
  production, paquet de ressources et langues de sa configuration officielle.
- Dofus Retro : versions des fichiers de langue dans les cinq langues et
  empreinte des images du manifeste du client.
- Wakfu : version du flux officiel et de la dernière transformation locale. Les
  sorts sont récoltés pour le build importé.
- Avant/après : intégrité SQLite, lignes par table, tables vidées, références
  orphelines, identifiants perdus ou réaffectés, stats ajoutées ou supprimées,
  nouveaux effets de la source, objets et sorts modifiés, objets retirés par
  Ankama et gardés masqués, concordance base/dump, images référencées présentes
  et lisibles.

Bloquent une version : table supprimée, perte de plus de 3 % dans une table,
identifiant perdu ou réaffecté, dump incohérent, table essentielle vide, image
existante perdue. Une suppression légitime d'Ankama demande donc un examen humain,
sauf dans les deux cas Wakfu ci-dessous.

Wakfu : un objet que l'ancienne base contenait et que le nouveau build n'a plus
est gardé sous son identifiant avec `removed = 1`, comme les objets retirés des
versions Dofus : le site le masque, les builds enregistrés le retrouvent. Le
compte apparaît dans le journal de l'étape « Construction de la base ». Pour
`item_recipes`, `item_recipe_ingredient_names` et `item_craft_jobs`, une perte
de plus de 3 % n'est qu'un avertissement quand `recipes.json` du miroir a
diminué d'au moins la part qui dépasse ces 3 % ; l'inventaire Wakfu garde le
nombre de recettes du miroir pour cette comparaison.

## Récapitulatif

Chaque exécution garde un dossier `.update-reports/<date>-<pid>/` :

- `RECAP.md` : statut général en première ligne, un bloc par version (statut,
  version locale -> importée, objets et sorts ajoutés, retirés, modifiés,
  nouvelles stats, nouveaux problèmes d'images, les compteurs à zéro regroupés
  sur une ligne, les données DofusDB conservées en une ligne, étapes avec
  avertissements), les tests en échec, la commande pour terminer une
  restauration incomplète, puis la commande pour annuler ;
- `report.json`, les inventaires `<version>-before.json` et `-after.json`, les
  journaux de chaque étape et des contrôles ;
- `<version>/` : sauvegarde de chaque version, `images/` : sauvegarde des images,
  `images-changed.json` : images modifiées pendant l'exécution.

Statut d'une version : `IMPORTÉ`, `ÉCHEC, RESTAURÉ`, `RESTAURATION INCOMPLÈTE`
ou `NON LANCÉ` (rien n'a été modifié, la cause est donnée). Statut général :
`IMPORTÉ`, `IMPORTÉ EN PARTIE`, `ÉCHEC` ou `INTERROMPU`, suivi au besoin de
`, TESTS À REVOIR`, `, ERREURS` ou `, RESTAURATION INCOMPLÈTE`.

Codes de sortie : `0` tout importé et tests verts, `2` tout importé mais tests à
revoir, `1` au moins une version en échec ou une restauration incomplète, `130`
interruption. Même après un Ctrl+C en toute fin d'exécution, le verrou est libéré
et `report.json` et `RECAP.md` sont écrits.

## Restauration

La restauration essaie chaque fichier. Remettre une base efface aussi ses
fichiers `-journal`, `-wal` et `-shm`, qui rejoueraient sinon l'import annulé
dans la base remise ; si l'un d'eux est bloqué, la base compte comme non
restaurée. Une base identique à la sauvegarde, ou restée telle qu'avant l'import,
n'est pas réécrite. Un fichier bloqué par Windows est réessayé jusqu'à 60 secondes
à la fin ; un fichier absent de la sauvegarde est signalé sans arrêter le reste.

Quand une restauration est incomplète ou a été interrompue, le terminal et le
récapitulatif donnent la commande qui la termine, limitée aux versions
concernées :

```powershell
py update_all.py --restore .update-reports\<dossier> --versions beta
```

Avec `--versions`, seules ces versions et leurs entrées de `state.json` sont
remises. Si une version suivante de la même exécution reste importée, ses
changements sont gardés : l'étiquette de la version restaurée est remise seule
dans `fashionista_version.py`, et un fichier partagé modifié ensuite par l'autre
version est gardé et listé.

Sans `--versions`, `--restore` annule toute l'exécution : les versions de la plus
récente à la plus ancienne, puis les images modifiées, et les entrées de
`state.json` écrites par elle. Relancer la commande termine une restauration
partielle. Le lanceur refuse de restaurer une version qu'une exécution plus
récente a importée depuis, et nomme cette exécution ; `--force` passe outre.
Les données applicatives (comptes, personnages, builds) ne sont jamais touchées.
Une erreur de restauration s'affiche en une phrase, sans trace Python.

## Arrêt brutal

Pendant l'import d'une version, le fichier `<dossier>/<version>.importing`
existe ; il disparaît dès que la version est importée ou restaurée. Le verrou
`.update-data.lock` nomme le dossier de l'exécution. Si la fenêtre est fermée ou
Windows redémarre pendant un import, le lanceur suivant récupère le verrou, puis
refuse de partir et affiche la commande exacte :

```powershell
py update_all.py --restore .update-reports\<dossier> --versions dofus3
```

Une fois cette version restaurée, le fichier `.importing` disparaît et le
lanceur repart normalement.

## Place disque

Chaque exécution avec images garde une sauvegarde des images. `py update_all.py
--clean-reports` liste les sauvegardes d'images plus anciennes que les trois
dernières (anciennes exécutions au format `backup/` comprises), avec leur taille,
et ne les supprime qu'après avoir tapé `oui`. `--yes` ne suffit pas. Une
exécution dont la restauration est inachevée est toujours gardée. Les journaux,
récapitulatifs et sauvegardes de données restent.

## Sources conservées

L'API DofusDB est désactivée dans ce lanceur. Les apparences de montures, grades
et sous-zones des monstres Dofus 3 et Dofus 3 Beta sont repris depuis la
sauvegarde de la même version et enregistrés dans la base et son dump. Les
apparences suivent l'identifiant et le type Ankama de chaque monture, pour
survivre à un renommage. Les illustrations de monstres Dofus 3 et Dofus 3 Beta
restent locales. Le récapitulatif le dit une fois par version.

Le choix « sans images » s'applique aussi aux sorts Dofus Touch et aux
illustrations Dofus Retro. Avec images, les scripts réutilisent leurs caches
habituels.

## Versions Dofus Touch et Dofus Retro

Dofus Touch utilise plusieurs numéros indépendants. Par exemple, le 23 septembre
2026 :

| Numéro | Signification | Source |
|---|---|---|
| Client `3.14.2` | Version de l'application installée sur le téléphone | Écran du téléphone ; pas détectée par le lanceur |
| Build `1.74.5` | Version du jeu affichée dans cette application | `window.buildVersion` dans le [client de production](https://dt-proxy-production-login.ankama-games.com/build/script.js) |
| Ressources `3.3.6_…` | Paquet graphique servi par le CDN | `assetsUrl` dans la [configuration officielle](https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr) |

Le lanceur présente le build du jeu comme version disponible, en lisant seulement
le début du fichier JavaScript sans l'exécuter. Un build illisible ou ambigu rend
la source indisponible. Un changement du build ou des ressources déclenche une
mise à jour.

Pour Dofus Retro, `1.49.5.5656.445-401e092` devient `1.49.5` dans la ligne de
version du jeu. L'identifiant Cytrus complet reste affiché et conservé pour les
contrôles.

## Prérequis et concurrence

Le lanceur utilise les dépendances existantes et
`fashionsite/fashionsite/settings_test.py` configuré avec SQLite. Il refuse de
partir si ce fichier manque ou si la configuration Fashionista pointe vers un
autre dépôt. Les étapes d'images Dofus Retro peuvent demander Java/JPEXS et
resvg : les outils de `~/Documents/fashionista-loop/tools/flash/` sont détectés
automatiquement, les variables `JAVA_EXE`, `FFDEC_JAR` et `RESVG_EXE` restent
prioritaires.

`.update-data.lock` empêche deux lanceurs en même temps. Le lanceur s'inscrit
aussi dans la section « En cours » de `~/Documents/fashionista-loop/RUNNING.md`
s'il existe (autre fichier avec `--running-file`) et refuse de partir si un autre
travail y figure ; la section s'arrête au titre suivant. Après un arrêt forcé,
l'ancien verrou est récupéré si aucun programme Python du dépôt, calcul ou
traitement d'images ne tourne encore ; sinon le lanceur nomme ce programme et
demande de le fermer (serveur de développement compris) avant de relancer.

Une étape dispose d'une heure, l'import complet d'une version de quatre heures :

```powershell
py update_all.py --step-timeout 7200
```
