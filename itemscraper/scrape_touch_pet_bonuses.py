#!/usr/bin/env python3
"""scrape_touch_pet_bonuses.py: auto-build touch_pet_bonuses.json from the
official Dofus Touch encyclopedia.

Touch pets gain their stats by feeding, so the backend datacenter carries no
bonus values: the Pets class only lists food items, and the pet items'
possibleEffects are feeding metadata (life points, corpulence, last meal). The
official site however renders an "Effets maximum sous hormone" block per pet
with the fed/hormone caps, which is exactly what the optimizer needs.

The site sits behind an anonymous Ankama SSO bounce (302 via account.ankama.com
with an authlogin token), which a cookie-aware client follows transparently.
Pages accept bare ids: /fr/mmorpg/encyclopedie/familiers/<ankama_id>. When the
French page answers 404 the English one, /en/mmorpg/encyclopedia/pets/<id>, is
read instead: on 2026-09-18 four pets had lost their French page and kept the
English one, and the English reader gives the French reader's lines on all 172
pets that have both.

Output: touch_pet_bonuses.json {"<EN items_touch.db name>": [["Stat", max], ...]}
(same shape as retro_pet_bonuses.json), consumed by store_touch_pet_bonuses.py.

Usage (from repo root):
    python itemscraper/scrape_touch_pet_bonuses.py [--delay 0.25] [--limit N]
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(CURRENT_DIRECTORY, 'touch_pet_bonuses.json')
DB_PATH = os.path.join(CURRENT_DIRECTORY, '..', 'fashionistapulp',
                       'fashionistapulp', 'items_touch.db')
BASE_URL = 'https://www.dofus-touch.com/fr/mmorpg/encyclopedie/familiers/%d'
ENGLISH_URL = 'https://www.dofus-touch.com/en/mmorpg/encyclopedia/pets/%d'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

ELEMENTS = {'air': 'Air', 'eau': 'Water', 'feu': 'Fire',
            'terre': 'Earth', 'neutre': 'Neutral'}
SIMPLE_STATS = {
    'force': 'Strength', 'intelligence': 'Intelligence', 'chance': 'Chance',
    'agilite': 'Agility', 'vitalite': 'Vitality', 'sagesse': 'Wisdom',
    'prospection': 'Prospecting', 'initiative': 'Initiative', 'soins': 'Heals',
    'dommages': 'Damage', 'pods': 'Pods', 'pod': 'Pods',
}

# Manual fixes keyed by English items_touch.db name; take precedence over the
# scrape (same mechanism as retro's OVERRIDES). Moowitty sat here from
# 2026-08-16, the day after its French page started answering 404; on 2026-09-18
# that page was back with the same 53 Prospecting and 98 Wisdom, and its English
# page had them too.
OVERRIDES = {}

_PCT_RESIST_RE = re.compile(
    r'^(\d+)\s*%\s*R[ée]sistance\s+(Air|Eau|Feu|Terre|Neutre)$', re.I)
_LIN_RESIST_RE = re.compile(
    r'^(\d+)\s*R[ée]sistance\s+(Air|Eau|Feu|Terre|Neutre)$', re.I)
_ELEM_DAMAGE_RE = re.compile(
    r'^(\d+)\s*Dommages?\s+(Air|Eau|Feu|Terre|Neutre)$', re.I)
_PCT_DAMAGE_RE = re.compile(r'^(\d+)\s*%\s*Dommages?$', re.I)
_SIMPLE_RE = re.compile(r'^(\d+)\s+([A-Za-zàâçéèêëîïôûù]+)$')

# None of these ever stops the reader. The line is compared after _norm has
# taken its accents off, so the first and last never match, and "Description"
# comes before the block. The reader runs to the end of the page and keeps the
# gain per meal listed under "Régime alimentaire" ("1 Prospection") as a second
# line, on 76 pets on 2026-09-18. Each of those lines is a variant, numbered in
# file order, so fixing this alone would move the ids saved builds keep.
_STOP_LINES = ('régime alimentaire', 'description', 'caractéristiques')

ENGLISH_ELEMENTS = {'air': 'Air', 'water': 'Water', 'fire': 'Fire',
                    'earth': 'Earth', 'neutral': 'Neutral'}
ENGLISH_SIMPLE_STATS = {
    'strength': 'Strength', 'intelligence': 'Intelligence', 'chance': 'Chance',
    'agility': 'Agility', 'vitality': 'Vitality', 'wisdom': 'Wisdom',
    'prospecting': 'Prospecting', 'initiative': 'Initiative', 'heals': 'Heals',
    'damage': 'Damage', 'pods': 'Pods', 'pod': 'Pods',
}
_EN_PCT_RESIST_RE = re.compile(
    r'^(\d+)\s*%\s*(Air|Water|Fire|Earth|Neutral)\s+Resistance$', re.I)
_EN_LIN_RESIST_RE = re.compile(
    r'^(\d+)\s*(Air|Water|Fire|Earth|Neutral)\s+Resistance$', re.I)
_EN_ELEM_DAMAGE_RE = re.compile(
    r'^(\d+)\s*(Air|Water|Fire|Earth|Neutral)\s+Damages?$', re.I)
_EN_PCT_DAMAGE_RE = re.compile(r'^(\d+)\s*%\s*Damages?$', re.I)
_EN_SIMPLE_RE = re.compile(r'^(\d+)\s+([A-Za-z]+)$')

# The French reader's one stop that can match, and not "Diet": the English
# page then gives the French reader's lines, the per-meal gain included, so a
# pet whose French page disappears keeps its lines and its variants their ids.
_EN_STOP_LINES = ('description',)


def _norm(text):
    text = text.lower()
    for src, dst in (('à', 'a'), ('â', 'a'), ('é', 'e'), ('è', 'e'), ('ê', 'e'),
                     ('ë', 'e'), ('î', 'i'), ('ï', 'i'), ('ô', 'o'), ('û', 'u'),
                     ('ù', 'u'), ('ç', 'c')):
        text = text.replace(src, dst)
    return text.strip()


def _page_lines(html):
    # Case-insensitive and attribute-tolerant: CodeQL (py/bad-tag-filter)
    # rightly notes <SCRIPT> or </script foo> would slip through otherwise.
    text = re.sub(r'<script\b[\s\S]*?</script[^>]*>', '', html,
                  flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '\n', text)
    return [line.strip() for line in text.split('\n') if line.strip()]


def _french_line(line):
    """(stat, value) for one line of a French block, or (None, None)."""
    m = _PCT_RESIST_RE.match(line)
    if m:
        return '%% %s Resist' % ELEMENTS[_norm(m.group(2))], int(m.group(1))
    m = _LIN_RESIST_RE.match(line)
    if m:
        return '%s Resist' % ELEMENTS[_norm(m.group(2))], int(m.group(1))
    m = _ELEM_DAMAGE_RE.match(line)
    if m:
        return '%s Damage' % ELEMENTS[_norm(m.group(2))], int(m.group(1))
    m = _PCT_DAMAGE_RE.match(line)
    if m:
        return 'Power', int(m.group(1))
    m = _SIMPLE_RE.match(line)
    if m and _norm(m.group(2)) in SIMPLE_STATS:
        return SIMPLE_STATS[_norm(m.group(2))], int(m.group(1))
    return None, None


def _english_line(line):
    """(stat, value) for one line of an English block, or (None, None)."""
    m = _EN_PCT_RESIST_RE.match(line)
    if m:
        return '%% %s Resist' % ENGLISH_ELEMENTS[_norm(m.group(2))], int(m.group(1))
    m = _EN_LIN_RESIST_RE.match(line)
    if m:
        return '%s Resist' % ENGLISH_ELEMENTS[_norm(m.group(2))], int(m.group(1))
    m = _EN_ELEM_DAMAGE_RE.match(line)
    if m:
        return '%s Damage' % ENGLISH_ELEMENTS[_norm(m.group(2))], int(m.group(1))
    m = _EN_PCT_DAMAGE_RE.match(line)
    if m:
        return 'Power', int(m.group(1))
    m = _EN_SIMPLE_RE.match(line)
    if m and _norm(m.group(2)) in ENGLISH_SIMPLE_STATS:
        return ENGLISH_SIMPLE_STATS[_norm(m.group(2))], int(m.group(1))
    return None, None


# language: (first words of the block's title, lines that end it, line reader)
_READERS = {
    'fr': ('effets maximum', _STOP_LINES, _french_line),
    'en': ('max effects', _EN_STOP_LINES, _english_line),
}


def parse_bonuses(html, language='fr'):
    """Extract [(stat, max)] from the lines after 'Effets maximum' ('Max
    effects' in English). The hormone-dropper line matches no stat. The reader
    runs to the end of the page, diet included, see _STOP_LINES."""
    title, stops, read_line = _READERS[language]
    lines = _page_lines(html)
    start = None
    for i, line in enumerate(lines):
        if _norm(line).startswith(title):
            start = i + 1
            break
    if start is None:
        return []

    bonuses = []
    seen = set()
    for line in lines[start:]:
        low = _norm(line)
        if any(low.startswith(stop) for stop in stops):
            break
        stat, value = read_line(line)
        if stat and value and (stat, value) not in seen:
            seen.add((stat, value))
            bonuses.append([stat, value])
    return bonuses


def build_opener():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [('User-Agent', USER_AGENT), ('Accept-Language', 'fr')]
    return opener


def fetch(opener, url, retries=2, timeout=30):
    """Return the page html, or None when the encyclopedia has no page for
    this id (404: legacy/internal pets)."""
    last = None
    for attempt in range(retries + 1):
        try:
            with opener.open(url, timeout=timeout) as resp:
                return resp.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last = exc
            time.sleep(1.0 + attempt)
        except Exception as exc:
            last = exc
            time.sleep(1.0 + attempt)
    raise RuntimeError('fetch failed for %s: %s' % (url, last))


def pets_in_db(cursor):
    """({pet name: [{(stat, value)} carried, one set per row]}, known stat
    names), read the way store_touch_pet_bonuses.py reads them."""
    known = {name for (name,) in cursor.execute('SELECT name FROM stats')}
    pets = {}
    for item_id, name in cursor.execute(
            """SELECT i.id, i.name FROM items i JOIN item_types t ON t.id = i.type
               WHERE t.name = 'Pet' AND i.id < 200000000 ORDER BY i.id""").fetchall():
        pets.setdefault(name, []).append(set(cursor.execute(
            """SELECT s.name, v.value FROM stats_of_item v
               JOIN stats s ON s.id = v.stat WHERE v.item = ?""", (item_id,))))
    return pets, known


def variant_layout(bonuses, pets=None, known=None):
    """[(pet, stat)], one per variant store_touch_pet_bonuses.py would write, in
    its order: the file's, sorted. It writes one per line and per db row of the
    pet, except a line the pet already carries as a stat of its own, a stat it
    does not know and a pet the db lacks. Without the db, one per line."""
    layout = []
    for name in sorted(bonuses):
        for carried in ([set()] if pets is None else pets.get(name, [])):
            for stat, value in bonuses[name]:
                if known is not None and stat not in known:
                    continue
                if (stat, int(value)) in carried:
                    continue
                layout.append((name, stat))
    return layout


def first_moved_line(previous, current, pets=None, known=None):
    """The first (pet, stat) whose variant would change id or meaning, or
    None. A variant added even at the very end moves nothing but takes the next
    id, and 200000228 is the id old Touch builds keep for the Gelano
    (structure.GELANO_DEPLOYED_IDS)."""
    before = variant_layout(previous, pets, known)
    after = variant_layout(current, pets, known)
    if before == after:
        return None
    for old, new in zip(before, after):
        if old != new:
            return old
    shorter = min(len(before), len(after))
    return before[shorter] if len(before) > len(after) else after[shorter]


def changed_values(previous, current):
    """(pet, stat, before, after) for the lines whose cap moved in place. Only
    meaningful when first_moved_line found nothing: the variant then keeps its
    id and saved builds get the new value."""
    changes = []
    for name in sorted(set(previous) & set(current)):
        for old, new in zip(previous[name], current[name]):
            if old[0] == new[0] and old[1] != new[1]:
                changes.append((name, old[0], old[1], new[1]))
    return changes


def explain_refusal(previous, current, moved):
    """The lines a human needs to decide on a refused write."""
    lost = sorted(set(previous) - set(current))
    added = sorted(set(current) - set(previous))
    reshaped = sorted(
        name for name in set(previous) & set(current)
        if [line[0] for line in previous[name]]
        != [line[0] for line in current[name]])
    lines = []
    if lost:
        lines.append('the scrape lost %d pet(s) the file already had: %s'
                     % (len(lost), ', '.join(lost)))
    if added:
        lines.append('the scrape found %d pet(s) the file does not have: %s'
                     % (len(added), ', '.join(added)))
    if reshaped:
        lines.append('lines added, removed or reordered on: %s'
                     % ', '.join(reshaped))
    if not (lost or added or reshaped):
        lines.append('a cap moved onto or off a stat its pet already carries, '
                     'which adds or removes a variant: %s' % ', '.join(
                         '%s %s %s -> %s' % change
                         for change in changed_values(previous, current)))
    lines.append('the variants saved builds point at would take other ids '
                 'from %s (%s) on' % moved)
    lines.append('nothing written. Give a lost pet an OVERRIDES entry, or pass '
                 '--allow-shrink once the game really changed them.')
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delay', type=float, default=0.25)
    parser.add_argument('--limit', type=int, default=0,
                        help='only scrape the first N pets (debug)')
    parser.add_argument('--out', default=OUT_PATH)
    parser.add_argument('--allow-shrink', action='store_true',
                        help='write even if variants saved builds point at '
                             'would change ids')
    args = parser.parse_args()

    cursor = sqlite3.connect(DB_PATH).cursor()
    pets = cursor.execute(
        """
        SELECT i.ankama_id, i.name FROM items i
        JOIN item_types t ON t.id = i.type
        WHERE t.name = 'Pet' AND i.removed IS NOT 1 AND i.ankama_id IS NOT NULL
          AND i.ankama_type != 'mounts'  -- mounts share the Pet slot but live under /montures/
          -- store_touch_pet_bonuses.py writes the maxed variants back into this
          -- same table as pets, sharing the pet's ankama id. Without this the
          -- second run reads them as pets and writes "Mosk (+110 Agility)" as a
          -- pet of its own, feeding the file its own output.
          AND i.id < 200000000
        ORDER BY i.ankama_id
        """).fetchall()
    if args.limit:
        pets = pets[:args.limit]

    opener = build_opener()
    result = {}
    missing = []
    no_page = []
    from_english = []
    for ankama_id, name in pets:
        html, language = fetch(opener, BASE_URL % ankama_id), 'fr'
        if html is None:
            time.sleep(args.delay)
            html, language = fetch(opener, ENGLISH_URL % ankama_id), 'en'
            if html is not None:
                from_english.append(name)
        if html is None:
            no_page.append(name)
            time.sleep(args.delay)
            continue
        bonuses = parse_bonuses(html, language)
        if bonuses:
            result[name] = bonuses
        else:
            missing.append(name)
        time.sleep(args.delay)
    if from_english:
        print('read from the English page, the French one answers 404: %d, '
              'e.g. %s' % (len(from_english), ', '.join(from_english[:6])))
    if no_page:
        print('pets with no encyclopedia page in either language (404): %d, '
              'e.g. %s' % (len(no_page), ', '.join(no_page[:6])))

    for name, bonuses in OVERRIDES.items():
        result[name] = bonuses

    # The variants are numbered in file order and a saved build keeps the
    # number, so a pet that drops out or comes in, or a line added, removed or
    # reordered, renumbers every variant after it. Losing Moowitty on
    # 2026-08-15 moved 82 ids.
    if os.path.exists(args.out):
        with open(args.out, encoding='utf-8') as fh:
            previous = json.load(fh)
        db_pets, known = pets_in_db(cursor)
        moved = first_moved_line(previous, result, db_pets, known)
        if moved and not args.allow_shrink:
            for line in explain_refusal(previous, result, moved):
                print(line)
            return 1
        if not moved:
            for name, stat, before, after in changed_values(previous, result):
                print('cap changed, same variant: %s %s %s -> %s'
                      % (name, stat, before, after))

    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print('pets scraped: %d with bonuses, %d without an effects block -> %s'
          % (len(result), len(missing), args.out))
    if missing:
        print('no-bonus pets (gift/GM pets with datacenter stats, or truly none):')
        for name in missing[:20]:
            print('   -', name)
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    raise SystemExit(main())
