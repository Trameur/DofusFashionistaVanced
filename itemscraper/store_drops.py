#!/usr/bin/env python3
"""store_drops.py - load the item->monster drops index (from get_monsters.py)
into items.db and re-dump it, so the encyclopedia can show "Dropped by ...".

Mirrors store_item_obtainment.py: it opens items.db (bootstrapping from the dump
if needed), fills two tables, then re-saves the dump so the data survives the
runtime rebuild that structure.py does from the dump.

    item_drops    (item internal id, monster_ankama_id, rate)   -- item = items.id
    monster_names (monster_ankama_id, language, name)           -- localized monster names

Usage (from repo root, after get_monsters.py produced the index):
    python itemscraper/store_drops.py \
        --drops itemscraper/transformed_drops.json --game-version dofus3
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3  # noqa: E402

from store_item_obtainment import (  # noqa: E402
    _load_db_from_dump, _save_db_to_dump, get_items_db_path)

LANGUAGES = ("en", "fr", "es", "pt", "de")


def _load_drops(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def store_drops(drops_path, game_version="dofus3"):
    drops = _load_drops(drops_path)
    items_db_path = get_items_db_path(game_version)
    # dofus3 rebuilds items.db from the dump at runtime (structure.py), so the DUMP
    # is the source of truth: rebuild from it first, then re-dump, for a clean add.
    # Every other version loads its committed items_<ver>.db as-is at runtime, so the
    # DB is the source of truth: edit it in place (never rebuild from a possibly-stale
    # dump), then re-dump to keep the dump in sync.
    if game_version == 'dofus3':
        _load_db_from_dump(items_db_path, game_version)
    conn = sqlite3.connect(items_db_path)
    try:
        cursor = conn.cursor()
        # ankama_id -> internal item id (only items we actually carry)
        ankama_to_id = {
            ankama_id: item_id
            for item_id, ankama_id in cursor.execute(
                "SELECT id, ankama_id FROM items WHERE ankama_id IS NOT NULL")
        }

        cursor.execute("DROP TABLE IF EXISTS item_drops")
        cursor.execute("DROP TABLE IF EXISTS monster_names")
        cursor.execute(
            "CREATE TABLE item_drops (item INTEGER, monster_ankama_id INTEGER, rate REAL)")
        cursor.execute(
            "CREATE TABLE monster_names (monster_ankama_id INTEGER, language TEXT, name TEXT)")

        drop_rows = []
        name_rows = []
        seen_monster = set()
        matched_items = 0
        for object_id_str, monsters in drops.items():
            item_id = ankama_to_id.get(int(object_id_str))
            if item_id is None:
                continue  # a dropped resource/consumable we don't carry
            matched_items += 1
            for m in monsters:
                mid = m["monster_ankama_id"]
                rate = max(m.get("rates") or [0]) or 0
                drop_rows.append((item_id, mid, rate))
                if mid not in seen_monster:
                    seen_monster.add(mid)
                    names = m.get("names") or {}
                    for lang in LANGUAGES:
                        if names.get(lang):
                            name_rows.append((mid, lang, names[lang]))

        cursor.executemany(
            "INSERT INTO item_drops (item, monster_ankama_id, rate) VALUES (?, ?, ?)",
            drop_rows)
        cursor.executemany(
            "INSERT INTO monster_names (monster_ankama_id, language, name) VALUES (?, ?, ?)",
            name_rows)
        cursor.execute("CREATE INDEX idx_item_drops_item ON item_drops (item)")
        cursor.execute(
            "CREATE INDEX idx_monster_names_id ON monster_names (monster_ankama_id)")
        conn.commit()
        print("[%s] item_drops: %d rows for %d items; monster_names: %d rows (%d monsters)"
              % (game_version, len(drop_rows), matched_items, len(name_rows),
                 len(seen_monster)))
    finally:
        conn.close()

    _save_db_to_dump(get_items_db_path(game_version), game_version)


def main():
    parser = argparse.ArgumentParser(description="Load the item->drops index into items.db")
    parser.add_argument("--drops", default="itemscraper/transformed_drops.json")
    parser.add_argument("--game-version", default="dofus3")
    args = parser.parse_args()
    store_drops(args.drops, args.game_version)


if __name__ == "__main__":
    main()
