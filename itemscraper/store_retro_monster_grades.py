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

"""Store the 1.29 monster stats per grade into items_retro.db.

Source: the Solomonk bestiary (the same AJAX endpoint the Retro drops come
from; Ankama has no Retro encyclopedia). Every stat in a card carries its
five grades as data-rank-N attributes keyed by data-mobid, with unambiguous
icon classes: icon-vita/icon-pa/icon-pm for the characteristics, the level
in the Niv. span, icon-neutral/earth/fire/water/air percent resistances and
the icon-pa/icon-pm percent AP/MP loss dodges. Numbers are language-neutral
so the French pages are enough.

The endpoint now requires a prior visit to the search page in the same
session (it answers "Restricted access" otherwise; hardening added some
time after the drops scrape).

The table matches the other versions' monster_grades so the encyclopedia
renders the same section while every version keeps its own numbers.

Usage (from itemscraper/):
    python store_retro_monster_grades.py [--delay 0.5] [--max-pages N]
"""

import argparse
import http.cookiejar
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                       'items_retro.db')

BASE = 'https://solomonk.fr'
SEARCH_PAGE = BASE + '/fr/monstres/chercher'
AJAX = BASE + '/ajax/select_monster.php'
BATCH = 10  # the endpoint only honours Q=10
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
COLLAPSE = {
    'CS[bestiaryCollapseSpells]': 'true',
    'CS[bestiaryCollapseSubareas]': 'true',
    'CS[bestiaryCollapseDrops]': 'true',
    'CS[bestiaryCollapseDropsTemporis]': 'true',
}

RANKS_RE = r'((?:\s+data-rank-\d=-?\d+)+)'
LEVEL_RE = re.compile(r'Niv\.<span data-mobid=(\d+)' + RANKS_RE)
CHAR_RE = re.compile(
    r'<li class="icon-entity icon-(vita|pa|pm)" data-mobid=(\d+)' + RANKS_RE)
PCT_RE = re.compile(
    r'<li class="icon-entity icon-(neutral|earth|fire|water|air|pa|pm)">'
    r'<span data-mobid=(\d+)' + RANKS_RE)
RANK_VALUE_RE = re.compile(r'data-rank-(\d)=(-?\d+)')


def parse_ranks(blob):
    return {int(rank): int(value) for rank, value in RANK_VALUE_RE.findall(blob)}


def fetch_page(opener, offset):
    query = urllib.parse.urlencode(
        {'lang': 'fr', 'Q': BATCH, 'O': offset, 'T': 'all', **COLLAPSE})
    req = urllib.request.Request(AJAX + '?' + query, headers={
        'Referer': SEARCH_PAGE, 'X-Requested-With': 'XMLHttpRequest'})
    with opener.open(req, timeout=60) as resp:
        body = resp.read().decode('utf-8', 'replace')
    # The endpoint wraps the cards in {"html": "..."}: decode it so the
    # quotes are real quotes for the regexes (the raw body escapes them).
    try:
        body = json.loads(body).get('html', '')
    except ValueError:
        pass
    if 'card-solo-monster-title' not in body:
        return None
    return body


def collect(html, stats):
    for mobid, blob in LEVEL_RE.findall(html):
        stats.setdefault(int(mobid), {})['level'] = parse_ranks(blob)
    for icon, mobid, blob in CHAR_RE.findall(html):
        stats.setdefault(int(mobid), {})[icon] = parse_ranks(blob)
    for icon, mobid, blob in PCT_RE.findall(html):
        stats.setdefault(int(mobid), {})['pct_' + icon] = parse_ranks(blob)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay', type=float, default=0.5)
    parser.add_argument('--max-pages', type=int, default=200)
    args = parser.parse_args()

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [('User-Agent', USER_AGENT), ('Accept-Language', 'fr')]
    with opener.open(SEARCH_PAGE, timeout=60) as resp:
        resp.read()

    stats = {}
    page = 0
    empty_streak = 0
    while page < args.max_pages:
        html = fetch_page(opener, page * BATCH)
        if html is None:
            # Intermittent empty responses mid-crawl: retry the same page
            # before treating it as the end of the bestiary.
            empty_streak += 1
            if empty_streak > 2:
                break
            time.sleep(2.0)
            continue
        empty_streak = 0
        collect(html, stats)
        page += 1
        time.sleep(args.delay)
    print('collected stats for %d monsters over %d pages' % (len(stats), page))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    known_ids = {row[0] for row in cursor.execute(
        'SELECT DISTINCT monster_ankama_id FROM monster_names')}
    cursor.execute('DROP TABLE IF EXISTS monster_grades')
    cursor.execute(
        """
        CREATE TABLE monster_grades (
            monster_ankama_id INTEGER NOT NULL,
            grade INTEGER NOT NULL,
            level INTEGER,
            life_points INTEGER,
            action_points INTEGER,
            movement_points INTEGER,
            ap_dodge INTEGER,
            mp_dodge INTEGER,
            earth_resistance INTEGER,
            air_resistance INTEGER,
            fire_resistance INTEGER,
            water_resistance INTEGER,
            neutral_resistance INTEGER,
            PRIMARY KEY (monster_ankama_id, grade)
        )
        """)
    stored = matched = 0
    for mobid, per_stat in sorted(stats.items()):
        if mobid not in known_ids:
            continue
        matched += 1
        grades = set()
        for ranks in per_stat.values():
            grades.update(ranks)
        for grade in sorted(grades):
            def val(key):
                return per_stat.get(key, {}).get(grade)
            cursor.execute(
                'INSERT OR REPLACE INTO monster_grades VALUES '
                '(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (mobid, grade, val('level'), val('vita'), val('pa'),
                 val('pm'), val('pct_pa'), val('pct_pm'), val('pct_earth'),
                 val('pct_air'), val('pct_fire'), val('pct_water'),
                 val('pct_neutral')))
            stored += 1
    conn.commit()
    conn.close()
    print('stored %d grade rows for %d retro monsters' % (stored, matched))

    # Keep the retro dump in sync so a future pipeline load-db (which rebuilds
    # the db from the dump) does not drop the table (same as store_drops).
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(DB_PATH, 'retro')
    print('retro dump refreshed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
