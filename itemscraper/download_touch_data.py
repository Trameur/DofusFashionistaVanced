#!/usr/bin/env python3
"""
Download the Dofus Touch game data tables.

The Touch client doesn't expose a public API; it pulls its data straight from its
own backend, so we go to the same place. config.json hands back the current data
host (dataUrl), then each table is a POST to /data/map with the class name. The
response is the whole table, keyed by id, with names already localised to the
requested language. Plain GETs 404 — the route only answers POST.

  config : GET  https://earlyproxy.touch.dofus.com/config.json?lang=<lang>
  table  : POST <dataUrl>/data/map   {"class": "Items", "lang": "<lang>"}

(The current dataUrl is https://dt-proxy-production-early.ankama-games.com, but we
read it from config.json so it keeps working when Ankama rotates the host.)

Records are Ankama's raw d2o objects, since Touch is a Dofus 2 fork: items carry
possibleEffects (effectId + diceNum/diceSide range), criteria, itemSetId,
recipeIds, level, typeId, iconId; item sets carry their per-piece bonuses inline.
get_equipments_touch.py turns these into the optimizer's item model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

# The "early" channel is the only Touch content host still resolving (the old
# production proxyconnection.touch.dofus.com is NXDOMAIN). Its config.json hands
# back the live dataUrl, so we resolve dynamically rather than hard-coding it.
CONFIG_URL = "https://earlyproxy.touch.dofus.com/config.json"
FALLBACK_DATA_URL = "https://dt-proxy-production-early.ankama-games.com"

# A mobile-ish UA; the data API doesn't gate on it, but be polite/identifiable.
USER_AGENT = "Dofus/2 CFNetwork"

# Tables needed to build an equipment optimizer. (Many more exist: Spells,
# Monsters, Areas, Jobs, … — add as needed.)
DEFAULT_CLASSES = [
    'Items', 'ItemSets', 'ItemTypes', 'Effects', 'Recipes', 'Breeds', 'Monsters',
]

# Languages Touch serves (config.serverLanguages). FR is primary for names here;
# the rest are pulled so the site can localise item names like the other versions.
ALL_LANGS = ['fr', 'en', 'es', 'pt', 'de']


def resolve_data_url(lang: str = 'fr') -> str:
    """Read the live client Config to get the current dataUrl (proxy host)."""
    try:
        resp = requests.get(f"{CONFIG_URL}?lang={lang}",
                            headers={'User-Agent': USER_AGENT}, timeout=30)
        resp.raise_for_status()
        cfg = resp.json()
        data_url = cfg.get('dataUrl')
        if data_url:
            return data_url.rstrip('/')
        print(f"  ! config.json had no dataUrl; using fallback", file=sys.stderr)
    except Exception as exc:
        print(f"  ! could not read config.json ({exc}); using fallback", file=sys.stderr)
    return FALLBACK_DATA_URL


def fetch_table(data_url: str, cls: str, lang: str) -> dict:
    """POST <dataUrl>/data/map -> full table as {id: record}, names localized."""
    resp = requests.post(
        f"{data_url}/data/map",
        json={'class': cls, 'lang': lang},
        headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--lang', default='fr', help='Primary language for names')
    parser.add_argument('--all-langs', action='store_true',
                        help='Also pull Items/ItemSets/ItemTypes names for en/es/pt/de')
    parser.add_argument('--classes', nargs='*', default=DEFAULT_CLASSES)
    parser.add_argument('--data-url', default=None,
                        help='Override the data proxy base (else resolved live)')
    parser.add_argument('--dest', default='itemscraper/touch_raw')
    args = parser.parse_args(argv)

    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)

    data_url = args.data_url.rstrip('/') if args.data_url else resolve_data_url(args.lang)
    print(f"Dofus Touch data proxy: {data_url}")

    # Primary language: every requested table.
    failures = 0
    for cls in args.classes:
        try:
            table = fetch_table(data_url, cls, args.lang)
            out = dest_dir / f"{cls}_{args.lang}.json"
            out.write_text(json.dumps(table, ensure_ascii=False), encoding='utf-8')
            print(f"  ok {cls}_{args.lang}.json -> {len(table)} records "
                  f"({out.stat().st_size} bytes)")
        except Exception as exc:
            print(f"  FAILED {cls} ({args.lang}): {exc}", file=sys.stderr)
            failures += 1

    # Other languages: only the name-bearing tables (Items/ItemSets/ItemTypes/Monsters).
    if args.all_langs:
        name_tables = [c for c in ('Items', 'ItemSets', 'ItemTypes', 'Monsters')
                       if c in args.classes]
        for lang in ALL_LANGS:
            if lang == args.lang:
                continue
            for cls in name_tables:
                try:
                    table = fetch_table(data_url, cls, lang)
                    out = dest_dir / f"{cls}_{lang}.json"
                    out.write_text(json.dumps(table, ensure_ascii=False), encoding='utf-8')
                    print(f"  ok {cls}_{lang}.json -> {len(table)} records")
                except Exception as exc:
                    print(f"  FAILED {cls} ({lang}): {exc}", file=sys.stderr)
                    failures += 1

    print(f"Done. Raw tables in {dest_dir}/")
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
