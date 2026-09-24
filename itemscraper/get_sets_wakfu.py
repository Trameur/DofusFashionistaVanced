#!/usr/bin/env python3
"""Wakfu set names from the encyclopedia, with a cookie jar and paced requests; only the name is taken, a Wakfu set grants nothing for wearing it."""

from __future__ import annotations

import argparse
import html
import io
import json
import re
import sys
import time
from pathlib import Path

try:
    from itemscraper.wakfu_http import opener, read_page
except ImportError:
    from wakfu_http import opener, read_page

PATHS = {
    'fr': 'fr/mmorpg/encyclopedie/panoplies',
    'en': 'en/mmorpg/encyclopedia/sets',
    'es': 'es/mmorpg/enciclopedia/sets',
    'pt': 'pt/mmorpg/enciclopedia/conjuntos',
}
FALLBACK = {'de': 'en'}
PACE = 0.35
TITLE = re.compile(r'<title>(.*?)</title>', re.S)


def set_name(reader, language, set_id):
    """The set's name in one language, or None when the page is not there."""
    url = 'https://www.wakfu.com/%s/%d' % (PATHS[language], set_id)
    page = read_page(reader, url, timeout=45)
    if page is None:
        return None
    found = TITLE.search(page)
    if not found:
        return None
    # "Panoplie Bouftou - Panoplies - Encyclopedie WAKFU - ..."
    title = html.unescape(found.group(1)).strip()
    name = title.split(' - ')[0].strip()
    return name or None


def wanted_sets(dump_path):
    with io.open(dump_path, encoding='utf-8') as handle:
        dump = json.load(handle)
    ids = {item['set_id'] for item in dump['equipment'] if item.get('set_id')}
    return sorted(ids), dump['version']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', default='itemscraper/transformed_wakfu.json')
    parser.add_argument('--out', default='itemscraper/wakfu_raw')
    parser.add_argument('--limit', type=int,
                        help='stop after this many sets, for a dry run')
    args = parser.parse_args(argv)

    dump_path = Path(args.dump)
    if not dump_path.exists():
        parser.error('%s is missing; run get_items_wakfu.py first' % dump_path)
    ids, version = wanted_sets(dump_path)
    if args.limit:
        ids = ids[:args.limit]

    cache_path = Path(args.out) / version / 'sets.json'
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    known = {}
    if cache_path.exists():
        known = json.loads(cache_path.read_text(encoding='utf-8'))

    reader = opener()
    missing = []
    for number, set_id in enumerate(ids, start=1):
        key = str(set_id)
        if known.get(key):
            continue
        names = {}
        for language in PATHS:
            name = set_name(reader, language, set_id)
            if name:
                names[language] = name
            time.sleep(PACE)
        if not names:
            missing.append(set_id)
            print('  set %-5s no page in any language' % set_id)
            continue
        for absent, instead in FALLBACK.items():
            if names.get(instead):
                names[absent] = names[instead]
        known[key] = names
        if number % 20 == 0:
            cache_path.write_text(json.dumps(known, ensure_ascii=False,
                                             indent=1, sort_keys=True),
                                  encoding='utf-8')
            print('  %d of %d' % (number, len(ids)))

    cache_path.write_text(json.dumps(known, ensure_ascii=False, indent=1,
                                     sort_keys=True), encoding='utf-8')
    print('%d sets named, %d without a page, written to %s'
          % (len(known), len(missing), cache_path))
    if missing:
        print('   no page: %s' % missing)
    return 0


if __name__ == '__main__':
    sys.exit(main())
