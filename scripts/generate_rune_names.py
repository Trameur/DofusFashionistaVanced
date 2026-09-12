#!/usr/bin/env python3
# Copyright (C) 2026 The Dofus Fashionista - LGPL (see COPYING.LESSER)
"""Build the five names each game gives to each of its forgemagie runes.

Why this exists
---------------
The workshop used to name every rune in French, to every reader, because the
names are BUILT in code from French abbreviations ("Rune %s %s"). Ankama
renames all of them: "Rune de Terre" is "Earth Rune", "Runa de Tierra",
"Runa de Terra", "Rune der Erde". A player searching their own client for the
French spelling found nothing.

Each version is read from ITS OWN table, never from another version's: the
rune sets differ (105 on Dofus 3, 98 on Dofus 2, 86 on Touch, 57 on Retro),
and so do the names.

    dofus3/beta/dofus2  itemscraper[/<version>]/all_resources_<lang>.json
    touch               itemscraper/touch_raw/Items_<lang>.json
    retro               itemscraper/retro_raw/items_<lang>.json

Output
------
fashionsite/chardata/forgemagie_rune_names.json, keyed by version then by the
FRENCH name, which is the key the site builds and stores:

    {"dofus3": {"Rune de Terre": {"fr": ..., "en": "Earth Rune", ...}}}

A version whose raw tables are absent from this checkout keeps whatever the
file already holds, and the run says so. Retro's raw tables are not committed,
so a blind overwrite would silently drop 57 runes.

Usage
-----
    python scripts/generate_rune_names.py
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SCRAPER = os.path.join(ROOT, "itemscraper")
OUT = os.path.join(ROOT, "fashionsite", "chardata",
                   "forgemagie_rune_names.json")

LANGUAGES = ("fr", "en", "es", "pt", "de")

#: The rune type in each table. The modern resource dumps file them under 133,
#: the Touch and Retro item tables under 78. Two tables, two numberings; this
#: is not one constant used twice.
RESOURCE_RUNE_TYPE = 133
ITEM_RUNE_TYPE = 78


def _load(path):
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _resources(subdir, language):
    name = "all_resources_%s.json" % language
    path = (os.path.join(SCRAPER, subdir, name) if subdir
            else os.path.join(SCRAPER, name))
    data = _load(path)
    if data is None:
        return None
    items = data if isinstance(data, list) else data["items"]
    return {item["ankama_id"]: item["name"] for item in items
            if isinstance(item, dict)
            and (item.get("type") or {}).get("id") == RESOURCE_RUNE_TYPE}


def _touch(language):
    data = _load(os.path.join(SCRAPER, "touch_raw", "Items_%s.json" % language))
    if data is None:
        return None
    return {int(key): entry["nameId"] for key, entry in data.items()
            if isinstance(entry, dict)
            and entry.get("typeId") == ITEM_RUNE_TYPE
            and isinstance(entry.get("nameId"), str)}


def _retro(language):
    data = _load(os.path.join(SCRAPER, "retro_raw", "items_%s.json" % language))
    if data is None:
        return None
    return {int(key): entry["n"] for key, entry in data["I"]["u"].items()
            if isinstance(entry, dict) and entry.get("t") == ITEM_RUNE_TYPE
            and isinstance(entry.get("n"), str)}


READERS = (
    ("dofus3", lambda lang: _resources("", lang)),
    ("beta", lambda lang: _resources("beta", lang)),
    ("dofus2", lambda lang: _resources("dofus2", lang)),
    ("touch", _touch),
    ("retro", _retro),
)


def names_for(reader):
    """{french name: {language: name}}, or None when a table is missing."""
    tables = {}
    for language in LANGUAGES:
        table = reader(language)
        if table is None:
            return None
        tables[language] = table
    out = {}
    for ankama_id, french in tables["fr"].items():
        names = {lang: tables[lang].get(ankama_id) for lang in LANGUAGES}
        # A rune one language does not name would be published as an empty
        # label; it stays out and the count below says so.
        if all(names.values()):
            out[french] = names
    return out


def main():
    existing = _load(OUT) or {}
    result = dict(existing)
    kept = []
    for version, reader in READERS:
        names = names_for(reader)
        if names is None:
            kept.append(version)
            continue
        result[version] = names
    for version, _reader in READERS:
        print("%-8s %4d runes%s" % (version, len(result.get(version, {})),
                                    "  (kept, raw tables absent here)"
                                    if version in kept else ""))
    if kept:
        print("NOT regenerated: %s. Their raw tables are not in this "
              "checkout, so the file keeps what it had." % ", ".join(kept))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1, sort_keys=True)
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
