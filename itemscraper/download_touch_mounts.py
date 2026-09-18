#!/usr/bin/env python3
"""
Fetch Dofus Touch mounts (Dragodindes) with their stats.

Touch's data backend has the mount catalogue (the Mounts table: id + localized
names) but not the stats, a mount's effects are server-side, derived from its
breeding, so they're never in the static data. The official Touch encyclopedia
does publish each mount's effects, so we take the names from the backend and the
effects from the encyclopedia and join them on the mount id (they share Ankama's
ids).

  names   : POST <dataUrl>/data/map {"class":"Mounts","lang":<lang>}
  effects : https://www.dofus-touch.com/en/mmorpg/encyclopedia/mounts/<id>

Output: touch_raw/mounts.json -> [{ankama_id, name_<lang>, level, stats:[[v,v,Stat]]}]
get_equipments_touch.py turns these into Pet-slot mount records.

A 404 means Ankama publishes no page for that id (75, 91 and 99 on 2026-09-18,
in English, French and Spanish alike).
Any other error is retried, then stops the run with nothing written, and so does
a scrape that would drop a mount the file already holds, unless --allow-shrink.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

LANGS = ['en', 'fr', 'es', 'pt', 'de']
CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json"
FALLBACK_DATA_URL = "https://dt-proxy-production-login.ankama-games.com"
ENCY_URL = "https://www.dofus-touch.com/en/mmorpg/encyclopedia/mounts/%s"
BACKEND_UA = "Dofus/2 CFNetwork"
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# Touch encyclopedia effect label -> internal stat name (STAT_NAME_TO_KEY). Covers
# the labels seen across all mounts plus the obvious others in case Ankama adds them.
STAT_MAP = {
    'Vitality': 'Vitality', 'Wisdom': 'Wisdom', 'Strength': 'Strength',
    'Intelligence': 'Intelligence', 'Chance': 'Chance', 'Agility': 'Agility',
    'Power': 'Power', 'AP': 'AP', 'MP': 'MP', 'Range': 'Range', 'Summons': 'Summon',
    'Initiative': 'Initiative', 'Prospecting': 'Prospecting', 'Heals': 'Heals',
    'Damage': 'Damage', 'Pods': 'Pods', '% Critical Hits': 'Critical Hits',
    'Pushback Damage': 'Pushback Damage', 'Critical Resistance': 'Critical Resist',
    'Pushback Resistance': 'Pushback Resist',
    '% Earth Resistance': '% Earth Resist', '% Fire Resistance': '% Fire Resist',
    '% Water Resistance': '% Water Resist', '% Air Resistance': '% Air Resist',
    '% Neutral Resistance': '% Neutral Resist',
    'Earth Resistance': 'Earth Resist', 'Fire Resistance': 'Fire Resist',
    'Water Resistance': 'Water Resist', 'Air Resistance': 'Air Resist',
    'Neutral Resistance': 'Neutral Resist',
}


def resolve_data_url() -> str:
    try:
        cfg = requests.get(CONFIG_URL + '?lang=fr', headers={'User-Agent': BACKEND_UA},
                           timeout=30).json()
        return (cfg.get('dataUrl') or FALLBACK_DATA_URL).rstrip('/')
    except Exception:
        return FALLBACK_DATA_URL


def fetch_mount_catalogue(data_url: str):
    """From the backend Mounts table: names per language and the look string
    (used to render the mount image from the Touch CDN)."""
    names, looks = {}, {}
    for lang in LANGS:
        table = requests.post(f"{data_url}/data/map", json={'class': 'Mounts', 'lang': lang},
                              headers={'User-Agent': BACKEND_UA, 'Accept': 'application/json'},
                              timeout=120).json()
        for mid, rec in table.items():
            if isinstance(rec, dict) and rec.get('nameId'):
                names.setdefault(mid, {})[lang] = rec['nameId']
            if lang == 'en' and isinstance(rec, dict) and rec.get('look'):
                looks[mid] = rec['look']
    return names, looks


def parse_effects(html: str):
    """The encyclopedia "Effects" panel lists each bonus as a clean
    `<div class="ak-title">N Stat</div>`; the "Characteristics" panel uses a
    `Label: <span>value</span>` shape, so anything with a tag or ':' is skipped."""
    out = []
    for raw in re.findall(r'<div class="ak-title">(.*?)</div>', html, re.S):
        if '<' in raw or ':' in raw:
            continue
        text = re.sub(r'\s+', ' ', raw).strip()
        m = re.match(r'^(-?\d+)\s*(%?\s*.+)$', text)
        if not m:
            continue
        value = int(m.group(1))
        label = re.sub(r'\s+', ' ', m.group(2)).strip()
        stat = STAT_MAP.get(label)
        if stat:
            out.append([value, value, stat])
    return out


def make_session():
    session = requests.Session()
    session.headers.update({'User-Agent': WEB_UA})
    return session


def fetch(session, url, retries=2, timeout=30):
    """Return the page html, or None when Ankama publishes no page for this id
    (404). Anything else is retried, then raised."""
    last = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            last = exc
            if attempt < retries:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"fetch failed for {url}: {last}")


def lost_mounts(previous, current):
    """[(ankama_id, name_en)] of the mounts `previous` holds and `current` does
    not: a saved build wearing one would lose its mount slot in silence."""
    kept = {m['ankama_id'] for m in current}
    return sorted((m['ankama_id'], m.get('name_en')) for m in previous
                  if m['ankama_id'] not in kept)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dest', default='itemscraper/touch_raw')
    parser.add_argument('--delay', type=float, default=0.15, help='Seconds between page fetches')
    parser.add_argument('--allow-shrink', action='store_true',
                        help='write even if mounts the file already had are gone')
    args = parser.parse_args(argv)

    data_url = resolve_data_url()
    print(f"Dofus Touch data proxy: {data_url}")
    names, looks = fetch_mount_catalogue(data_url)
    print(f"  {len(names)} mounts in the backend catalogue")

    session = make_session()

    mounts = []
    no_stats = 0
    unpublished = []
    unknown = set()
    for mid, by_lang in sorted(names.items(), key=lambda kv: int(kv[0])):
        try:
            html = fetch(session, ENCY_URL % mid)
        except RuntimeError as exc:
            print(f"  ! mount {mid}: {exc}", file=sys.stderr)
            print("nothing written.", file=sys.stderr)
            return 1
        if html is None:
            unpublished.append(mid)
            time.sleep(args.delay)
            continue
        # collect labels we couldn't map, to surface gaps
        for raw in re.findall(r'<div class="ak-title">(.*?)</div>', html, re.S):
            if '<' in raw or ':' in raw:
                continue
            mm = re.match(r'^-?\d+\s*(%?\s*.+)$', re.sub(r'\s+', ' ', raw).strip())
            if mm and re.sub(r'\s+', ' ', mm.group(1)).strip() not in STAT_MAP \
                    and not mm.group(1).strip().isdigit():
                unknown.add(re.sub(r'\s+', ' ', mm.group(1)).strip())

        stats = parse_effects(html)
        if not stats:
            no_stats += 1
            continue
        name_en = by_lang.get('en') or next(iter(by_lang.values()), 'Mount %s' % mid)
        mounts.append({
            'ankama_id': int(mid),
            'ankama_type': 'mounts',
            'name_en': name_en,
            'name_fr': by_lang.get('fr') or name_en,
            'name_es': by_lang.get('es') or name_en,
            'name_pt': by_lang.get('pt') or name_en,
            'name_de': by_lang.get('de') or name_en,
            'level': 60,
            'stats': stats,
            'look': looks.get(mid),
        })
        time.sleep(args.delay)
    if unpublished:
        print(f"  not published by Ankama (404), no stats to read: mounts "
              f"{', '.join(unpublished)}")

    dest = Path(args.dest)
    out = dest / 'mounts.json'
    if out.exists() and not args.allow_shrink:
        lost = lost_mounts(json.loads(out.read_text(encoding='utf-8')), mounts)
        if lost:
            print(f"the scrape lost {len(lost)} mount(s) mounts.json already had: "
                  + ', '.join(f"{name} ({mid})" for mid, name in lost))
            print("nothing written. Pass --allow-shrink if Ankama really dropped them.")
            return 1
    dest.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(mounts, ensure_ascii=False, indent=4), encoding='utf-8')
    print(f"Wrote {len(mounts)} mounts with stats to {dest / 'mounts.json'} "
          f"({no_stats} had no published effects).")
    if unknown:
        print("Unmapped effect labels (add to STAT_MAP): " + ', '.join(sorted(unknown)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
