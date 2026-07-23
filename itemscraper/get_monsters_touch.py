#!/usr/bin/env python3
"""get_monsters_touch.py - build the item -> monster drops index for Dofus Touch.

Touch is a Dofus 2 fork; its backend returns the Monsters table (POST /data/map
class=Monsters) as a dict {id: monster}, each with an already-localized `nameId`
(the backend localizes per requested lang) and a `drops` list of
{objectId, percentDropForGrade1..5}. So we read Monsters_<lang>.json for every
language to collect the localized names, and emit the exact same reverse index
{item_ankama_id: [monsters with names + rates]} that get_monsters.py produces, so
store_drops.py can load it unchanged.

Usage (from itemscraper/):
    python get_monsters_touch.py --raw-dir touch_raw --output transformed_drops_touch.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LANGUAGES = ("en", "fr", "es", "pt", "de")


def _load(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_drops_index(raw_dir, languages=LANGUAGES):
    raw_dir = Path(raw_dir)
    # per language: {monster_id: monster}; monster["nameId"] is the localized name
    per_lang = {
        lang: {int(m["id"]): m for m in _load(raw_dir / f"Monsters_{lang}.json").values()}
        for lang in languages
    }
    base = per_lang.get("en") or next(iter(per_lang.values()))

    index = {}

    def add(object_id, monster_id, names, rates, conditions=None):
        if object_id is None or max(rates) <= 0:
            return
        per = index.setdefault(int(object_id), {})
        # Same merge rule as get_monsters.py: one unconditional entry for the
        # pair means the drop is freely available.
        existing = per.get(int(monster_id))
        if existing is None:
            per[int(monster_id)] = {"names": names, "rates": rates,
                                    "conditions": conditions}
            return
        best_is_new = max(rates) > max(existing["rates"])
        if best_is_new:
            existing["rates"] = rates
        if not conditions or not existing["conditions"]:
            existing["conditions"] = None
        elif best_is_new:
            existing["conditions"] = conditions

    for monster_id, monster in base.items():
        names = {lang: (per_lang[lang].get(monster_id) or {}).get("nameId")
                 for lang in languages}
        for drop in monster.get("drops") or []:
            rates = [drop.get("percentDropForGrade%d" % g, 0) for g in range(1, 6)]
            conditions = (drop.get("criteria") or "").strip()
            # The Touch backend serializes "no criteria" as the string "null".
            if conditions.lower() == "null":
                conditions = ""
            conditions = conditions or None
            add(drop.get("objectId"), monster_id, names, rates, conditions)

    out = {}
    for item_id in sorted(index):
        out[str(item_id)] = [
            {"monster_ankama_id": mid, "names": info["names"], "rates": info["rates"],
             "conditions": info["conditions"]}
            for mid, info in sorted(index[item_id].items(),
                                    key=lambda kv: max(kv[1]["rates"]), reverse=True)
        ]
    return out


def main():
    parser = argparse.ArgumentParser(description="Build the Touch item->drops index")
    parser.add_argument("--raw-dir", default="touch_raw")
    parser.add_argument("--output", default="transformed_drops_touch.json")
    args = parser.parse_args()
    index = build_drops_index(args.raw_dir)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    total = sum(len(v) for v in index.values())
    print("items with drops: %d | item/monster pairs: %d -> %s"
          % (len(index), total, args.output))


if __name__ == "__main__":
    main()
