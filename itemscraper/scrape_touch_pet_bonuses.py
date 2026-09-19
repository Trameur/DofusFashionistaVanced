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
    'puissance': 'Power', 'pa': 'AP', 'pm': 'MP', 'fuite': 'Dodge',
    'tacle': 'Lock', 'esquive pa': 'AP Loss Resist',
    'esquive pm': 'MP Loss Resist', 'dommages critiques': 'Critical Damage',
    'resistance critiques': 'Critical Resist',
    'resistance critique': 'Critical Resist',
    'dommages poussee': 'Pushback Damage',
    'resistance poussee': 'Pushback Resist',
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
_SIMPLE_RE = re.compile(
    r'^(\d+)\s+([A-Za-zàâçéèêëîïôûù][A-Za-zàâçéèêëîïôûù ]*)$')

# Compared after _norm, so written without accents: until 2026-09-18 they had
# them, never matched, and the reader kept the gain per meal listed under
# "Régime alimentaire" ("1 Prospection") as a cap, on 76 pets. A pet with no
# diet ends at the page footer or at the recipes that use it.
_STOP_LINES = ('regime alimentaire', 'est utilise pour', 'partager',
               'description', 'caracteristiques')

ENGLISH_ELEMENTS = {'air': 'Air', 'water': 'Water', 'fire': 'Fire',
                    'earth': 'Earth', 'neutral': 'Neutral'}
ENGLISH_SIMPLE_STATS = {
    'strength': 'Strength', 'intelligence': 'Intelligence', 'chance': 'Chance',
    'agility': 'Agility', 'vitality': 'Vitality', 'wisdom': 'Wisdom',
    'prospecting': 'Prospecting', 'initiative': 'Initiative', 'heals': 'Heals',
    'damage': 'Damage', 'pods': 'Pods', 'pod': 'Pods',
    'power': 'Power', 'ap': 'AP', 'mp': 'MP', 'dodge': 'Dodge',
    'lock': 'Lock', 'ap parry': 'AP Loss Resist', 'mp parry': 'MP Loss Resist',
    'critical damage': 'Critical Damage',
    'critical resistance': 'Critical Resist',
    'pushback damage': 'Pushback Damage',
    'pushback resistance': 'Pushback Resist',
}
_EN_PCT_RESIST_RE = re.compile(
    r'^(\d+)\s*%\s*(Air|Water|Fire|Earth|Neutral)\s+Resistance$', re.I)
_EN_LIN_RESIST_RE = re.compile(
    r'^(\d+)\s*(Air|Water|Fire|Earth|Neutral)\s+Resistance$', re.I)
_EN_ELEM_DAMAGE_RE = re.compile(
    r'^(\d+)\s*(Air|Water|Fire|Earth|Neutral)\s+Damages?$', re.I)
_EN_PCT_DAMAGE_RE = re.compile(r'^(\d+)\s*%\s*Damages?$', re.I)
_EN_SIMPLE_RE = re.compile(r'^(\d+)\s+([A-Za-z][A-Za-z ]*)$')

_EN_STOP_LINES = ('diet', 'used to craft', 'share', 'description',
                  'characteristics')


def _norm(text):
    text = text.lower()
    for src, dst in (('à', 'a'), ('â', 'a'), ('é', 'e'), ('è', 'e'), ('ê', 'e'),
                     ('ë', 'e'), ('î', 'i'), ('ï', 'i'), ('ô', 'o'), ('û', 'u'),
                     ('ù', 'u'), ('ç', 'c')):
        text = text.replace(src, dst)
    return text.strip()


def _words(text):
    return ' '.join(_norm(text).split())


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
    if m and _words(m.group(2)) in SIMPLE_STATS:
        return SIMPLE_STATS[_words(m.group(2))], int(m.group(1))
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
    if m and _words(m.group(2)) in ENGLISH_SIMPLE_STATS:
        return ENGLISH_SIMPLE_STATS[_words(m.group(2))], int(m.group(1))
    return None, None


# language: (first words of the block's title, lines that end it, line reader)
_READERS = {
    'fr': ('effets maximum', _STOP_LINES, _french_line),
    'en': ('max effects', _EN_STOP_LINES, _english_line),
}


def parse_bonuses(html, language='fr'):
    """Extract [(stat, max)] from the block under 'Effets maximum' ('Max
    effects' in English), up to the diet. The hormone-dropper line matches no
    stat."""
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
               WHERE t.name = 'Pet' AND i.id < 200000000
               AND i.ankama_type != 'mounts' ORDER BY i.id""").fetchall():
        pets.setdefault(name, []).append(set(cursor.execute(
            """SELECT s.name, v.value FROM stats_of_item v
               JOIN stats s ON s.id = v.stat WHERE v.item = ?""", (item_id,))))
    return pets, known


def _best(lines):
    """{stat: highest value}: one variant per pet and stat, at its cap."""
    best = {}
    for stat, value in lines:
        best[stat] = max(int(value), best.get(stat, int(value)))
    return best


def variant_keys(bonuses, pets=None, known=None):
    """{(pet, stat)} store_touch_pet_bonuses.py writes a variant for: one per
    stat of each pet, except a stat it does not know, a cap the pet already
    carries as a stat of its own and a pet the db lacks. Without the db, one
    per stat. The variant's id comes from the pet and the stat alone."""
    keys = set()
    for name, lines in bonuses.items():
        for carried in ([set()] if pets is None else pets.get(name, [])):
            for stat, value in _best(lines).items():
                if known is not None and stat not in known:
                    continue
                if (stat, value) in carried:
                    continue
                keys.add((name, stat))
    return keys


def lost_variants(previous, current, pets=None, known=None):
    """[(pet, stat)] the previous file gave a variant and the current one does
    not. A pet or a line that comes in moves no id; one that goes takes a
    variant saved builds may wear back to the bare pet."""
    return sorted(variant_keys(previous, pets, known)
                  - variant_keys(current, pets, known))


def changed_values(previous, current):
    """(pet, stat, before, after) for the caps that moved: the variant keeps
    its id and saved builds get the new value."""
    changes = []
    for name in sorted(set(previous) & set(current)):
        before, after = _best(previous[name]), _best(current[name])
        for stat in before:
            if stat in after and before[stat] != after[stat]:
                changes.append((name, stat, before[stat], after[stat]))
    return changes


def explain_refusal(previous, current, lost):
    """The lines a human needs to decide on a refused write."""
    gone = sorted(set(previous) - set(current))
    lines = []
    if gone:
        lines.append('the scrape lost %d pet(s) the file already had: %s'
                     % (len(gone), ', '.join(gone)))
    lines.append('variants that would disappear: %s' % ', '.join(
        '%s (%s)' % key for key in lost))
    lines.append('a saved build wearing one of them would get the bare pet.')
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
                        help='write even if variants saved builds may wear '
                             'would disappear')
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

    if os.path.exists(args.out):
        with open(args.out, encoding='utf-8') as fh:
            previous = json.load(fh)
        db_pets, known = pets_in_db(cursor)
        lost = lost_variants(previous, result, db_pets, known)
        if lost and not args.allow_shrink:
            for line in explain_refusal(previous, result, lost):
                print(line)
            return 1
        for name, stat, before, after in changed_values(previous, result):
            print('cap changed, same variant: %s %s %s -> %s'
                  % (name, stat, before, after))
        added = sorted(variant_keys(result, db_pets, known)
                       - variant_keys(previous, db_pets, known))
        if added:
            print('new variants: %d, e.g. %s' % (len(added), ', '.join(
                '%s (%s)' % key for key in added[:6])))

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
