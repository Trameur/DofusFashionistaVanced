# Application mobile (Android / iOS) — Dofus Fashionista

Date : 2026-06-19 · Branche : `mobile-app`

## Objectif

Fournir une application mobile (APK Android, projet iOS prêt) **en gardant
exactement le même design** que le site, et rendre le site **utilisable sur
mobile** (avant : on arrivait « zoomé », rien ne rentrait à l'écran).

## Approche retenue

Le builder (optimisation d'équipement) est rendu **côté serveur** (Django +
solveur PuLP). Réécrire l'UI en natif aurait cassé le design et dupliqué toute
la logique. On encapsule donc le site dans une coquille native **Capacitor
(WebView)** qui charge `https://dofusfashionista.gg`.

Conséquences :
- Design **identique** au web, 100 % des fonctionnalités, une seule base de code.
- L'app affiche toujours la version en production. **Pour que le design mobile
  apparaisse dans l'app, il faut déployer la branche `mobile-app`** (voir plus bas).

## Deux livrables

### 1. Site responsive (le cœur de la demande)

Le site n'avait **aucune** media query. Ajout d'une couche responsive **non
destructive**, limitée à `≤ 900px` — le rendu PC (`> 900px`) est strictement
inchangé.

Fichiers :
- `fashionsite/chardata/static/chardata/responsive.css` — **nouveau**. Toute
  l'adaptation mobile (conteneurs fluides, bannière fluide, barre de contrôles
  qui passe à la ligne, menu latéral → menu « hamburger » repliable, colonne
  principale pleine largeur, cartes CTA empilées, grille d'items décorative
  réduite/atténuée, formulaires et boîtes larges ramenés dans l'écran).
- `fashionsite/chardata/templates/chardata/base.html` — **modifié** (8 lignes) :
  - chargement de `responsive.css` en dernier (pour surcharger les CSS de page) ;
  - bouton « Menu » (`.mobile-nav-toggle`) + petit JS `toggleMobileNav()` ;
  - classes `header-controls` (barre langue/thème/version/login) et
    `char-overlay` (personnage de la bannière) pour pouvoir les cibler en mobile.

Principe : la couche est scoppée en `@media (max-width: 900px)` et utilise
`!important` sur les règles structurelles uniquement, car certaines pages
ré-importent les CSS fixes desktop dans leur bloc `{% block css %}`.

Vérification visuelle : captures à 390 px (mobile) **et** 1280 px (PC) des pages
home, création de projet, login, smart build, about, faq — via un navigateur
headless. Le PC est identique à l'avant, le mobile rentre entièrement.

### 2. Coquille mobile Capacitor — `mobile/`

```
mobile/
  capacitor.config.json   appId gg.dofusfashionista.app, server.url = https://dofusfashionista.gg
  package.json            Capacitor 6 (core/cli/android/ios)
  www/index.html          écran de chargement / repli hors-ligne
  assets/                 sources d'icône (logo cintre doré sur fond sombre) + splash
  android/                projet Android natif (généré)
  ios/                    projet iOS natif (généré ; pod install à faire sur Mac)
```

APK produit : **debug, signé (clé debug), installable** par sideload.
`gg.dofusfashionista.app` · versionName 1.0 · ~4,2 Mo · permission INTERNET.

## Reconstruire l'APK (Android)

Pré-requis : JDK 17, Android SDK (platform-tools, `platforms;android-34`,
`build-tools;34.0.0`), Node.

```bash
cd mobile
npm install
npx cap sync android
npx @capacitor/assets generate --android   # icônes/splash depuis assets/
cd android
./gradlew assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk
```

## Construire iOS (nécessite un Mac)

```bash
cd mobile
npm install
npx cap add ios          # si le dossier ios/ n'est pas présent
npx @capacitor/assets generate --ios
cd ios/App && pod install
npx cap open ios         # ouvre Xcode -> Run / Archive
```

## Déploiement (action requise de ta part)

- L'app charge la **prod**. Le nouveau design mobile n'apparaîtra dans l'app
  (et sur le web mobile) **qu'après déploiement** de la branche `mobile-app`
  (`responsive.css` + `base.html`). Aucun déploiement n'a été fait.
- L'APK livré est un **build debug** (test / sideload). Pour le Play Store il
  faut un build **release signé** (keystore = secret) + un `.aab` — à faire
  avec ton accord et tes clés.

## Limites connues

- **Connexion Google** : Google bloque souvent OAuth dans une WebView embarquée.
  La connexion par identifiant/mot de passe et l'usage anonyme fonctionnent ;
  le login Google pourra nécessiter un plugin natif (Capacitor) si besoin.
- L'app a besoin d'une connexion (builder côté serveur) ; `www/index.html` sert
  d'écran de repli.

## Pistes suivantes

- Déployer la branche puis re-tester l'app sur appareil réel.
- Build release signé + fiche Play Store (titre, description, captures, ASO).
- Éventuel plugin natif pour le login Google in-app.
