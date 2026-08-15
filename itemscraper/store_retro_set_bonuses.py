#!/usr/bin/env python
# coding=utf-8

"""store_retro_set_bonuses.py: fill missing Dofus Retro set bonuses.

Set bonuses are server-side, so no Ankama file carries them and there is no
first-party source to read. Two unrelated fan databases publish them:

  * solomonk.fr lists 140 sets, in French prose ("+25% de dommages aux pieges").
  * dofusretrotools.com exposes 173 at /api/set-bonuses, keyed by the Ankama set
    id (`clothId`), which matches sets.ankama_id exactly, in short stat codes.

Where the two overlap they disagree on 66 tiers, and every disagreement checks
out in solomonk's favour against the items the set is made of: the Panoplignon
grants percent TRAP damage, which its own weapon also grants, where the API
codes plain percent damage; the Prespic set reflects damage, which its ring and
belt also do, where the API has no line at all. A player reported the
Panoplignon one. So solomonk leads and the API fills the 33 sets it does not
cover.

Only sets with no set_bonus row at all are filled, unless --all is given.
  * --scrape: fetch both sources and rewrite the committed snapshot
    retro_set_bonuses_drt.json, then apply it.
  * default: apply the committed snapshot, with no network.
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
SOLOMONK_URL = 'https://solomonk.fr/fr/panoplies'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
# Vendored snapshot of the scraped bonuses, keyed by set ankama id.
CACHE_PATH = os.path.join(CURRENT_DIRECTORY, 'retro_set_bonuses_drt.json')

# Dofus Retro Tools stat codes -> internal stat names.
#
# The codes are not documented, so each one here was read off the game's own
# files rather than guessed: for 2190 items the API's (code, min, max) lines
# were matched against the same item's ISTA string in retro_raw, which is keyed
# by Ankama effect id. Every code below agreed unanimously across every item
# that carries it. The effect id and the game's own French text are noted where
# a code is easy to read the wrong way.
STAT_CODE = {
    'vi': 'Vitality', 'sa': 'Wisdom', 'ag': 'Agility', 'in': 'Intelligence',
    'ch': 'Chance', 'fo': 'Strength', 'dmg': 'Damage', 'so': 'Heals',
    'pp': 'Prospecting', 'ii': 'Initiative', 'po': 'Range', 'cc': 'Critical Hits',
    'pa': 'AP', 'pm': 'MP',
    # 138, "Augmente les dommages de X%", which the model applies as Power.
    'pu': 'Power',
    # On items rn is the flat resist (244) and rnp the percent one (214), but
    # this endpoint uses both for the percent: no tier carries the two at once,
    # and solomonk prints a percent for all 43 rn tiers and all 24 rnp ones.
    'rn': '% Neutral Resist', 'rnp': '% Neutral Resist',
    # 225 and 226. Both were absent, so the Aerdala and Rat Noir sets, the only
    # two trap sets in the game, reached the site with no trap bonus at all.
    'pi': 'Trap Damage', 'pip': '% Trap Damage',
    'ic': 'Summon', 'pd': 'Pods',
}
_ELEMENTS = {'feu': 'Fire', 'terre': 'Earth', 'eau': 'Water', 'air': 'Air', 'neutre': 'Neutral'}

# Solomonk prints its bonuses as the game words them, so the lines are read the
# same way the API's own French fallback phrases are.
_SOLOMONK_PLAIN = {
    'vitalite': 'Vitality', 'sagesse': 'Wisdom', 'agilite': 'Agility',
    'intelligence': 'Intelligence', 'chance': 'Chance', 'force': 'Strength',
    'soins': 'Heals', 'prospection': 'Prospecting', 'initiative': 'Initiative',
    'portee': 'Range', 'coups critiques': 'Critical Hits',
    'creatures invocables': 'Summon', 'vie': 'HP',
}
_SOLOMONK_TAB = re.compile(r'href="#is(\d+)-(\d+)"[^>]*>\s*(\d+)\s*objets?', re.S)
_SOLOMONK_PANE = re.compile(
    r'id="is(\d+)-(\d+)"(.*?)(?=<div class="col tab-pane|</div></div></div></div>)', re.S)
_SOLOMONK_BONUS = re.compile(
    r'Bonus de la panoplie</u><ul class="list-unstyled">(.*?)</ul>', re.S)
_SOLOMONK_LINE = re.compile(r'<li>(.*?)</li>', re.S)


def _ascii(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def _line_to_stat(line):
    """One solomonk bonus line -> (internal stat name, value), or (None, None)."""
    flat = _ascii(line).strip()
    number = re.search(r'-?\d+', flat)
    if not number:
        return None, None
    value = int(number.group(0))
    if 'dommages aux pieges' in flat:
        return ('% Trap Damage' if '%' in flat else 'Trap Damage'), value
    if flat.startswith('augmente les dommages de'):
        return 'Power', value
    if flat.startswith('augmente le poids portable'):
        return 'Pods', value
    if flat.startswith('renvoie'):
        return 'Reflects', value
    if 'resistance' in flat:
        for fr_element, en_element in _ELEMENTS.items():
            if fr_element in flat:
                return (('%% %s Resist' % en_element) if '%' in flat
                        else ('%s Resist' % en_element)), value
        return None, None
    if re.search(r'\bpa\b', flat):
        return 'AP', value
    if re.search(r'\bpm\b', flat):
        return 'MP', value
    if 'de dommages' in flat:
        return 'Damage', value
    for french, english in _SOLOMONK_PLAIN.items():
        if french in flat:
            return english, value
    return None, None


def fetch_solomonk_records(report_unmapped=True):
    """Solomonk's sets as snapshot records, same shape as the API's."""
    page = requests.get(SOLOMONK_URL, headers=HEADERS, timeout=120).text
    pieces = {(int(set_id), int(index)): int(count)
              for set_id, index, count in _SOLOMONK_TAB.findall(page)}
    names = dict((int(set_id), name) for set_id, name in re.findall(
        r'/fr/panoplie/(\d+)/[^"]*"[^>]*>([^<]+)</a>', page))
    tiers_by_set = {}
    dropped = {}
    for set_id, index, body in _SOLOMONK_PANE.findall(page):
        block = _SOLOMONK_BONUS.search(body)
        count = pieces.get((int(set_id), int(index)))
        if not block or count is None:
            continue
        stats = {}
        for raw in _SOLOMONK_LINE.findall(block.group(1)):
            line = re.sub(r'<[^>]+>', '', raw).strip()
            stat_name, value = _line_to_stat(line)
            if stat_name is not None:
                stats[stat_name] = value
            else:
                dropped.setdefault(line, set()).add(names.get(int(set_id), ''))
        if stats:
            tiers_by_set.setdefault(int(set_id), {})[str(count)] = stats
    if dropped and report_unmapped:
        print('  ! %d solomonk lines have no stat and were dropped:' % len(dropped))
        for line in sorted(dropped):
            print('      %-40s %d set(s)' % (repr(line)[:40], len(dropped[line])))
    return [{'ankama_id': set_id, 'name': names.get(set_id, ''), 'tiers': tiers,
             'source': 'solomonk'}
            for set_id, tiers in sorted(tiers_by_set.items())]


def _code_to_stat(code, value):
    """A bonus entry's code/value -> (internal stat name, value), or (None, _).

    Resists, flat HP and physical reduction arrive not as a STAT_CODE key but as
    a French phrase carrying the value: "10 % de resistance a la terre",
    "+100 en vie", "Reduction physique de 1".
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


def fetch_api_records(report_unmapped=True):
    """The API's sets as snapshot records: [{ankama_id, name, tiers}, ...].

    tiers: {num_pieces(str): {stat_name: value}}. A line whose code is not in
    STAT_CODE is dropped, and dropping one silently is how four codes went
    missing for as long as they did, so what was dropped is printed.
    """
    data = requests.get(API_URL, headers=HEADERS, timeout=60).json()
    records = []
    dropped = {}
    for entry in data:
        tiers = {}
        for num_pieces, bonuses in (entry.get('bonuses') or {}).items():
            stats = {}
            for bonus in bonuses:
                stat_name, value = _code_to_stat(bonus['code'], bonus.get('max', bonus.get('min')))
                if stat_name is not None and value is not None:
                    stats[stat_name] = value
                else:
                    dropped.setdefault(bonus['code'], set()).add(entry.get('name', ''))
            if stats:
                tiers[str(int(num_pieces))] = stats
        if tiers:
            records.append({'ankama_id': entry['clothId'], 'name': entry.get('name', ''),
                            'tiers': tiers, 'source': 'dofusretrotools'})
    if dropped and report_unmapped:
        print('  ! %d API codes have no stat and were dropped:' % len(dropped))
        for code in sorted(dropped):
            sets = sorted(dropped[code])
            print('      %-40s %d set(s): %s' % (repr(code), len(sets), ', '.join(sets[:4])))
    return records


def fetch_records(report_unmapped=True):
    """Both sources merged, solomonk leading, one source per set.

    A set takes all of its tiers from one source or the other. Mixing them
    within a set would blend two readings of the same bonus, which is exactly
    what the 66 disagreements are.
    """
    solomonk = fetch_solomonk_records(report_unmapped)
    api = fetch_api_records(report_unmapped)
    merged = {record['ankama_id']: record for record in api}
    merged.update({record['ankama_id']: record for record in solomonk})
    records = [merged[key] for key in sorted(merged)]
    print('[retro] %d sets from solomonk, %d more from the API, %d in all.'
          % (len(solomonk), len(records) - len(solomonk), len(records)))
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
        records = fetch_records()
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
