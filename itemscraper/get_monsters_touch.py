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

    def add(object_id, monster_id, names, rates):
        if object_id is None or max(rates) <= 0:
            return
        per = index.setdefault(int(object_id), {})
        existing = per.get(int(monster_id))
        if existing is None or max(rates) > max(existing["rates"]):
            per[int(monster_id)] = {"names": names, "rates": rates}

    for monster_id, monster in base.items():
        names = {lang: (per_lang[lang].get(monster_id) or {}).get("nameId")
                 for lang in languages}
        for drop in monster.get("drops") or []:
            rates = [drop.get("percentDropForGrade%d" % g, 0) for g in range(1, 6)]
            add(drop.get("objectId"), monster_id, names, rates)

    out = {}
    for item_id in sorted(index):
        out[str(item_id)] = [
            {"monster_ankama_id": mid, "names": info["names"], "rates": info["rates"]}
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
