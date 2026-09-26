#!/usr/bin/env python3
"""Download the Dofus Touch game data tables: config.json gives dataUrl, each table is a POST to <dataUrl>/data/map {class, lang}."""

from __future__ import annotations

import argparse
import os
import json
import sys
from pathlib import Path

import requests

# The live channel; the "early" channel that replaced proxyconnection.touch.
# dofus.com is the test server and serves items nobody can own.
CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json"
FALLBACK_DATA_URL = "https://dt-proxy-production-login.ankama-games.com"

# The data API does not gate on the UA.
USER_AGENT = "Dofus/2 CFNetwork"

# ShieldModelsLevels says how many ranks each shield model has: the transform
# reads a shield's final line off it (models 1 to 5 have 100 ranks, the
# TemporiX Shield of Infinity's model 7 has 1000). It carries no name, so it is
# fetched in the primary language only.
DEFAULT_CLASSES = [
    'Items', 'ItemSets', 'ItemTypes', 'Effects', 'Recipes', 'Breeds', 'Monsters',
    'ShieldModelsLevels', 'Documents',
]

# Languages this scraper knows how to ask for. Which of them Touch still
# SERVES is read from the live config at run time, never assumed: see
# served_languages below.
ALL_LANGS = ['fr', 'en', 'es', 'pt', 'de']


def served_languages(lang: str = 'fr') -> set:
    """The languages Touch still serves, from its own config; a dropped language is answered in English with no marker, and an empty set means unreadable, so the caller skips nothing"""
    try:
        resp = requests.get(f"{CONFIG_URL}?lang={lang}",
                            headers={'User-Agent': USER_AGENT}, timeout=30)
        resp.raise_for_status()
        served = resp.json().get('serverLanguages')
        return set(served) if served else set()
    except Exception as exc:
        print(f"  ! could not read serverLanguages ({exc}); "
              f"keeping every language", file=sys.stderr)
        return set()


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
    default_dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'touch_raw')
    parser.add_argument('--dest', default=default_dest)
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

    # Other languages: only the name-bearing tables (Recipes carries the
    # localized jobName).
    if args.all_langs:
        name_tables = [c for c in ('Items', 'ItemSets', 'ItemTypes', 'Monsters', 'Recipes')
                       if c in args.classes]
        served = served_languages(args.lang)
        for lang in ALL_LANGS:
            if lang == args.lang:
                continue
            if served and lang not in served:
                # Asking anyway would hand us the failover language and
                # overwrite a real translation with it.
                print(f"  ! {lang} is no longer in serverLanguages "
                      f"({', '.join(sorted(served))}); keeping the "
                      f"{lang} files already on disk", file=sys.stderr)
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
