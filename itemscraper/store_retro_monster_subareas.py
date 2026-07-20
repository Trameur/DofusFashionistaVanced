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

"""Store where each Retro monster can be found into items_retro.db.

Source: the same Solomonk bestiary cards the drops and grades come from.
Each card carries a "Sous-zones" block whose id encodes the monster id:

    <div ... id="collapse-<mobid>-1" data-collapse-target="bestiaryCollapseSubareas">
      <div ...><a ...>Port de Madrestam</a>, <a ...>...</a></div>

The card list is language-aware, so the subarea names are pulled for every
language the site serves. The endpoint needs a prior same-session visit to
the search page and intermittently serves empty pages mid-crawl (only a few
consecutive empties mean the real end).

Usage (from itemscraper/):
    python store_retro_monster_subareas.py [--delay 0.5] [--max-pages N]
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
AJAX = BASE + '/ajax/select_monster.php'
BATCH = 10  # the endpoint only honours Q=10
LANGUAGES = ('fr', 'en', 'es')  # the languages Solomonk serves
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
COLLAPSE = {
    'CS[bestiaryCollapseSpells]': 'true',
    'CS[bestiaryCollapseDrops]': 'true',
    'CS[bestiaryCollapseDropsTemporis]': 'true',
}

SUBAREA_BLOCK_RE = re.compile(
    r'id="collapse-(\d+)-1"[^>]*data-collapse-target="bestiaryCollapseSubareas"'
    r'[^>]*>\s*<div[^>]*>(.*?)</div>', re.S)
LINK_RE = re.compile(r'<a[^>]*>([^<]+)</a>')


def fetch_page(opener, lang, offset):
    query = urllib.parse.urlencode(
        {'lang': lang, 'Q': BATCH, 'O': offset, 'T': 'all', **COLLAPSE})
    req = urllib.request.Request(AJAX + '?' + query, headers={
        'Referer': BASE + '/%s/monstres/chercher' % lang,
        'X-Requested-With': 'XMLHttpRequest'})
    with opener.open(req, timeout=60) as resp:
        body = resp.read().decode('utf-8', 'replace')
    try:
        body = json.loads(body).get('html', '')
    except ValueError:
        pass
    if 'card-solo-monster-title' not in body:
        return None
    return body


def crawl_language(opener, lang, delay, max_pages):
    """{mobid: [subarea names]} for one language."""
    subareas = {}
    page = 0
    empty_streak = 0
    while page < max_pages:
        html = fetch_page(opener, lang, page * BATCH)
        if html is None:
            empty_streak += 1
            if empty_streak > 2:
                break
            time.sleep(2.0)
            continue
        empty_streak = 0
        for mobid, blob in SUBAREA_BLOCK_RE.findall(html):
            names = [name.strip() for name in LINK_RE.findall(blob)
                     if name.strip()]
            if names:
                subareas[int(mobid)] = names
        page += 1
        time.sleep(delay)
    return subareas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay', type=float, default=0.5)
    parser.add_argument('--max-pages', type=int, default=200)
    args = parser.parse_args()

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [('User-Agent', USER_AGENT), ('Accept-Language', 'fr')]
    with opener.open(BASE + '/fr/monstres/chercher', timeout=60) as resp:
        resp.read()

    per_language = {}
    for lang in LANGUAGES:
        per_language[lang] = crawl_language(opener, lang, args.delay,
                                            args.max_pages)
        print('%s: subareas for %d monsters' % (lang, len(per_language[lang])))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    known_ids = {row[0] for row in cursor.execute(
        'SELECT DISTINCT monster_ankama_id FROM monster_names')}
    cursor.execute('DROP TABLE IF EXISTS monster_subareas')
    cursor.execute(
        """
        CREATE TABLE monster_subareas (
            monster_ankama_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            position INTEGER NOT NULL,
            name TEXT NOT NULL,
            PRIMARY KEY (monster_ankama_id, language, position)
        )
        """)
    stored = 0
    matched = set()
    for lang, subareas in per_language.items():
        for mobid, names in subareas.items():
            if mobid not in known_ids:
                continue
            matched.add(mobid)
            for position, name in enumerate(names):
                cursor.execute(
                    'INSERT OR REPLACE INTO monster_subareas VALUES (?,?,?,?)',
                    (mobid, lang, position, name))
                stored += 1
    conn.commit()
    conn.close()
    print('stored %d subarea rows for %d retro monsters' % (stored, len(matched)))

    # Keep the retro dump in sync so a future pipeline load-db does not drop
    # the table (same as the drops and grades stores).
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(DB_PATH, 'retro')
    print('retro dump refreshed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
