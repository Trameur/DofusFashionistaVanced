#!/usr/bin/env python3
"""
update_data_beta.py - DofusFashionista data pipeline for Dofus 3 Beta

Usage:
    python update_data_beta.py                         # full update (current beta version)
    python update_data_beta.py --version 3.5.17.0      # update + bump beta version
    python update_data_beta.py --skip-images           # skip all image steps (faster)
    python update_data_beta.py --images-only           # only run image steps
    python update_data_beta.py --no-resize             # skip 60x60 resize step
    python update_data_beta.py --version 3.8.2.3 --local-raw itemscraper/raw/3.8.2.3
                                                       # items and spells from our own client extraction

With --local-raw the folder holds the client extraction plus what doduda 0.7.5
made from it: MAPPED_ITEMS, MAPPED_SETS and MAPPED_RECIPES.json (doduda map)
next to the dump, and img/item/1x and 2x (doduda images). --local-mapped and
--local-icons default to those. Every data step reads the folder; only item
icons missing from img/item are fetched, and the resource and monster image
downloads are skipped.

Pipeline steps:
    items/download      get_equipments.py     -> itemscraper/all_*.json
    data/download       download_raw_data.py  -> itemscraper/raw/<version>/items.json
    items/transform     get_equipments2.py    -> itemscraper/transformed_equipment.json
    items/dump          get_equipments3.py    -> item_db_dumped_beta.dump
    items/load-db       load_item_db.py       -> items_beta.db
    items/obtainment    store_item_obtainment.py -> recipes/descriptions in items_beta.db
    item-images         get_equipments4.py    -> static item images (shared with dofus3)
    spells/download     download_raw_data.py  -> itemscraper/raw/<version>/
    spells/transform    get_spells.py         -> itemscraper/transformed_spells_beta.json
    spells/duplicates   find_duplicated_damage_rows.py -> itemscraper/duplicated_damage_rows.json
    spells/variants     store_spell_variants.py -> spell_variants.json (beta entry)
    spells/reference    store_spell_reference.py -> spell_reference/beta.json
    stats/starting      store_starting_stats.py -> starting_stats/beta.json
    items/weapon-conversions store_weapon_conversions.py -> weapon_conversions/beta.json
    items/dracorunes    store_dracorunes.py   -> dracorunes/beta.json (only if the dump has runes)
    items/transcendence store_transcendence_runes.py -> transcendence/beta.json
    transcendence-icons download_transcendence_icons.py -> static rune icons (missing ones)
    spells/states       store_spell_states.py -> spell_states/beta.json
    spells/constants    generate_damage_spells.py -> dofus_constants_beta.py
    spells/tooltips     store_spell_tooltips.py -> spell_tooltips (what a named spell does)
    spells/modifiers    store_spell_modifiers.py -> spell_modifiers/beta.json
    spell-images        download_spell_images.py  -> static spell icons
    resize              resize_images.py      -> 60x60 thumbnails
    elements/defaults   store_default_elements -> default_elements/beta.json
    presets/golden      REGENERATE_GOLDEN_PRESETS=1 preset test -> golden_presets/*.json
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent
ITEMSCRAPER = ROOT / "itemscraper"
PY = sys.executable
sys.path.insert(0, str(ITEMSCRAPER))
import release_items  # noqa: E402

BETA_API_URL = "https://api.dofusdu.de/dofus3beta/v1/"
BETA_REPO = "dofusdude/dofus3-beta"
BETA_DUMP = str(ROOT / "fashionistapulp" / "fashionistapulp" / "item_db_dumped_beta.dump")
BETA_WORK_DIR = str(ITEMSCRAPER / "beta")
LOCAL_RAW_FILES = ("items.json", "breeds.json", "effects.json", "spells.json", "spell_levels.json",
                   "monsters.json", "recipes.json", "jobs.json", "characteristics.json",
                   "spell_pairs.json", "spell_scripts.json", "spell_states.json", "spell_types.json",
                   "spell_variants.json", "bomb_spells.json", "companion_spells.json",
                   "custom_breed_spells.json", "forgettable_spells.json",
                   "mounts.json", "subareas.json",
                   "spell_images_96.tar.gz", "spell_images_48.tar.gz",
                   "en.json", "fr.json", "es.json", "pt.json", "de.json")
TEST_SETTINGS = ROOT / "fashionsite" / "fashionsite" / "settings_test.py"
GOLDEN_FLAG = "REGENERATE_GOLDEN_PRESETS"
GOLDEN_TESTS = "chardata.tests_every_preset_keeps_its_weights_and_minimums"

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


def refetch_if_cut_short(raw_dir: Path) -> list[str]:
    """--no-skip-existing when a cached file does not close its JSON: a download cut short."""
    for name in ("items.json", "breeds.json", "en.json"):
        path = raw_dir / name
        if not path.exists():
            continue
        with open(path, "rb") as handle:
            handle.seek(max(0, path.stat().st_size - 64))
            if not handle.read().rstrip().endswith((b"]", b"}")):
                return ["--no-skip-existing"]
    return []


def set_patch_started(content: str, key: str, patch: str) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    new_content, found = re.subn(
        r"(PATCH_TIMELINE\s*=\s*\{.*?'%s'\s*:\s*\[.*?)(\n[ \t]*\],)" % key,
        f"\\g<1>\n        ('{today}', '{patch}'),\\g<2>",
        content,
        count=1,
        flags=re.S,
    )
    if found:
        print(f"[version] {key} patch {patch} started {today}")
    else:
        print(f"[version] no PATCH_TIMELINE entry for {key}, set it by hand")
    return new_content


def timeline_ends_on(content: str, key: str, patch: str) -> bool:
    block = re.search(r"PATCH_TIMELINE\s*=\s*\{.*?'%s'\s*:\s*\[(.*?)\n[ \t]*\]," % key, content, re.S)
    patches = re.findall(r"'(\d+(?:\.\d+)*)'\)", block.group(1)) if block else []
    return bool(patches) and patches[-1] == patch


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
    patch = ".".join(new_version.split(".")[:2])
    if old_v.split(".")[:2] != new_version.split(".")[:2] and not timeline_ends_on(new_content, "beta", patch):
        new_content = set_patch_started(new_content, "beta", patch)
    version_file.write_text(new_content, encoding="utf-8")
    print(f"[version] beta {old_v} -> {new_version}")
    return new_version


def missing_local_raw(folder: Path, holds_map: bool = False) -> list[str]:
    wanted = LOCAL_RAW_FILES + (release_items.ASSETS if holds_map else ())
    return [name for name in wanted if not (folder / name).is_file()]


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
    parser.add_argument("--local-raw", metavar="DIR", type=Path,
                        help="Our own client extraction of --version, itemscraper/raw/<version>: nothing is "
                             "downloaded, every item and spell step reads it and --local-mapped")
    parser.add_argument("--local-mapped", metavar="DIR", type=Path,
                        help="doduda map output with MAPPED_ITEMS, MAPPED_SETS and MAPPED_RECIPES.json")
    parser.add_argument("--local-icons", metavar="DIR", type=Path,
                        help="doduda image export (img/item, with 1x and 2x) read before any icon download")
    args = parser.parse_args()
    local_raw = args.local_raw.resolve() if args.local_raw else None
    if local_raw:
        if not args.version:
            parser.error("--local-raw needs --version")
        holds_map = not args.local_mapped
        if holds_map:
            args.local_mapped = local_raw
        if not args.local_icons and (local_raw / "img" / "item").is_dir():
            args.local_icons = local_raw / "img" / "item"
        expected = (ITEMSCRAPER / "raw" / args.version).resolve()
        if local_raw != expected:
            parser.error(f"--local-raw must be {expected}: the spell steps read the raw folder of --version")
        missing = missing_local_raw(local_raw, holds_map)
        if missing:
            parser.error(f"--local-raw {local_raw} lacks {', '.join(missing)}")

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
    if local_raw:
        flags.append(f"data read from {local_raw} and {args.local_mapped.resolve()}")
        flags.append(f"item icons from {args.local_icons.resolve()} first" if args.local_icons
                     else "item icons downloaded")
        flags.append("resource and monster image downloads skipped")
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

    raw_dir = ITEMSCRAPER / "raw" / version
    snapshot = Path(tempfile.mkdtemp(prefix="beta_items_")) / "items_beta_before.db" if local_raw else None
    if do_data and local_raw:
        step("items/download", [PY, "get_equipments.py", "--api-url", BETA_API_URL, "--work-dir", BETA_WORK_DIR,
                                "--skip-endpoints", "mounts", "--mapped-dir", str(args.local_mapped.resolve())],
             cwd=ITEMSCRAPER)
    elif do_data:
        step("items/download", [PY, "get_equipments.py", "--api-url", BETA_API_URL, "--work-dir", BETA_WORK_DIR,
                                "--skip-endpoints", "mounts", "--tag", version, "--repo", BETA_REPO],
             cwd=ITEMSCRAPER)
        # The equip criteria as the game writes them, and the class names they use
        step("data/download", [
            PY, "-m", "itemscraper.download_raw_data",
            "--repo", BETA_REPO,
            "--tag", version,
            "--filter", "items.json",
            "--filter", "breeds.json",
            "--filter", "characteristics.json",
            "--filter", "en.json",
            "--filter", "effects.json",
            "--filter", "spells.json",
            "--filter", "spell_levels.json",
            "--filter", "fr.json",
            "--filter", "es.json",
            "--filter", "pt.json",
            "--filter", "de.json",
            *refetch_if_cut_short(raw_dir),
        ])
    if do_data:
        step("items/transform", [PY, "get_equipments2.py", "--work-dir", BETA_WORK_DIR,
                                 "--raw-dir", str(raw_dir),
                                 "--game-version", "beta"], cwd=ITEMSCRAPER)
        step("items/dump", [PY, "get_equipments3.py", "--input-dir", BETA_WORK_DIR,
                                 "--raw-dir", str(raw_dir), "--dump-output", BETA_DUMP], cwd=ITEMSCRAPER)
        if snapshot:
            step("items/keep-save", [PY, "keep_db_tables.py", "--game-version", "beta",
                                     "--save", str(snapshot)], cwd=ITEMSCRAPER)
        step("items/load-db", [PY, "load_item_db.py", "--game-version", "beta"])
        step("items/obtainment", [
            PY, "store_item_obtainment.py",
            "--game-version", "beta",
            str(ITEMSCRAPER / "beta"),
        ], cwd=ITEMSCRAPER)
        step("mount-looks", [PY, "store_dofusdb_mount_looks.py", "--game-version", "beta",
                             *(["--tag", version] if local_raw else [])], cwd=ITEMSCRAPER)
        # Replayed from the repo; --names catches items beta renumbered
        step("item-skins", [PY, "store_item_skins.py", "--game-version", "beta",
                            "--input", "item_skins.json",
                            "--names", "item_skins_by_name.json"], cwd=ITEMSCRAPER)

    if do_images:
        step("item-images", [
            PY, "get_equipments4.py",
            "--game-version", "beta",
            "--input-file", str(ITEMSCRAPER / "beta" / "transformed_equipment.json"),
            *(["--local-icons", str(args.local_icons.resolve())] if args.local_icons else []),
        ], cwd=ITEMSCRAPER)
        if not local_raw:
            step("resource-icons", [PY, "download_resource_icons.py"], cwd=ITEMSCRAPER)
            step("monster-images", [PY, "download_monster_images.py"], cwd=ITEMSCRAPER)

    if do_data:
        if not local_raw:
            step("spells/download", [
                PY, "-m", "itemscraper.download_raw_data",
                "--repo", BETA_REPO,
                "--tag", version,
                "--filter", "spell",
                "--filter", "effects.json",
                "--filter", "breeds.json",
                "--filter", "monsters.json",
                "--filter", "subareas.json",
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
            # Not the shared transformed_spell_names.json, that one is Dofus 3's
            "--names-output", "itemscraper/transformed_spell_names_beta.json",
        ])
        step("spells/duplicates", [PY, "-m", "itemscraper.find_duplicated_damage_rows",
                                   "--raw-root", str(ITEMSCRAPER / "raw")])
        step("spells/variants", [
            PY, "itemscraper/store_spell_variants.py",
            "--game-version", "beta", "--tag", version,
        ])
        step("spells/reference", [
            PY, "itemscraper/store_spell_reference.py",
            "--game-version", "beta", "--tag", version,
        ])
        step("stats/starting", [
            PY, "itemscraper/store_starting_stats.py",
            "--game-version", "beta", "--tag", version,
        ])
        step("items/weapon-conversions", [
            PY, "itemscraper/store_weapon_conversions.py",
            "--game-version", "beta", "--tag", version, "--raw-dir", str(raw_dir),
        ])
        step("items/dracorunes", [
            PY, "itemscraper/store_dracorunes.py", str(raw_dir),
            "--game-version", "beta", "--tag", version,
        ])
        step("items/transcendence", [
            PY, "itemscraper/store_transcendence_runes.py", str(raw_dir),
            "--game-version", "beta", "--tag", version,
        ])
        # Names of the states a damage row is gated on; needs the transform
        step("spells/states", [
            PY, "itemscraper/store_spell_states.py",
            "--game-version", "beta", "--tag", version,
        ])
        step("spells/constants", [
            PY, "-m", "itemscraper.generate_damage_spells",
            "--game-version", "beta",
            "--class-json", "itemscraper/transformed_class_spells_beta.json",
            "--spells-json", "itemscraper/transformed_spells_beta.json",
            "--constants", "fashionistapulp/fashionistapulp/dofus_constants_beta.py",
        ])
        # Tooltips for spells named by items; needs the spells and the item db
        step("spells/tooltips", [
            PY, "-m", "itemscraper.store_spell_tooltips",
            "--game-version", "beta", "--tag", version, "--raw-dir", str(raw_dir),
        ])
        step("spells/modifiers", [
            PY, "-m", "itemscraper.store_spell_modifiers",
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
        # Need monster_names, which drops/store creates
        step("monster-grades", [PY, "store_monster_grades.py",
                                "--game-version", "beta", "--tag", version],
             cwd=ITEMSCRAPER)
        step("monster-subareas", [PY, "store_monster_subareas.py",
                                  "--game-version", "beta", "--tag", version],
             cwd=ITEMSCRAPER)
        step("monster-spells", [PY, "store_monster_spells.py",
                                "--game-version", "beta", "--tag", version],
             cwd=ITEMSCRAPER)
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
        if snapshot:
            step("items/keep-restore", [PY, "keep_db_tables.py", "--game-version", "beta",
                                        "--restore", str(snapshot)], cwd=ITEMSCRAPER)

    # Manual fixes last, so they survive whatever the stores rebuilt.
    step("items/corrections", [
        PY, "store_item_corrections.py", "--game-version", "beta",
    ], cwd=ITEMSCRAPER)

    # Refresh runtime-translated strings (item types, stats...) for makemessages
    step("dynamic-translations", [PY, "generate_dynamic_translations.py"], cwd=ITEMSCRAPER)

    if do_images:
        step("transcendence-icons", [
            PY, "download_transcendence_icons.py", "--game-version", "beta",
        ], cwd=ITEMSCRAPER)
        for label, scope in (("spell-images", "damage"), ("spell-images/class", "class")):
            step(label, [
                PY, "-m", "itemscraper.download_spell_images",
                "--version", version,
                "--size", "96",
                "--game-version", "beta",
                "--scope", scope,
                "--metadata", "itemscraper/transformed_spells_beta.json",
                "--constants", "fashionistapulp/fashionistapulp/dofus_constants_beta.py",
                "--static-dir", "fashionsite/chardata/static/chardata/spells/beta",
                "--extra-static-dirs", "fashionsite/staticfiles/chardata/spells/beta",
            ])

    if do_images and not args.no_resize:
        step("resize", [PY, "resize_images.py"])

    if do_data:
        manage = [PY, "manage.py"]
        if TEST_SETTINGS.exists():
            manage_settings = ["--settings=fashionsite.settings_test"]
        else:
            manage_settings = []
        step("elements/defaults", [*manage, "store_default_elements", "--game-version", "beta",
                                   *manage_settings], cwd=ROOT / "fashionsite")
        if TEST_SETTINGS.exists():
            os.environ[GOLDEN_FLAG] = "1"
            try:
                step("presets/golden", [*manage, "test", GOLDEN_TESTS, *manage_settings,
                                        "--noinput", "--parallel", "1"], cwd=ROOT / "fashionsite")
            finally:
                os.environ.pop(GOLDEN_FLAG, None)
        else:
            print(f"\n[presets/golden] not run: no {TEST_SETTINGS.name}; regenerate with "
                  f"{GOLDEN_FLAG}=1 manage.py test {GOLDEN_TESTS}")


    # Tables that lost rows, item ids that moved
    step("verify/rebuild", [PY, "check_rebuild.py", "--only", "beta"],
         cwd=ITEMSCRAPER)

    if snapshot:
        shutil.rmtree(snapshot.parent, ignore_errors=True)
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
