#!/usr/bin/env python3
"""Collect the Wakfu spells from Ankama's encyclopedia, every level of them.

    python get_spells_wakfu.py [--lang fr] [--classes 8] [--limit 3]

WHY NOT THE CDN. Ankama's game data feed publishes items and crafting and
nothing else: classes.json, breeds.json, spells.json and monsters.json all
answer 403 (see get_items_wakfu.py). The encyclopedia publishes the lot, and
it is the same company, so this is a first-party source and not a fan mirror.

WHAT A SPELL PAGE CARRIES. Each one embeds a single JSON object, in the
largest inline script on the page, keyed by spell level from 1 to 245:

    store_PA        the AP cost at that level
    store_PM        the MP cost, absent when the spell costs none
    store_PW        the WP cost, same
    store_PO        the range, as the string the game shows, "1 - 4"
    normalEffect    the effect line as HTML, at that level
    criticalEffect  the same on a critical hit

So ONE fetch gives all 245 levels of a spell. Nothing is loaded on demand, the
level selector only shows and hides what is already there. The Iop's Celestial
Sword goes from 2 damage at level 1 to 65 at 245, and 81 on a critical.

THE ELEMENT IS IN AN IMAGE FILENAME, which sounds fragile and is the only
place it exists: the effect HTML reads

    Dommage <img src=".../element/FIRE.png" /> : 65

There is no textual element anywhere in the line, in any language, so the
filename is not a shortcut, it is the data. FIRE, WATER, EARTH and AIR are the
four gear can buy; HLINE is a separator and enemy/caster mark who a clause
applies to.

LIGHT IS A FIFTH ONE AND IT IS REAL. 39 of the 715 spells deal it, across 12
of the 18 classes, and Ankama's own actions.json declares "Dommage : Lumiere"
as action 1083, marked [el6]. No item in the game grants Light mastery or Light
resistance, so a spell that deals it cannot be scaled by gear; see
wakfu_stats.DAMAGE_ELEMENTS_NO_GEAR_SELLS.

This is also why a spell's BRANCH and its damage element can honestly disagree.
Eight Huppermage spells sit in a fire, water, earth or air block and deal
Light. Nothing is mis-parsed there, and a check that insists the two match
would be wrong rather than strict.

245 LEVELS IS ALSO THE CHARACTER CAP, which is worth knowing on its own: the
selector runs 1 to 245 and the item catalogue tops out at level 245 too.

Effect lines that this cannot read are COUNTED AND PRINTED rather than
dropped, the same way get_items_wakfu.py reports the actions it cannot name.
A spell whose damage nobody could parse is a spell the site would show as
harmless.

THE FILE IS 68 MB A LANGUAGE AND ALMOST ALL OF IT IS REPETITION, which the
step that puts this in a database should know before it copies it row for row:
708 of the 715 spells carry ONE text template across all 245 levels, with only
the numbers moving. Seven change template, and even those only gain a figure.
So the compact form is the template once and the numbers per level, not the
sentence 245 times.
"""

from __future__ import annotations

import argparse
import collections
import html
import http.cookiejar
from html.parser import HTMLParser
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# The four Wakfu is played in. German has never existed for this game and
# falls back to English, like every other Wakfu string.
PATHS = {
    'fr': 'fr/mmorpg/encyclopedie/classes',
    'en': 'en/mmorpg/encyclopedia/classes',
    'es': 'es/mmorpg/enciclopedia/clases',
    'pt': 'pt/mmorpg/enciclopedia/classes',
}
FALLBACK = {'de': 'en'}

# Ankama's own class ids. 17 does not exist.
CLASSES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19)

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
           ' (KHTML, like Gecko) Chrome/120 Safari/537.36')
PACE = 0.35

# The class slug can be EMPTY. The Ouginak, class 15, links its spells as
# ".../classes/15-/6260-emeute" on Ankama's own page, so the slug part has to
# be allowed to be nothing at all. Requiring one character silently lost every
# spell of that class, and only that class.
SPELL_LINK = re.compile(
    r'<a href="(/[a-z]{2}/mmorpg/[^"/]+/[^"/]+/(\d+)-[a-z0-9\-]*/(\d+)-[a-z0-9\-]*)"'
    r'[^>]*class="ak-elementary-spell[^"]*"[^>]*title="([^"]*)"')
ELEMENT_BLOCK = re.compile(r'class="ak-elementary-spell-([a-z]+)"')
BIG_SCRIPT = re.compile(r'<script type="application/json">\s*(\{"store_PA".*?)</script>',
                        re.S)
# A row reads "<label> <element image> : <value>", and all three parts need
# care.
#
# THE LABEL SAYS WHAT THE NUMBER IS, and it is the only thing that does. "Soin"
# and "Dommage" produce identical markup, so reading the image and the number
# alone turned every heal into damage. The Sadida's Priere Sadida was recorded
# as dealing 4 damage when it heals 4.
#
# A few words may stand between the colon and the number, and which words
# depends on the language: French writes "Dommages : 32 supplementaires" while
# English writes "damage: additional 32". Demanding a digit right after the
# colon read the French and silently dropped the English, which made one spell
# out of 706 carry different damage in two languages and looked like Ankama
# contradicting itself. It was not.
#
# The pattern must never cross a tag. An earlier one let the element bind to a
# colon further down the line, so the Iop's Posture came back dealing 500 in
# three elements when it grants 25 armour and its element images mark STATES.
EFFECT_ROW = re.compile(
    r'([A-Za-zÀ-ÿ\']{2,20})\s*(?:</?\w[^>]*>\s*)*'
    r'<img src="[^"]*element/([A-Za-z]+)\.png"[^>]*>\s*(?:</\w+>\s*)*'
    r':\s*[^\d<:]{0,24}?(-?\d+)')

# The six that are elements. The other fifteen images in that directory are
# decoration: enemy, caster, ally and fighter mark who a clause applies to,
# CROSS, VLINE, HLINE, CIRCLE, CIRCLERING, RECTANGLERING, CONE and SMALLT are
# area shapes, glyph, barrel and shield are objects, and b.png is a bold
# marker. Reading them as elements is how a spell ends up dealing damage in an
# element called SHIELD.
ELEMENTS_IN_IMAGES = ('FIRE', 'WATER', 'EARTH', 'AIR', 'LIGHT', 'PHYSICAL')

# The words in front of the image, in the four languages Wakfu is played in.
# Anything else is kept with its label and counted, never guessed at.
DAMAGE_WORDS = frozenset((
    'dommage', 'dommages', 'damage', 'damages',
    'dano', 'danos', 'daño', 'daños'))
HEAL_WORDS = frozenset((
    'soin', 'soins', 'heal', 'heals', 'healing',
    'cura', 'curas', 'curação', 'curación'))
SELECTOR_MAX = re.compile(r'class="ak-level-selector-max"[^>]*>\s*(\d+)')


def opener():
    """A reader with a cookie jar: the site answers a bare request with a loop."""
    jar = http.cookiejar.CookieJar()
    built = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    built.addheaders = [('User-Agent', BROWSER)]
    return built


class _Readable(HTMLParser):
    """The text of a fragment, by parsing it rather than by pattern.

    Written with a parser on purpose. Cutting tags out with a regexp is the
    classic way to be wrong about markup, because a pattern cannot tell a real
    tag from the same characters inside an attribute, and a `<script>` that
    does not close the way the pattern expects survives the cut. Ankama's
    effect lines embed script tags carrying tooltip JSON, so this is not
    hypothetical here.
    """

    SILENT = ('script', 'style')

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.parts = []
        self.quiet = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SILENT:
            self.quiet += 1

    def handle_endtag(self, tag):
        if tag in self.SILENT and self.quiet:
            self.quiet -= 1

    def handle_data(self, data):
        if not self.quiet:
            self.parts.append(data)


def strip(markup):
    """The readable text of an effect line, images and tooltips removed."""
    reader = _Readable()
    reader.feed(markup or '')
    reader.close()
    return re.sub(r'\s+', ' ', ''.join(reader.parts)).strip()


def effect_rows(markup, report=None):
    """[(label, element, value)] for every figure attached to an element."""
    out = []
    for label, element, value in EFFECT_ROW.findall(markup or ''):
        if element not in ELEMENTS_IN_IMAGES:
            continue
        out.append((label.strip(), element, int(value)))
    return out


def of_kind(rows, words, report=None, kind=''):
    """The [(element, value)] of the rows whose label is one of `words`."""
    out = []
    for label, element, value in rows:
        if label.lower() in words:
            out.append((element, value))
        elif report is not None and kind == 'damage':
            # Counted once, under its own label, so that a form nobody has
            # seen shows up as a name rather than as a missing number.
            report['row labelled %s' % label.lower()] += 1
    return out


def elements_and_damage(markup, report=None):
    """[(element, value)] for every DAMAGE figure in one effect line."""
    return of_kind(effect_rows(markup), DAMAGE_WORDS, report, 'damage')


def elements_and_healing(markup):
    """[(element, value)] for every HEALING figure in one effect line."""
    return of_kind(effect_rows(markup), HEAL_WORDS)


def spell_links(page, language):
    """[(url, spell id, name, element)] for one class page.

    Only the ELEMENTAL spells have an element. They sit between
    `ak-spells-element-line` and the first `ak-spell-list-row`; everything
    after that is passives and specialties, which carry the same link class and
    no element at all. Splitting the whole page on the element markers gave
    every passive the last element seen, which was wrong for 24 of the Iop's
    40 spells and looked entirely plausible.
    """
    start = page.find('ak-spells-element-line')
    end = page.find('ak-spell-list-row', start + 1 if start >= 0 else 0)
    elemental = page[start:end] if start >= 0 and end > start else ''

    found = []
    for block in re.split(r'(?=class="ak-elementary-spell-)', elemental):
        element = ELEMENT_BLOCK.search(block)
        element = element.group(1).upper() if element else None
        # Ankama names the same element two ways on one page: the block says
        # WIND and the damage image says AIR. AIR is what the item data uses,
        # so that is the one kept.
        element = 'AIR' if element == 'WIND' else element
        for url, _class_id, spell_id, name in SPELL_LINK.findall(block):
            found.append((url, int(spell_id), html.unescape(name), element))
    for url, _class_id, spell_id, name in SPELL_LINK.findall(page):
        found.append((url, int(spell_id), html.unescape(name), None))
    # The same spell can be linked twice; keep the first sighting of each.
    seen, unique = set(), []
    for entry in found:
        if entry[1] in seen:
            continue
        seen.add(entry[1])
        unique.append(entry)
    return unique


def read_spell(reader, url, report):
    """Every level of one spell, or None when the page carries no store."""
    page = reader.open('https://www.wakfu.com' + url,
                       timeout=60).read().decode('utf-8', 'replace')
    found = BIG_SCRIPT.search(page)
    if not found:
        report['page with no store'] += 1
        return None
    try:
        store = json.loads(found.group(1))
    except ValueError:
        report['store that is not json'] += 1
        return None

    # The levels come from every store that has any, not from store_PA alone.
    # A spell that costs no AP publishes store_PA as an empty LIST while
    # store_MP, store_WP and normalEffect all carry their 245 levels: keying on
    # store_PA lost every passive and every MP-cost spell, half the catalogue,
    # and the loss looked like a page that simply had no data.
    def keyed(name):
        value = store.get(name)
        return value if isinstance(value, dict) else {}

    numbered = set()
    for name in ('store_PA', 'store_PM', 'store_PW', 'store_PO',
                 'normalEffect', 'criticalEffect'):
        numbered.update(key for key in keyed(name) if key.isdigit())

    # normalEffect carries ONE MORE entry than the level selector offers: every
    # spell came back with 246 levels where Ankama's own selector stops at 245,
    # and that last one has no AP cost, no MP, no WP and no range, only the
    # text repeated. It is a rendering artifact. The ceiling is read from the
    # page rather than written here, because it is Ankama's number and it has
    # already moved once.
    ceiling = SELECTOR_MAX.search(page)
    if ceiling:
        top = int(ceiling.group(1))
        dropped = {key for key in numbered if int(key) > top}
        if dropped:
            report['level past the selector, dropped'] += len(dropped)
        numbered -= dropped
    else:
        report['page with no level ceiling'] += 1

    levels = {}
    for level in sorted(map(int, numbered)):
        key = str(level)
        normal = keyed('normalEffect').get(key) or ''
        critical = keyed('criticalEffect').get(key) or ''
        rows = effect_rows(normal)
        damage = of_kind(rows, DAMAGE_WORDS, report, 'damage')
        if not damage:
            report['level with no damage figure'] += 1
        levels[level] = {
            'ap': keyed('store_PA').get(key),
            'mp': keyed('store_PM').get(key),
            'wp': keyed('store_PW').get(key),
            'range': keyed('store_PO').get(key),
            'damage': damage,
            'healing': of_kind(rows, HEAL_WORDS),
            'critical_damage': elements_and_damage(critical),
            'critical_healing': elements_and_healing(critical),
            'rows': rows,
            'normal': strip(normal),
            'critical': strip(critical),
        }
    if not levels:
        report['spell with no level at all'] += 1
        return None
    report['levels'] += len(levels)
    return levels


def collect(language, classes, limit, report, known=None):
    reader = opener()
    out = dict(known or {})
    for class_id in classes:
        url = 'https://www.wakfu.com/%s/%d-x' % (PATHS[language], class_id)
        try:
            page = reader.open(url, timeout=60).read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as error:
            report['class page %s' % error.code] += 1
            continue
        links = spell_links(page, language)
        if not links:
            report['class with no spell link'] += 1
        for number, (spell_url, spell_id, name, element) in enumerate(links):
            if limit and number >= limit:
                break
            if str(spell_id) in out:
                report['already collected'] += 1
                continue
            levels = read_spell(reader, spell_url, report)
            time.sleep(PACE)
            if levels is None:
                continue
            out[str(spell_id)] = {
                'class': class_id,
                'name': name,
                'element': element,
                'levels': levels,
            }
            report['spells'] += 1
        report['classes'] += 1
        print('   class %-3d %3d spells' % (class_id, len(links)))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', default='fr', choices=sorted(PATHS))
    parser.add_argument('--out', default='itemscraper/wakfu_raw')
    parser.add_argument('--version', default='1.92.1.60')
    parser.add_argument('--classes', type=int, nargs='*', default=None,
                        help='Ankama class ids, default all 18')
    parser.add_argument('--limit', type=int,
                        help='stop after this many spells per class')
    parser.add_argument('--refresh', action='store_true',
                        help='fetch every spell again instead of only the new')
    args = parser.parse_args(argv)

    report = collections.Counter()
    classes = args.classes if args.classes else list(CLASSES)
    target = Path(args.out) / args.version
    target.mkdir(parents=True, exist_ok=True)
    path = target / ('spells_%s.json' % args.lang)

    # A spell already collected is not fetched again, so a second run costs the
    # 18 class pages and nothing else. Without this a routine rebuild would
    # re-download 715 pages of half a megabyte each, which is why the pipeline
    # can afford to call this step at all. --refresh takes the whole book
    # again, for the day Ankama changes one.
    known = {}
    if path.exists() and not args.refresh:
        known = json.loads(path.read_text(encoding='utf-8'))
        report['already collected'] = 0
    spells = collect(args.lang, classes, args.limit, report, known)
    path.write_text(json.dumps(spells, ensure_ascii=False, indent=1,
                               sort_keys=True), encoding='utf-8')
    print('wrote %s' % path)
    for name, count in sorted(report.items()):
        print('   %-34s %6d' % (name, count))
    return 0


if __name__ == '__main__':
    sys.exit(main())
