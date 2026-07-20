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

"""Scrape the Retro set bonuses from Solomonk into retro_set_bonuses.json.

Set bonuses are not in the Ankama lang CDN (they are server-side), so the
pipeline used to rely on a community snapshot frozen at 1.29 (108 sets while
live Retro has 178). Solomonk follows the live game and serves every set at
/fr/panoplie/<ankama id>/<slug> (the slug is ignored), with one tab pane per
piece-count tier:

    <a href="#is<ID>-<k>">N objets</a> ...
    <div class="col tab-pane" id="is<ID>-<k>">
      <u>Bonus de la panoplie</u><ul class="list-unstyled"><li>+5 en force</li>...

Tier values are the TOTAL bonus at that piece count (verified against the
Gobball set), which is exactly the semantics load_set_bonuses expects. The
last pane also carries a second "Bonus total" column: only the first list of
each pane is read. The site requires a session-priming visit first.

Set ids, names and member items come from the committed lang raws so the
output matches the pipeline's own set list; the page only supplies bonuses.

Usage (from the repo root):
    python itemscraper/get_retro_set_bonuses.py [--delay 0.4] [--only-id N]
"""

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent / 'retro_raw'
OUT_PATH = Path(__file__).resolve().parent / 'retro_set_bonuses.json'

BASE = 'https://solomonk.fr'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

TAB_RE = re.compile(r'href="#is\d+-(\d+)"[^>]*>\s*(\d+)\s*objets?')
PANE_RE = re.compile(
    r'id="is\d+-(\d+)"[^>]*>.*?Bonus de la panoplie</u>'
    r'<ul class="list-unstyled">(.*?)</ul>', re.S)
LI_RE = re.compile(r'<li>(.*?)</li>', re.S)
VALUE_RE = re.compile(r'^\+?(-?\d+)\s*(%?)\s*(.*)$')
PREPOSITION_RE = re.compile(r"^(?:en|de|d'|du|des|aux|au|a|la|le|les)\s+",
                            re.I)


def parse_bonus_line(text):
    """'+5 en force' -> ('force', '5'); '+1 PA' -> ('PA', '1');
    '+5% de resistance terre' -> ('% resistance terre', '5')."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    m = VALUE_RE.match(text)
    if not m:
        m = re.match(r'^Renvoie\s+(\d+)\s+dommages?', text, re.I)
        if m:
            return 'renvoie', m.group(1)
        m = re.match(r'^Augmente les dommages de (\d+)\s*%', text, re.I)
        if m:
            return '% dommages', m.group(1)
        return None
    value, pct, label = m.groups()
    label = label.strip()
    while True:
        stripped = PREPOSITION_RE.sub('', label)
        if stripped == label:
            break
        label = stripped
    if pct:
        label = '% ' + label
    return (label, value) if label else None


def fetch_set_bonuses(opener, ankama_id, retries=2):
    url = '%s/fr/panoplie/%d/x' % (BASE, ankama_id)
    pieces_by_tab = {}
    for attempt in range(retries + 1):
        with opener.open(url, timeout=30) as resp:
            html = resp.read().decode('utf-8', 'replace')
        pieces_by_tab = {int(k): int(n) for k, n in TAB_RE.findall(html)}
        if pieces_by_tab:
            break
        # The site intermittently serves the page without the bonus block
        # during a long crawl: back off and retry before giving up.
        time.sleep(2.0)
    if not pieces_by_tab:
        return None
    tiers = {}
    for k, blob in PANE_RE.findall(html):
        num_pieces = pieces_by_tab.get(int(k))
        if not num_pieces:
            continue
        lines = []
        for li in LI_RE.findall(blob):
            parsed = parse_bonus_line(li)
            if parsed:
                lines.append({'type': parsed[0], 'value': parsed[1]})
            else:
                print('  unparsed bonus line on set %d: %s'
                      % (ankama_id, li.strip()[:60]))
        if lines:
            tiers[num_pieces] = lines
    if not tiers:
        return None
    bonus = [[] for _ in range(max(tiers))]
    for num_pieces, lines in tiers.items():
        bonus[num_pieces - 1] = lines
    return bonus


def _legacy_fallbacks(missing_sets, items_root):
    """Entries from the previous snapshot for sets Solomonk has no bonus
    block for (matched by member-item overlap, the legacy format has no
    ids). Keeps the pipeline from regressing below what it already had."""
    import subprocess
    try:
        legacy = json.loads(subprocess.run(
            ['git', 'show', 'HEAD:itemscraper/retro_set_bonuses.json'],
            capture_output=True, text=True, encoding='utf-8',
            cwd=str(Path(__file__).resolve().parent.parent)).stdout or '[]')
    except (ValueError, OSError):
        return []
    out = []
    for sid, sd in missing_sets:
        wanted = {items_root[str(i)].get('n') for i in sd.get('i', [])
                  if isinstance(items_root.get(str(i)), dict)}
        wanted.discard(None)
        best, best_overlap = None, 0
        for entry in legacy:
            overlap = len(wanted & set(entry.get('items', ())))
            if overlap > best_overlap:
                best, best_overlap = entry, overlap
        if best is not None and best_overlap >= 2:
            out.append({
                'ankama_id': int(sid),
                'name': sd.get('n'),
                'items': sorted(wanted),
                'bonus': best.get('bonus', []),
                'source': 'legacy-1.29',
            })
    return out


def _db_fallbacks(missing_sets, items_root):
    """Entries from the committed items_retro.db for sets neither Solomonk
    nor the legacy snapshot covers (~28 event sets: Gato, Cigale...). Their
    origin predates this scraper and no scrapable source is known, so the
    committed values are carried forward instead of being dropped. Types are
    English stat names (passed through by _map_set_stat)."""
    import sqlite3
    db = (Path(__file__).resolve().parent.parent / 'fashionistapulp'
          / 'fashionistapulp' / 'items_retro.db')
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    out = []
    for sid, sd in missing_sets:
        rows = conn.execute(
            """SELECT b.num_pieces_used, st.name, b.value
               FROM set_bonus b
               JOIN sets s ON s.id = b.item_set
               JOIN stats st ON st.id = b.stat
               WHERE s.ankama_id = ?""", (int(sid),)).fetchall()
        if not rows:
            continue
        tiers = {}
        for num_pieces, stat, value in rows:
            tiers.setdefault(num_pieces, []).append(
                {'type': stat, 'value': str(value)})
        bonus = [[] for _ in range(max(tiers))]
        for num_pieces, lines in tiers.items():
            bonus[num_pieces - 1] = lines
        item_names = [items_root[str(i)].get('n') for i in sd.get('i', [])
                      if isinstance(items_root.get(str(i)), dict)]
        out.append({
            'ankama_id': int(sid),
            'name': sd.get('n'),
            'items': [n for n in item_names if n],
            'bonus': bonus,
            'source': 'committed-db',
        })
    conn.close()
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay', type=float, default=0.4)
    parser.add_argument('--only-id', type=int, default=None)
    args = parser.parse_args()

    sets_root = json.loads(
        (RAW_DIR / 'itemsets_fr.json').read_text(encoding='utf-8'))['IS']
    items_root = json.loads(
        (RAW_DIR / 'items_fr.json').read_text(encoding='utf-8'))['I']['u']

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [('User-Agent', USER_AGENT), ('Accept-Language', 'fr')]
    with opener.open(BASE + '/fr/', timeout=30) as resp:
        resp.read()

    out = []
    missing = []
    for sid in sorted(sets_root, key=int):
        ankama_id = int(sid)
        if args.only_id is not None and ankama_id != args.only_id:
            continue
        sd = sets_root[sid]
        if not isinstance(sd, dict) or not sd.get('i'):
            continue
        try:
            bonus = fetch_set_bonuses(opener, ankama_id)
        except Exception as exc:
            print('set %d: ERROR %s' % (ankama_id, exc))
            missing.append((sid, sd))
            continue
        time.sleep(args.delay)
        if bonus is None:
            print('set %d %s: no bonuses found' % (ankama_id, sd.get('n')))
            missing.append((sid, sd))
            continue
        item_names = [items_root[str(i)].get('n') for i in sd['i']
                      if isinstance(items_root.get(str(i)), dict)]
        out.append({
            'ankama_id': ankama_id,
            'name': sd.get('n'),
            'items': [n for n in item_names if n],
            'bonus': bonus,
            'source': 'solomonk',
        })

    if args.only_id is not None:
        print(json.dumps(out, ensure_ascii=False, indent=1)[:2000])
        return 0

    legacy = _legacy_fallbacks(missing, items_root)
    covered = {entry['ankama_id'] for entry in legacy}
    still = [(sid, sd) for sid, sd in missing if int(sid) not in covered]
    from_db = _db_fallbacks(still, items_root)
    out.extend(legacy)
    out.extend(from_db)
    out.sort(key=lambda s: s['ankama_id'])
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    still_missing = ({int(sid) for sid, _sd in missing} - covered
                     - {entry['ankama_id'] for entry in from_db})
    print('wrote %d sets with bonuses to %s (%d solomonk, %d legacy, '
          '%d committed-db, %d without: %s)'
          % (len(out), OUT_PATH, len(out) - len(legacy) - len(from_db),
             len(legacy), len(from_db), len(still_missing),
             sorted(still_missing)[:20]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
