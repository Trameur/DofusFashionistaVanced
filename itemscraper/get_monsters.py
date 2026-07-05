#!/usr/bin/env python3
"""get_monsters.py - build the item -> monster drops index from the raw dofusdude
dump (dofusdude/dofus3-main releases), the same source get_spells.py reads.

The REST API (api.dofusdu.de) doesn't expose monsters, but the raw release does:
monsters.json holds every monster with a `drops` list of {objectId, dropId,
percentDropForGrade1..5, ...}. This turns that into a reverse index
{item_ankama_id: [monsters that drop it, with localized names and per-grade rates]}
so the encyclopedia can show "Dropped by ...".

Usage (from repo root):
    python itemscraper/get_monsters.py --dataset-dir itemscraper/raw/<version> \
        --output itemscraper/transformed_drops.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

LANGUAGES: Sequence[str] = ("en", "fr", "es", "pt", "de")
DEFAULT_OUTPUT = Path("itemscraper/transformed_drops.json")


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _unwrap_array(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, dict) and "Array" in value:
        return list(value.get("Array") or [])
    if isinstance(value, list):
        return value
    return [value]


def _load_datacenter_table(path: Path) -> Dict[int, Dict[str, Any]]:
    """Resolve the Unity reference serialization (objectsById + references.RefIds)
    into a plain {id: record} map. Same shape as get_spells._load_datacenter_table."""
    data = _load_json(path)
    refs = {ref["rid"]: ref["data"] for ref in data.get("references", {}).get("RefIds", [])}
    keys = data.get("objectsById", {}).get("m_keys", {}).get("Array", [])
    values = data.get("objectsById", {}).get("m_values", {}).get("Array", [])
    table: Dict[int, Dict[str, Any]] = {}
    if keys and values:
        for key, value in zip(keys, values):
            record = refs.get(value.get("rid")) if isinstance(value, dict) else None
            if record is not None:
                table[int(key)] = record
        return table
    for record in refs.values():
        if record.get("id") is not None:
            table[int(record["id"])] = record
    return table


def _load_translations(root: Path, languages: Sequence[str]) -> Dict[str, Dict[str, str]]:
    translations: Dict[str, Dict[str, str]] = {}
    for lang in languages:
        path = root / f"{lang}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing localisation file: {path}")
        entries = _load_json(path).get("entries")
        if not isinstance(entries, Mapping):
            raise ValueError(f"Unexpected language payload format in {path}")
        translations[lang] = {str(k): v for k, v in entries.items()}
    return translations


def _name(translations: Dict[str, Dict[str, str]], text_id: Any,
          languages: Sequence[str]) -> Dict[str, str]:
    key = str(text_id)
    return {lang: translations.get(lang, {}).get(key) for lang in languages}


def build_drops_index(dataset_dir: Path,
                      languages: Sequence[str] = LANGUAGES) -> Dict[str, Any]:
    monsters = _load_datacenter_table(dataset_dir / "monsters.json")
    translations = _load_translations(dataset_dir, languages)

    # item_ankama_id -> {monster_ankama_id: {name, rates}}
    index: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for monster_id, monster in monsters.items():
        names = _name(translations, monster.get("nameId"), languages)
        for drop in _unwrap_array(monster.get("drops")):
            object_id = drop.get("objectId")
            if object_id is None:
                continue
            rates = [drop.get("percentDropForGrade%d" % g, 0) for g in range(1, 6)]
            per_item = index.setdefault(int(object_id), {})
            # a monster can list the same item twice (different criterions); keep the best rate
            existing = per_item.get(int(monster_id))
            if existing is None or max(rates) > max(existing["rates"]):
                per_item[int(monster_id)] = {"names": names, "rates": rates}

    # flatten to a JSON-friendly, sorted structure
    out: Dict[str, Any] = {}
    for item_id in sorted(index):
        monsters_list = [
            {"monster_ankama_id": mid, "names": info["names"], "rates": info["rates"]}
            for mid, info in sorted(index[item_id].items(),
                                    key=lambda kv: max(kv[1]["rates"]), reverse=True)
        ]
        out[str(item_id)] = monsters_list
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the item->drops index from the raw dump")
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--languages", nargs="*", default=list(LANGUAGES))
    args = parser.parse_args()

    index = build_drops_index(args.dataset_dir, args.languages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    total_pairs = sum(len(v) for v in index.values())
    print("items with drops: %d | item/monster pairs: %d -> %s"
          % (len(index), total_pairs, args.output))


if __name__ == "__main__":
    main()
