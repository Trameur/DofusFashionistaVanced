#!/usr/bin/env python3
"""
update_data_touch.py - DofusFashionista data pipeline for Dofus Touch.

Usage:
    python update_data_touch.py                  # full update (latest live Touch data)
    python update_data_touch.py --skip-images    # skip the item-icon download
    python update_data_touch.py --skip-translations  # FR names only (faster)
    python update_data_touch.py --channel early  # Touch Beta data, from Ankama's test server
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

sys.path.insert(0, str(ITEMSCRAPER))
import touch_channels  # noqa: E402

TOUCH_RAW_DIR = str(ITEMSCRAPER / "touch_raw")
TOUCH_WORK_DIR = str(ITEMSCRAPER / "touch")
TOUCH_DUMP = str(ROOT / "fashionistapulp" / "fashionistapulp" / "item_db_dumped_touch.dump")

NOT_REGISTERED = "the version is not in the game version registry yet"
NOTICE_KEYWORDS = ["attention", "warning", "could not", "missing", "not found",
                   "failed", "mismatch", "error"]
NOISE_PATTERNS = [
    r"^\s*$", r"successfully saved", r"database import completed", r"permissions set",
    r"^wrote \d+", r"^\s*ok ", r"^done", r"^\s*\.\.\. \d+ written",
    r"^skipping ",                 # dump routes weapon hit lines out of stats_of_item
]


def registered_versions() -> set:
    """The game versions the registry knows, staged ones included."""
    sys.path.insert(0, str(ROOT / "fashionistapulp"))
    from fashionistapulp.game_versions import version_keys
    return set(version_keys(include_experimental=True))


def with_channel(cmd: list, channel: str) -> list:
    """The command, asked to read a channel other than the default one."""
    if channel == touch_channels.DEFAULT_CHANNEL:
        return cmd
    return cmd + ["--channel", channel]


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
    touch_channels.add_channel_argument(parser)
    args = parser.parse_args()

    channel = args.channel
    key = touch_channels.game_version(channel)
    early = channel != touch_channels.DEFAULT_CHANNEL
    raw_dir = touch_channels.raw_dir(channel) if early else TOUCH_RAW_DIR
    work_dir = touch_channels.work_dir(channel) if early else TOUCH_WORK_DIR
    dump = touch_channels.dump_path(channel) if early else TOUCH_DUMP
    staged = early and key not in registered_versions()

    t_total = time.time()
    all_notices: list[str] = []
    failed_steps: list[str] = []

    print(f"\n{'-'*60}")
    print("  DofusFashionista update - DOFUS TOUCH" + (" (%s channel)" % channel if early else ""))
    print(f"{'-'*60}")

    def step(label: str, cmd: list, cwd: Path | None = None, aware: bool = True,
             early_skip: str = "") -> bool:
        if early and (early_skip or not aware):
            print(f"\n[{label}]\n  skipped: " + (early_skip or f"not read from the {channel} channel yet"))
            return True
        ok, lines = run_step(label, cmd, cwd)
        all_notices.extend(l.strip() for l in lines if _is_notice(l))
        if not ok:
            failed_steps.append(label)
        return ok

    download_cmd = [PY, "download_touch_data.py", "--lang", "fr", "--dest", raw_dir]
    if not args.skip_translations:
        download_cmd.append("--all-langs")
    step("data/download", with_channel(download_cmd, channel), cwd=ITEMSCRAPER)

    if early and not args.skip_translations:
        step("data/seed-languages", [
            PY, "seed_unserved_language.py", "--channel", channel,
            "--tables", "Items", "ItemSets", "ItemTypes", "Monsters", "Recipes",
        ], cwd=ITEMSCRAPER)

    # Backend has no mount stats, they come from the encyclopedia. Before items/transform
    step("data/mounts", with_channel([PY, "download_touch_mounts.py", "--dest", raw_dir], channel),
         cwd=ITEMSCRAPER)

    step("stats/starting", [
        PY, "itemscraper/store_starting_stats.py", "--game-version", key,
    ], early_skip=NOT_REGISTERED if staged else "")

    step("items/weapon-conversions", [
        PY, "itemscraper/store_weapon_conversions.py", "--game-version", key,
    ], early_skip=NOT_REGISTERED if staged else "")

    step("items/transform", [
        PY, "get_equipments_touch.py",
        "--raw-dir", raw_dir, "--out-dir", work_dir,
    ], cwd=ITEMSCRAPER)

    if staged:
        print(f"\n{key} is not in the game version registry yet: raw tables, mounts and the "
              f"transformed files are written, the database steps wait for it.")
        if failed_steps:
            print("\nFAILED steps: " + ", ".join(failed_steps))
            sys.exit(1)
        return

    step("items/dump", [
        PY, "get_equipments3.py",
        "--input-dir", work_dir, "--dump-output", dump,
    ], cwd=ITEMSCRAPER)

    step("items/load-db", [PY, "load_item_db.py", "--game-version", key])

    # The dump has no recipes, added after load-db
    step("items/recipes", with_channel([PY, "store_touch_recipes.py"], channel), cwd=ITEMSCRAPER)

    # "Casts spell at start of combat" tooltip lines (Dofus/shields) -> extra_lines.
    step("items/special-spells", with_channel([PY, "store_touch_special_spells.py"], channel),
         cwd=ITEMSCRAPER)

    # What those spells do, for their tooltip
    step("spells/tooltips", [
        PY, "-m", "itemscraper.store_spell_tooltips", "--game-version", key,
    ])
    step("spells/modifiers", [
        PY, "-m", "itemscraper.store_spell_modifiers", "--game-version", key,
    ])

    # Pet bonuses from the encyclopedia; before drops/store or the variants get no drops
    step("pets/scrape-bonuses", [PY, "scrape_touch_pet_bonuses.py"], cwd=ITEMSCRAPER,
         early_skip="the official encyclopedia only describes the live game; the login "
                    "bonuses are used")
    step("pets/store-bonuses", with_channel([PY, "store_touch_pet_bonuses.py"], channel),
         cwd=ITEMSCRAPER)

    # Monster drops -> item_drops / monster_names
    drops_file = "transformed_drops_%s.json" % key
    step("drops/transform", [
        PY, "get_monsters_touch.py",
        "--raw-dir", raw_dir, "--output", drops_file,
    ], cwd=ITEMSCRAPER)
    step("drops/store", [
        PY, "store_drops.py",
        "--drops", drops_file, "--game-version", key,
    ], cwd=ITEMSCRAPER)
    step("monsters/grades", with_channel([
        PY, "store_touch_monster_grades.py", "--raw-dir", raw_dir,
    ], channel), cwd=ITEMSCRAPER)

    # Monster locations from the SubAreas table
    step("monsters/subareas", [
        PY, "store_touch_monster_subareas.py", "--download",
    ] + (["--channel", channel] if early else []), cwd=ITEMSCRAPER)

    # Craft professions -> item_craft_jobs / job_names, names need --all-langs
    jobs_file = "transformed_craft_jobs_%s.json" % key
    step("craftjobs/transform", [
        PY, "get_craft_jobs_touch.py",
        "--raw-dir", raw_dir,
        "--output", jobs_file,
    ], cwd=ITEMSCRAPER)
    step("craftjobs/store", [
        PY, "store_craft_jobs.py",
        "--jobs", jobs_file,
        "--game-version", key,
    ], cwd=ITEMSCRAPER)

    # Dofus 3 skins by ankama id, or type and name; the preview cache only knows Dofus 3 ids
    step("item-skins", [PY, "store_item_skins.py", "--game-version", key,
                        "--input", "item_skins.json",
                        "--names", "item_skins_by_name.json"], cwd=ITEMSCRAPER)

    # Manual fixes last
    step("items/corrections", [
        PY, "store_item_corrections.py", "--game-version", key,
    ], cwd=ITEMSCRAPER)

    # Runtime-translated strings (item types, stats...) for makemessages
    step("dynamic-translations", [PY, "generate_dynamic_translations.py"], cwd=ITEMSCRAPER,
         aware=False)

    # Damage spells per class -> dofus_constants_touch_spells.py (independent of items).
    step("spells/build", with_channel([PY, "get_spells_touch.py"], channel), cwd=ITEMSCRAPER)
    step("spells/reference", [
        PY, "itemscraper/store_spell_reference.py",
        "--game-version", key,
    ])

    if not args.skip_images:
        step("item-images", with_channel(
            [PY, "download_touch_images.py", "--raw-dir", raw_dir], channel), cwd=ITEMSCRAPER)
        step("resource-icons", with_channel(
            [PY, "download_resource_icons.py", "--game-version", "touch"], channel),
             cwd=ITEMSCRAPER)
        step("monster-images", with_channel(
            [PY, "download_monster_images.py", "--game-version", "touch"], channel),
             cwd=ITEMSCRAPER)


    # Tables that lost rows, items whose row id moved
    step("verify/rebuild", [PY, "check_rebuild.py", "--only", key], cwd=ITEMSCRAPER)

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
