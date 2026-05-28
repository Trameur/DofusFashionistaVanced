# Phase 0 — Recherche de sources de données (Retro, Touch, HDV)

> Livrable d'analyse demandé par le plan stratégique pour les chantiers bloqués.
> Date : 2026-05-28. Méthode : interrogation directe des APIs + revue des projets communautaires.

## Résumé exécutif (go / no-go)

| Cible | Source viable ? | Recommandation |
|---|---|---|
| **Dofus 2** | ✅ dofusdude (`dofus2-main`) | **FAIT** (implémenté) |
| **Dofus Retro (1.29)** | ✅ **Source + extraction FONCTIONNELLES** | **GO** : download + parseur AS2 Python opérationnels (11 203 items extraits). Reste : mapping modèle interne + DB + builder |
| **Dofus Touch** | 🔴 Pas de source fiable actuellement | **NO-GO pour l'instant** : dofapi (la seule source Touch connue) est hors-ligne |
| **HDV / budget kamas** | ⛔ Bloqué légalement | **NO-GO** : accès aux prix HDV interdit par Ankama, aucune API stable. Alternative conforme ci-dessous |

---

## Dofus Retro (1.29)

**Sources évaluées (vérifiées par appel direct) :**
- **`api.dofusdb.fr`** — API Feathers.js live, riche et multilingue (de/en/es/fr/pt), avec `effects`, `possibleEffects`, `recipeIds`/`hasRecipe`, `itemSet`, `criterions`. **MAIS données = Dofus moderne (Unity 3)**, confirmé (« Twiggy Sword » lvl 7, syntaxe de conditions moderne `SC!5|ST!5`). **Ne contient PAS de données Retro 1.29.** Redondant avec notre source dofusdude actuelle.
- **`Spx0001/DofusAPI`** — malgré le titre « API pour Dofus 1.29 », c'est en réalité un **émulateur de serveur / système de comptes** (registration, gifts, server status, RSS) en PHP self-host, abandonné. **Pas une base d'items.** Inutilisable.
- **`bot4dofus/Datafus`** — dumps JSON Dofus moderne + events socket. Pas Retro.
- **Kaggle « Dofus Database »** — dump statique non maintenu. À éviter.

**✅ SOURCE TROUVÉE ET PROUVÉE — le CDN Lang officiel d'Ankama.** (Verdict initial « NO-GO » corrigé après investigation des parseurs communautaires Cyberia / Arakne / retrolangdl.)

- **Manifeste** : `https://dofusretro.cdn.ankama.com/lang/versions_fr.txt` → HTTP 200. Liste `<catégorie>,<lang>,<version>` pour 38 catégories : `items,fr,1260`, `itemstats,fr,1259`, `itemsets,fr,1254`, `crafts,fr,1258` (= recettes !), `classes`, `effects`, `weapons`…
- **Fichiers** : `https://dofusretro.cdn.ankama.com/lang/swf/<catégorie>_<lang>_<version>.swf` → HTTP 200, format **CWS (SWF zlib, décompression depuis l'octet 8)**.
- **Vérifié end-to-end** : `items_fr_1260.swf` (702 Ko) se décompresse en 2,6 Mo contenant les données **en clair** (« Petite Amulette du Hibou », « PETITE EPEE DE BOISAILLE », descriptions, types). Données **officielles, autoritatives, toujours à jour**.
- **Stage 1 + 2 implémentés et testés** (pur Python, aucune dépendance Java/JPEXS) :
  - [itemscraper/retro_swf_parser.py](../itemscraper/retro_swf_parser.py) — interpréteur AS2 (zlib → tags SWF → DoAction → machine à pile sur ConstantPool/Push/Get-SetMember/InitObject/InitArray/NewObject). Reconstruit les globales.
  - [itemscraper/download_retro_langs.py](../itemscraper/download_retro_langs.py) — manifeste → download → décompression → **JSON parsé**.
  - **Résultat vérifié** : `items_fr` → `I['u']` = **11 203 items**, 123 types. Chaque item : `n` (nom), `nn` (nom maj.), `l` (niveau), `t` (type), `e` (effets/stats), `c` (conditions, ex. `CI>200&CW>100`), `s` (set, 815 items), `g` (gfx), `w` (poids), `d` (description). Ex. « La Baguette des Limbes » lvl 105.

**Reste à faire (stage 3 — implémentation maîtrisée, données acquises)** :
1. **Mapper** les records Retro sur le modèle interne (`item.py`/`structure.py`) : décoder le tableau `e` (effets) et la syntaxe de conditions `c` (`CI`/`CS`/`CA`/`CC`/`CW`… > seuils), résoudre les stats via `itemstats_fr.json`, les sets via `itemsets_fr.json`.
2. **Audit stat-par-stat Retro↔Dofus3** (pas de Coup Critique indépendant, 12 classes, pas de sublimations).
3. Générer `items_retro.db` (réutiliser `get_equipments2/3.py` + `load_item_db.py --game-version retro`), puis conditionner `lpproblem.py`/`smart_build.py` par `game_version == 'retro'`.

**Recommandation** : **GO confirmé**. L'inconnue dure (« peut-on obtenir les données Retro ? ») est **résolue avec du code qui tourne**. Le reste est de l'implémentation cadrée sur des données déjà en main.

**Note utile (hors Retro)** : `api.dofusdb.fr` expose les **recettes** (`recipeIds`/`recipeSlots`) du Dofus moderne. C'est une piste pour peupler la table `item_recipes` manquante (qui débloquerait l'agrégation de ressources du Workshop) — mais mélanger les sources (dofusdude + dofusdb) demande une réconciliation des IDs, à évaluer séparément.

## Dofus Touch

**Sources évaluées :**
- **`dofapi.fr`** — historiquement LA source Dofus + **Dofus-Touch** (items 100 %, JSON, FR/EN). **Problème : hors-ligne au moment du test** (DNS `api.dofapi.fr` non résolu, `dofapi.fr/api/*` → 404). Service instable / en sommeil.
- **dofusdb.fr** — ne couvre pas Touch (cible Unity).
- Le flag legacy `dofustouch=1` dans `items.db` est **obsolète** (déjà documenté).

**Verdict** : **NO-GO actuellement**. La seule source Touch identifiée est indisponible. Ne pas écrire de pipeline Touch tant qu'une source pérenne n'est pas confirmée (sinon code mort). 

**Prochaines étapes** :
1. Surveiller le retour en ligne de dofapi (contacter le mainteneur via leur Discord).
2. Sinon : reverse-engineering des assets de l'app Touch (licence Ankama à vérifier) — chantier lourd.
3. Tant que bloqué : `/touch/` reste non proposé dans le sélecteur de version.

## HDV / budget kamas — ⛔ bloqué légalement

**Constat (important pour le plan)** :
- L'**accès automatisé aux prix HDV est interdit par Ankama** (ToS). C'est un risque juridique, pas seulement technique.
- **Vulbis** (cité dans le plan) est **hors-ligne depuis Dofus 3.0**.
- Les outils actuels (La Boubourse, KamaMaster) **n'exposent pas d'API publique** et reposent sur de la saisie communautaire / scraping en zone grise.

**Recommandation — abandonner le scraping, garder une voie conforme** :
- **Saisie manuelle / communautaire des prix** : les utilisateurs renseignent les prix de leurs items (par serveur), stockés dans un model `ItemPrice(item, server, price, updated_by, updated_at)`. La contrainte budget du LP utilise ces prix.
- Avantages : 100 % conforme ToS, pas de dépendance externe fragile, alimente un dataset propriétaire avec le temps.
- Inconvénient : couverture initiale faible (dépend de la communauté) → démarrer sur les serveurs/items populaires.

**Verdict** : la version « scraping HDV » du plan est **à retirer** (illégale + pas de source). La version « budget » reste possible uniquement via saisie communautaire — à planifier comme une vraie feature distincte.

---

## Sources

- [dofusdude / doduapi](https://github.com/dofusdude/doduapi) — Dofus 2 + 3 + 3beta (déjà utilisé)
- [api.dofusdb.fr](https://api.dofusdb.fr/items) — API Feathers.js live (Dofus moderne, Retro à confirmer)
- [Spx0001/DofusAPI](https://github.com/Spx0001/DofusAPI) — API Dofus 1.29 (candidat Retro)
- [dofapi/dofapi](https://github.com/dofapi/dofapi) — Dofus + Touch (service hors-ligne au test)
- [bot4dofus/Datafus](https://github.com/bot4dofus/Datafus) — dumps JSON
- [Suivi prix HDV — claviersouris](https://www.claviersouris.fr/guides/outil-suivi-prix-hdv-dofus) (Vulbis HS depuis Dofus 3)
- [Forum Ankama — API HDV](https://www.dofus.com/fr/forum/1003-divers/2298605-api-hdv) (accès prix interdit)
