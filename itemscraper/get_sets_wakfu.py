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
- ONLY THE NAME IS TAKEN, BECAUSE A WAKFU SET GRANTS NOTHING FOR WEARING IT.
  Measured on twelve sets from level 11 to 200: the block a set page prints,
  "Bonus / Malus cumules", is the SUM of its members' own item pages, and no
  set page carries the per-piece-count bonus Dofus has. Set 41 was checked
  stat by stat: its eight item pages add up to exactly the 63 HP, 2 AP, 10
  Dodge, 4 % critical, 1 Control, 82 mastery and 5 resistance the set page
  shows. So the total is a roll-up, and there is nothing there to read.

- WHERE THAT ROLL-UP DISAGREES WITH THIS PROJECT, THE ENCYCLOPEDIA IS THE ODD
  ONE OUT. Set 41 sums to 65 HP here because its belt reads 8 HP in the game
  data and "6 HP and 1 Control" on its encyclopedia page. Forty items were
  sampled against their item pages and four differ, three of them belts, always
  the same way: a Control line the client data has no action for, paid with
  about a third of the item's level in HP (2 at level 6, 10 at 32, 20 at 65, 57
  at 170). The Control line is also the only line the page renders with no
  action tag beside it. Ankama's actions.json declares 71 actions and not one
  is Control, so the live feed cannot express that line at all; the item pages
  are read as an older revision, and the client data is what is kept.

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
