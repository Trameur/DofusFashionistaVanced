"""Record the sets an update removed: record_retired_sets.py --old OLD --new NEW --removed-in VERSION"""
import argparse
import json
from pathlib import Path

RETIRED_SETS_FILE = 'retired_sets.json'


def merge_retired_sets(previous_sets, new_sets, recorded, removed_in):
    """The recorded rows plus the sets that left, minus any set the game brought back, sorted by id."""
    live = {s['ankama_id'] for s in new_sets}
    kept = {r['ankama_id']: r for r in recorded if r['ankama_id'] not in live}
    for old in previous_sets:
        set_id = old['ankama_id']
        if set_id in live or set_id in kept:
            continue
        kept[set_id] = {
            'ankama_id': set_id,
            'names': {k[5:]: v for k, v in old.items() if k.startswith('name_') and v},
            'removed_in': removed_in,
        }
    return [kept[i] for i in sorted(kept)]


def record_retired_sets(previous_sets, new_sets, path, removed_in):
    """Update the record at path and return the ids added by this run."""
    if not new_sets:
        return []
    path = Path(path)
    recorded = json.loads(path.read_text(encoding='utf-8'))['sets'] if path.exists() else []
    rows = merge_retired_sets(previous_sets, new_sets, recorded, removed_in)
    if rows != recorded:
        path.write_text(
            json.dumps({'sets': rows}, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
            encoding='utf-8')
    known = {r['ankama_id'] for r in recorded}
    return [r['ankama_id'] for r in rows if r['ankama_id'] not in known]


def main(argv=None):
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', required=True)
    parser.add_argument('--new', required=True)
    parser.add_argument('--removed-in', required=True)
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    previous = json.loads(Path(args.old).read_text(encoding='utf-8'))
    new = json.loads(Path(args.new).read_text(encoding='utf-8'))
    out = Path(args.out) if args.out else Path(args.new).with_name(RETIRED_SETS_FILE)
    added = record_retired_sets(previous, new, out, args.removed_in)
    print('%d sets recorded as retired in %s: %s' % (len(added), args.removed_in, added))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
