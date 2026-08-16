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
Pages accept bare ids: /fr/mmorpg/encyclopedie/familiers/<ankama_id>.

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
# scrape (same mechanism as retro's OVERRIDES).
OVERRIDES = {
    # Moowitty is still a Touch pet (ankama 13000, type Pet in items_touch.db)
    # but its encyclopedia page answers 404 since 2026-08-15 and the site search
    # returns nothing for the name. These are the values this same scrape read
    # on 2026-07-09, the last day the page existed.
    'Moowitty': [['Prospecting', 53], ['Wisdom', 98]],
}

_PCT_RESIST_RE = re.compile(
    r'^(\d+)\s*%\s*R[ée]sistance\s+(Air|Eau|Feu|Terre|Neutre)$', re.I)
_LIN_RESIST_RE = re.compile(
    r'^(\d+)\s*R[ée]sistance\s+(Air|Eau|Feu|Terre|Neutre)$', re.I)
_ELEM_DAMAGE_RE = re.compile(
    r'^(\d+)\s*Dommages?\s+(Air|Eau|Feu|Terre|Neutre)$', re.I)
_PCT_DAMAGE_RE = re.compile(r'^(\d+)\s*%\s*Dommages?$', re.I)
_SIMPLE_RE = re.compile(r'^(\d+)\s+([A-Za-zàâçéèêëîïôûù]+)$')

_STOP_LINES = ('régime alimentaire', 'description', 'caractéristiques')


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


def parse_bonuses(html):
    """Extract [(stat, max)] from the 'Effets maximum' block, ignoring the
    hormone-dropper line and stopping at the diet section (whose '+1 Soins'
    feeding rewards must not be mistaken for caps)."""
    lines = _page_lines(html)
    start = None
    for i, line in enumerate(lines):
        if _norm(line).startswith('effets maximum'):
            start = i + 1
            break
    if start is None:
        return []

    bonuses = []
    seen = set()
    for line in lines[start:]:
        low = _norm(line)
        if any(low.startswith(stop) for stop in _STOP_LINES):
            break

        stat = None
        value = None
        m = _PCT_RESIST_RE.match(line)
        if m:
            value, stat = int(m.group(1)), '%% %s Resist' % ELEMENTS[_norm(m.group(2))]
            stat = stat.replace('%%', '%')
        if stat is None:
            m = _LIN_RESIST_RE.match(line)
            if m:
                value, stat = int(m.group(1)), '%s Resist' % ELEMENTS[_norm(m.group(2))]
        if stat is None:
            m = _ELEM_DAMAGE_RE.match(line)
            if m:
                value, stat = int(m.group(1)), '%s Damage' % ELEMENTS[_norm(m.group(2))]
        if stat is None:
            m = _PCT_DAMAGE_RE.match(line)
            if m:
                value, stat = int(m.group(1)), 'Power'
        if stat is None:
            m = _SIMPLE_RE.match(line)
            if m and _norm(m.group(2)) in SIMPLE_STATS:
                value, stat = int(m.group(1)), SIMPLE_STATS[_norm(m.group(2))]

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delay', type=float, default=0.25)
    parser.add_argument('--limit', type=int, default=0,
                        help='only scrape the first N pets (debug)')
    parser.add_argument('--out', default=OUT_PATH)
    parser.add_argument('--allow-shrink', action='store_true',
                        help='write even if pets the file already had are gone')
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
    for ankama_id, name in pets:
        html = fetch(opener, BASE_URL % ankama_id)
        if html is None:
            no_page.append(name)
            time.sleep(args.delay)
            continue
        bonuses = parse_bonuses(html)
        if bonuses:
            result[name] = bonuses
        else:
            missing.append(name)
        time.sleep(args.delay)
    if no_page:
        print('pets with no encyclopedia page (404): %d, e.g. %s'
              % (len(no_page), ', '.join(no_page[:6])))

    for name, bonuses in OVERRIDES.items():
        result[name] = bonuses

    # A pet that drops out of this file drops its variants, and the variants are
    # numbered in file order: losing one renumbers every pet after it, and a
    # saved build keeps the number. Losing Moowitty on 2026-08-15 moved 82 ids.
    if os.path.exists(args.out):
        with open(args.out, encoding='utf-8') as fh:
            lost = sorted(set(json.load(fh)) - set(result))
        if lost and not args.allow_shrink:
            print('the scrape lost %d pet(s) the file already had: %s'
                  % (len(lost), ', '.join(lost)))
            print('nothing written. Add them to OVERRIDES, or pass '
                  '--allow-shrink if the game really dropped them.')
            return 1

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
