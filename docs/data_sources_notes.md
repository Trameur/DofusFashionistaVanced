# Notes on data sources (Retro, Touch, market prices)

A few notes on where the data for each version comes from (or could come from),
and on what can and cannot be done.

## Dofus Retro and Dofus Touch: done

Both are implemented and pull their data straight from Ankama:

- **Retro**: the official "lang" files on the Retro CDN. Details in
  [retro_data_from_ankama.md](retro_data_from_ankama.md).
- **Touch**: the Touch client's data backend (POST `/data/map`). Details
  in [touch_data_sources.md](touch_data_sources.md).

Leads dropped along the way, for the record:

- `api.dofusdb.fr`: a rich, multilingual API, but its data is modern Dofus
  (Unity 3), not Retro 1.29. Redundant with dofusdude.
- `Spx0001/DofusAPI`: despite its "API Dofus 1.29" title, it is a server
  emulator and account manager in PHP, not an item database.
- `bot4dofus/Datafus`: JSON dumps of modern Dofus, not Retro.
- `dofapi.fr`: used to be the JSON source for Touch, but the API can no longer
  be reached. The `crawlit-dofus-encyclopedia-parser` crawler that fed it scrapes
  the `www.dofus-touch.com` encyclopedia; we keep it as a fallback (see
  touch_data_sources.md).

## Market prices and kama budget: blocked

For a budget constraint (market prices), there is no clean way in:

- Automated access to market prices is **forbidden by Ankama's terms of use**.
  It is a legal risk, not only a technical one.
- **Vulbis** has been offline since Dofus 3.0.
- The existing tools (La Boubourse, KamaMaster) expose no public API and rely on
  community input or grey-area scraping.

The only compliant way would be **community price input**: users enter the
prices of their items per server (an
`ItemPrice(item, server, price, updated_by, updated_at)` model), and the solver's
budget constraint relies on that. It complies with the terms of use and has no
fragile outside dependency, but coverage depends on the community; treat it as a
real feature if we take it on.

## Links

- [dofusdude / doduda](https://github.com/dofusdude/doduda): Dofus 2 / 3 (already used)
- [api.dofusdb.fr](https://api.dofusdb.fr/items): live API, modern Dofus
- [dofapi/dofapi](https://github.com/dofapi/dofapi): Dofus + Touch (offline when tested)
- [Ankama forum: market price access forbidden](https://www.dofus.com/fr/forum/1003-divers/2298605-api-hdv)
