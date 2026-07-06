#!/usr/bin/env python
# coding=utf-8

"""store_retro_set_bonuses.py: fill missing Dofus Retro set bonuses.

Set bonuses are not in Ankama's Retro lang CDN (they're server-side), so the
builder seeds them from a vendored 1.29 community snapshot
(itemscraper/retro_set_bonuses.json). That snapshot misses ~70 sets added since
1.29: their `set_bonus` rows are absent, so equipping >=2 pieces used to crash
the optimizer and, once that was made safe, simply granted no set bonus.

Dofus Retro Tools (dofusretrotools.com) exposes a clean JSON API,
/api/set-bonuses, with every set keyed by its Ankama set id (`clothId`) and a
full per-piece-count bonus table. We key on that id (it matches sets.ankama_id
exactly) and map its stat codes to our internal stat names. Validated against
the sets we already have: the common codes agree exactly; the snapshot's gaps
and a Puissance/Damage conflation are corrected by this source.

Conservative by default: only sets with zero existing set_bonus rows are filled,
leaving the validated data for the rest untouched (pass --all to refresh every
set from the API instead).

Two phases, mirroring the repo's vendored-snapshot approach:
  * --scrape: fetch the API and (re)write the committed snapshot
    retro_set_bonuses_drt.json (full source, keyed by ankama id), then apply it.
  * default: apply the committed snapshot to the DB with no network, so this
    post-load step works offline on every rebuild.
Run after load_item_db, like the other retro post-steps.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

import requests

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY, os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

from store_item_obtainment import (  # noqa: E402  (sys.path set above)
    get_items_db_path, _open_items_db, _save_db_to_dump, _table_exists)

GAME_VERSION = 'retro'
API_URL = 'https://dofusretrotools.com/api/set-bonuses'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
# Vendored snapshot of the scraped bonuses, keyed by set ankama id so it can be
# re-applied to a freshly rebuilt DB without touching the network. Committed to
# the repo; --scrape refreshes it, the default run just applies it.
CACHE_PATH = os.path.join(CURRENT_DIRECTORY, 'retro_set_bonuses_drt.json')

# Dofus Retro Tools two-letter stat codes -> internal stat names. Validated by
# exact agreement with the sets that already had bonuses (and by per-code spot
# checks: pd=Pods on the Bwork Chief set, rn=Neutral resist on Country, ic=Summon
# on Bearman, pu=Power being a code distinct from dmg=Damage).
STAT_CODE = {
    'vi': 'Vitality', 'sa': 'Wisdom', 'ag': 'Agility', 'in': 'Intelligence',
    'ch': 'Chance', 'fo': 'Strength', 'dmg': 'Damage', 'so': 'Heals',
    'pp': 'Prospecting', 'ii': 'Initiative', 'po': 'Range', 'cc': 'Critical Hits',
    'pa': 'AP', 'pm': 'MP', 'pu': 'Power', 'rn': '% Neutral Resist',
    'ic': 'Summon', 'pd': 'Pods',
}
_ELEMENTS = {'feu': 'Fire', 'terre': 'Earth', 'eau': 'Water', 'air': 'Air', 'neutre': 'Neutral'}


def _code_to_stat(code, value):
    """A bonus entry's code/value -> (internal stat name, value), or (None, _).

    Most codes are the two-letter STAT_CODE keys; resists, flat HP and physical
    reduction come through as a full French phrase (e.g. "10 % de resistance a la
    terre", "+100 en vie", "Reduction physique de 1") whose value is in the text.
    """
    if code in STAT_CODE:
        return STAT_CODE[code], value
    text = unicodedata.normalize('NFKD', code).encode('ascii', 'ignore').decode().lower()
    match = re.match(r'([+-]?\d+)\s*(%?)\s*(.+)', text)
    if not match:
        return None, value
    parsed_value = int(match.group(1))
    is_percent = match.group(2) == '%'
    label = match.group(3)
    if 'vie' in label:
        return 'HP', parsed_value
    if 'resistance' in label:
        for fr_element, en_element in _ELEMENTS.items():
            if fr_element in label:
                stat = ('%% %s Resist' % en_element) if is_percent else ('%s Resist' % en_element)
                return stat, parsed_value
    return None, parsed_value  # e.g. "reduction physique", no matching stat row


def fetch_api_records():
    """The API's sets as snapshot records: [{ankama_id, name, tiers}, ...].

    tiers: {num_pieces(str): {stat_name: value}}. Unmappable entries are dropped.
    """
    data = requests.get(API_URL, headers=HEADERS, timeout=60).json()
    records = []
    for entry in data:
        tiers = {}
        for num_pieces, bonuses in (entry.get('bonuses') or {}).items():
            stats = {}
            for bonus in bonuses:
                stat_name, value = _code_to_stat(bonus['code'], bonus.get('max', bonus.get('min')))
                if stat_name is not None and value is not None:
                    stats[stat_name] = value
            if stats:
                tiers[str(int(num_pieces))] = stats
        if tiers:
            records.append({'ankama_id': entry['clothId'], 'name': entry.get('name', ''),
                            'tiers': tiers})
    return records


def apply_records(cursor, records, set_id_by_ankama, stat_id_by_name, fill_ankama, dry_run):
    """Write set_bonus rows from snapshot records for sets in fill_ankama.

    Returns (sets_filled, rows_written, unknown_stats).
    """
    filled = 0
    rows_written = 0
    unknown_stats = set()
    for record in records:
        ankama_id = record['ankama_id']
        set_id = set_id_by_ankama.get(ankama_id)
        if set_id is None or ankama_id not in fill_ankama:
            continue
        rows = []
        for num_pieces, entries in record['tiers'].items():
            for stat_name, value in entries.items():
                stat_id = stat_id_by_name.get(stat_name)
                if stat_id is None:
                    unknown_stats.add(stat_name)
                    continue
                rows.append((set_id, int(num_pieces), stat_id, int(value)))
        if not rows:
            continue
        if not dry_run:
            cursor.execute("DELETE FROM set_bonus WHERE item_set = ?", (set_id,))
            cursor.executemany(
                "INSERT INTO set_bonus(item_set, num_pieces_used, stat, value) VALUES (?, ?, ?, ?)",
                rows)
        filled += 1
        rows_written += len(rows)
    return filled, rows_written, unknown_stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scrape', action='store_true',
                        help='Refresh the vendored snapshot from the API (needs network).')
    parser.add_argument('--all', action='store_true',
                        help='Apply to every set, not just those missing bonuses.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Report only; do not write the snapshot or the DB.')
    args = parser.parse_args()

    conn = _open_items_db(GAME_VERSION)
    cursor = conn.cursor()
    for table in ('sets', 'set_bonus', 'stats'):
        if not _table_exists(cursor, table):
            raise RuntimeError('%s table missing in %s' % (table, get_items_db_path(GAME_VERSION)))

    stat_id_by_name = {name: sid for sid, name in cursor.execute("SELECT id, name FROM stats")}
    sets = cursor.execute("SELECT id, ankama_id FROM sets").fetchall()
    set_id_by_ankama = {ankama_id: set_id for set_id, ankama_id in sets}
    have_bonus = {row[0] for row in cursor.execute("SELECT DISTINCT item_set FROM set_bonus")}
    missing_ankama = {ankama_id for set_id, ankama_id in sets if set_id not in have_bonus}
    print('[retro] %d sets total, %d without bonuses.' % (len(sets), len(missing_ankama)))

    if args.scrape:
        records = fetch_api_records()
        print('[retro] Fetched %d sets from %s.' % (len(records), API_URL))
        if not args.dry_run:
            with open(CACHE_PATH, 'w', encoding='utf-8') as out_file:
                json.dump(records, out_file, ensure_ascii=False, indent=2, sort_keys=True)
            print('[retro] Wrote snapshot %s (%d sets).' % (CACHE_PATH, len(records)))
    else:
        if not os.path.exists(CACHE_PATH):
            raise SystemExit('No snapshot at %s -- run with --scrape first (needs network).' % CACHE_PATH)
        with open(CACHE_PATH, encoding='utf-8') as in_file:
            records = json.load(in_file)
        print('[retro] Loaded snapshot %s (%d sets).' % (CACHE_PATH, len(records)))

    fill_ankama = set(set_id_by_ankama) if args.all else missing_ankama
    filled, rows_written, unknown_stats = apply_records(
        cursor, records, set_id_by_ankama, stat_id_by_name, fill_ankama, args.dry_run)
    if unknown_stats:
        print('  ! unmapped stat names (skipped): %s' % ', '.join(sorted(unknown_stats)))
    still_missing = sorted(missing_ankama - {r['ankama_id'] for r in records})
    print('[retro] Filled %d sets (%d bonus rows). %d missing sets not in API: %s'
          % (filled, rows_written, len(still_missing), still_missing))

    if args.dry_run:
        print('[retro] dry-run: no changes written.')
        conn.close()
        return

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    print('[retro] Wrote set_bonus rows and re-dumped items_retro.db.')


if __name__ == '__main__':
    main()
