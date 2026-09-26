# Copyright (C) 2026 The Dofus Fashionista
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

"""Special item effects as stat equivalents, one generated table per game version."""

import hashlib
import json
import os
import re
import unicodedata

TABLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'effect_tables')

ELEMENT_KEYS = ('str', 'int', 'cha', 'agi')
PLAYED_SHARE = 0.7
PSEUDO_KEYS = ('final', 'played_char')
STAT_KEYS = ELEMENT_KEYS + ('hp', 'ap', 'mp', 'ch', 'pow', 'dam', 'perspedam', 'lock', 'dodge',
                            'apres', 'mpres', 'apred', 'mpred', 'pshdam')
EQUIVALENT_KEYS = frozenset(PSEUDO_KEYS + STAT_KEYS)

# Worth depends on the wearer's class, which effect_term does not read
CLASS_BOUND_RULES = ('class_item_spell_modifiers',)

_MARKUP = [(re.compile(r'<sprite name="[^"]*">\s*'), ''),
           (re.compile(r'\{\{[a-z]+,[\d,]+::([^}]*)\}\}'), r'\1')]
_BULLET = re.compile('^[' + chr(0x2022) + r'*-]\s*')

_tables = {}


def _normalized_lines(lines):
    out = []
    for line in lines or []:
        text = unicodedata.normalize('NFC', line)
        for pattern, replacement in _MARKUP:
            text = pattern.sub(replacement, text)
        text = ' '.join(text.split())
        if text:
            out.append(text)
    return out


def canonical_text(lines):
    """The effect's wording without markup, bullets, a title line or line breaks."""
    kept = []
    for index, line in enumerate(_normalized_lines(lines)):
        line = _BULLET.sub('', line)
        if index == 0 and line.endswith(':') and not re.search(r'\d', line):
            continue
        if line:
            kept.append(line)
    return ' '.join(' '.join(kept).split())


def text_fingerprint(lines):
    return hashlib.sha1(canonical_text(lines).encode('utf-8')).hexdigest()[:16]


def load_effect_table(version):
    """The version's own table, or None: never another version's."""
    if version not in _tables:
        path = os.path.join(TABLE_DIR, '%s.json' % version)
        table = None
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as handle:
                table = json.load(handle)
        _tables[version] = table
    return _tables[version]


def versions_with_effect_table():
    if not os.path.isdir(TABLE_DIR):
        return ()
    return tuple(sorted(name[:-len('.json')] for name in os.listdir(TABLE_DIR)
                        if name.endswith('.json')))


def played_characteristics(weights):
    """Characteristics weighted at least PLAYED_SHARE times the heaviest one."""
    top = max(weights.get(key, 0) for key in ELEMENT_KEYS)
    return [key for key in ELEMENT_KEYS
            if weights.get(key, 0) > 0 and weights.get(key, 0) >= PLAYED_SHARE * top]


def _weight(stat, weights, played, level):
    if stat == 'final':
        return weights.get('permedam', 0) + weights.get('perrandam', 0)
    if stat == 'played_char':
        return sum(weights[key] for key in played) / float(len(played)) if played else 0
    if stat == 'hp':
        return weights.get('hp', 0) * level / 200.0
    return weights.get(stat, 0)


def is_valued(entry):
    return bool(entry.get('equivalents')) and entry.get('rule') not in CLASS_BOUND_RULES


def effect_term(entry, weights, level):
    """Objective weight of wearing the item: its stat equivalents times the build's weights."""
    if not is_valued(entry):
        return 0
    played = played_characteristics(weights)
    equivalents = entry['equivalents']
    by_count = (entry.get('equivalents_by_elements') or {}).get(str(len(played)))
    if by_count is not None:
        equivalents = by_count
    return sum(amount * _weight(stat, weights, played, level)
               for stat, amount in equivalents.items() if stat != 'sets')
