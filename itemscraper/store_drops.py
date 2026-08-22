#!/usr/bin/env python3
"""store_drops.py - load the item->monster drops index (from get_monsters.py)
into items.db and re-dump it.

    item_drops     (item internal id, monster_ankama_id, rate)   -- item = items.id
    resource_drops (resource_ankama_id, monster_ankama_id, rate) -- crafting-ingredient resources
    monster_names  (monster_ankama_id, language, name)           -- localized monster names

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
from untranslated_tag import clean_display_name  # noqa: E402

LANGUAGES = ("en", "fr", "es", "pt", "de")


def _load_drops(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def store_drops(drops_path, game_version="dofus3"):
    drops = _load_drops(drops_path)
    # The three tables below are dropped and rebuilt, so an empty index does not
    # leave them as they were, it empties them, and the monster names go with
    # them: grades and subareas key off those names and empty in turn. It has
    # happened once, when the source moved its drop rate into a span.
    if not drops:
        raise SystemExit(
            '%s holds no drops at all; refusing to empty item_drops, '
            'resource_drops and monster_names for %s.'
            % (drops_path, game_version))
    items_db_path = get_items_db_path(game_version)
    # dofus3 rebuilds items.db from the dump at runtime, so the dump is the source
    # of truth; every other version loads its committed items_<ver>.db as-is.
    if game_version == 'dofus3':
        _load_db_from_dump(items_db_path, game_version)
    conn = sqlite3.connect(items_db_path)
    try:
        cursor = conn.cursor()
        # One ankama_id can be several internal rows: alternative conditions are
        # flattened into "(#1)" and "(#2)", a fed pet into one row per bonus. Touch
        # and Retro reuse ankama ids across kinds, so only equipment rows are eligible.
        ankama_to_ids = {}
        columns = [row[1] for row in cursor.execute('PRAGMA table_info(items)')]
        query = ("SELECT id, ankama_id FROM items WHERE ankama_id IS NOT NULL"
                 + (" AND ankama_type = 'equipment'"
                    if 'ankama_type' in columns else '')
                 + " ORDER BY id")
        for item_id, ankama_id in cursor.execute(query):
            ankama_to_ids.setdefault(ankama_id, []).append(item_id)
        # Crafting-ingredient resources are not items we carry, so their drops go
        # in their own table, keyed by ankama_id.
        resource_ankama_ids = set()
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'item_recipe_ingredient_names'")
        if cursor.fetchone() is not None:
            resource_ankama_ids = {
                row[0] for row in cursor.execute(
                    "SELECT DISTINCT ingredient_ankama_id FROM item_recipe_ingredient_names "
                    "WHERE ingredient_subtype = 'resources'")
            }

        cursor.execute("DROP TABLE IF EXISTS item_drops")
        cursor.execute("DROP TABLE IF EXISTS resource_drops")
        cursor.execute("DROP TABLE IF EXISTS monster_names")
        # conditions = raw Ankama criterion string ("PL>19&PL<61"), NULL when the drop is free.
        cursor.execute(
            "CREATE TABLE item_drops (item INTEGER, monster_ankama_id INTEGER, rate REAL, "
            "conditions TEXT)")
        cursor.execute(
            "CREATE TABLE resource_drops (resource_ankama_id INTEGER, monster_ankama_id INTEGER, "
            "rate REAL, conditions TEXT)")
        cursor.execute(
            "CREATE TABLE monster_names (monster_ankama_id INTEGER, language TEXT, name TEXT)")

        drop_rows = []
        resource_drop_rows = []
        name_rows = []
        seen_monster = set()
        matched_items = 0
        matched_resources = 0
        for object_id_str, monsters in drops.items():
            object_id = int(object_id_str)
            item_ids = ankama_to_ids.get(object_id) or []
            is_resource = object_id in resource_ankama_ids
            if not item_ids and not is_resource:
                continue  # a dropped thing we neither carry nor give a page to
            if item_ids:
                matched_items += 1
            if is_resource:
                matched_resources += 1
            for m in monsters:
                mid = m["monster_ankama_id"]
                rate = max(m.get("rates") or [0]) or 0
                conditions = m.get("conditions") or None
                for item_id in item_ids:
                    drop_rows.append((item_id, mid, rate, conditions))
                if is_resource:
                    resource_drop_rows.append((object_id, mid, rate, conditions))
                if mid not in seen_monster:
                    seen_monster.add(mid)
                    names = m.get("names") or {}
                    for lang in LANGUAGES:
                        if names.get(lang):
                            name_rows.append(
                                (mid, lang, clean_display_name(names[lang])))

        cursor.executemany(
            "INSERT INTO item_drops (item, monster_ankama_id, rate, conditions) "
            "VALUES (?, ?, ?, ?)",
            drop_rows)
        cursor.executemany(
            "INSERT INTO resource_drops (resource_ankama_id, monster_ankama_id, rate, conditions) "
            "VALUES (?, ?, ?, ?)",
            resource_drop_rows)
        cursor.executemany(
            "INSERT INTO monster_names (monster_ankama_id, language, name) VALUES (?, ?, ?)",
            name_rows)
        cursor.execute("CREATE INDEX idx_item_drops_item ON item_drops (item)")
        cursor.execute("CREATE INDEX idx_resource_drops_res ON resource_drops (resource_ankama_id)")
        cursor.execute(
            "CREATE INDEX idx_monster_names_id ON monster_names (monster_ankama_id)")
        # Not this script's table, but this script is what a rebuild runs and
        # the index is what makes the drop previews above cheap to read back.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_item_names_item ON item_names (item, language)")
        conn.commit()
        print("[%s] item_drops: %d rows / %d items; resource_drops: %d rows / %d resources; "
              "monster_names: %d rows (%d monsters)"
              % (game_version, len(drop_rows), matched_items, len(resource_drop_rows),
                 matched_resources, len(name_rows), len(seen_monster)))
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
