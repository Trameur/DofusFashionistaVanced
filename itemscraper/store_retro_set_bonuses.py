#!/usr/bin/env python
# coding=utf-8

"""Refresh retro_set_bonuses_drt.json, the community set bonuses the pipeline compares the game's against."""

import json
import os
import re
import unicodedata

import requests

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

API_URL = 'https://dofusretrotools.com/api/set-bonuses'
SOLOMONK_URL = 'https://solomonk.fr/fr/panoplies'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
# Vendored snapshot of the scraped bonuses, keyed by set ankama id.
CACHE_PATH = os.path.join(CURRENT_DIRECTORY, 'retro_set_bonuses_drt.json')

# Dofus Retro Tools codes (undocumented, matched on retro_raw effect ids) -> stat names
STAT_CODE = {
    'vi': 'Vitality', 'sa': 'Wisdom', 'ag': 'Agility', 'in': 'Intelligence',
    'ch': 'Chance', 'fo': 'Strength', 'dmg': 'Damage', 'so': 'Heals',
    'pp': 'Prospecting', 'ii': 'Initiative', 'po': 'Range', 'cc': 'Critical Hits',
    'pa': 'AP', 'pm': 'MP',
    # Effect 138, "Augmente les dommages de X%"
    'pu': 'Power',
    # rn is flat on items, but this endpoint uses rn and rnp both for the percent
    'rn': '% Neutral Resist', 'rnp': '% Neutral Resist',
    # Effects 225 and 226
    'pi': 'Trap Damage', 'pip': '% Trap Damage',
    'ic': 'Summon', 'pd': 'Pods',
}
_ELEMENTS = {'feu': 'Fire', 'terre': 'Earth', 'eau': 'Water', 'air': 'Air', 'neutre': 'Neutral'}

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
    """Code/value -> (stat name, value); resists and HP come as a phrase ("+100 en vie")."""
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
    """[{ankama_id, name, tiers: {num_pieces(str): {stat_name: value}}}, ...]"""
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
    """Both sources merged, solomonk leading, one source per set."""
    solomonk = fetch_solomonk_records(report_unmapped)
    api = fetch_api_records(report_unmapped)
    merged = {record['ankama_id']: record for record in api}
    merged.update({record['ankama_id']: record for record in solomonk})
    records = [merged[key] for key in sorted(merged)]
    print('[retro] %d sets from solomonk, %d more from the API, %d in all.'
          % (len(solomonk), len(records) - len(solomonk), len(records)))
    return records


def main():
    """Fetch both community sources and rewrite the vendored snapshot."""
    records = fetch_records()
    with open(CACHE_PATH, 'w', encoding='utf-8') as out_file:
        json.dump(records, out_file, ensure_ascii=False, indent=2, sort_keys=True)
    print('[retro] Wrote snapshot %s (%d sets).' % (CACHE_PATH, len(records)))


if __name__ == '__main__':
    main()
