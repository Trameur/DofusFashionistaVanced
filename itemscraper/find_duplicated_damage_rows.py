"""Find spells whose damage rows a patch copied instead of adding a hit.

Ankama sometimes rewrites a spell and leaves its damage row in the data twice.
Nothing in a single archive tells that from a spell that really hits twice, but
two archives do: a patch that doubles the rows while leaving the AP cost and the
value of each row alone did not double the damage, it duplicated the row. The
four Huppermage elemental basics are the case this was written for.

It only sees as far back as the oldest archive that carries spell_levels.json,
and until 2026-08-27 that was 3.5.17.26. Giving Dofus 2 its own spell levels
put 2.73.3.14 in reach and three more spells came out: Epidemic, Commotion and
the Ouginak's Vertebra. Only Vertebra changed what a page shows, from two rows
of 32-36 to one, and Ankama's own words settle it -- "applies a start-of-turn
Water poison", one poison, where the data carried the same row twice under the
same mask, zone, state and value.

Run it as a module over every archive under itemscraper/raw and commit the
result; the constants generator reads it so the page counts those rows once.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from itemscraper.get_spells import _load_datacenter_table, _unwrap_array

RAW_ROOT = Path("itemscraper/raw")
DEFAULT_OUTPUT = Path("itemscraper/duplicated_damage_rows.json")
DAMAGE_EFFECT_IDS = {96, 97, 98, 99}


def _version_key(name: str) -> Tuple[int, ...]:
    parts = []
    for chunk in name.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _snapshot(directory: Path) -> Dict[int, Tuple[List[Any], Any]]:
    spells = _load_datacenter_table(directory / "spells.json")
    levels = _load_datacenter_table(directory / "spell_levels.json")
    out: Dict[int, Tuple[List[Any], Any]] = {}
    for spell_id, spell in spells.items():
        level_ids = _unwrap_array(spell.get("spellLevels"))
        if not level_ids:
            continue
        level = levels.get(int(level_ids[-1]))
        if not level:
            continue
        rows = [
            (effect.get("effectId"), effect.get("diceNum"), effect.get("diceSide"),
             effect.get("targetMask"))
            for effect in _unwrap_array(level.get("effects"))
            if effect.get("effectId") in DAMAGE_EFFECT_IDS and effect.get("diceNum")
        ]
        if rows:
            out[int(spell_id)] = (rows, level.get("apCost"))
    return out


def find(raw_root: Path) -> Dict[str, Dict[str, Any]]:
    tags = sorted((path.name for path in raw_root.iterdir()
                   if (path / "spell_levels.json").exists()), key=_version_key)
    if len(tags) < 2:
        return {}
    snapshots = {tag: _snapshot(raw_root / tag) for tag in tags}
    found: Dict[str, Dict[str, Any]] = {}
    for older, newer in zip(tags, tags[1:]):
        before, after = snapshots[older], snapshots[newer]
        for spell_id, (rows, ap_cost) in before.items():
            later = after.get(spell_id)
            if not later:
                continue
            new_rows, new_ap = later
            if new_ap != ap_cost or len(new_rows) != 2 * len(rows):
                continue
            if new_rows[:len(rows)] != rows or new_rows[len(rows):] != rows:
                continue
            found[str(spell_id)] = {"kept": len(rows),
                                    "seen": "%s -> %s" % (older, newer)}
    return found


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not args.raw_root.is_dir():
        print("No raw root at %s" % args.raw_root, file=sys.stderr)
        return 1
    found = find(args.raw_root)
    args.output.write_text(
        json.dumps(found, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8")
    print("Wrote %d duplicated-row spells -> %s" % (len(found), args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
