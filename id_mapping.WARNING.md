# Do not apply `id_mapping.json` again

`id_mapping.json` translated the old sequential item ids to ankama_ids for the
switch of 6 November 2025 (commit `71e9ba059`, *Updated to 3.3.18.17 +
migration of old data to ankama_id*). It ran once, over `Char.objects.all()`,
and its work is already in the stored builds.

**Applying it a second time would corrupt them.** Its keys run 1..3782, and the
ids stored today are ankama_ids that fall in the same range: a correct id looks
exactly like an unmigrated one. Measured on the production copy on 28 August
2026:

| Re-running the migration today | |
|---|---|
| Slots it would translate | 328 323 |
| of those, correct today and would be rewritten | **312 683** |
| Builds damaged | **166 103** |

Concretely, `dofus1` holding 737 — Emerald Dofus — becomes 6886, an Astrub
Mercenary Cloak. `boots` holding 2421, Fire Kwakoboots, becomes a Just Ring.

The migration also left damage behind, because it assumed every id below 3782
came from the November 2025 catalogue. Builds carrying ids from an older
catalogue generation were translated from the wrong starting point. That is why
20.7 % of stored slots still hold an item of a type the slot cannot take.

Repairing those needs a **per-generation** mapping, not this one: the hundred
versions of `items.db` in this repository each numbered items by insertion
order, so the same number means a different item in each. The last catalogue on
the old numbering is `d6052f8eb` (3 November 2025).

Nothing in the running site reads this file.
