# How the Dofus Touch data is sourced

The Fashionista's **Dofus Touch** item database is built from the same data the
Touch client itself uses. Touch doesn't have a public API and isn't in Ankama's
desktop launcher (Cytrus is desktop-only), so instead of scraping the encyclopedia
we go to the client's own data backend.

This is written up here because finding it took some digging, and the few moving
parts (a config endpoint, a POST-only data API, a separate asset CDN) are worth
having in one place.

## Finding the source

The Touch client is a JavaScript app. The community "no-emu" client
[Lindo](https://github.com/prixe/lindo) just wraps the real client in Electron and
points it at Ankama's servers — its `packages/main/constants/index.ts` lists the
hosts (`proxyconnection.touch.dofus.com`, `earlyproxy.touch.dofus.com`). Neither
is the one to use: the first is NXDOMAIN and the second is the **test** channel.
Production lives at `dt-proxy-production-login.ankama-games.com`, which is what
we read. A player reported the difference in August 2026 and the measurement
confirmed it: on 2026-08-08 the early channel served assets 3.2.4 against
production's 3.2.11, and 27 items nobody can own, among them
"Frozenfoux [WIP]", "Elixir d'Ascension du testeur" and "[FM] Capistil".
Nothing exists only in production, so reading it loses nothing.

Downloading that client bundle (`build/script.js`) and reading how it loads data
gives the whole picture: it fetches a config file, reads a data host and an asset
host out of it, then loads the game tables from the data host and the graphics
from the asset host.

## The data API

The client bootstraps from `config.json`, which returns the live hosts:

```
GET https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr
→ { "dataUrl":  "https://dt-proxy-production-login.ankama-games.com",
    "assetsUrl":"https://dofustouch.cdn.ankama.com/assets/3.2.11_<hash>", ... }
```

Game tables are then a **POST** (every plain GET 404s — the route only answers
POST):

```
POST <dataUrl>/data/map
{"class": "Items", "lang": "fr"}
→ 200, application/json, ~22 MB, keyed by id, names already localised to the lang
```

We read `dataUrl` from `config.json` rather than hard-coding it, so it keeps
working when Ankama rotates the host. The tables we pull are `Items`, `ItemSets`,
`ItemTypes`, `Effects`, `Recipes` and `Breeds`; re-POSTing with a different `lang`
gives the translated names (no separate i18n lookup needed).

Item icons come from the asset CDN at `<assetsUrl>/gfx/items/<iconId>.png`.

## The data shape

Touch is a fork of the Dofus 2 client, so the records are Ankama's raw d2o objects
rather than the friendlier JSON the dofusdude API gives for Dofus 2/3. Each item
carries `possibleEffects` (each effect is an `effectId` into the `Effects` table
plus `diceNum`/`diceSide` for its value range), a `criteria` string for equip
conditions (e.g. `CS>20&CV>6`), `itemSetId`, `recipeIds`, `level`, `typeId` and
`iconId`. Item sets carry their per-piece bonuses inline.

`get_equipments_touch.py` decodes all of that into the same shape the Dofus 3
transformer produces, so the rest of the pipeline (`get_equipments3.py`,
`load_item_db.py`) is reused unchanged.

## Touch is its own version

Touch diverged from Dofus 2 over the years, so it's treated as a fully separate
version, not an alias of another:

- **15 classes** — the original 12 plus Rogue, Masqueraider and Foggernaut
  (`version_compat.py`).
- **Its own item catalogue and stat set** — it still has PvP resists, AP/MP parry
  and reduction, dodge/lock and trap stats that Dofus 3 dropped or reworked. The
  stat mapping in `get_equipments_touch.py` is built from Touch's own `Effects`
  table.
- **Its own database** (`items_touch.db`) and item icons
  (`static/chardata/{items,pets}/touch/60x60/`).

## The pipeline

`update_data_touch.py` runs the whole thing:

| Step | Script | Output |
|---|---|---|
| download | `download_touch_data.py` | `touch_raw/*_<lang>.json` |
| transform | `get_equipments_touch.py` | `touch/transformed_{equipment,sets}.json` |
| dump | `get_equipments3.py --input-dir` | `item_db_dumped_touch.dump` |
| load | `load_item_db.py --game-version touch` | `items_touch.db` |
| icons | `download_touch_images.py` | `static/chardata/{items,pets}/touch/60x60/` |

`test_touch.py` checks the result: known items decode correctly, weapons and sets
are populated, the 15 classes are right, and a real optimisation solves.

## Alternative: the encyclopedia

`www.dofus-touch.com` has the official encyclopedia in HTML, which the old
`touch_*` Scrapy spiders here (and the dofapi crawler) scrape. It still works with
cookie/redirect handling, and is a reasonable cross-check, but the client data
above is more direct and always current.
