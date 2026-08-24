#!/usr/bin/env python3
"""Recover the Wakfu set names, which the game data does not publish.

    python get_sets_wakfu.py [--dump itemscraper/transformed_wakfu.json]

Items name an `itemSetId` and the CDN publishes no set file at all: every
plausible filename answers 403, and the forum post that announces the feed does
not list one. The official encyclopedia uses THE SAME ids, so the names are
recovered from there, one page per set per language.

    fr  https://www.wakfu.com/fr/mmorpg/encyclopedie/panoplies/<id>
    en  https://www.wakfu.com/en/mmorpg/encyclopedia/sets/<id>
    es  https://www.wakfu.com/es/mmorpg/enciclopedia/sets/<id>
    pt  https://www.wakfu.com/pt/mmorpg/enciclopedia/conjuntos/<id>

Three things learned the hard way, all of them in the code below:

- The encyclopedia answers a cookie-less request with a redirect loop. Keeping
  a cookie jar for the run is enough; nothing is sent that a browser would not.
- It resets the connection when hammered, so requests are paced and the answers
  are cached. A second run costs nothing.
- ONLY THE NAME IS TAKEN. The set page also prints a bonus total, and that
  total is stale: set 41 claims +63 HP and +1 Control while its eight items sum
  to 65 HP and no Control, which the item pages confirm. Set totals are
  computed from the items, never read here.

German is absent from Wakfu entirely, so it falls back to English, exactly as
the item names do.
"""

from __future__ import annotations

import argparse
import html
import http.cookiejar
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PATHS = {
    'fr': 'fr/mmorpg/encyclopedie/panoplies',
    'en': 'en/mmorpg/encyclopedia/sets',
    'es': 'es/mmorpg/enciclopedia/sets',
    'pt': 'pt/mmorpg/enciclopedia/conjuntos',
}
FALLBACK = {'de': 'en'}
BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
           ' (KHTML, like Gecko) Chrome/120 Safari/537.36')
PACE = 0.35
TITLE = re.compile(r'<title>(.*?)</title>', re.S)


def opener():
    jar = http.cookiejar.CookieJar()
    built = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    built.addheaders = [('User-Agent', BROWSER)]
    return built


def set_name(reader, language, set_id):
    """The set's name in one language, or None when the page is not there."""
    url = 'https://www.wakfu.com/%s/%d' % (PATHS[language], set_id)
    try:
        page = reader.open(url, timeout=45).read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
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
