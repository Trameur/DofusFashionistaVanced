#!/usr/bin/env python3
"""
update_data_touch.py - DofusFashionista data pipeline for Dofus Touch.

Usage:
    python update_data_touch.py                  # full update (latest live Touch data)
    python update_data_touch.py --skip-images    # skip the item-icon download
    python update_data_touch.py --skip-translations  # FR names only (faster)

Like Retro, there's no version tag to bump: the data comes straight from the live
Touch backend, so download_touch_data.py always pulls the current tables. See
docs/touch_data_sources.md for where that data lives and how it's structured.

Steps:
    data/download    download_touch_data.py   -> touch_raw/{Items,ItemSets,ItemTypes,Effects,Recipes,Breeds}_<lang>.json
    data/mounts      download_touch_mounts.py -> touch_raw/mounts.json (names from backend, stats from encyclopedia)
    items/transform  get_equipments_touch.py  -> touch/transformed_{equipment,sets}.json
    items/dump       get_equipments3.py        -> item_db_dumped_touch.dump
    items/load-db    load_item_db.py           -> items_touch.db
    items/recipes    store_touch_recipes.py    -> item_recipes + descriptions + pods in items_touch.db
    items/special-spells store_touch_special_spells.py -> "casts spell" extra_lines (Dofus/shields)
    spells/build     get_spells_touch.py       -> dofus_constants_touch_spells.py (TOUCH_DAMAGE_SPELLS)
    item-images      download_touch_images.py  -> static/chardata/{items,pets}/touch/60x60/

Touch is a Dofus 2 fork with its own quirks (it keeps PvP resists, AP/MP parry and
reduction, dodge/lock and trap stats, and has 15 classes); get_equipments_touch.py
and version_compat.py handle those.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent
ITEMSCRAPER = ROOT / "itemscraper"
PY = sys.executable

TOUCH_RAW_DIR = str(ITEMSCRAPER / "touch_raw")
TOUCH_WORK_DIR = str(ITEMSCRAPER / "touch")
TOUCH_DUMP = str(ROOT / "fashionistapulp" / "fashionistapulp" / "item_db_dumped_touch.dump")

NOTICE_KEYWORDS = ["attention", "warning", "could not", "missing", "not found",
                   "failed", "mismatch", "error"]
NOISE_PATTERNS = [
    r"^\s*$", r"successfully saved", r"database import completed", r"permissions set",
    r"^wrote \d+", r"^\s*ok ", r"^done", r"^\s*\.\.\. \d+ written",
    r"^skipping ",                 # dump routes weapon hit lines out of stats_of_item
]


def _is_noise(line: str) -> bool:
    low = line.lower()
    return any(re.search(p, low) for p in NOISE_PATTERNS)


def _is_notice(line: str) -> bool:
    low = line.lower()
    return any(k in low for k in NOTICE_KEYWORDS)


def get_env() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_step(label: str, cmd: list, cwd: Path | None = None) -> tuple[bool, list[str]]:
    print(f"\n[{label}]")
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(cwd or ROOT), env=get_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    lines: list[str] = []
    for raw in proc.stdout:
        line = raw.rstrip()
        lines.append(line)
        if not _is_noise(line):
            print(f"  {line}")
    proc.wait()
    elapsed = time.time() - t0
    ok = proc.returncode == 0
    print(f"  {'ok' if ok else 'FAILED'} ({elapsed:.1f}s)")
    return ok, lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DofusFashionista data pipeline for Dofus Touch",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip the item/pet icon download from the Touch CDN")
    parser.add_argument("--skip-translations", action="store_true",
                        help="Skip the EN/ES/PT/DE name downloads (use FR names everywhere)")
    args = parser.parse_args()

    t_total = time.time()
    all_notices: list[str] = []
    failed_steps: list[str] = []

    print(f"\n{'-'*60}")
    print("  DofusFashionista update - DOFUS TOUCH")
    print(f"{'-'*60}")

    def step(label: str, cmd: list, cwd: Path | None = None) -> bool:
        ok, lines = run_step(label, cmd, cwd)
        all_notices.extend(l.strip() for l in lines if _is_notice(l))
        if not ok:
            failed_steps.append(label)
        return ok

    download_cmd = [PY, "download_touch_data.py", "--lang", "fr", "--dest", TOUCH_RAW_DIR]
    if not args.skip_translations:
        download_cmd.append("--all-langs")
    step("data/download", download_cmd, cwd=ITEMSCRAPER)

    # Mounts: names from the backend Mounts table, stats scraped from the Touch
    # encyclopedia (the backend has no mount stats). Must run before items/transform.
    step("data/mounts", [PY, "download_touch_mounts.py", "--dest", TOUCH_RAW_DIR],
         cwd=ITEMSCRAPER)

    step("items/transform", [
        PY, "get_equipments_touch.py",
        "--raw-dir", TOUCH_RAW_DIR, "--out-dir", TOUCH_WORK_DIR,
    ], cwd=ITEMSCRAPER)

    step("items/dump", [
        PY, "get_equipments3.py",
        "--input-dir", TOUCH_WORK_DIR, "--dump-output", TOUCH_DUMP,
    ], cwd=ITEMSCRAPER)

    step("items/load-db", [PY, "load_item_db.py", "--game-version", "touch"])

    # Recipes are added after load-db (the dump from get_equipments3 doesn't carry
    # them); this fills item_recipes in items_touch.db and re-dumps it.
    step("items/recipes", [PY, "store_touch_recipes.py"], cwd=ITEMSCRAPER)

    # "Casts spell at start of combat" tooltip lines (Dofus/shields) -> extra_lines.
    step("items/special-spells", [PY, "store_touch_special_spells.py"], cwd=ITEMSCRAPER)

    # Monster drops (from the backend Monsters table) -> item_drops / monster_names
    # in items_touch.db (encyclopedia "Dropped by"). Runs after recipes finalize the db.
    step("drops/transform", [
        PY, "get_monsters_touch.py",
        "--raw-dir", TOUCH_RAW_DIR, "--output", "transformed_drops_touch.json",
    ], cwd=ITEMSCRAPER)
    step("drops/store", [
        PY, "store_drops.py",
        "--drops", "transformed_drops_touch.json", "--game-version", "touch",
    ], cwd=ITEMSCRAPER)
    step("monsters/grades", [
        PY, "store_touch_monster_grades.py", "--raw-dir", TOUCH_RAW_DIR,
    ], cwd=ITEMSCRAPER)

    # Where each monster can be found: the client's SubAreas table (official
    # data proxy) lists the monsters per subarea with localized names.
    step("monsters/subareas", [
        PY, "store_touch_monster_subareas.py", "--download",
    ], cwd=ITEMSCRAPER)

    # Feeding pets carry no bonuses in the backend datacenter: scrape the official
    # dofus-touch.com encyclopedia hormone caps, then generate the maxed variants
    # ("<Pet> (+110 Agility)") the optimizer picks from. Runs after drops so the
    # re-dump keeps every table in sync.
    step("pets/scrape-bonuses", [PY, "scrape_touch_pet_bonuses.py"], cwd=ITEMSCRAPER)
    step("pets/store-bonuses", [PY, "store_touch_pet_bonuses.py"], cwd=ITEMSCRAPER)

    # Craft professions -> item_craft_jobs / job_names ("Crafted by ..."). The
    # localized Recipes_<lang>.json come from data/download with --all-langs.
    step("craftjobs/transform", [
        PY, "get_craft_jobs_touch.py",
        "--raw-dir", TOUCH_RAW_DIR,
        "--output", "transformed_craft_jobs_touch.json",
    ], cwd=ITEMSCRAPER)
    step("craftjobs/store", [
        PY, "store_craft_jobs.py",
        "--jobs", "transformed_craft_jobs_touch.json",
        "--game-version", "touch",
    ], cwd=ITEMSCRAPER)

    # Replayed, not matched: Touch is a fork of the Dofus 2 client and keeps the
    # same equipment designs, so the Dofus 3 skins fit here by ankama id, and by
    # type and name for the third of the catalogue Touch renumbered. Its own
    # mapping (item_skins_touch.json) is not used: the baked preview cache is a
    # single Dofus 3 id space and a Touch skin id there would draw another piece.
    step("item-skins", [PY, "store_item_skins.py", "--game-version", "touch",
                        "--input", "item_skins.json",
                        "--names", "item_skins_by_name.json"], cwd=ITEMSCRAPER)

    # Manual fixes last, so they survive whatever the stores rebuilt.
    step("items/corrections", [
        PY, "store_item_corrections.py", "--game-version", "touch",
    ], cwd=ITEMSCRAPER)

    # Data changed: refresh the scanned list of runtime-translated
    # strings (item types, stats...) so makemessages keeps them.
    step("dynamic-translations", [PY, "generate_dynamic_translations.py"], cwd=ITEMSCRAPER)

    # Damage spells per class -> dofus_constants_touch_spells.py (independent of items).
    step("spells/build", [PY, "get_spells_touch.py"], cwd=ITEMSCRAPER)

    if not args.skip_images:
        step("item-images", [PY, "download_touch_images.py", "--raw-dir", TOUCH_RAW_DIR],
             cwd=ITEMSCRAPER)
        step("resource-icons", [PY, "download_resource_icons.py", "--game-version", "touch"],
             cwd=ITEMSCRAPER)
        step("monster-images", [PY, "download_monster_images.py", "--game-version", "touch"],
             cwd=ITEMSCRAPER)

    elapsed = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"  Dofus Touch update complete - {elapsed:.0f}s")
    print(f"{'='*60}")

    if failed_steps:
        print(f"\nFAILED steps ({len(failed_steps)}):")
        for s in failed_steps:
            print(f"   - {s}")

    seen: set[str] = set()
    unique = [n for n in all_notices if not (n in seen or seen.add(n))]
    if unique:
        print(f"\nWarnings / items to review ({len(unique)}):")
        for n in unique:
            print(f"   - {n}")
    else:
        print("\nNo warnings")

    if failed_steps:
        sys.exit(1)


if __name__ == "__main__":
    main()
