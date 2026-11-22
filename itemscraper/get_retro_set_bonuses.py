# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Build retro_set_bonuses.json from the set bonuses in the game's itemsets file."""

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(CURRENT_DIR.parent))
sys.path.insert(0, str(CURRENT_DIR.parent / 'fashionistapulp'))

from get_equipments_retro import _hex, decode_stats

RAW_DIR = CURRENT_DIR / 'retro_raw'
OUT_PATH = CURRENT_DIR / 'retro_set_bonuses.json'
SNAPSHOT_PATH = CURRENT_DIR / 'retro_set_bonuses_drt.json'
LANGUAGES = ('en', 'es', 'pt', 'de')


def decode_tier(tier_string):
    """One itemsets tier string -> ({stat name: value}, [raw parts with no stat])."""
    stats = {}
    unmapped = []
    for part in (tier_string or '').split(','):
        if not part:
            continue
        lines, hits = decode_stats(part)
        if hits or not lines or any(low is None for low, _high, _name in lines):
            unmapped.append(part)
            continue
        for low, high, name in lines:
            stats[name] = stats.get(name, 0) + max(low, high)
    return stats, unmapped


def decode_sets(sets_root, items_root):
    """itemsets IS -> (retro_set_bonuses.json entries, [(set id, pieces, raw part)])."""
    entries = []
    unmapped = []
    for sid in sorted(sets_root, key=int):
        sd = sets_root[sid]
        if not isinstance(sd, dict) or not sd.get('i'):
            continue
        tiers = {}
        for key, tier_string in (sd.get('b') or {}).items():
            pieces = int(key[1:])
            stats, dropped = decode_tier(tier_string)
            unmapped.extend((int(sid), pieces, part) for part in dropped)
            if stats:
                tiers[pieces] = stats
        bonus = [[] for _ in range(max(tiers, default=0))]
        for pieces, stats in tiers.items():
            bonus[pieces - 1] = [{'type': name, 'value': str(value)}
                                 for name, value in sorted(stats.items())]
        names = [items_root[str(i)].get('n') for i in sd['i']
                 if isinstance(items_root.get(str(i)), dict)]
        entries.append({'ankama_id': int(sid), 'name': sd.get('n'),
                        'items': [n for n in names if n], 'bonus': bonus,
                        'source': 'itemsets_fr.json'})
    return entries, unmapped


def lost_sets(previous, entries):
    """Set ids that had bonus lines in the previous file and decode to none now."""
    now = {e['ankama_id']: any(e['bonus']) for e in entries}
    return sorted(e['ankama_id'] for e in previous
                  if any(e.get('bonus', [])) and e['ankama_id'] in now
                  and not now[e['ankama_id']])


def other_language_mismatches(fr_root, roots_by_lang):
    """{language: set ids whose raw bonuses differ from French} for languages that carry them."""
    out = {}
    for lang, root in roots_by_lang.items():
        if not any(isinstance(sd, dict) and sd.get('b') for sd in root.values()):
            continue
        out[lang] = sorted(
            int(sid) for sid, sd in fr_root.items()
            if isinstance(sd, dict) and sd.get('b') and isinstance(root.get(sid), dict)
            and root[sid].get('b') != sd['b'])
    return out


def cross_check(entries, records):
    """Lines where a community snapshot differs -> [(set, pieces, stat, ours, theirs)]."""
    ours = {e['ankama_id']: {n + 1: {line['type']: int(line['value']) for line in tier}
                             for n, tier in enumerate(e['bonus']) if tier}
            for e in entries}
    out = []
    for record in records:
        sid = record['ankama_id']
        if sid not in ours:
            continue
        theirs = {int(n): v for n, v in record['tiers'].items()}
        for pieces in sorted(set(ours[sid]) | set(theirs)):
            a, b = ours[sid].get(pieces, {}), theirs.get(pieces, {})
            for stat in sorted(set(a) | set(b)):
                if a.get(stat) != b.get(stat):
                    out.append((sid, pieces, stat, a.get(stat), b.get(stat)))
    return out


def _read_root(path, key):
    """One lang JSON file -> its root object, or None when the file is absent."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8')).get(key)


def main(argv=None):
    """Decode the French itemsets bonuses, write them, report the cross-checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, default=RAW_DIR)
    parser.add_argument('--out', type=Path, default=OUT_PATH)
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args(argv)

    fr_file = json.loads((args.raw_dir / 'itemsets_fr.json').read_text(encoding='utf-8'))
    sets_root = fr_file['IS']
    items_root = json.loads(
        (args.raw_dir / 'items_fr.json').read_text(encoding='utf-8'))['I']['u']
    entries, unmapped = decode_sets(sets_root, items_root)

    previous = []
    if args.out.exists():
        previous = json.loads(args.out.read_text(encoding='utf-8'))
    lost = lost_sets(previous, entries)
    if lost or not any(any(e['bonus']) for e in entries):
        raise SystemExit('itemsets_fr.json has no bonuses (missing) for sets %s'
                         % (lost or 'all'))

    args.out.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    lines = sum(len(tier) for e in entries for tier in e['bonus'])
    print('Wrote %d sets, %d bonus lines from itemsets_fr.json VERSION %s'
          % (len(entries), lines, fr_file.get('VERSION')))
    if unmapped:
        effect_ids = sorted({_hex(part.split('#')[0]) or part.split('#')[0]
                             for _s, _p, part in unmapped}, key=str)
        print('Warning: %d bonus parts unmapped (no stat the site models), effects %s'
              % (len(unmapped), effect_ids))

    roots = {lang: _read_root(args.raw_dir / ('itemsets_%s.json' % lang), 'IS')
             for lang in LANGUAGES}
    roots = {lang: root for lang, root in roots.items() if root is not None}
    differing = other_language_mismatches(sets_root, roots)
    for lang in sorted(roots):
        if lang not in differing:
            print('itemsets_%s.json carries no bonuses to compare' % lang)
        elif differing[lang]:
            print('Set bonus mismatch with French in %s: sets %s'
                  % (lang, differing[lang]))

    if not args.snapshot.exists():
        print('No community snapshot at %s, nothing to compare' % args.snapshot)
        return 0
    records = json.loads(args.snapshot.read_text(encoding='utf-8'))
    differences = cross_check(entries, records)
    by_set = {}
    for sid, pieces, stat, ours, theirs in differences:
        by_set.setdefault(sid, []).append((pieces, stat, ours, theirs))
    if differences:
        print('[retro] Set bonus mismatch, report only: the community snapshot '
              'differs on %d lines in %d sets' % (len(differences), len(by_set)))
        names = {e['ankama_id']: e['name'] for e in entries}
        for sid in sorted(by_set):
            stats = sorted({stat for _p, stat, _o, _t in by_set[sid]})
            print('  set %d %s: %s' % (sid, names.get(sid), ', '.join(stats)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
