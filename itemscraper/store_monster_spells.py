# Copyright (C) 2020 The Dofus Fashionista
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

"""Store the spells each monster casts, from the datacenter dump.

    python store_monster_spells.py [--game-version dofus3|beta] [--tag 3.6.8.8]
"""

import argparse
import io
import json
import os
import re
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from version_tags import latest_tag as _latest_tag  # noqa: E402  (sys.path set above)

RAW_ROOT = os.path.join(CURRENT_DIR, 'raw')
DB_FILES = {
    'dofus3': 'items.db',
    'beta': 'items_beta.db',
}
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def _table(path):
    """A datacenter table as {id: record}."""
    with io.open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    refs = {ref['rid']: ref['data'] for ref in data['references']['RefIds']}
    keys = data['objectsById']['m_keys']['Array']
    values = data['objectsById']['m_values']['Array']
    return {key: refs[value['rid']] for key, value in zip(keys, values)
            if value['rid'] in refs}


def _labels(dump_dir):
    out = {}
    for language in LANGUAGES:
        path = os.path.join(dump_dir, '%s.json' % language)
        with io.open(path, encoding='utf-8') as handle:
            out[language] = json.load(handle)['entries']
    return out


_OPTIONAL = re.compile(r'\{\{?~1~2(.*?)\}\}?')
# Ankama's agreement markup: "Repousse de #1 case{{~ps}}{{~zs}}". A marker
# holds slots written ~<letter><payload>; ~p is what a plural adds and ~s what
# a singular adds. ~z is a second slot, and no label in the dump carries it
# without ~p, so it only ever repeats a decision already made. ~f and ~m are
# the gender of a referent a spell line never names. Inside one marker an empty
# payload takes the next segment's, which is how "{{~p~zies}}" spells
# territories.
_AGREEMENT = re.compile(r'\{\{?~([^{}]*?)\}\}?')
_SPACES = re.compile(r'\s{2,}')
# Prose keeps its paragraph breaks, so only runs of horizontal space collapse.
_HORIZONTAL = re.compile(r'[^\S\n]{2,}')
# "{{spell,24510,1::<color=#ebc304>Telefrag</color>}}" is a link to another
# spell; the part after :: is what the client shows. The colour is the link's,
# and <sprite name="PA"> is an inline icon that always sits next to the word it
# illustrates ("1 <sprite name=\"PA\"> AP used"), so it says nothing on its own.
_SPELL_LINK = re.compile(r'\{\{spell,[^:}]*::(.*?)\}\}')
_DISPLAY_TAG = re.compile(r'</?(?:sprite|color)\b[^>]*>')
_LETTER = re.compile(r'[^\W\d_]', re.UNICODE)

# On these effects "#1" holds a monster id, not an amount.
_SUMMON_EFFECTS = frozenset([181, 185])


def _agree(text, plural):
    """Resolve the agreement markers, keeping the form the count calls for."""
    def one(match):
        parts = [part for part in match.group(1).split('~') if part]
        slots = [(part[0], part[1:]) for part in parts]
        for index, (letter, payload) in enumerate(slots):
            if payload:
                continue
            inherited = next((later for _slot, later in slots[index + 1:]
                              if later), '')
            slots[index] = (letter, inherited)
        for letter, payload in slots:
            if letter == 'p':
                return payload if plural else ''
            if letter == 's':
                return '' if plural else payload
        return ''
    return _AGREEMENT.sub(one, text)


def render_effect(template, dice_num, dice_side, monster_names=None):
    """One effect row read the way the client reads it, or None.

    A template carries two numbers and a segment that only appears when the row
    is a range: "#1{{~1~2 a }}#2 dommages Eau" reads "13 a 16 dommages Eau" when
    both are set, "20% des PV max" when the second is 0.
    """
    if not template:
        return None
    dice_num = dice_num or 0
    dice_side = dice_side or 0
    if dice_side and dice_side != dice_num:
        text = _OPTIONAL.sub(lambda match: match.group(1), template)
        text = text.replace('#2', str(dice_side))
    else:
        text = _OPTIONAL.sub('', template).replace('#2', '')
    plural = dice_num > 1 or (dice_side and dice_side > 1)
    text = _agree(text, plural)
    if monster_names is not None:
        summoned = monster_names.get(dice_num)
        if not summoned:
            return None
        text = text.replace('#1', summoned)
    else:
        text = text.replace('#1', str(dice_num))
    text = _SPACES.sub(' ', strip_display_markup(text)).strip()
    # A row with no letter left is a bare state id the dump never names.
    if not text or '#' in text or not _LETTER.search(text):
        return None
    return text


def strip_display_markup(text):
    """A description as a reader sees it, without the client's own markup."""
    if not text:
        return text
    text = _SPELL_LINK.sub(lambda match: match.group(1), text)
    text = _DISPLAY_TAG.sub('', text)
    return _HORIZONTAL.sub(' ', text).strip()


def spell_description(spell, levels, effects, entries, monsters):
    """What a monster spell does, in one line: Ankama's prose description, or
    failing that the effect rows of the spell's first grade."""
    prose = strip_display_markup(
        entries.get(str(spell.get('descriptionId'))) or '')
    if prose:
        return prose
    for level_id in (spell.get('spellLevels') or {}).get('Array') or []:
        level = levels.get(level_id) or {}
        rendered = []
        for row in (level.get('effects') or {}).get('Array') or []:
            if not isinstance(row, dict):
                continue
            effect_id = row.get('effectId')
            effect = effects.get(effect_id) or {}
            names = monsters if effect_id in _SUMMON_EFFECTS else None
            line = render_effect(entries.get(str(effect.get('descriptionId'))),
                                 row.get('diceNum'), row.get('diceSide'), names)
            if line and line not in rendered:
                rendered.append(line)
        if rendered:
            return ', '.join(rendered)
    return None


def parse_grade_mapping(raw):
    """Spell grade per monster grade, from "1,54;1,56;..."."""
    grades = []
    for chunk in (raw or '').split(';'):
        head = chunk.split(',')[0].strip()
        if head.isdigit():
            grades.append(int(head))
    return grades


def latest_tag():
    return _latest_tag(RAW_ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-version', default='dofus3', choices=sorted(DB_FILES))
    parser.add_argument('--tag', help='datacenter dump to read, default the latest')
    args = parser.parse_args()

    dump_dir = os.path.join(RAW_ROOT, args.tag or latest_tag())
    if not os.path.isdir(dump_dir):
        raise SystemExit('no such dump: %s' % dump_dir)
    print('%s: reading %s' % (args.game_version, dump_dir))

    monsters = _table(os.path.join(dump_dir, 'monsters.json'))
    spells = _table(os.path.join(dump_dir, 'spells.json'))
    levels = _table(os.path.join(dump_dir, 'spell_levels.json'))
    effects = _table(os.path.join(dump_dir, 'effects.json'))
    labels = _labels(dump_dir)

    db_path = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                           DB_FILES[args.game_version])
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    known = {row[0] for row in cursor.execute(
        'SELECT DISTINCT monster_ankama_id FROM monster_names')}
    print('%s: %d monsters in db' % (args.game_version, len(known)))

    for table in ('monster_spells', 'monster_spell_names', 'monster_spell_levels'):
        cursor.execute('DROP TABLE IF EXISTS %s' % table)
    cursor.execute("""
        CREATE TABLE monster_spells (
            monster_ankama_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            spell_ankama_id INTEGER NOT NULL,
            grade_mapping TEXT,
            PRIMARY KEY (monster_ankama_id, position)
        )""")
    cursor.execute("""
        CREATE TABLE monster_spell_names (
            spell_ankama_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            PRIMARY KEY (spell_ankama_id, language)
        )""")
    cursor.execute("""
        CREATE TABLE monster_spell_levels (
            spell_ankama_id INTEGER NOT NULL,
            grade INTEGER NOT NULL,
            ap_cost INTEGER,
            range_min INTEGER,
            range_max INTEGER,
            PRIMARY KEY (spell_ankama_id, grade)
        )""")

    used = set()
    linked = 0
    unknown = set()
    for monster_id, monster in monsters.items():
        if monster_id not in known:
            continue
        spell_ids = (monster.get('spells') or {}).get('Array') or []
        mappings = (monster.get('spellGrades') or {}).get('Array') or []
        for position, spell_id in enumerate(spell_ids):
            if spell_id not in spells:  # -1 and friends, undescribed
                unknown.add(spell_id)
                continue
            mapping = mappings[position] if position < len(mappings) else ''
            grades = parse_grade_mapping(mapping)
            cursor.execute(
                'INSERT OR REPLACE INTO monster_spells VALUES (?, ?, ?, ?)',
                (monster_id, position, spell_id,
                 ','.join(str(grade) for grade in grades)))
            used.add(spell_id)
            linked += 1

    monster_names = {
        language: {mid: labels[language].get(str(monster.get('nameId')))
                   for mid, monster in monsters.items()}
        for language in LANGUAGES}

    named = priced = 0
    for spell_id in sorted(used):
        spell = spells.get(spell_id)
        if not spell:
            continue
        name_id = str(spell.get('nameId'))
        for language in LANGUAGES:
            name = labels[language].get(name_id)
            if not name:
                continue
            cursor.execute(
                'INSERT OR REPLACE INTO monster_spell_names VALUES (?, ?, ?, ?)',
                (spell_id, language, name,
                 spell_description(spell, levels, effects, labels[language],
                                   monster_names[language])))
            named += 1
        for level_id in (spell.get('spellLevels') or {}).get('Array') or []:
            level = levels.get(level_id)
            if not level:
                continue
            cursor.execute(
                'INSERT OR REPLACE INTO monster_spell_levels VALUES (?, ?, ?, ?, ?)',
                (spell_id, level.get('grade'), level.get('apCost'),
                 level.get('minRange'), level.get('range')))
            priced += 1

    conn.commit()
    conn.close()
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(db_path, args.game_version)
    print('stored %d monster spells, %d names, %d grades'
          % (linked, named, priced))
    if unknown:
        print('skipped %d spell ids the dump does not describe: %s'
              % (len(unknown), ', '.join(str(i) for i in sorted(unknown)[:10])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
