#!/usr/bin/env python3
"""
update_data_retro.py - DofusFashionista data pipeline for Dofus Retro (1.29)

Usage:
    python update_data_retro.py                    # full update (latest CDN lang versions)
    python update_data_retro.py --skip-translations  # FR names only (faster)
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
    r"^skipping ",          # weapon hit lines the dump keeps out of stats_of_item
    r"is missing ap",
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
                        help="Skip the item/mount icon rendering step")
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
        "jobs", "skills", "monsters", "effects",
        "--dest", RETRO_RAW_DIR,
    ], cwd=ITEMSCRAPER)

    if not args.skip_translations:
        # Names in the other languages, plus itemstats: no lang file is complete
        for lang in ("en", "es", "pt", "de"):
            if lang == args.lang:
                continue
            step(f"lang/download-{lang}", [
                PY, "download_retro_langs.py",
                "--lang", lang,
                "--categories", "items", "itemstats", "spells", "jobs",
                "--dest", RETRO_RAW_DIR,
            ], cwd=ITEMSCRAPER)

    # Set bonuses are server-side: solomonk.fr, then the Dofus Retro Tools API
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

    # Before drops/store: it finds resources through item_recipe_ingredient_names
    step("recipes/store", [
        PY, "store_retro_recipes.py",
    ], cwd=ITEMSCRAPER)

    # Pet feeding caps are server-side in 1.29: dofux and Solomonk
    step("pets/scrape", [
        PY, "scrape_retro_pet_bonuses.py",
    ], cwd=ITEMSCRAPER)

    # Pet variants, before drops/store: it only fills the rows that already exist
    step("pets/store", [
        PY, "store_retro_pet_bonuses.py",
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

    # Per-grade monster stats from the Solomonk bestiary
    step("monsters/grades", [
        PY, "store_retro_monster_grades.py",
    ], cwd=ITEMSCRAPER)

    # Where each monster can be found, from Solomonk
    step("monsters/subareas", [
        PY, "store_retro_monster_subareas.py",
    ], cwd=ITEMSCRAPER)

    # Subarea names in five languages, after monsters/subareas which rebuilds the table
    step("monsters/subarea-langs", [
        PY, "store_retro_subarea_languages.py",
    ], cwd=ITEMSCRAPER)

    # Monster artworks from the 1.29 client, needs java, ffdec and resvg
    step("monsters/artworks", [
        PY, "download_retro_monster_artworks.py",
    ], cwd=ITEMSCRAPER)

    # Craft professions from the skills lang, 1.29 has no per-recipe level
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

    # Item descriptions for the encyclopedia pages
    step("descriptions/store", [PY, "store_retro_descriptions.py"], cwd=ITEMSCRAPER)

    # Runtime-translated strings, for makemessages
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

    # Tooltips for the spells an item names
    step("spells/tooltips", [
        PY, "-m", "itemscraper.store_spell_tooltips", "--game-version", "retro",
    ])
    step("spells/modifiers", [
        PY, "-m", "itemscraper.store_spell_modifiers", "--game-version", "retro",
    ])

    # Manual fixes last, after the stores
    step("items/corrections", [
        PY, "store_item_corrections.py", "--game-version", "retro",
    ], cwd=ITEMSCRAPER)

    step("spells/reference", [
        PY, "itemscraper/store_spell_reference.py",
        "--game-version", "retro",
    ])
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


    # Tables that lost rows, item ids that moved
    step("verify/rebuild", [PY, "check_rebuild.py", "--only", "retro"],
         cwd=ITEMSCRAPER)

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
