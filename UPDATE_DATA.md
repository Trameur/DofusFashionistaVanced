# Mettre à jour les données

Depuis le dépôt, avec le Python qui fait déjà tourner les scripts `update_data_*.py` :

```powershell
py update_all.py
```

Le lanceur affiche la version locale, celle du client Ankama et celle réellement
importable. Répondre avec les numéros ou noms des versions (`1,4`, `dofus3,touch`),
`changed` pour celles qui ont changé, ou `all` pour les cinq versions de Dofus.
Wakfu est disponible avec `6` ou `wakfu`, et reste un choix explicite car il est
expérimental. Ensuite, choisir avec ou sans images pour chaque version et confirmer
le résumé. Entrée sans sélection quitte le programme.

Les mises à jour s'exécutent successivement. Les anciens scripts restent utilisables
directement ; le lanceur réutilise leurs étapes et leurs arguments.

Le terminal affiche la version traitée, le début et la durée de chaque étape,
puis les contrôles et, si nécessaire, la restauration. Pendant une opération
longue, un rappel apparaît toutes les 30 secondes. Les messages détaillés de
chaque téléchargement restent dans les journaux : seuls les jalons du lanceur
sont affichés en direct. Une erreur indique l'étape, sa cause et son journal.
Le dossier des journaux est annoncé avant la sauvegarde.

## Consulter ou préparer une commande

```powershell
py update_all.py --list
py update_all.py --dry-run --versions dofus3,beta --images no
py update_all.py --versions dofus3,touch --images yes --yes
```

`--list` et `--dry-run` consultent les sources sans modifier les données. La dernière
commande lance réellement les mises à jour choisies. `--yes` exige des choix
explicites pour les versions et les images. Aucun mode ne fait de commit, de push,
de publication ni de déploiement.

## Ce qui est vérifié

- Dofus 3, Beta et Dofus 2 : le tag de l'API d'objets doit disposer de son archive
  de sorts et de langues. Un client Ankama plus récent est indiqué séparément.
- Touch : build du jeu lu dans `window.buildVersion` du client de production,
  ainsi que le paquet de ressources et les langues de sa configuration officielle.
- Retro : versions des fichiers de langue dans les cinq langues et empreinte des
  images du manifeste du client. Un numéro de client seul ne prouve pas un
  changement d'équipement.
- Wakfu : version du flux officiel et de la dernière transformation locale.
- Avant/après : intégrité SQLite, nombre de lignes par table, tables vidées,
  références d'objets orphelines, identifiants perdus ou réaffectés, statistiques
  ajoutées/supprimées, nouveaux effets présents dans la source mais éventuellement
  ignorés par le transformateur, objets et sorts modifiés.
- Concordance des nombres de lignes entre la base et son dump, pour éviter qu'un
  rechargement ultérieur supprime des données.
- Présence et lecture des images référencées : équipements, sorts, ressources et
  monstres selon les versions. Les fichiers déjà absents sont distingués des
  nouveaux manquants. Cela contrôle les fichiers, pas la justesse visuelle du dessin.
- Génération réelle d'un Iop terre niveau 50 dans chaque version de Dofus, affichage
  du résultat et des sorts, et calcul d'un tour avec des dégâts positifs. Wakfu a
  aussi ses contrôles de solveur lorsqu'il est sélectionné.
- Contrôle des données d'armes, puis suite Django complète avec
  `--settings=fashionsite.settings_test`, sans argument `--parallel`.

Les contrôles ne changent pas automatiquement les attentes des tests quand une
nouvelle version les fait échouer. Le rapport fournit les journaux pour déterminer
si c'est un changement du jeu ou un défaut d'import/calcul.

## Rapport et récupération

Chaque exécution conserve un dossier `.update-reports/<date>-<pid>/` contenant :

- `RECAP.md` : bilan lisible et points à corriger ;
- `report.json` : bilan structuré, différences détaillées et commandes exécutées ;
- `<version>-before.json` et `<version>-after.json` : inventaires ;
- les journaux de chaque étape, `generation.log`, `weapons.log` et `django.log` ;
- `backup/manifest.json` et les fichiers sauvegardés.

Les tables supprimées, les pertes de plus de 3 % dans une table, les identifiants
incompatibles, les dumps incohérents et les échecs de tests bloquent la validation.
Les suppressions légitimes d'une mise à jour peuvent donc demander un examen humain.
Les autres différences et les images manquantes sont signalées pour examen.

En cas d'erreur bloquante, le lanceur restaure les bases, dumps, constantes,
référentiels de sorts et métadonnées sauvegardés. Avec images, il sauvegarde et
restaure aussi les répertoires d'images, y compris leur copie dans `staticfiles`.
La sauvegarde contient l'état local de départ, même non commité. Les données
applicatives (comptes, personnages, builds) ne sont pas modifiées par le lanceur.
La restauration compare les empreintes et conserve les fichiers déjà identiques.
Les remplacements de bases et de fichiers restaurés réessaient pendant au plus
15 secondes si Windows les bloque temporairement, puis signalent l'échec.
Les téléchargements bruts restent en cache pour la prochaine tentative ; les
archives de sorts sélectionnées sont retéléchargées pour ne pas réutiliser un
téléchargement incomplet.

Codes de sortie : `0` validé ou consultation réussie, `2` appliqué avec points à
vérifier, `1` échec, `130` annulation avant mise à jour. Le rapport précise si la
restauration est terminée ou incomplète. Une fermeture forcée de Python ou de
Windows peut empêcher la restauration : conserver le dossier de sauvegarde et
relancer les versions concernées. La récupération du verrou ne restaure pas les
données d'un import interrompu.

## Images et sources conservées

Le choix « sans images » s'applique aussi aux sorts Touch et aux illustrations
Retro, que les anciennes options ne couvraient pas entièrement. Avec images, les
scripts réutilisent leurs caches habituels : ce n'est pas une réimportation forcée
de chaque dessin existant.

L'API DofusDB est désactivée dans ce lanceur. Les apparences de montures, grades et
sous-zones des monstres Dofus 3/Beta sont repris depuis la sauvegarde de **la même
version**, en vérifiant leurs identifiants. Les illustrations de monstres Dofus
3/Beta restent locales. Le rapport signale ces compléments comme non actualisés ;
ils ne sont jamais présentés comme des données fraîchement téléchargées.
Ces compléments sont enregistrés dans la base et dans son dump pour résister
aux rechargements effectués par les étapes suivantes.

## Comprendre les versions Touch et Retro

Touch utilise plusieurs numéros indépendants. Par exemple, le 23 septembre 2026 :

| Numéro | Signification | Source |
|---|---|---|
| Client `3.14.2` | Version de l'application installée sur le téléphone | Écran du téléphone ; pas détectée par le lanceur |
| Build `1.74.5` | Version du jeu affichée dans cette application | `window.buildVersion` dans le [client de production](https://dt-proxy-production-login.ankama-games.com/build/script.js) |
| Ressources `3.3.6_…` | Paquet graphique servi par le CDN | `assetsUrl` dans la [configuration officielle](https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr) |

Le lanceur présente le build du jeu comme version disponible. Il lit seulement
le début du fichier JavaScript sans l'exécuter. Un build illisible ou ambigu
rend la source indisponible ; le numéro des ressources ne sert jamais de repli.
Un changement du build déclenche une mise à jour même si les ressources restent
identiques, et un changement des ressources reste détecté à build identique.

Pour Retro, `1.49.5.5656.445-401e092` devient `1.49.5` dans la ligne de version du
jeu. L'identifiant Cytrus complet reste affiché séparément et conservé pour les
contrôles, avec les versions des langues et l'empreinte des images.

Les constantes de version de `fashionista_version.py`, utilisées par le site,
sont mises à jour après les imports et la réussite de tous les contrôles, pour les
cinq versions de Dofus. Un échec restaure aussi ces constantes. La simple
consultation ne modifie rien : une ancienne valeur locale `1.74` ou `1.49` reste
visible jusqu'à la prochaine mise à jour validée. L'état détaillé est conservé
dans `.update-reports/state.json` ; les anciens états sans build Touch sont
revalidés au prochain import.

## Prérequis et concurrence

Le lanceur utilise les dépendances existantes et le fichier local
`fashionsite/fashionsite/settings_test.py` configuré avec SQLite. Il refuse de partir
si ce fichier manque ou si la configuration Fashionista pointe vers un autre dépôt.
Il isole les chemins Python des scripts d'import de ceux utilisés par les tests
Django ; aucune modification manuelle de `PYTHONPATH` n'est nécessaire.
Les étapes d'images Retro peuvent nécessiter Java/JPEXS et resvg, comme les scripts
actuels ; leur absence apparaît dans le journal de l'étape.
Les outils déjà présents dans `~/Documents/fashionista-loop/tools/flash/` sont
détectés automatiquement. Les variables `JAVA_EXE`, `FFDEC_JAR` et `RESVG_EXE`
restent prioritaires lorsqu'elles sont renseignées.

Ne pas reconstruire les mêmes données ni modifier les fichiers générés pendant
une mise à jour. `.update-data.lock` empêche deux instances du lanceur. Le lanceur
consulte aussi `~/Documents/fashionista-loop/RUNNING.md` s'il existe, y inscrit son
travail jusqu'à la fin des tests ou de la restauration, puis enlève sa ligne.
Un autre fichier peut être fourni avec `--running-file CHEMIN`.

Après un arrêt forcé, le lanceur récupère son ancien verrou seulement si le
processus propriétaire et ses enfants sont arrêtés et qu'aucun import, test ou
calcul potentiellement actif n'est détecté. Une vérification impossible conserve
le verrou et affiche la cause dans le terminal. Les marqueurs d'autres travaux
dans `RUNNING.md` restent bloquants. Le fichier `.update-data.guard` peut rester
présent : son verrou système est libéré automatiquement à la fin du processus
et empêche deux lanceurs de récupérer simultanément un ancien verrou.

Une étape dispose par défaut d'une heure. Ajuster, si nécessaire :

```powershell
py update_all.py --step-timeout 7200
```
