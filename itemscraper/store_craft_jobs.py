#!/usr/bin/env python3
"""store_craft_jobs.py - load the crafted-item -> profession index (from
get_craft_jobs.py) into items.db and re-dump it, so the encyclopedia can show
"Craft: <job> (lvl N)" next to each recipe.

Same persistence model as store_drops.py: dofus3 rebuilds items.db from the dump
at runtime, so the dump is the source of truth (rebuild first, then re-dump);
every other version's committed items_<ver>.db is the runtime truth (edit in
place, then re-dump to keep them in sync).

    item_craft_jobs (item internal id, job_ankama_id, level)
    job_names       (job_ankama_id, language, name)

Usage (from repo root, after get_craft_jobs.py produced the index):
    python itemscraper/store_craft_jobs.py \
        --jobs itemscraper/transformed_craft_jobs.json --game-version dofus3
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


def store_craft_jobs(jobs_path, game_version="dofus3"):
    with open(jobs_path, "r", encoding="utf-8") as fh:
        index = json.load(fh)

    items_db_path = get_items_db_path(game_version)
    if game_version == 'dofus3':
        _load_db_from_dump(items_db_path, game_version)
    conn = sqlite3.connect(items_db_path)
    try:
        cursor = conn.cursor()
        ankama_to_id = {
            ankama_id: item_id
            for item_id, ankama_id in cursor.execute(
                "SELECT id, ankama_id FROM items WHERE ankama_id IS NOT NULL")
        }

        cursor.execute("DROP TABLE IF EXISTS item_craft_jobs")
        cursor.execute("DROP TABLE IF EXISTS job_names")
        cursor.execute(
            "CREATE TABLE item_craft_jobs (item INTEGER, job_ankama_id INTEGER, level INTEGER)")
        cursor.execute(
            "CREATE TABLE job_names (job_ankama_id INTEGER, language TEXT, name TEXT)")

        job_rows = []
        name_rows = []
        seen_jobs = set()
        for result_ankama_id_str, info in index.items():
            item_id = ankama_to_id.get(int(result_ankama_id_str))
            if item_id is None:
                continue  # a crafted resource/consumable we don't carry
            job_id = info["job_ankama_id"]
            job_rows.append((item_id, job_id, info.get("level") or 0))
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                for lang in LANGUAGES:
                    name = (info.get("names") or {}).get(lang)
                    if name:
                        name_rows.append((job_id, lang, name))

        cursor.executemany(
            "INSERT INTO item_craft_jobs (item, job_ankama_id, level) VALUES (?, ?, ?)",
            job_rows)
        cursor.executemany(
            "INSERT INTO job_names (job_ankama_id, language, name) VALUES (?, ?, ?)",
            name_rows)
        cursor.execute("CREATE INDEX idx_item_craft_jobs_item ON item_craft_jobs (item)")
        cursor.execute("CREATE INDEX idx_job_names_id ON job_names (job_ankama_id)")
        conn.commit()
        print("[%s] item_craft_jobs: %d rows; job_names: %d rows (%d jobs)"
              % (game_version, len(job_rows), len(name_rows), len(seen_jobs)))
    finally:
        conn.close()

    _save_db_to_dump(get_items_db_path(game_version), game_version)


def main():
    parser = argparse.ArgumentParser(
        description="Load the crafted-item -> profession index into items.db")
    parser.add_argument("--jobs", default="itemscraper/transformed_craft_jobs.json")
    parser.add_argument("--game-version", default="dofus3")
    args = parser.parse_args()
    store_craft_jobs(args.jobs, args.game_version)


if __name__ == "__main__":
    main()
