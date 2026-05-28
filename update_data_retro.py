#!/usr/bin/env python3
"""
update_data_retro.py - DofusFashionista data pipeline for Dofus Retro (1.29)

Usage:
    python update_data_retro.py              # full update (latest CDN lang versions)
    python update_data_retro.py --skip-en    # skip the English-names download (FR only)

Unlike Dofus 2/3/Beta, Retro has no version tag to bump: the source is Ankama's
official "lang" CDN and download_retro_langs.py always fetches the latest versions
listed in the live manifest (versions_<lang>.txt).

Pipeline steps:
    lang/download-fr   download_retro_langs.py  -> retro_raw/{items,itemstats,itemsets}_fr.json
    lang/download-en   download_retro_langs.py  -> retro_raw/items_en.json (English names)
    items/transform    get_equipments_retro.py  -> retro/transformed_{equipment,sets}.json
    items/dump         get_equipments3.py        -> item_db_dumped_retro.dump
    items/load-db      load_item_db.py           -> items_retro.db

Not run for Retro (data lives in the 1.29 game client, not the lang CDN):
    item-images   - the gfx field points to compiled client SWF clips, no PNG CDN
    set bonuses   - itemsets lang exposes only {item_ids, name}
    spells        - retro spells use the SWF "spells" lang, not the dofusdude pipeline
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
    parser.add_argument("--skip-en", action="store_true",
                        help="Skip the English-names download (use FR names for name_en)")
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
        "--categories", "items", "itemstats", "itemsets",
        "--dest", RETRO_RAW_DIR,
    ], cwd=ITEMSCRAPER)

    if not args.skip_en:
        step("lang/download-en", [
            PY, "download_retro_langs.py",
            "--lang", "en",
            "--categories", "items",
            "--dest", RETRO_RAW_DIR,
        ], cwd=ITEMSCRAPER)

    step("items/transform", [
        PY, "get_equipments_retro.py",
        "--raw-dir", RETRO_RAW_DIR,
        "--out-dir", RETRO_WORK_DIR,
        "--lang", args.lang,
    ], cwd=ITEMSCRAPER)

    step("items/dump", [
        PY, "get_equipments3.py",
        "--input-dir", RETRO_WORK_DIR,
        "--dump-output", RETRO_DUMP,
    ], cwd=ITEMSCRAPER)

    step("items/load-db", [PY, "load_item_db.py", "--game-version", "retro"])

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
