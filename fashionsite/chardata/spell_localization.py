# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

LANGUAGES = ("en", "fr", "es", "pt", "de")
SPELL_NAMES_JSON = Path(__file__).resolve().parents[2] / "itemscraper" / "transformed_spell_names.json"
SPELLS_JSON = Path(__file__).resolve().parents[2] / "itemscraper" / "transformed_spells.json"


@lru_cache(maxsize=1)
def _spell_name_map() -> Dict[str, Dict[str, str]]:
    if SPELL_NAMES_JSON.exists():
        with SPELL_NAMES_JSON.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return {
                str(name_en): {
                    lang: str(localized)
                    for lang, localized in names.items()
                    if lang in LANGUAGES and isinstance(localized, str) and localized.strip()
                }
                for name_en, names in payload.items()
                if isinstance(names, dict)
            }

    if not SPELLS_JSON.exists():
        return {}

    with SPELLS_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    mapping: Dict[str, Dict[str, str]] = {}
    for spell in payload:
        name_en = (spell.get("name_en") or "").strip()
        if not name_en:
            continue

        names: Dict[str, str] = {}
        for lang in LANGUAGES:
            value = spell.get(f"name_{lang}")
            if isinstance(value, str) and value.strip():
                names[lang] = value.strip()

        if not names:
            continue

        # Keep the first occurrence for stable spell naming in case of duplicates.
        mapping.setdefault(name_en, names)

    return mapping


def get_localized_spell_name(name_en: str, language: str) -> str:
    if not isinstance(name_en, str) or not name_en:
        return name_en

    lang = (language or "en").split("-")[0].lower()
    localized = _spell_name_map().get(name_en)
    if not localized:
        return name_en

    return localized.get(lang) or localized.get("en") or name_en
