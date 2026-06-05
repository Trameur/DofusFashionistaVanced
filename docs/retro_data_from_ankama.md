# How the Dofus Retro data is sourced from Ankama

The Fashionista's **Dofus Retro** item database is built directly from Ankama's
own official game data — the public "lang" CDN that the Retro client itself
downloads — not from any third-party API. Everything below is reproducible with
the scripts in this repository; it's written up here because a few people asked
how to get Retro data straight from Ankama.

## 1. The official "lang" CDN

The Retro client localises items, stats, sets and recipes from versioned `.swf`
"lang" files served by Ankama:

- **Manifest** (lists every category and its current version):
  `https://dofusretro.cdn.ankama.com/lang/versions_<lang>.txt`
  Each line is `<category>,<lang>,<version>`, e.g. `items,fr,1260`,
  `itemstats,fr,1259`, `itemsets,fr,1254`, `crafts,fr,1258` (recipes!),
  plus `effects`, `weapons`, `classes`, …
- **Files**:
  `https://dofusretro.cdn.ankama.com/lang/swf/<category>_<lang>_<version>.swf`

The files are **CWS** (zlib-compressed SWF: decompress from byte 8). Inside, the
data is stored in plain ActionScript 2 globals — official, authoritative, and
always current for live Retro.

## 2. Parsing the SWF (pure Python, no Java)

The `.swf` files embed their data as AS2 bytecode rather than a tidy JSON blob,
so we run a small interpreter rather than a full Flash decompiler:

- [itemscraper/retro_swf_parser.py](../itemscraper/retro_swf_parser.py) — zlib
  decompress → walk SWF tags → on each `DoAction`, run an AS2 stack machine
  (`ConstantPool` / `Push` / `GetMember` / `SetMember` / `InitObject` /
  `InitArray` / `NewObject`) that rebuilds the global objects. No JPEXS, no JVM.
- [itemscraper/download_retro_langs.py](../itemscraper/download_retro_langs.py) —
  reads the manifest, downloads each category, decompresses and parses it to JSON.

For example `items_fr` parses to `I['u']` ≈ **11,200 items**, each carrying
`n` (name), `l` (level), `t` (type), `e` (effects/stats), `c` (equip
conditions, e.g. `CI>200&CW>100`), `s` (set id), `w` (weight) and `d`
(description).

## 3. Mapping to the optimizer's model

[itemscraper/get_equipments_retro.py](../itemscraper/get_equipments_retro.py)
turns those records into the same shape the other game versions use: it decodes
the effect array into internal stats (resolved via `itemstats`), the condition
syntax into equip requirements, set membership via `itemsets`, and craft recipes
via `crafts`. The result is loaded into `items_retro.db`, and the linear-program
solver is conditioned for Retro rules (12 classes, no ring doubling, no
exomages/prysmaradite). Spells come from the Retro spell lang the same way.

## 4. What isn't in the lang data

A couple of things genuinely aren't published in Ankama's public lang files:

- **Set bonuses** are applied server-side in Retro, so they're not in the lang
  data. They're filled from community-maintained data instead.
- **Familiar (pet) feedable bonuses** — the stat a pet grows toward when fed —
  likewise aren't in the lang data and are sourced separately.

Everything else — items, stats, equip conditions, set membership, recipes and
spells — comes straight from Ankama's official CDN as described above.
