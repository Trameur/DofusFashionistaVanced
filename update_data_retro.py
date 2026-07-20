#!/usr/bin/env python3
"""
update_data_retro.py - DofusFashionista data pipeline for Dofus Retro (1.29)

Usage:
    python update_data_retro.py                    # full update (latest CDN lang versions)
    python update_data_retro.py --skip-translations  # FR names only (faster)

Unlike Dofus 2/3/Beta, Retro has no version tag to bump: the source is Ankama's
official "lang" CDN and download_retro_langs.py always fetches the latest versions
listed in the live manifest (versions_<lang>.txt).

Pipeline steps:
    lang/download-fr     download_retro_langs.py  -> retro_raw/{items,itemstats,itemsets}_fr.json
    lang/download-en/... download_retro_langs.py  -> retro_raw/items_{en,es,pt,de}.json (names)
    items/transform      get_equipments_retro.py  -> retro/transformed_{equipment,sets}.json
    items/dump           get_equipments3.py        -> item_db_dumped_retro.dump
    items/load-db        load_item_db.py           -> items_retro.db
    drops/transform      get_monsters_retro.py     -> itemscraper/transformed_drops_retro.json (Solomonk.fr 1.48)
    drops/store          store_drops.py            -> item_drops / monster_names in items_retro.db
    item-images          download_retro_images.py  -> static/chardata/{items,pets}/retro/60x60/ (Cyberia CDN)
    spells/decode        get_spells_retro.py       -> dofus_constants_retro_spells.py (DAMAGE_SPELLS)
    spell-images         download_retro_spell_images.py -> static/chardata/spells/retro/ (Cyberia CDN)

Set bonuses are NOT in the lang CDN (1.29 set bonuses are server-side): they are
scraped from Solomonk set pages by get_retro_set_bonuses.py (legacy snapshot and
committed-db fallbacks for the sets Solomonk lacks) into retro_set_bonuses.json,
matched to lang sets by ankama id inside get_equipments_retro.py.

Item/mount icons and damage-spell icons come from the community Cyberia CDN
(download_retro_images.py, download_retro_spell_images.py).
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

RETRO_RAW_DIR = str(ITEMSCRAPER / "retro_raw")
RETRO_WORK_DIR = str(ITEMSCRAPER / "retro")
RETRO_DUMP = str(ROOT / "fashionistapulp" / "fashionistapulp" / "item_db_dumped_retro.dump")

NOTICE_KEYWORDS = [
    "attention", "warning", "could not", "missing", "not found",
    "failed", "mismatch", "error",
]
NOISE_PATTERNS = [
    r"^\s*$",
    r"successfully saved",
    r"database import completed",
    r"permissions set",
    r"^wrote \d+",
    r"^\s*ok ",
    r"^done",
    r"^fetching ",
    r"^\s+\d+ categories available",
    r"^skipping ",          # dump routes weapon hit lines out of stats_of_item
    r"is missing ap",       # retro weapons now carry ap; keep quiet if any slip
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
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd or ROOT),
        env=get_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
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


def extract_notices(lines: list[str]) -> list[str]:
    return [l.strip() for l in lines if _is_notice(l)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DofusFashionista data pipeline for Dofus Retro (1.29)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--skip-translations", action="store_true",
                        help="Skip the EN/ES/PT/DE name downloads (use FR names everywhere)")
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip the item/mount icon download from the Cyberia CDN")
    parser.add_argument("--lang", default="fr", help="Primary lang for names (default fr)")
    args = parser.parse_args()

    t_total = time.time()
    all_notices: list[str] = []
    failed_steps: list[str] = []

    print(f"\n{'-'*60}")
    print(f"  DofusFashionista update - DOFUS RETRO 1.29 (lang: {args.lang})")
    print(f"{'-'*60}")

    def step(label: str, cmd: list, cwd: Path | None = None) -> bool:
        ok, lines = run_step(label, cmd, cwd)
        all_notices.extend(extract_notices(lines))
        if not ok:
            failed_steps.append(label)
        return ok

    step("lang/download-fr", [
        PY, "download_retro_langs.py",
        "--lang", args.lang,
        "--categories", "items", "itemstats", "itemsets", "spells", "classes",
        "jobs", "skills", "monsters",
        "--dest", RETRO_RAW_DIR,
    ], cwd=ITEMSCRAPER)

    if not args.skip_translations:
        # Pull item names for the other supported languages (ES/PT ~= 40% of users).
        for lang in ("en", "es", "pt", "de"):
            if lang == args.lang:
                continue
            step(f"lang/download-{lang}", [
                PY, "download_retro_langs.py",
                "--lang", lang,
                "--categories", "items", "spells", "jobs",
                "--dest", RETRO_RAW_DIR,
            ], cwd=ITEMSCRAPER)

    # Set bonuses from the Dofus Retro Tools API (expressly offered, keyed
    # by ankama set id; replaced the Solomonk page scrape per the sourcing
    # policy). A network failure leaves the committed retro_set_bonuses.json
    # in place for items/transform below.
    step("sets/bonuses", [
        PY, "get_retro_set_bonuses.py",
    ], cwd=ITEMSCRAPER)

    step("items/transform", [
        PY, "get_equipments_retro.py",
        "--raw-dir", RETRO_RAW_DIR,
        "--out-dir", RETRO_WORK_DIR,
        "--set-bonuses", str(ITEMSCRAPER / "retro_set_bonuses.json"),
        "--lang", args.lang,
    ], cwd=ITEMSCRAPER)

    step("items/dump", [
        PY, "get_equipments3.py",
        "--input-dir", RETRO_WORK_DIR,
        "--dump-output", RETRO_DUMP,
    ], cwd=ITEMSCRAPER)

    step("items/load-db", [PY, "load_item_db.py", "--game-version", "retro"])

    # Monster drops -> item_drops / monster_names in items_retro.db (encyclopedia "Dropped by").
    # Retro has no first-party drop source (the 1.29 client/lang files carry monster names but
    # not the server-side drop tables, and Ankama has no Retro monster encyclopedia), so we scrape
    # the current (1.48) community reference Solomonk.fr. Runs after load-db, which rebuilds the DB
    # from the dump; store_drops then adds the two tables and re-dumps so both stay in sync.
    # Craft recipes from the 1.29 crafts lang (load-db rebuilds the DB from
    # the dump, dropping them: this restores the tables and re-dumps).
    # MUST run before drops/store: store_drops classifies a drop as a
    # resource via item_recipe_ingredient_names, which is empty until here
    # (an empty table once zeroed resource_drops on a full rebuild).
    step("recipes/store", [
        PY, "store_retro_recipes.py",
    ], cwd=ITEMSCRAPER)

    step("drops/transform", [
        PY, "get_monsters_retro.py",
        "--output", "transformed_drops_retro.json",
    ], cwd=ITEMSCRAPER)

    step("drops/store", [
        PY, "store_drops.py",
        "--drops", "transformed_drops_retro.json",
        "--game-version", "retro",
    ], cwd=ITEMSCRAPER)

    # Per-grade 1.29 monster stats from the same Solomonk bestiary cards
    # (level, HP, AP, MP, dodges, resistances); re-dumps to stay in sync.
    step("monsters/grades", [
        PY, "store_retro_monster_grades.py",
    ], cwd=ITEMSCRAPER)

    # Where each monster can be found (Solomonk subarea blocks, localized);
    # re-dumps to stay in sync like the other stores.
    step("monsters/subareas", [
        PY, "store_retro_monster_subareas.py",
    ], cwd=ITEMSCRAPER)

    # Monster artworks straight from the official 1.29 client (Cytrus CDN,
    # clips/artworks/big). Existing WebPs are skipped; without java/ffdec/
    # resvg on the machine the script warns and leaves the committed art.
    step("monsters/artworks", [
        PY, "download_retro_monster_artworks.py",
    ], cwd=ITEMSCRAPER)

    # Refresh the pet feeding caps first (dofux + Solomonk, credited on
    # About; no first-hand source: the caps are server-side in 1.29). A
    # network failure leaves the committed retro_pet_bonuses.json in place.
    step("pets/scrape", [
        PY, "scrape_retro_pet_bonuses.py",
    ], cwd=ITEMSCRAPER)

    # Pet variants (one maxed variant per bonus, from the vendored
    # retro_pet_bonuses.json snapshot): load-db drops them with every
    # rebuild, this recreates them (idempotent) and re-dumps.
    step("pets/store", [
        PY, "store_retro_pet_bonuses.py",
    ], cwd=ITEMSCRAPER)

    # Craft professions ("Crafted by ..."): the 1.29 skills lang lists every
    # craftable item per skill (cl) with its owning job; jobs_<lang> localizes
    # the pre-merge profession names. No per-recipe level in 1.29 data.
    step("craftjobs/transform", [
        PY, "get_craft_jobs_retro.py",
        "--raw-dir", RETRO_RAW_DIR,
        "--output", "transformed_craft_jobs_retro.json",
    ], cwd=ITEMSCRAPER)

    step("craftjobs/store", [
        PY, "store_craft_jobs.py",
        "--jobs", "transformed_craft_jobs_retro.json",
        "--game-version", "retro",
    ], cwd=ITEMSCRAPER)

    # Data changed: refresh the scanned list of runtime-translated
    # strings (item types, stats...) so makemessages keeps them.
    step("dynamic-translations", [PY, "generate_dynamic_translations.py"], cwd=ITEMSCRAPER)

    if not args.skip_images:
        step("item-images", [
            PY, "download_retro_images.py",
            "--raw-dir", RETRO_RAW_DIR,
            "--lang", args.lang,
        ], cwd=ITEMSCRAPER)
        step("resource-icons", [
            PY, "download_resource_icons.py",
            "--game-version", "retro",
        ], cwd=ITEMSCRAPER)

    step("spells/decode", [
        PY, "get_spells_retro.py",
        "--raw-dir", RETRO_RAW_DIR,
        "--out", str(ITEMSCRAPER / "retro" / "retro_damage_spells.json"),
        "--module-out", str(ROOT / "fashionistapulp" / "fashionistapulp"
                            / "dofus_constants_retro_spells.py"),
        "--lang", args.lang,
    ], cwd=ITEMSCRAPER)

    if not args.skip_images:
        step("spell-images", [PY, "download_retro_spell_images.py"], cwd=ITEMSCRAPER)

    elapsed = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"  Dofus Retro update complete - {elapsed:.0f}s")
    print(f"{'='*60}")

    if failed_steps:
        print(f"\nFAILED steps ({len(failed_steps)}):")
        for s in failed_steps:
            print(f"   - {s}")

    seen: set[str] = set()
    unique_notices = [n for n in all_notices if not (n in seen or seen.add(n))]
    if unique_notices:
        print(f"\nWarnings / items to review ({len(unique_notices)}):")
        for n in unique_notices:
            print(f"   - {n}")
    else:
        print("\nNo warnings")

    if failed_steps:
        sys.exit(1)


if __name__ == "__main__":
    main()
