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
    """Resolve the monster table into a plain {id: record} map. Handles both the
    dofus3/beta Unity serialization (objectsById + references.RefIds) and the
    Dofus 2 / Touch legacy format (a plain list of monster records)."""
    data = _load_json(path)
    if isinstance(data, list):  # Dofus 2 / Touch: a plain list of records
        return {int(r["id"]): r for r in data
                if isinstance(r, dict) and r.get("id") is not None}
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
        data = _load_json(path)
        # dofus3/beta use "entries"; Dofus 2 / Touch use "texts". Both are {id: string}.
        entries = data.get("entries")
        if not isinstance(entries, Mapping):
            entries = data.get("texts")
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

    # item_ankama_id -> {monster_ankama_id: {name, rates, conditions}}
    index: Dict[int, Dict[int, Dict[str, Any]]] = {}

    def add(object_id, monster_id, names, rates, conditions=None):
        if object_id is None or max(rates) <= 0:
            return  # a 0% entry is not a real drop
        per_item = index.setdefault(int(object_id), {})
        # a monster can list the same item more than once (different criterions
        # or drops[] + globalDrops); keep the best rate. One unconditional entry
        # means the drop is free, so only keep a condition when every entry has one.
        existing = per_item.get(int(monster_id))
        if existing is None:
            per_item[int(monster_id)] = {"names": names, "rates": rates,
                                         "conditions": conditions}
            return
        best_is_new = max(rates) > max(existing["rates"])
        if best_is_new:
            existing["rates"] = rates
        if not conditions or not existing["conditions"]:
            existing["conditions"] = None
        elif best_is_new:
            existing["conditions"] = conditions

    for monster_id, monster in monsters.items():
        names = _name(translations, monster.get("nameId"), languages)
        for drop in _unwrap_array(monster.get("drops")):
            rates = [drop.get("percentDropForGrade%d" % g, 0) for g in range(1, 6)]
            # dofus3/beta name the field criterions; Dofus 2 calls it criteria.
            conditions = (drop.get("criterions") or drop.get("criteria") or "").strip()
            if conditions.lower() == "null":  # some raws serialize "none" this way
                conditions = ""
            conditions = conditions or None
            add(drop.get("objectId"), monster_id, names, rates, conditions)
        # globalDrops apply regardless of grade (a min/max rate range); use the max.
        # No conditions there, receiverCriterion is empty across the dataset.
        for gd in _unwrap_array(monster.get("globalDrops")):
            rate = gd.get("maxPercentDrop", gd.get("minPercentDrop", 0)) or 0
            add(gd.get("objectId"), monster_id, names, [rate])

    # flatten to a JSON-friendly, sorted structure
    out: Dict[str, Any] = {}
    for item_id in sorted(index):
        monsters_list = [
            {"monster_ankama_id": mid, "names": info["names"], "rates": info["rates"],
             "conditions": info["conditions"]}
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
