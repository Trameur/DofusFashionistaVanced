#!/usr/bin/env python3
"""
update_data_dofus2.py - DofusFashionista data pipeline for Dofus 2

Usage:
    python update_data_dofus2.py                         # full update (current dofus2 version)
    python update_data_dofus2.py --version 2.73.3.14     # update + bump dofus2 version
    python update_data_dofus2.py --skip-images           # skip all image steps (faster)
    python update_data_dofus2.py --images-only           # only run image steps
    python update_data_dofus2.py --no-resize             # skip 60x60 resize step

Pipeline steps:
    items/download      get_equipments.py     -> itemscraper/dofus2/all_*.json
    items/transform     get_equipments2.py    -> itemscraper/dofus2/transformed_equipment.json
    items/dump          get_equipments3.py    -> item_db_dumped_dofus2.dump
    items/load-db       load_item_db.py       -> items_dofus2.db
    items/obtainment    store_item_obtainment.py -> recipes/descriptions in items_dofus2.db
    item-images         get_equipments4.py    -> static item images (shared with dofus3)
    monsters/grades     store_dofus2_monster_grades.py -> monster_grades in items_dofus2.db
    spells/download     download_raw_data.py  -> itemscraper/raw/<version>/
    spells/transform    get_spells.py         -> itemscraper/transformed_spells_dofus2.json
    spells/constants    generate_damage_spells.py -> dofus_constants_dofus2.py
    spell-icons         store_dofus2_spell_icons.py -> spells/dofus2/ (the renamed ones)
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

DOFUS2_API_URL = "https://api.dofusdu.de/dofus2/"
DOFUS2_REPO = "dofusdude/dofus2-main"
DOFUS2_DUMP = str(ROOT / "fashionistapulp" / "fashionistapulp" / "item_db_dumped_dofus2.dump")
DOFUS2_WORK_DIR = str(ITEMSCRAPER / "dofus2")

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
    r"\[exists\]",
    r"^\s*->\s+\S+:\s+[\d.]+\s+MB",
    r"^progress:\s*\d+%",
    r"^skipping .+change below",
    r"^skipping ",
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


def set_dofus2_version(new_version: str) -> str:
    version_file = ROOT / "fashionista_version.py"
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'FASHIONISTA_DOFUS2_VERSION\s*=\s*"([^"]+)"', content)
    old_v = match.group(1) if match else "?"
    if old_v == new_version:
        print(f"[version] dofus2 already {new_version}")
        return new_version
    new_content = re.sub(
        r'(FASHIONISTA_DOFUS2_VERSION\s*=\s*)"[^"]+"',
        f'\\1"{new_version}"',
        content,
    )
    version_file.write_text(new_content, encoding="utf-8")
    print(f"[version] dofus2 {old_v} -> {new_version}")
    return new_version


def get_current_dofus2_version() -> str:
    sys.path.insert(0, str(ROOT))
    import importlib
    if "fashionista_version" in sys.modules:
        importlib.reload(sys.modules["fashionista_version"])
    from fashionista_version import FASHIONISTA_DOFUS2_VERSION
    return FASHIONISTA_DOFUS2_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DofusFashionista data pipeline for Dofus 2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", metavar="TAG", help="New dofus2 version tag (e.g. 2.73.3.14)")
    parser.add_argument("--skip-images", action="store_true", help="Skip all image steps")
    parser.add_argument("--images-only", action="store_true", help="Only run image steps")
    parser.add_argument("--no-resize", action="store_true", help="Skip 60x60 resize step")
    args = parser.parse_args()

    t_total = time.time()
    all_notices: list[str] = []
    failed_steps: list[str] = []

    if args.version:
        version = set_dofus2_version(args.version)
    else:
        version = get_current_dofus2_version()
        print(f"[version] dofus2 {version}")

    do_data = not args.images_only
    do_images = not args.skip_images

    print(f"\n{'-'*60}")
    print(f"  DofusFashionista update - DOFUS 2 - version {version}")
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

    constants_dofus2 = ROOT / "fashionistapulp" / "fashionistapulp" / "dofus_constants_dofus2.py"
    constants_src = ROOT / "fashionistapulp" / "fashionistapulp" / "dofus_constants.py"
    if not constants_dofus2.exists():
        shutil.copy(constants_src, constants_dofus2)
        print(f"[constants] bootstrapped dofus_constants_dofus2.py from dofus_constants.py")

    if do_data:
        step("items/download", [PY, "get_equipments.py", "--api-url", DOFUS2_API_URL, "--work-dir", DOFUS2_WORK_DIR,
                                "--skip-endpoints", "mounts"], cwd=ITEMSCRAPER)
        step("items/transform", [PY, "get_equipments2.py", "--work-dir", DOFUS2_WORK_DIR], cwd=ITEMSCRAPER)
        step("items/dump", [PY, "get_equipments3.py", "--input-dir", DOFUS2_WORK_DIR, "--dump-output", DOFUS2_DUMP], cwd=ITEMSCRAPER)
        step("items/load-db", [PY, "load_item_db.py", "--game-version", "dofus2"])
        # Descriptions and recipes, and with them the ingredient table drops/store
        # reads to know which resources have a page of their own. Dofus 3 and the
        # beta have always run this; Dofus 2 was left to a hand-typed command, so
        # any rebuild came out with no description, no recipe and no resource drop
        # at all, while still exiting 0.
        step("items/obtainment", [
            PY, "store_item_obtainment.py",
            "--game-version", "dofus2",
            str(ITEMSCRAPER / "dofus2"),
        ], cwd=ITEMSCRAPER)
        # What the spells an item names actually do, for the tooltip on the
        # extra lines. The 2.73 archive ships no spell levels but it does ship
        # the spell text, so this one works where spells/constants cannot.
        step("spells/tooltips", [
            PY, "-m", "itemscraper.store_spell_tooltips",
            "--game-version", "dofus2", "--tag", version,
        ])

    if do_images:
        step("item-images", [
            PY, "get_equipments4.py",
            "--game-version", "dofus2",
            "--input-file", str(ITEMSCRAPER / "dofus2" / "transformed_equipment.json"),
        ], cwd=ITEMSCRAPER)
        step("resource-icons", [PY, "download_resource_icons.py", "--game-version", "dofus2"],
             cwd=ITEMSCRAPER)

    if do_data:
        step("spells/download", [
            PY, "-m", "itemscraper.download_raw_data",
            "--repo", DOFUS2_REPO,
            "--tag", version,
            "--filter", "spell",
            "--filter", "effects.json",
            "--filter", "breeds.json",
            "--filter", "monsters.json",
            "--filter", "en.json",
            "--filter", "fr.json",
            "--filter", "es.json",
            "--filter", "pt.json",
            "--filter", "de.json",
        ])
        # NO spells/transform + spells/constants here: the dofus2 archives
        # (2.73.3.7 and 2.73.3.9 are the only ones) ship no spell level
        # data at all, so get_spells/generate_damage_spells can never run
        # for this version. The committed DAMAGE_SPELLS block is the 2.73
        # content Dofus 3 launched with, with spell ids injected from the
        # archive names (see dofus_constants_dofus2.py header).
        # The archive does name every class spell and describe it, which is
        # what the reference carries; the numbers stay empty for this version.
        step("spells/reference", [
            PY, "itemscraper/store_spell_reference.py",
            "--game-version", "dofus2",
        ])
        # Monster drops -> item_drops / monster_names in items_dofus2.db (encyclopedia "Dropped by").
        step("drops/transform", [
            PY, "get_monsters.py",
            "--dataset-dir", f"raw/{version}",
            "--output", "transformed_drops_dofus2.json",
        ], cwd=ITEMSCRAPER)
        step("drops/store", [
            PY, "store_drops.py",
            "--drops", "transformed_drops_dofus2.json",
            "--game-version", "dofus2",
        ], cwd=ITEMSCRAPER)
        # Monster stats per grade -> monster_grades (the level range the
        # encyclopedia prints; dofus2 was the only version without it).
        step("monsters/grades", [
            PY, "store_dofus2_monster_grades.py",
            "--raw-dir", f"raw/{version}",
        ], cwd=ITEMSCRAPER)
        # Craft professions -> item_craft_jobs / job_names ("Crafted by ").
        # The dofus2 release ships no jobs.json: job ids are stable since the
        # 2.44 profession merge, so borrow the dofus3 id->nameId table (the
        # names still resolve in the dofus2 language files).
        from fashionista_version import FASHIONISTA_VERSION as _dofus3_version
        step("craftjobs/jobs-table", [
            PY, "-m", "itemscraper.download_raw_data",
            "--tag", _dofus3_version,
            "--filter", "jobs.json",
        ])
        step("craftjobs/transform", [
            PY, "get_craft_jobs.py",
            "--dataset-dir", f"raw/{version}",
            "--jobs-file", f"raw/{_dofus3_version}/jobs.json",
            "--output", "transformed_craft_jobs_dofus2.json",
        ], cwd=ITEMSCRAPER)
        step("craftjobs/store", [

            PY, "store_craft_jobs.py",
            "--jobs", "transformed_craft_jobs_dofus2.json",
            "--game-version", "dofus2",
        ], cwd=ITEMSCRAPER)

        # Replayed, not matched: Dofus 2 keeps the same equipment designs, so
        # the skins worked out from the Dofus 3 art fit here by ankama id, and
        # by type and name where Dofus 3 renumbered the item.
        step("item-skins", [PY, "store_item_skins.py", "--game-version", "dofus2",
                            "--input", "item_skins.json",
                            "--names", "item_skins_by_name.json"], cwd=ITEMSCRAPER)

    # Manual fixes last, so they survive whatever the stores rebuilt.
    step("items/corrections", [
        PY, "store_item_corrections.py", "--game-version", "dofus2",
    ], cwd=ITEMSCRAPER)

    # Data changed: refresh the scanned list of runtime-translated
    # strings (item types, stats...) so makemessages keeps them.
    step("dynamic-translations", [PY, "generate_dynamic_translations.py"], cwd=ITEMSCRAPER)

    if do_images:
        # download_spell_images cannot run here: the Dofus 2 release ships no
        # spell image archive, only items and mounts. The icons are addressed by
        # id though, so the ids from the 2.73 lang pick the right images out of
        # the Dofus 3 pool, and only the names Dofus 3 renamed are stored per
        # version. The rest is read from the shared directory.
        step("spell-icons", [PY, "store_dofus2_spell_icons.py"], cwd=ITEMSCRAPER)

    if do_images and not args.no_resize:
        step("resize", [PY, "resize_images.py"])


    # A rebuild reports success either way. This asks what it changed that
    # nobody asked for: a table that lost rows, an item whose row id moved.
    # A moved id empties that slot in every saved build, in silence, which is
    # how 82 Touch pets changed owner on 2026-08-15.
    step("verify/rebuild", [PY, "check_rebuild.py", "--only", "dofus2"],
         cwd=ITEMSCRAPER)

    elapsed = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"  Dofus 2 update complete - {elapsed:.0f}s")
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
