#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import polib

LOCALE_ROOT = Path("fashionsite/locale")
PO_FILES = ("django.po", "djangojs.po")


def fill_file(po_path: Path) -> tuple[int, int]:
    po = polib.pofile(str(po_path))
    updated = 0
    total_missing = 0

    for entry in po:
        if entry.obsolete:
            continue
        if not entry.msgid:
            continue

        if not entry.msgstr or not entry.msgstr.strip():
            total_missing += 1
            entry.msgstr = entry.msgid
            updated += 1

    po.save(str(po_path))
    return updated, total_missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill missing gettext msgstr values with msgid as fallback.")
    parser.add_argument("--langs", nargs="+", default=["de", "es", "pt", "fr"], help="Target locale folders under fashionsite/locale")
    args = parser.parse_args()

    for lang in args.langs:
        print(f"=== {lang} ===")
        for filename in PO_FILES:
            po_path = LOCALE_ROOT / lang / "LC_MESSAGES" / filename
            if not po_path.exists():
                print(f"  {filename}: missing file")
                continue
            updated, total_missing = fill_file(po_path)
            print(f"  {filename}: filled={updated} (was_missing={total_missing})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
