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

Level, resistances and AP/MP dodges come from Ankama's lang CDN
(retro_raw/monsters_fr.json, category "monsters"), where each grade carries l
plus r = [mp dodge, ap dodge, air, water, fire, earth, neutral]. HP/AP/MP are
mostly server-side in 1.29: the lang carries lp/ap/mp for a small set of
monsters, the rest come from the Solomonk bestiary cards (credited on the About
page), keyed by data-mobid with icon-vita/icon-pa/icon-pm classes. The AJAX
endpoint answers "Restricted access" without a prior visit to the search page
in the same session.

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
    # The endpoint wraps the cards in {"html": "..."}, with the quotes escaped.
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

    # The raw is not committed: the pipeline's lang/download-fr step fetches it.
    lang_path = os.path.join(CURRENT_DIR, 'retro_raw', 'monsters_fr.json')
    lang_grades = {}
    if not os.path.exists(lang_path):
        print('WARNING: %s missing (run download_retro_langs.py with '
              '--categories monsters); falling back to Solomonk for every '
              'field' % lang_path)
    else:
        with open(lang_path, encoding='utf-8') as fh:
            for mid, entry in json.load(fh)['M'].items():
                if not isinstance(entry, dict):
                    continue
                grades = {}
                # Up to six grades; the monsters carrying a g6 are mostly bosses.
                for gnum in range(1, 7):
                    g = entry.get('g%d' % gnum)
                    if isinstance(g, dict) and 'r' in g and len(g['r']) >= 7:
                        r = g['r']
                        grades[gnum] = {
                            'level': g.get('l'),
                            'mp_dodge': r[0], 'ap_dodge': r[1],
                            'air': r[2], 'water': r[3], 'fire': r[4],
                            'earth': r[5], 'neutral': r[6],
                            # The lang has these for a few monsters only;
                            # None means "ask Solomonk".
                            'lp': g.get('lp'), 'ap': g.get('ap'),
                            'mp': g.get('mp'),
                        }
                if grades:
                    lang_grades[int(mid)] = grades

    stats = {}
    page = 0
    empty_streak = 0
    while page < args.max_pages:
        html = fetch_page(opener, page * BATCH)
        if html is None:
            # The endpoint answers empty intermittently mid-crawl.
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
    official_hp = disagreements = empty = 0
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
            official = lang_grades.get(mobid, {}).get(grade)
            if official is not None:
                hp_ap_mp = []
                for lang_key, solomonk_key in (('lp', 'vita'), ('ap', 'pa'),
                                               ('mp', 'pm')):
                    lang_value = official.get(lang_key)
                    solomonk_value = val(solomonk_key)
                    if lang_value is None:
                        hp_ap_mp.append(solomonk_value)
                        continue
                    official_hp += 1
                    hp_ap_mp.append(lang_value)
                    if (solomonk_value is not None
                            and solomonk_value != lang_value):
                        disagreements += 1
                        print('  overlap mismatch: monster %d grade %d %s: '
                              'lang %s vs solomonk %s'
                              % (mobid, grade, lang_key, lang_value,
                                 solomonk_value))
                row = (mobid, grade, official['level'], hp_ap_mp[0],
                       hp_ap_mp[1], hp_ap_mp[2], official['ap_dodge'],
                       official['mp_dodge'], official['earth'],
                       official['air'], official['fire'], official['water'],
                       official['neutral'])
            else:
                row = (mobid, grade, val('level'), val('vita'), val('pa'),
                       val('pm'), val('pct_pa'), val('pct_pm'),
                       val('pct_earth'), val('pct_air'), val('pct_fire'),
                       val('pct_water'), val('pct_neutral'))
            # The grade set is the union over every stat, so a grade that only
            # `level` knows about produced a row with no life points. Tofu Royal
            # ended up with a sixth grade at 0 hp, which dragged its published
            # range down to 0-5000 instead of 4600-5000. A row we cannot fill
            # is worse than no row.
            if not row[2] or not row[3]:
                empty += 1
                continue
            # A negative AP or MP is the client's way of saying a creature does
            # not move, not a value a player ever sees. Store the absence and
            # let the page print a dash.
            row = list(row)
            for i in (4, 5):
                if row[i] is not None and row[i] < 0:
                    row[i] = None
            cursor.execute(
                'INSERT OR REPLACE INTO monster_grades VALUES '
                '(?,?,?,?,?,?,?,?,?,?,?,?,?)', row)
            stored += 1
    conn.commit()
    conn.close()
    print('stored %d grade rows for %d retro monsters '
          '(%d dropped: no level or life points)' % (stored, matched, empty))

    # The pipeline's load-db rebuilds the db from the dump.
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(DB_PATH, 'retro')
    print('retro dump refreshed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
