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

"""Build retro_set_bonuses.json from the Dofus Retro Tools API.

Set bonuses are not in the Ankama lang CDN (they are server-side), so no
first-hand source exists. Dofus Retro Tools expressly offers a JSON API
(/api/set-bonuses) keyed by the Ankama set id with the full per-piece-count
bonus table: per the site's data-sourcing policy an offered API beats
scraping a fan site's pages, so this replaced the earlier Solomonk page
scrape (2026-07-20). The API is credited on the About page.

The API mapping (codes -> internal stat names) lives in
store_retro_set_bonuses.py and is reused as-is; values are written with the
internal English stat names, which load_set_bonuses passes through.

Sets the API has no bonuses for fall back to the committed items_retro.db
(none today: the API covers all 171 bonus-carrying sets), so a rebuild can
never regress below what production already serves.

Usage (from the repo root):
    python itemscraper/get_retro_set_bonuses.py
"""

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(CURRENT_DIR.parent))
sys.path.insert(0, str(CURRENT_DIR.parent / 'fashionistapulp'))

RAW_DIR = CURRENT_DIR / 'retro_raw'
OUT_PATH = CURRENT_DIR / 'retro_set_bonuses.json'


def _db_fallbacks(missing_sets, items_root):
    """Entries from the committed items_retro.db for sets the API lacks."""
    import sqlite3
    db = (CURRENT_DIR.parent / 'fashionistapulp' / 'fashionistapulp'
          / 'items_retro.db')
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
    from store_retro_set_bonuses import fetch_api_records

    sets_root = json.loads(
        (RAW_DIR / 'itemsets_fr.json').read_text(encoding='utf-8'))['IS']
    items_root = json.loads(
        (RAW_DIR / 'items_fr.json').read_text(encoding='utf-8'))['I']['u']

    records = {r['ankama_id']: r for r in fetch_api_records()}
    print('fetched %d sets with bonuses from the Dofus Retro Tools API'
          % len(records))

    out = []
    missing = []
    for sid in sorted(sets_root, key=int):
        ankama_id = int(sid)
        sd = sets_root[sid]
        if not isinstance(sd, dict) or not sd.get('i'):
            continue
        record = records.get(ankama_id)
        if record is None:
            missing.append((sid, sd))
            continue
        max_pieces = max(int(p) for p in record['tiers'])
        bonus = [[] for _ in range(max_pieces)]
        for num_pieces, stats in record['tiers'].items():
            bonus[int(num_pieces) - 1] = [
                {'type': stat, 'value': str(value)}
                for stat, value in sorted(stats.items())]
        item_names = [items_root[str(i)].get('n') for i in sd['i']
                      if isinstance(items_root.get(str(i)), dict)]
        out.append({
            'ankama_id': ankama_id,
            'name': sd.get('n'),
            'items': [n for n in item_names if n],
            'bonus': bonus,
            'source': 'dofusretrotools',
        })

    fallbacks = _db_fallbacks(missing, items_root)
    out.extend(fallbacks)
    out.sort(key=lambda s: s['ankama_id'])
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    still_missing = ({int(sid) for sid, _sd in missing}
                     - {entry['ankama_id'] for entry in fallbacks})
    print('wrote %d sets to %s (%d from the API, %d committed-db, '
          '%d without bonuses anywhere: %s)'
          % (len(out), OUT_PATH, len(out) - len(fallbacks), len(fallbacks),
             len(still_missing), sorted(still_missing)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
