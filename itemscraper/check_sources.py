#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Is every source the five versions are built from still giving us data?

A source that answers 200 and parses to nothing is the dangerous case: the
Retro drop rate moved into a span, the parser matched nothing, and the rebuild
that followed emptied five tables while every step printed ok. So each probe
here runs the real parser on a real sample and holds it to a floor, rather than
checking a status code.

    python itemscraper/check_sources.py            # every source
    python itemscraper/check_sources.py --only retro
    python itemscraper/check_sources.py --json     # for the loop

Exit code is 1 when any probe comes back under its floor.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import urllib.parse
from urllib.request import Request, urlopen

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
for path in (PROJECT_ROOT, CURRENT_DIR, os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
         '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
TIMEOUT = 60


def _get(url, headers=None, timeout=TIMEOUT):
    request = Request(url, headers=dict({'User-Agent': AGENT}, **(headers or {})))
    with urlopen(request, timeout=timeout) as answer:
        return answer.read().decode('utf-8', 'replace')


def _get_json(url, headers=None, timeout=TIMEOUT):
    return json.loads(_get(url, headers, timeout))


def probe_retro_lang():
    """Ankama's Retro lang CDN, where the item and effect files come from."""
    from download_retro_langs import fetch_manifest
    return len(fetch_manifest('fr')), 'lang categories'


def probe_retro_drops():
    """One page of the Solomonk bestiary, read by the drop scraper's own regexes."""
    import get_monsters_retro as scraper
    params = {'lang': 'fr', 'Q': '10', 'O': '0', 'T': 'all'}
    params.update(scraper.COLLAPSE)
    payload = _get_json(scraper.AJAX + '?' + urllib.parse.urlencode(params),
                        {'X-Requested-With': 'XMLHttpRequest',
                         'Referer': scraper.REFERER})
    page = payload.get('html', '')
    monsters = len(scraper.TITLE_RE.findall(page))
    drops = len(scraper.DROP_RE.findall(page))
    if monsters < 5:
        return 0, 'monster cards on the first page (found %d)' % monsters
    return drops, 'drops on the first page of 10 monsters'


def probe_retro_set_bonuses_solomonk():
    """The panoplies page, read by the set bonus scraper's own parser."""
    import store_retro_set_bonuses as scraper
    records = scraper.fetch_solomonk_records(report_unmapped=False)
    return len(records), 'sets with bonuses'


def probe_retro_set_bonuses_drt():
    """Dofus Retro Tools, which fills the sets solomonk does not list."""
    import store_retro_set_bonuses as scraper
    records = scraper.fetch_api_records(report_unmapped=False)
    return len(records), 'sets with bonuses'


def probe_retro_pets():
    """dofux.org, part of the Retro pet feeding caps."""
    import scrape_retro_pet_bonuses as scraper
    return len(scraper._parse_dofux(_get(scraper.DOFUX_URL))), 'pets with bonuses'


def probe_dofus3_items():
    """dofusdude, the source of the Dofus 3 and Beta items."""
    payload = _get_json('https://api.dofusdu.de/dofus3/v1/fr/items/equipment'
                        '?page%5Bsize%5D=50')
    items = payload.get('items') or []
    return len(items), 'items on one page'


def probe_dofus3_sets():
    payload = _get_json('https://api.dofusdu.de/dofus3/v1/fr/sets'
                        '?page%5Bsize%5D=50')
    return len(payload.get('sets') or []), 'sets on one page'


def probe_dofusdb_monsters():
    """DofusDB, the source of the modern monster stats and artwork."""
    payload = _get_json('https://api.dofusdb.fr/monsters?$limit=50')
    return len(payload.get('data') or []), 'monsters on one page'


def probe_beta_items():
    payload = _get_json('https://api.dofusdu.de/dofus3beta/v1/fr/items/equipment'
                        '?page%5Bsize%5D=50')
    return len(payload.get('items') or []), 'items on one page'


def probe_beta_monsters():
    payload = _get_json('https://api.beta.dofusdb.fr/monsters?$limit=50')
    return len(payload.get('data') or []), 'monsters on one page'


def probe_touch_config():
    """The Touch login proxy, which points at the build's data map."""
    payload = _get_json(
        'https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr')
    urls = [value for value in json.dumps(payload).split('"')
            if value.startswith('http')]
    return len(urls), 'urls in the touch config'


def probe_cytrus():
    """Ankama's Cytrus CDN, where the Retro monster artwork comes from."""
    payload = _get_json('https://cytrus.cdn.ankama.com/cytrus.json')
    return len(payload.get('games') or {}), 'games listed by cytrus'


PROBES = (
    ('retro', 'ankama lang cdn', probe_retro_lang, 20),
    ('retro', 'solomonk drops', probe_retro_drops, 10),
    ('retro', 'solomonk set bonuses', probe_retro_set_bonuses_solomonk, 100),
    ('retro', 'dofusretrotools set bonuses', probe_retro_set_bonuses_drt, 100),
    ('retro', 'dofux pets', probe_retro_pets, 10),
    ('retro', 'cytrus cdn', probe_cytrus, 1),
    ('dofus3', 'dofusdude items', probe_dofus3_items, 40),
    ('dofus3', 'dofusdude sets', probe_dofus3_sets, 40),
    ('dofus3', 'dofusdb monsters', probe_dofusdb_monsters, 40),
    ('beta', 'dofusdude items', probe_beta_items, 40),
    ('beta', 'dofusdb monsters', probe_beta_monsters, 40),
    ('touch', 'ankama touch config', probe_touch_config, 1),
)

# Dofus 2 is built from a committed 2.73 datacenter dump, not from anything
# live, so there is nothing here that could go quietly empty on it.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', help='one game version')
    parser.add_argument('--json', action='store_true',
                        help='machine-readable, for the loop')
    args = parser.parse_args(argv)

    probes = [row for row in PROBES if not args.only or row[0] == args.only]
    results = []
    for version, name, probe, floor in probes:
        started = time.time()
        try:
            count, unit = probe()
            ok = count >= floor
            error = ''
        except Exception:                                    # noqa: BLE001
            count, unit, ok = 0, '', False
            error = traceback.format_exc(limit=1).strip().splitlines()[-1]
        results.append({'version': version, 'source': name, 'count': count,
                        'floor': floor, 'unit': unit, 'ok': ok,
                        'error': error, 'seconds': round(time.time() - started, 1)})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        print('%-8s %-28s %7s %7s  %s' % ('version', 'source', 'found', 'floor', ''))
        for row in results:
            print('%-8s %-28s %7s %7s  %s%s'
                  % (row['version'], row['source'], row['count'], row['floor'],
                     'ok ' if row['ok'] else 'LOW ',
                     row['error'] or row['unit']))
        broken = [row for row in results if not row['ok']]
        print()
        print('%d source(s) under floor' % len(broken))

    return 1 if any(not row['ok'] for row in results) else 0


if __name__ == '__main__':
    sys.exit(main())
