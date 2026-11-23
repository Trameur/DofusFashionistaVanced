#!/usr/bin/env python3
"""
update_data_retro.py - DofusFashionista data pipeline for Dofus Retro (1.29)

Usage:
    python update_data_retro.py                    # full update (the lang tree the live client reads)
    python update_data_retro.py --skip-translations  # FR names only (faster)
    python update_data_retro.py --release beta     # the beta client, into retrobeta_raw and retrobeta
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

if str(ITEMSCRAPER) not in sys.path:
    sys.path.insert(0, str(ITEMSCRAPER))
import retro_release  # noqa: E402

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


def export_lang_root(release: str = retro_release.MAIN) -> str:
    """Resolve the lang root once from the release's client config and hand it to every step."""
    if str(ITEMSCRAPER) not in sys.path:
        sys.path.insert(0, str(ITEMSCRAPER))
    import download_retro_langs
    key = retro_release.version_key(release)
    root = download_retro_langs.lang_root(key) if retro_release.is_beta(release) else download_retro_langs.lang_root()
    os.environ[download_retro_langs.lang_root_env(key)] = root
    return root


def release_dirs(release: str = retro_release.MAIN) -> tuple[str, str, str]:
    """(raw folder, work folder, dump) the steps of a release write."""
    if retro_release.is_beta(release):
        return (str(retro_release.raw_dir(release)), str(retro_release.work_dir(release)),
                str(retro_release.dump_path(release)))
    return RETRO_RAW_DIR, RETRO_WORK_DIR, RETRO_DUMP


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
    retro_release.add_release_argument(parser)
    args = parser.parse_args()
    beta = retro_release.is_beta(args.release)
    raw_dir, work_dir, dump = release_dirs(args.release)
    release_args = ["--release", args.release] if beta else []

    t_total = time.time()
    all_notices: list[str] = []
    failed_steps: list[str] = []
    skipped_steps: list[str] = []
    release_report: list[str] = []

    print(f"\n{'-'*60}")
    if beta:
        print(f"  DofusFashionista update - DOFUS RETRO 1.29 {args.release.upper()} (lang: {args.lang})")
    else:
        print(f"  DofusFashionista update - DOFUS RETRO 1.29 (lang: {args.lang})")
    print(f"{'-'*60}")

    print(f"  lang root: {export_lang_root(args.release)}")
    if beta:
        print(f"  raw: {raw_dir}\n  work: {work_dir}\n  dump: {dump}")
        Path(work_dir).mkdir(parents=True, exist_ok=True)

    def step(label: str, cmd: list, cwd: Path | None = None) -> bool:
        ok, lines = run_step(label, cmd, cwd)
        all_notices.extend(extract_notices(lines))
        release_report.extend(l.strip() for l in lines if l.startswith(retro_release.NOTICE))
        if not ok:
            failed_steps.append(label)
        return ok

    def main_step(label: str, cmd: list, cwd: Path | None = None) -> bool:
        if beta:
            skipped_steps.append(label)
            return True
        return step(label, cmd, cwd)

    step("lang/download-fr", [
        PY, "download_retro_langs.py",
        "--lang", args.lang,
        "--categories", "items", "itemstats", "itemsets", "spells", "classes",
        "jobs", "skills", "monsters", "kb", "effects", "maps",
        "--dest", raw_dir,
    ] + release_args, cwd=ITEMSCRAPER)

    main_step("stats/starting", [
        PY, "itemscraper/store_starting_stats.py", "--game-version", "retro",
    ])

    if not args.skip_translations:
        # Names in the other languages, plus itemstats: no lang file is complete
        for lang in ("en", "es", "pt", "de"):
            if lang == args.lang:
                continue
            step(f"lang/download-{lang}", [
                PY, "download_retro_langs.py",
                "--lang", lang,
                "--categories", "items", "itemstats", "itemsets", "spells", "jobs", "maps",
                "--dest", raw_dir,
            ] + release_args, cwd=ITEMSCRAPER)

    main_step("items/weapon-conversions", [
        PY, "itemscraper/store_weapon_conversions.py", "--game-version", "retro",
        "--lang", args.lang,
    ])

    if beta:
        set_bonuses = str(Path(work_dir) / "retro_set_bonuses.json")
        step("sets/bonuses", [
            PY, "get_retro_set_bonuses.py",
            "--raw-dir", raw_dir,
            "--out", set_bonuses,
        ], cwd=ITEMSCRAPER)
    else:
        set_bonuses = str(ITEMSCRAPER / "retro_set_bonuses.json")
        step("sets/bonuses", [
            PY, "get_retro_set_bonuses.py",
        ], cwd=ITEMSCRAPER)

    step("items/transform", [
        PY, "get_equipments_retro.py",
        "--raw-dir", raw_dir,
        "--out-dir", work_dir,
        "--set-bonuses", set_bonuses,
        "--lang", args.lang,
    ], cwd=ITEMSCRAPER)

    step("items/dump", [
        PY, "get_equipments3.py",
        "--input-dir", work_dir,
        "--dump-output", dump,
    ], cwd=ITEMSCRAPER)

    main_step("items/load-db", [PY, "load_item_db.py", "--game-version", "retro"])

    # Before drops/store: it finds resources through item_recipe_ingredient_names
    main_step("recipes/store", [
        PY, "store_retro_recipes.py",
    ], cwd=ITEMSCRAPER)

    # Pet feeding caps are server-side in 1.29: dofux and Solomonk
    main_step("pets/scrape", [
        PY, "scrape_retro_pet_bonuses.py",
    ], cwd=ITEMSCRAPER)

    # Pet variants, before drops/store: it only fills the rows that already exist
    main_step("pets/store", [
        PY, "store_retro_pet_bonuses.py",
    ], cwd=ITEMSCRAPER)

    if beta:
        step("drops/transform", [
            PY, "get_monsters_retro.py",
            "--release", args.release,
            "--output", str(Path(work_dir) / "transformed_drops_retrobeta.json"),
        ], cwd=ITEMSCRAPER)
    else:
        step("drops/transform", [
            PY, "get_monsters_retro.py",
            "--output", "transformed_drops_retro.json",
        ], cwd=ITEMSCRAPER)

    main_step("drops/store", [
        PY, "store_drops.py",
        "--drops", "transformed_drops_retro.json",
        "--game-version", "retro",
    ], cwd=ITEMSCRAPER)

    # Per-grade monster stats from the Solomonk bestiary
    main_step("monsters/grades", [
        PY, "store_retro_monster_grades.py",
    ], cwd=ITEMSCRAPER)

    main_step("monsters/subareas", [
        PY, "store_retro_monster_subareas.py",
    ], cwd=ITEMSCRAPER)

    # Monster artworks from the 1.29 client, needs java, ffdec and resvg
    step("monsters/artworks", [
        PY, "download_retro_monster_artworks.py",
    ] + (release_args + ["--workers", "1"] if beta else []), cwd=ITEMSCRAPER)

    # Craft professions from the skills lang, 1.29 has no per-recipe level
    step("craftjobs/transform", [
        PY, "get_craft_jobs_retro.py",
        "--raw-dir", raw_dir,
        "--output", (str(Path(work_dir) / "transformed_craft_jobs_retrobeta.json") if beta
                     else "transformed_craft_jobs_retro.json"),
    ], cwd=ITEMSCRAPER)

    main_step("craftjobs/store", [
        PY, "store_craft_jobs.py",
        "--jobs", "transformed_craft_jobs_retro.json",
        "--game-version", "retro",
    ], cwd=ITEMSCRAPER)

    # Item descriptions for the encyclopedia pages
    main_step("descriptions/store", [PY, "store_retro_descriptions.py"], cwd=ITEMSCRAPER)

    # Runtime-translated strings, for makemessages
    main_step("dynamic-translations", [PY, "generate_dynamic_translations.py"], cwd=ITEMSCRAPER)

    if not args.skip_images:
        step("item-images", [
            PY, "download_retro_images.py",
            "--raw-dir", raw_dir,
            "--lang", args.lang,
        ] + (release_args + ["--workers", "1"] if beta else []), cwd=ITEMSCRAPER)
        main_step("resource-icons", [
            PY, "download_resource_icons.py",
            "--game-version", "retro",
        ], cwd=ITEMSCRAPER)

    # Tooltips for the spells an item names
    main_step("spells/tooltips", [
        PY, "-m", "itemscraper.store_spell_tooltips", "--game-version", "retro",
    ])
    main_step("spells/modifiers", [
        PY, "-m", "itemscraper.store_spell_modifiers", "--game-version", "retro",
    ])

    # Manual fixes last, after the stores
    main_step("items/corrections", [
        PY, "store_item_corrections.py", "--game-version", "retro",
    ], cwd=ITEMSCRAPER)

    main_step("spells/reference", [
        PY, "itemscraper/store_spell_reference.py",
        "--game-version", "retro",
    ])
    step("spells/decode", [
        PY, "get_spells_retro.py",
        "--raw-dir", raw_dir,
        "--out", str(Path(work_dir) / "retro_damage_spells.json"),
        "--module-out", (str(Path(work_dir) / "dofus_constants_retrobeta_spells.py") if beta
                         else str(ROOT / "fashionistapulp" / "fashionistapulp"
                                  / "dofus_constants_retro_spells.py")),
        "--lang", args.lang,
    ], cwd=ITEMSCRAPER)

    if not args.skip_images:
        step("spell-images", [PY, "download_retro_spell_images.py"]
             + (release_args + ["--no-mirror", "--compose-missing"] if beta else []),
             cwd=ITEMSCRAPER)


    # Tables that lost rows, item ids that moved
    main_step("verify/rebuild", [PY, "check_rebuild.py", "--only", "retro"],
              cwd=ITEMSCRAPER)

    elapsed = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"  Dofus Retro update complete - {elapsed:.0f}s")
    print(f"{'='*60}")

    if skipped_steps:
        print(f"\nSkipped for the {args.release} release, they write the database or a file of a "
              f"registered version ({len(skipped_steps)}): {', '.join(skipped_steps)}")
    if release_report:
        print(f"\n{args.release.capitalize()} release report ({len(release_report)}):")
        for line in release_report:
            print(f"   - {line}")

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
