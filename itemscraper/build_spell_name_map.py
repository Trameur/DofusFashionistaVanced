#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "transformed_spells.json"
TARGET = ROOT / "transformed_spell_names.json"
LANGUAGES = ("en", "fr", "es", "pt", "de")


def main() -> int:
    if not SOURCE.exists():
        print(f"Missing source file: {SOURCE}")
        return 1

    with SOURCE.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    result = {}
    for spell in payload:
        name_en = (spell.get("name_en") or "").strip()
        if not name_en:
            continue

        localized = {}
        for lang in LANGUAGES:
            value = spell.get(f"name_{lang}")
            if isinstance(value, str) and value.strip():
                localized[lang] = value.strip()

        if not localized:
            continue

        result.setdefault(name_en, localized)

    with TARGET.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote {len(result)} spell names to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
