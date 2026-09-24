#!/usr/bin/env python3
"""Collect the Wakfu spells, every level, from Ankama's encyclopedia.

    python get_spells_wakfu.py [--lang fr] [--classes 8] [--limit 3]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import re
import sys
import time
from pathlib import Path

try:
    from itemscraper.wakfu_http import opener, read_page
    from itemscraper.wakfu_mirror import current_build
except ImportError:
    from wakfu_http import opener, read_page
    from wakfu_mirror import current_build

HERE = Path(__file__).resolve().parent.parent

# The CDN answers 403 on spells.json, the encyclopedia has them
# No German for Wakfu, it falls back to English
PATHS = {
    'fr': 'fr/mmorpg/encyclopedie/classes',
    'en': 'en/mmorpg/encyclopedia/classes',
    'es': 'es/mmorpg/enciclopedia/clases',
    'pt': 'pt/mmorpg/enciclopedia/classes',
}
FALLBACK = {'de': 'en'}

# Ankama's own class ids. 17 does not exist.
CLASSES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19)

PACE = 0.35

# The class slug can be empty: the Ouginak links ".../classes/15-/6260-emeute"
SPELL_LINK = re.compile(
    r'<a href="(/[a-z]{2}/mmorpg/[^"/]+/[^"/]+/(\d+)-[a-z0-9\-]*/(\d+)-[a-z0-9\-]*)"'
    r'[^>]*class="ak-elementary-spell[^"]*"[^>]*title="([^"]*)"')
ELEMENT_BLOCK = re.compile(r'class="ak-elementary-spell-([a-z]+)"')
# Every level of the spell is in this one JSON object
BIG_SCRIPT = re.compile(r'<script type="application/json">\s*(\{"store_PA".*?)</script>',
                        re.S)
# The element is only in the image filename, element/FIRE.png
ELEMENT_IMAGE = re.compile(r'element/([A-Za-z]+)\.png')

# Labels can be several words, Portuguese writes "Dano de <img> : 101"
WORDS = re.compile(r"[A-Za-zÀ-ÿ']{2,20}")
# Words can precede the number, and a trailing % is not damage
FIGURE = re.compile(
    r"\s*((?:[A-Za-zÀ-ÿ']{2,20}\s+){0,2}[A-Za-zÀ-ÿ']{2,20})?\s*:"
    r"\s*[^\d:]{0,24}?(-?\d+)\s*(%)?")

# The other images there are target marks, area shapes and objects
ELEMENTS_IN_IMAGES = ('FIRE', 'WATER', 'EARTH', 'AIR', 'LIGHT', 'PHYSICAL')

# Heal and damage rows have the same markup, only the label tells them apart
DAMAGE_WORDS = frozenset((
    'dommage', 'dommages', 'damage', 'damages',
    'dano', 'danos', 'daño', 'daños'))
HEAL_WORDS = frozenset((
    'soin', 'soins', 'heal', 'heals', 'healing',
    'cura', 'curas', 'curação', 'curación'))
SELECTOR_MAX = re.compile(r'class="ak-level-selector-max"[^>]*>\s*(\d+)')


def fingerprint():
    """Hash of this script, to tell harvests read by other versions apart."""
    with io.open(__file__, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest()[:16]


class _Readable(HTMLParser):
    """Text of a fragment, without the tooltip scripts in effect lines."""

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


class _Tokens(HTMLParser):
    """An effect line as a flat run of text and element images."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.items = []
        self.quiet = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.quiet += 1
            return
        if tag != 'img' or self.quiet:
            return
        found = ELEMENT_IMAGE.search(dict(attrs).get('src') or '')
        if found:
            self.items.append(('element', found.group(1)))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'script' and self.quiet:
            self.quiet -= 1

    def handle_data(self, data):
        if not self.quiet:
            self.items.append(('text', data))


def _words_before(items, at):
    """Last words before `at`, across tags, up to a damage or heal word."""
    words = []
    known = DAMAGE_WORDS | HEAL_WORDS
    for kind, value in reversed(items[:at]):
        # Several element images can share one figure
        if kind == 'element':
            continue
        words = WORDS.findall(value) + words
        if {word.lower() for word in words} & known or len(words) >= 3:
            break
    return ' '.join(words[-3:])


# A conditional row starts with ": -", in every language
# English puts the label after the image, French before it
INTRODUCED_BARE = re.compile(r":\s*-\s*$")
INTRODUCED = re.compile(
    r":\s*-\s*(?:[A-Za-zÀ-ÿ']{2,20}\s+){0,2}[A-Za-zÀ-ÿ']{0,20}\s*:?\s*$")

# Enough to cross a bold marker and a target icon, not the row before
INTRODUCTION_REACH = 60


def _is_conditional(items, at, label_after=None):
    """Whether the row at `at` only lands on a condition (": -")."""
    tail = ''
    for kind, value in reversed(items[:at]):
        if kind == 'element':
            continue
        tail = value + tail
        if len(tail) >= INTRODUCTION_REACH:
            break
    pattern = INTRODUCED_BARE if label_after else INTRODUCED
    return bool(pattern.search(tail))


def _pick_label(before, after):
    """The side of the image with a damage or heal word, else both joined."""
    for candidate in (after, before, '%s %s' % (before or '', after or '')):
        words = {word.lower() for word in WORDS.findall(candidate or '')}
        if words & DAMAGE_WORDS or words & HEAL_WORDS:
            return ' '.join(WORDS.findall(candidate))
    return ' '.join(WORDS.findall(after or before or ''))


def effect_rows(markup, report=None):
    """[(label, element, value, unit, conditional)] per element figure."""
    reader = _Tokens()
    reader.feed(markup or '')
    reader.close()
    items = reader.items

    out = []
    for at, (kind, value) in enumerate(items):
        if kind != 'element' or value not in ELEMENTS_IN_IMAGES:
            continue
        after = items[at + 1][1] if at + 1 < len(items) \
            and items[at + 1][0] == 'text' else ''
        figure = FIGURE.match(after)
        if not figure:
            continue
        label = _pick_label(_words_before(items, at), figure.group(1))
        out.append((label, value, int(figure.group(2)),
                    figure.group(3) or '',
                    _is_conditional(items, at, figure.group(1))))
    return out


def of_kind(rows, words, report=None, kind=''):
    """[(element, value)] of rows labelled with `words`, % rows left out."""
    out = []
    for label, element, value, unit, _conditional in rows:
        said = {word for word in re.split(r'\s+', label.lower()) if word}
        if unit == '%':
            if report is not None and kind == 'damage' and (said & words):
                report['damage given as a per cent'] += 1
            continue
        if said & words:
            out.append((element, value))
        elif report is not None and kind == 'damage' and not (said & HEAL_WORDS):
            # Unknown labels are counted by name
            report['row labelled %s' % label.lower()] += 1
    return out


def elements_and_damage(markup, report=None):
    """[(element, value)] for every DAMAGE figure in one effect line."""
    return of_kind(effect_rows(markup), DAMAGE_WORDS, report, 'damage')


def elements_and_healing(markup):
    """[(element, value)] for every HEALING figure in one effect line."""
    return of_kind(effect_rows(markup), HEAL_WORDS)


def spell_links(page, language):
    """[(url, spell id, name, element)] for one class page."""
    # Passives come after the first ak-spell-list-row, with no element
    start = page.find('ak-spells-element-line')
    end = page.find('ak-spell-list-row', start + 1 if start >= 0 else 0)
    elemental = page[start:end] if start >= 0 and end > start else ''

    found = []
    for block in re.split(r'(?=class="ak-elementary-spell-)', elemental):
        element = ELEMENT_BLOCK.search(block)
        element = element.group(1).upper() if element else None
        # The block says WIND where the damage image and the items say AIR
        element = 'AIR' if element == 'WIND' else element
        for url, _class_id, spell_id, name in SPELL_LINK.findall(block):
            found.append((url, int(spell_id), html.unescape(name), element))
    for url, _class_id, spell_id, name in SPELL_LINK.findall(page):
        found.append((url, int(spell_id), html.unescape(name), None))
    # A spell can be linked twice
    seen, unique = set(), []
    for entry in found:
        if entry[1] in seen:
            continue
        seen.add(entry[1])
        unique.append(entry)
    return unique


def read_spell(reader, url, report):
    """Every level of one spell, or None when the page carries no store."""
    page = read_page(reader, 'https://www.wakfu.com' + url)
    if page is None:
        report['spell page answering 404'] += 1
        return None
    found = BIG_SCRIPT.search(page)
    if not found:
        report['page with no store'] += 1
        return None
    try:
        store = json.loads(found.group(1))
    except ValueError:
        report['store that is not json'] += 1
        return None

    # A spell with no AP cost has store_PA as an empty list
    def keyed(name):
        value = store.get(name)
        return value if isinstance(value, dict) else {}

    numbered = set()
    for name in ('store_PA', 'store_PM', 'store_PW', 'store_PO',
                 'normalEffect', 'criticalEffect'):
        numbered.update(key for key in keyed(name) if key.isdigit())

    # normalEffect has one level past the selector max, with only the text
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


def collect(language, classes, limit, report, known=None, save=None):
    reader = opener()
    out = dict(known or {})
    for class_id in classes:
        url = 'https://www.wakfu.com/%s/%d-x' % (PATHS[language], class_id)
        page = read_page(reader, url)
        if page is None:
            report['class page 404'] += 1
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
        print('   class %-3d %3d spells' % (class_id, len(links)), flush=True)
        if save is not None:
            save(out)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', default='fr', choices=sorted(PATHS))
    parser.add_argument('--out', default='itemscraper/wakfu_raw')
    parser.add_argument('--version', default=None,
                        help='the mirrored build (default: the one in transformed_wakfu.json)')
    parser.add_argument('--classes', type=int, nargs='*', default=None,
                        help='Ankama class ids, default all 18')
    parser.add_argument('--limit', type=int,
                        help='stop after this many spells per class')
    parser.add_argument('--refresh', action='store_true',
                        help='fetch every spell again instead of only the new')
    args = parser.parse_args(argv)

    version = args.version or current_build()
    if not version:
        parser.error('no mirrored build; run get_items_wakfu.py first or pass --version')
    report = collections.Counter()
    classes = args.classes if args.classes else list(CLASSES)
    target = Path(args.out) / version
    target.mkdir(parents=True, exist_ok=True)
    path = target / ('spells_%s.json' % args.lang)

    def save(spells):
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_text(json.dumps(spells, ensure_ascii=False, indent=1,
                                        sort_keys=True), encoding='utf-8')
        temporary.replace(path)

    known = {}
    if path.exists() and not args.refresh:
        known = json.loads(path.read_text(encoding='utf-8'))
        report['already collected'] = 0
    print('build %s, %d spells already collected' % (version, len(known)), flush=True)
    spells = collect(args.lang, classes, args.limit, report, known, save)
    save(spells)
    # Not in the spells file, readers take every key there as a spell id
    (target / ('spells_%s.meta.json' % args.lang)).write_text(
        json.dumps({'parser': fingerprint(), 'spells': len(spells)},
                   indent=1, sort_keys=True), encoding='utf-8')
    print('wrote %s' % path)
    for name, count in sorted(report.items()):
        print('   %-34s %6d' % (name, count))
    return 0


if __name__ == '__main__':
    sys.exit(main())
