# Mobile app (Android / iOS): Dofus Fashionista

Date: 2026-06-19, branch: `mobile-app`

## Goal

Ship a mobile app (Android APK, iOS project ready) **with exactly the same
design** as the site, and make the site **usable on mobile** (before, pages
opened "zoomed in" and nothing fit on the screen).

## Chosen approach

The builder (equipment optimization) is rendered **on the server** (Django +
PuLP solver). Rewriting the UI natively would have broken the design and
duplicated all the logic. So the site is wrapped in a native **Capacitor
(WebView)** shell that loads `https://dofusfashionista.gg`.

Consequences:
- The design is **identical** to the web, 100% of the features, one code base.
- The app always shows the production version. **For the mobile design to show
  up in the app, the `mobile-app` branch has to be deployed** (see below).

## Two deliverables

### 1. Responsive site (the core of the request)

The site had **no** media query at all. A **non-destructive** responsive layer
was added, limited to `<= 900px`; the desktop layout (`> 900px`) is strictly
unchanged.

Files:
- `fashionsite/chardata/static/chardata/responsive.css`: **new**. All of the
  mobile adaptation (fluid containers, fluid banner, a control bar that wraps,
  the side menu turned into a collapsible "hamburger" menu, a full-width main
  column, stacked CTA cards, a smaller and dimmer decorative item grid, wide
  forms and boxes brought back inside the screen).
- `fashionsite/chardata/templates/chardata/base.html`: **changed** (8 lines):
  - loads `responsive.css` last (to override the page CSS);
  - a "Menu" button (`.mobile-nav-toggle`) + a small `toggleMobileNav()` script;
  - `header-controls` (language/theme/version/login bar) and `char-overlay`
    (the banner character) classes, so mobile rules can target them.

How it works: the layer is scoped in `@media (max-width: 900px)` and uses
`!important` on structural rules only, because some pages re-import the fixed
desktop CSS in their `{% block css %}`.

Visual check: screenshots at 390 px (mobile) **and** 1280 px (desktop) of the
home, project creation, login, smart build, about and faq pages, through a
headless browser. Desktop is identical to before, mobile fits entirely.

### 2. Capacitor mobile shell: `mobile/`

```
mobile/
  capacitor.config.json   appId gg.dofusfashionista.app, server.url = https://dofusfashionista.gg
  package.json            Capacitor 6 (core/cli/android/ios)
  www/index.html          loading screen / offline fallback
  assets/                 icon sources (gold hanger logo on a dark background) + splash
  android/                native Android project (generated)
  ios/                    native iOS project (generated; pod install to run on a Mac)
```

APK produced: **debug, signed (debug key), installable** by sideload.
`gg.dofusfashionista.app`, versionName 1.0, about 4.2 MB, INTERNET permission.

## Rebuilding the APK (Android)

Prerequisites: JDK 17, Android SDK (platform-tools, `platforms;android-34`,
`build-tools;34.0.0`), Node.

```bash
cd mobile
npm install
npx cap sync android
npx @capacitor/assets generate --android   # icons/splash from assets/
cd android
./gradlew assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk
```

## Building iOS (needs a Mac)

```bash
cd mobile
npm install
npx cap add ios          # if the ios/ folder is missing
npx @capacitor/assets generate --ios
cd ios/App && pod install
npx cap open ios         # opens Xcode -> Run / Archive
```

## Deployment (action needed from you)

- The app loads **production**. The new mobile design will only show up in the
  app (and on the mobile web) **after the `mobile-app` branch is deployed**
  (`responsive.css` + `base.html`). Nothing has been deployed.
- The APK shipped is a **debug build** (testing / sideload). The Play Store
  needs a **signed release** build (the keystore is a secret) + an `.aab`; to be
  done with your go-ahead and your keys.

## Known limits

- **Google sign-in**: Google often blocks OAuth inside an embedded WebView.
  Sign-in with a user name and password and anonymous use both work; Google
  login may need a native (Capacitor) plugin if required.
- The app needs a connection (the builder runs on the server); `www/index.html`
  is the fallback screen.

## Next steps

- Deploy the branch, then test the app again on a real device.
- Signed release build + Play Store listing (title, description, screenshots, ASO).
- Possibly a native plugin for in-app Google login.
