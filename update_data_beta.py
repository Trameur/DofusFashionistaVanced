#!/usr/bin/env python3
"""
update_data_beta.py - DofusFashionista data pipeline for Dofus 3 Beta

Usage:
    python update_data_beta.py                         # full update (current beta version)
    python update_data_beta.py --version 3.5.17.0      # update + bump beta version
    python update_data_beta.py --skip-images           # skip all image steps (faster)
    python update_data_beta.py --images-only           # only run image steps
    python update_data_beta.py --no-resize             # skip 60x60 resize step

Pipeline steps:
    items/download      get_equipments.py     -> itemscraper/all_*.json
    items/transform     get_equipments2.py    -> itemscraper/transformed_equipment.json
    items/dump          get_equipments3.py    -> item_db_dumped_beta.dump
    items/load-db       load_item_db.py       -> items_beta.db
    items/obtainment    store_item_obtainment.py -> recipes/descriptions in items_beta.db
    item-images         get_equipments4.py    -> static item images (shared with dofus3)
    spells/download     download_raw_data.py  -> itemscraper/raw/<version>/
    spells/transform    get_spells.py         -> itemscraper/transformed_spells_beta.json
    spells/duplicates   find_duplicated_damage_rows.py -> itemscraper/duplicated_damage_rows.json
    spells/constants    generate_damage_spells.py -> dofus_constants_beta.py
    spells/tooltips     store_spell_tooltips.py -> spell_tooltips (what a named spell does)
    spell-images        download_spell_images.py  -> static spell icons
    resize              resize_images.py      -> 60x60 thumbnails
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent
ITEMSCRAPER = ROOT / "itemscraper"
PY = sys.executable

BETA_API_URL = "https://api.dofusdu.de/dofus3beta/v1/"
BETA_REPO = "dofusdude/dofus3-beta"
BETA_DUMP = str(ROOT / "fashionistapulp" / "fashionistapulp" / "item_db_dumped_beta.dump")
BETA_WORK_DIR = str(ITEMSCRAPER / "beta")

NOTICE_KEYWORDS = [
    "attention", "warning", "could not find", "missing",
    "need attention", "not found", "updated", "removed for",
    "modified name", "ebony dofus", "mismatch",
]
NOISE_PATTERNS = [
    r"^\s*$",
    r"successfully saved",
    r"database import completed",
    r"permissions set",
    r"^\d+ files? correctly",
    r"^wrote \d+",
    r"\[exists\]",                        # download_raw_data: cached asset lines
    r"^\s*->\s+\S+:\s+[\d.]+\s+MB",     # download_raw_data: per-chunk progress
    r"^progress:\s*\d+%",               # get_equipments4: per-percent progress
    r"^skipping .+change below",        # get_equipments4: per-image skip
    r"^skipping ",                      # get_equipments3: unsupported stat/type names
    r"^updated damage_spells",
    r"damage_spells already up to date",
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
    status = "ok" if ok else "FAILED"
    print(f"  {status} ({elapsed:.1f}s)")
    return ok, lines


def extract_notices(lines: list[str]) -> list[str]:
    return [l.strip() for l in lines if _is_notice(l)]


def set_beta_version(new_version: str) -> str:
    version_file = ROOT / "fashionista_version.py"
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'FASHIONISTA_BETA_VERSION\s*=\s*"([^"]+)"', content)
    old_v = match.group(1) if match else "?"
    if old_v == new_version:
        print(f"[version] beta already {new_version}")
        return new_version
    new_content = re.sub(
        r'(FASHIONISTA_BETA_VERSION\s*=\s*)"[^"]+"',
        f'\\1"{new_version}"',
        content,
    )
    version_file.write_text(new_content, encoding="utf-8")
    print(f"[version] beta {old_v} -> {new_version}")
    return new_version


def get_current_beta_version() -> str:
    sys.path.insert(0, str(ROOT))
    import importlib
    if "fashionista_version" in sys.modules:
        importlib.reload(sys.modules["fashionista_version"])
    from fashionista_version import FASHIONISTA_BETA_VERSION
    return FASHIONISTA_BETA_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DofusFashionista data pipeline for Dofus 3 Beta",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", metavar="TAG", help="New beta version tag (e.g. 3.5.17.0)")
    parser.add_argument("--skip-images", action="store_true", help="Skip all image steps")
    parser.add_argument("--images-only", action="store_true", help="Only run image steps")
    parser.add_argument("--no-resize", action="store_true", help="Skip 60x60 resize step")
    args = parser.parse_args()

    t_total = time.time()
    all_notices: list[str] = []
    failed_steps: list[str] = []

    if args.version:
        version = set_beta_version(args.version)
    else:
        version = get_current_beta_version()
        print(f"[version] beta {version}")

    do_data = not args.images_only
    do_images = not args.skip_images

    print(f"\n{'-'*60}")
    print(f"  DofusFashionista update - BETA - version {version}")
    flags = []
    if args.images_only: flags.append("images-only")
    if args.skip_images: flags.append("skip-images")
    if args.no_resize: flags.append("no-resize")
    if flags: print(f"  Flags: {', '.join(flags)}")
    print(f"{'-'*60}")

    def step(label: str, cmd: list, cwd: Path | None = None) -> bool:
        ok, lines = run_step(label, cmd, cwd)
        all_notices.extend(extract_notices(lines))
        if not ok:
            failed_steps.append(label)
        return ok

    constants_beta = ROOT / "fashionistapulp" / "fashionistapulp" / "dofus_constants_beta.py"
    constants_src = ROOT / "fashionistapulp" / "fashionistapulp" / "dofus_constants.py"
    if not constants_beta.exists():
        shutil.copy(constants_src, constants_beta)
        print(f"[constants] bootstrapped dofus_constants_beta.py from dofus_constants.py")

    if do_data:
        step("items/download", [PY, "get_equipments.py", "--api-url", BETA_API_URL, "--work-dir", BETA_WORK_DIR,
                                "--skip-endpoints", "mounts"], cwd=ITEMSCRAPER)
        step("items/transform", [PY, "get_equipments2.py", "--work-dir", BETA_WORK_DIR], cwd=ITEMSCRAPER)
        step("items/dump", [PY, "get_equipments3.py", "--input-dir", BETA_WORK_DIR, "--dump-output", BETA_DUMP], cwd=ITEMSCRAPER)
        step("items/load-db", [PY, "load_item_db.py", "--game-version", "beta"])
        step("items/obtainment", [
            PY, "store_item_obtainment.py",
            "--game-version", "beta",
            str(ITEMSCRAPER / "beta"),
        ], cwd=ITEMSCRAPER)
        step("mount-looks", [PY, "store_dofusdb_mount_looks.py",
                             "--game-version", "beta"], cwd=ITEMSCRAPER)
        # Replayed, not matched: working the skins out from the art takes hours,
        # so the decisions it reached are kept in the repo. Beta renumbered a few
        # items, and --names catches those by type and name.
        step("item-skins", [PY, "store_item_skins.py", "--game-version", "beta",
                            "--input", "item_skins.json",
                            "--names", "item_skins_by_name.json"], cwd=ITEMSCRAPER)

    if do_images:
        step("item-images", [
            PY, "get_equipments4.py",
            "--game-version", "beta",
            "--input-file", str(ITEMSCRAPER / "beta" / "transformed_equipment.json"),
        ], cwd=ITEMSCRAPER)
        step("resource-icons", [PY, "download_resource_icons.py"], cwd=ITEMSCRAPER)
        step("monster-images", [PY, "download_monster_images.py"], cwd=ITEMSCRAPER)

    if do_data:
        step("spells/download", [
            PY, "-m", "itemscraper.download_raw_data",
            "--repo", BETA_REPO,
            "--tag", version,
            "--filter", "spell",
            "--filter", "effects.json",
            "--filter", "breeds.json",
            "--filter", "monsters.json",
            "--filter", "recipes.json",
            "--filter", "jobs.json",
            "--filter", "en.json",
            "--filter", "fr.json",
            "--filter", "es.json",
            "--filter", "pt.json",
            "--filter", "de.json",
        ])
        step("spells/transform", [
            PY, "-m", "itemscraper.get_spells",
            "--tag", version,
            "--output", "itemscraper/transformed_spells_beta.json",
            "--class-output", "itemscraper/transformed_class_spells_beta.json",
        ])
        step("spells/duplicates", [PY, "-m", "itemscraper.find_duplicated_damage_rows"])
        step("spells/constants", [
            PY, "-m", "itemscraper.generate_damage_spells",
            "--class-json", "itemscraper/transformed_class_spells_beta.json",
            "--spells-json", "itemscraper/transformed_spells_beta.json",
            "--constants", "fashionistapulp/fashionistapulp/dofus_constants_beta.py",
        ])
        # What the spells an item names actually do, for the tooltip on the
        # extra lines. Needs both the spell archive and the finished item db.
        step("spells/tooltips", [
            PY, "-m", "itemscraper.store_spell_tooltips",
            "--game-version", "beta", "--tag", version,
        ])
        # Monster drops -> item_drops / monster_names in items_beta.db (encyclopedia "Dropped by").
        step("drops/transform", [
            PY, "get_monsters.py",
            "--dataset-dir", f"raw/{version}",
            "--output", "transformed_drops_beta.json",
        ], cwd=ITEMSCRAPER)
        step("drops/store", [
            PY, "store_drops.py",
            "--drops", "transformed_drops_beta.json",
            "--game-version", "beta",
        ], cwd=ITEMSCRAPER)
        # After drops/store, which is what creates monster_names: all three read
        # it to know which monsters the database has. items/load-db rebuilds the
        # file from the item dump, so on a run from scratch these three used to
        # find no such table and die, and the rebuilt database came out with no
        # monster grade, subarea or spell at all.
        step("monster-grades", [PY, "store_dofusdb_monster_grades.py",
                                "--game-version", "beta"], cwd=ITEMSCRAPER)
        step("monster-subareas", [PY, "store_dofusdb_monster_subareas.py",
                                     "--game-version", "beta"], cwd=ITEMSCRAPER)
        step("monster-spells", [PY, "store_monster_spells.py",
                                "--game-version", "beta"], cwd=ITEMSCRAPER)
        # Craft professions -> item_craft_jobs / job_names ("Crafted by ...").
        step("craftjobs/transform", [
            PY, "get_craft_jobs.py",
            "--dataset-dir", f"raw/{version}",
            "--output", "transformed_craft_jobs_beta.json",
        ], cwd=ITEMSCRAPER)
        step("craftjobs/store", [

            PY, "store_craft_jobs.py",
            "--jobs", "transformed_craft_jobs_beta.json",
            "--game-version", "beta",
        ], cwd=ITEMSCRAPER)

    # Manual fixes last, so they survive whatever the stores rebuilt.
    step("items/corrections", [
        PY, "store_item_corrections.py", "--game-version", "beta",
    ], cwd=ITEMSCRAPER)

    # Data changed: refresh the scanned list of runtime-translated
    # strings (item types, stats...) so makemessages keeps them.
    step("dynamic-translations", [PY, "generate_dynamic_translations.py"], cwd=ITEMSCRAPER)

    if do_images:
        step("spell-images", [
            PY, "-m", "itemscraper.download_spell_images",
            "--version", version,
            "--size", "96",
            "--scope", "damage",
            "--prune",
            "--metadata", "itemscraper/transformed_spells_beta.json",
            "--constants", "fashionistapulp/fashionistapulp/dofus_constants_beta.py",
            "--static-dir", "fashionsite/chardata/static/chardata/spells/beta",
            "--extra-static-dirs", "fashionsite/staticfiles/chardata/spells/beta",
        ])

    if do_images and not args.no_resize:
        step("resize", [PY, "resize_images.py"])

    elapsed = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"  Beta update complete - {elapsed:.0f}s")
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
