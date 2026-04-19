#!/usr/bin/env python3

from __future__ import annotations

import argparse
import time
from pathlib import Path

import polib
from deep_translator import GoogleTranslator

LOCALE_ROOT = Path("fashionsite/locale")
PO_FILES = ("django.po", "djangojs.po")


def translate_po_file(po_path: Path, target_lang: str, source_lang: str = "en", delay: float = 0.05) -> tuple[int, int]:
    po = polib.pofile(str(po_path))
    translator = GoogleTranslator(source=source_lang, target=target_lang)

    translated = 0
    failed = 0

    for entry in po:
        if entry.obsolete:
            continue
        if entry.msgid == "":
            continue
        if entry.msgstr and entry.msgstr.strip():
            continue

        text = entry.msgid.strip()
        if not text:
            continue

        try:
            out = translator.translate(text)
            if out and out.strip():
                entry.msgstr = out.strip()
                translated += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        if delay > 0:
            time.sleep(delay)

    po.save(str(po_path))
    return translated, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill missing gettext msgstr values using machine translation.")
    parser.add_argument("--langs", nargs="+", default=["de", "es", "pt", "fr"], help="Target locale folders under fashionsite/locale")
    parser.add_argument("--source", default="en", help="Source language code")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between translation requests")
    args = parser.parse_args()

    for lang in args.langs:
        print(f"\\n=== {lang} ===")
        for filename in PO_FILES:
            po_path = LOCALE_ROOT / lang / "LC_MESSAGES" / filename
            if not po_path.exists():
                print(f"Skipping missing file: {po_path}")
                continue
            translated, failed = translate_po_file(po_path, target_lang=lang, source_lang=args.source, delay=args.delay)
            print(f"{filename}: translated={translated}, failed={failed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
