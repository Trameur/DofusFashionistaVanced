# Phase 0 — Recherche de sources de données (Retro, Touch, HDV)

> Livrable d'analyse demandé par le plan stratégique pour les chantiers bloqués.
> Date : 2026-05-28. Méthode : interrogation directe des APIs + revue des projets communautaires.

## Résumé exécutif (go / no-go)

| Cible | Source viable ? | Recommandation |
|---|---|---|
| **Dofus 2** | ✅ dofusdude (`dofus2-main`) | **FAIT** (implémenté) |
| **Dofus Retro (1.29)** | 🟡 Partiel — sources communautaires, pas d'API officielle stable | **GO conditionnel** : démarrer sur `dofusdb.fr` (Retro) ou un dump 1.29, après audit stat-par-stat |
| **Dofus Touch** | 🔴 Pas de source fiable actuellement | **NO-GO pour l'instant** : dofapi (la seule source Touch connue) est hors-ligne |
| **HDV / budget kamas** | ⛔ Bloqué légalement | **NO-GO** : accès aux prix HDV interdit par Ankama, aucune API stable. Alternative conforme ci-dessous |

---

## Dofus Retro (1.29)

**Sources évaluées :**
- **`api.dofusdb.fr`** — API live confirmée (HTTP 200, ~21 500 items, schéma riche : `id`, `level`, `typeId`, `iconId`, `price`, `effects`, `criterions`…). C'est une API Feathers.js requêtable (`?$limit=`, `?$select[]=`). DofusDB cible le Dofus moderne (Unity) ; **une déclinaison Retro existe côté site** mais la couverture Retro via l'API publique reste à confirmer endpoint par endpoint.
- **`Spx0001/DofusAPI`** (GitHub) — explicitement « API pour Dofus 1.29 ». Repo accessible. Candidat dédié Retro à auditer (fraîcheur, exhaustivité, licence).
- **`bot4dofus/Datafus`** — dumps JSON de la base Dofus + events socket. Plutôt orienté Dofus moderne / bots.
- **Kaggle « Dofus Database »** — dump statique, non maintenu, à éviter pour de la prod.

**Verdict** : une source Retro existe (dofusdb Retro et/ou Spx0001), mais aucune n'est aussi clé-en-main que dofusdude. Le vrai coût reste **l'implémentation** (le builder Retro diffère : pas de Coup Critique en stat indépendante, calculs de dommages différents, 12 classes, pas de sublimations) — c'est ce que le plan avait anticipé.

**Prochaines étapes concrètes (avant tout code)** :
1. Auditer `api.dofusdb.fr` : confirmer s'il existe un filtre/version Retro (ex. `?version=` ou un host `retro.*`). Sinon évaluer `Spx0001/DofusAPI`.
2. Écrire un mapping stat-par-stat Retro ↔ Dofus 3 (document) — prérequis du chantier T1b.
3. Si source validée : nouveau `get_equipments_retro.py` (schéma dofusdb ≠ dofusdude → parseur dédié) → `items_retro.db` → conditionner `lpproblem.py`/`smart_build.py` par `game_version == 'retro'`.

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
