#!/usr/bin/env python
# coding=utf-8

"""scrape_retro_pet_bonuses.py: auto-build retro_pet_bonuses.json from dofux.org.

Dofus Retro pet bonuses (the stats a pet can be fed toward, and their caps) are
not in Ankama's lang data. The fan database dofux.org lists them per pet in a
"Nourriture" (food) block, e.g. for Bwak d'Air:

    +0 à 80 en vitalité (...)
    +0 à 80 en agilité (...)
    0 à 20 % de résistance à l'air (...)

This scrapes that page, maps the French stat words to the internal stat names,
and maps each French pet name -> ankama id -> English name (via the retro lang
files in retro_raw/) so the output keys match items_retro.db. Result is written
to retro_pet_bonuses.json, consumed by store_retro_pet_bonuses.py.

Network + the retro_raw items_{fr,en}.json lang dumps are required.
"""

import json
import os
import re
import sqlite3
import sys
import unicodedata

import requests

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for _path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if _path not in sys.path:
        sys.path.append(_path)
from store_item_obtainment import get_items_db_path  # noqa: E402

DOFUX_URL = 'https://www.dofux.org/item-familier.dx'
RAW_DIR = os.path.join(CURRENT_DIRECTORY, 'retro_raw')
OUT_PATH = os.path.join(CURRENT_DIRECTORY, 'retro_pet_bonuses.json')

ELEMENTS = {'feu': 'Fire', 'terre': 'Earth', 'air': 'Air', 'eau': 'Water', 'neutre': 'Neutral'}
# French "en <word>" food stat -> internal stat name.
FOOD_STATS = {
    'force': 'Strength', 'intelligence': 'Intelligence', 'chance': 'Chance',
    'agilite': 'Agility', 'vitalite': 'Vitality', 'sagesse': 'Wisdom',
    'prospection': 'Prospecting', 'initiative': 'Initiative', 'soins': 'Heals',
    'dommages': 'Damage', 'pods': 'Pods', 'pod': 'Pods', 'renvoi': 'Reflects',
    'renvois': 'Reflects',
}

# Manual data (keyed by English items_retro.db name) that overrides / fills the
# scrape. dofux omits a "Nourriture" block for some quest-reward pets, so they're
# supplied here from community sources (millenium / dofusretro.jeuxonline).
# Edit this to correct any pet, it takes precedence over the scrape.
OVERRIDES = {
    'Nomoon': [['Prospecting', 80]],
    'Bworky': [['Pods', 1000]],
    'Peki': [['Vitality', 400]],
    'Armoured Dragoone': [['Wisdom', 50]],
    'Black Dragoone': [['Wisdom', 50]],
    'Golden Dragoone': [['Wisdom', 50]],
    'Pink Dragoone': [['Wisdom', 50]],
    'Red Dragoone': [['Wisdom', 50]],
}

_FOOD_RE = re.compile(
    r'(\d+)\s*[àa]\s*(\d+)\s*(?:en|[àa]\s+la)\s+([A-Za-zàâçéèêëîïôûùü]+)', re.I)
_PCTDMG_RE = re.compile(r'(\d+)\s*[àa]\s*(\d+)\s*%\s*de\s+dommages', re.I)
_RES_RE = re.compile(
    r'(\d+)\s*[àa]\s*(\d+)\s*%\s*de\s+r[ée]sistance[^.(]*?(feu|terre|air|eau|neutre)', re.I)
_NAME_RE = re.compile(r'<center>\s*<B>([^<]+)</B>')


def _norm(text):
    folded = ''.join(c for c in unicodedata.normalize('NFKD', text or '')
                     if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', ' ', folded).strip()


def _strip_tags(html):
    return re.sub(r'<[^>]+>', ' ', html)


def _parse_dofux(html):
    """{normalized FR pet name: [[stat, max], ...]} from the dofux familier page."""
    pets = {}
    names = list(_NAME_RE.finditer(html))
    for index, match in enumerate(names):
        fr_name = match.group(1).strip()
        end = names[index + 1].start() if index + 1 < len(names) else match.end() + 2500
        block = html[match.end():end]
        if 'Nourriture' not in block:
            continue
        segment = _strip_tags(block.split('Nourriture', 1)[1].split('Le maximum')[0])

        bonuses = []
        seen = set()

        def add(stat, value):
            key = (stat, value)
            if stat and key not in seen:
                seen.add(key)
                bonuses.append([stat, value])

        for _lo, hi, word in _FOOD_RE.findall(segment):
            add(FOOD_STATS.get(_norm(word)), int(hi))
        for _lo, hi in _PCTDMG_RE.findall(segment):
            add('% Weapon Damage', int(hi))
        for _lo, hi, element in _RES_RE.findall(segment):
            add('%% %s Resist' % ELEMENTS[element.lower()], int(hi))

        if bonuses:
            pets[_norm(fr_name)] = bonuses
    return pets


_SOLOMONK_LIST = 'https://solomonk.fr/fr/equipements/18/familier'
_SOLOMONK_AJAX = 'https://solomonk.fr/ajax/select_stuff.php'
_CARD_RE = re.compile(
    r'card-solo-item-title"><a href="https://solomonk\.fr/fr/equipement/(\d+)/')
_EFFECT_LINE_RE = re.compile(r'<span class="font-weight-bold">([^<]+)</span>')


def _parse_effect_lines(lines):
    """[[stat, max], ...] from Solomonk effect lines like
    '+0 à 80 en intelligence (Capacités accrues : 90)'."""
    bonuses = []
    seen = set()

    def add(stat, value):
        key = (stat, value)
        if stat and key not in seen:
            seen.add(key)
            bonuses.append([stat, value])

    for line in lines:
        for _lo, hi, word in _FOOD_RE.findall(line):
            add(FOOD_STATS.get(_norm(word)), int(hi))
        for _lo, hi in _PCTDMG_RE.findall(line):
            add('% Weapon Damage', int(hi))
        for _lo, hi, element in _RES_RE.findall(line):
            add('%% %s Resist' % ELEMENTS[element.lower()], int(hi))
    return bonuses


def _fetch_solomonk_pets():
    """{ankama_id: [[stat, max], ...]} from the Solomonk pets listing (the
    live 1.48 reference; covers event pets dofux never had). Cards come from
    the select_stuff endpoint (session-primed, T=18, minimal params: adding
    C=false makes it return empty) and carry the ankama id in the item URL.
    The endpoint intermittently serves empty pages mid-crawl, so only two
    consecutive empties end the crawl (same rule as the bestiary scrapers)."""
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'
    session.get(_SOLOMONK_LIST, timeout=60)
    pets = {}
    offset = 0
    empty_streak = 0
    for _ in range(80):
        response = session.get(_SOLOMONK_AJAX, timeout=60, params={
            'lang': 'fr', 'Q': 10, 'O': offset, 'T': '18',
        }, headers={'Referer': _SOLOMONK_LIST,
                    'X-Requested-With': 'XMLHttpRequest'})
        try:
            html = response.json().get('html') or ''
        except ValueError:
            html = ''
        cards = list(_CARD_RE.finditer(html))
        if not cards:
            empty_streak += 1
            if empty_streak > 2:
                break
            import time
            time.sleep(2.0)
            continue
        empty_streak = 0
        for index, match in enumerate(cards):
            end = cards[index + 1].start() if index + 1 < len(cards) else len(html)
            lines = _EFFECT_LINE_RE.findall(html[match.end():end])
            bonuses = _parse_effect_lines(lines)
            if bonuses:
                pets[int(match.group(1))] = bonuses
        offset += 10
        import time
        time.sleep(0.4)
    return pets


def _lang_names(lang):
    with open(os.path.join(RAW_DIR, 'items_%s.json' % lang), encoding='utf-8') as in_file:
        return (json.load(in_file).get('I') or {}).get('u') or {}


def _db_feedable_en_names():
    """EN names of pets with no characteristic stats (so candidates for variants)."""
    conn = sqlite3.connect(get_items_db_path('retro'))
    cursor = conn.cursor()
    pet_type = cursor.execute("SELECT id FROM item_types WHERE name = 'Pet'").fetchone()[0]
    rows = cursor.execute(
        """SELECT name FROM items i WHERE type = ? AND id < 10000000 AND NOT EXISTS
               (SELECT 1 FROM stats_of_item s WHERE s.item = i.id)""", (pet_type,)).fetchall()
    conn.close()
    return sorted(name for (name,) in rows)


def main():
    print('Fetching %s ...' % DOFUX_URL)
    html = requests.get(DOFUX_URL, timeout=60, headers={'User-Agent': 'Mozilla/5.0'}).text
    by_fr = _parse_dofux(html)
    print('Parsed bonuses for %d pets from dofux.' % len(by_fr))

    fr_items = _lang_names('fr')
    en_items = _lang_names('en')
    fr_norm_to_id = {_norm(v.get('n')): int(k) for k, v in fr_items.items()
                     if isinstance(v, dict) and v.get('n')}
    en_by_id = {int(k): v.get('n') for k, v in en_items.items() if isinstance(v, dict)}

    # Map scraped FR names -> EN names via ankama id.
    scraped_en = {}
    unmatched = []
    for fr_norm, bonuses in by_fr.items():
        ankama_id = fr_norm_to_id.get(fr_norm)
        en_name = en_by_id.get(ankama_id) if ankama_id is not None else None
        if en_name:
            scraped_en[en_name] = bonuses
        else:
            unmatched.append(fr_norm)

    # Solomonk (live 1.48, id-keyed: no name matching) overrides dofux.
    print('Fetching the Solomonk pets listing ...')
    solomonk = _fetch_solomonk_pets()
    solomonk_named = 0
    for ankama_id, bonuses in solomonk.items():
        en_name = en_by_id.get(ankama_id)
        if en_name:
            scraped_en[en_name] = bonuses
            solomonk_named += 1
    print('Parsed bonuses for %d pets from Solomonk (%d matched to the db).'
          % (len(solomonk), solomonk_named))

    # Result: every DB-feedable pet as a key (so it's a complete checklist),
    # filled from the scrape where available, plus any extra scraped pets.
    result = {}
    for en_name in _db_feedable_en_names():
        result[en_name] = scraped_en.get(en_name, [])
    for en_name, bonuses in scraped_en.items():
        result.setdefault(en_name, bonuses)

    # Manual overrides win (and add any pet not otherwise present).
    result.update(OVERRIDES)

    result = dict(sorted(result.items()))
    with open(OUT_PATH, 'w', encoding='utf-8') as out_file:
        json.dump(result, out_file, ensure_ascii=False, indent=2)

    filled = sum(1 for v in result.values() if v)
    print('Wrote %s: %d pets (%d with bonuses, %d blank).'
          % (OUT_PATH, len(result), filled, len(result) - filled))
    if unmatched:
        print('FR names not matched to an ankama id (%d): %s'
              % (len(unmatched), ', '.join(sorted(unmatched)[:15])))


if __name__ == '__main__':
    main()
