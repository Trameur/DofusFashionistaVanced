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
from untranslated_tag import clean_description, clean_display_name  # noqa: E402
from get_spells import effect_id_of  # noqa: E402

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

# On these effects "#1" holds a monster id, not an amount; summon_effects finds the others.
_SUMMON_EFFECTS = frozenset([181, 185])
_TARGET_MONSTER = re.compile(r'([Ff])(\d+)$')
_EXCEPT = {'en': 'except', 'fr': 'sauf', 'es': 'excepto', 'pt': 'exceto', 'de': 'außer'}
_SEPARATORS = {'fr': (' : ', ' ; ')}
_DEFAULT_SEPARATORS = (': ', '; ')


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


def summon_effects(effects, entries):
    """The summon effects plus those sharing their icon whose text holds only #1."""
    icons = {(effects.get(effect_id) or {}).get('textIconReferenceId')
             for effect_id in _SUMMON_EFFECTS} - {None, 0}
    found = set(_SUMMON_EFFECTS)
    for effect_id, effect in effects.items():
        if effect.get('textIconReferenceId') not in icons:
            continue
        text = entries.get(str(effect.get('descriptionId'))) or ''
        if '#1' in text and '#2' not in text and '#3' not in text:
            found.add(effect_id)
    return frozenset(found)


def _mask_monsters(mask):
    only, spared = [], []
    for part in (mask or '').split(','):
        match = _TARGET_MONSTER.match(part.strip())
        if match:
            (only if match.group(1) == 'F' else spared).append(int(match.group(2)))
    return only, spared


def target_monsters(mask, monsters, language):
    """'Artand' for a row its mask limits to F<id>, 'except Artand' for one kept off f<id>."""
    labels = []
    for ids in _mask_monsters(mask):
        names = []
        for monster_id in ids:
            name = (monsters or {}).get(monster_id)
            if name and name not in names:
                names.append(name)
        labels.append(', '.join(names))
    only, spared = labels
    if spared:
        spared = '%s %s' % (_EXCEPT.get(language, _EXCEPT['en']), spared)
    return ', '.join(label for label in (only, spared) if label) or None


def _targets_nobody(mask, monsters):
    only = _mask_monsters(mask)[0]
    return bool(only) and not any(monster_id in (monsters or {}) for monster_id in only)


def _join_groups(groups, language):
    colon, semicolon = _SEPARATORS.get(language, _DEFAULT_SEPARATORS)
    text = semicolon.join('%s%s%s' % (label, colon, ', '.join(lines)) if label
                          else ', '.join(lines) for label, lines in groups)
    if groups and groups[0][0]:
        text = text[:1].upper() + text[1:]
    return text or None


def grade_description(level, effects, entries, monsters, language='en',
                      summons=_SUMMON_EFFECTS):
    """One spell grade's effect rows in one line, under the monsters they target, or None."""
    groups = []
    for row in (level.get('effects') or {}).get('Array') or []:
        if not isinstance(row, dict) or _targets_nobody(row.get('targetMask'), monsters):
            continue
        effect_id = effect_id_of(row)
        effect = effects.get(effect_id) or {}
        names = monsters if effect_id in summons else None
        line = render_effect(entries.get(str(effect.get('descriptionId'))),
                             row.get('diceNum'), row.get('diceSide'), names)
        if not line:
            continue
        label = target_monsters(row.get('targetMask'), monsters, language)
        lines = next((lines for target, lines in groups if target == label), None)
        if lines is None:
            lines = []
            groups.append((label, lines))
        if line not in lines:
            lines.append(line)
    return _join_groups(groups, language)


def _prose(spell, entries):
    return strip_display_markup(entries.get(str(spell.get('descriptionId'))) or '')


def _grade_texts(spell, levels, effects, entries, monsters, language, summons):
    """[(grade, text)] in level order; a grade without text reads the grades it casts or draws."""
    graded = []
    for level_id in (spell.get('spellLevels') or {}).get('Array') or []:
        level = levels.get(level_id) or {}
        graded.append((level.get('grade'), level, grade_description(
            level, effects, entries, monsters, language, summons)))
    by_grade = {grade: (level, text) for grade, level, text in graded if grade is not None}
    colon, semicolon = _SEPARATORS.get(language, _DEFAULT_SEPARATORS)

    def relayed(grade, seen):
        level, text = by_grade[grade]
        if text:
            return text
        chances = {}
        for row in (level.get('effects') or {}).get('Array') or []:
            if not isinstance(row, dict):
                continue
            target = row.get('diceSide')
            effect = effects.get(effect_id_of(row)) or {}
            if (row.get('diceNum') == spell.get('id') and target in by_grade
                    and target not in seen and (row.get('triggers') or 'I') == 'I'
                    and (entries.get(str(effect.get('descriptionId'))) or '').strip() == '#1'):
                chances[target] = chances.get(target, 0) + (row.get('random') or 0)
        if len(chances) == 1:
            return relayed(next(iter(chances)), seen | set(chances))
        if not chances or not all(chances.values()):
            return None
        parts = []
        for target, chance in chances.items():
            text = relayed(target, seen | {target})
            if text:
                parts.append('%d%%%s%s' % (round(chance), colon, text))
        return semicolon.join(parts) or None

    return [(grade, relayed(grade, {grade}) if grade is not None else text)
            for grade, _level, text in graded]


def spell_description(spell, levels, effects, entries, monsters, language='en',
                      summons=_SUMMON_EFFECTS):
    """What a monster spell does, in one line: Ankama's prose description, or
    failing that the effect rows of the spell's first grade."""
    prose = _prose(spell, entries)
    if prose:
        return prose
    return next((text for _grade, text in _grade_texts(
        spell, levels, effects, entries, monsters, language, summons) if text), None)


def grade_descriptions(spell, levels, effects, entries, monsters, language='en',
                       summons=_SUMMON_EFFECTS):
    """{spell grade: text} when the grades of a spell without prose read differently, else {}."""
    if _prose(spell, entries):
        return {}
    by_grade = {grade: text for grade, text in _grade_texts(
        spell, levels, effects, entries, monsters, language, summons) if grade is not None}
    if len(set(by_grade.values())) < 2:
        return {}
    return {grade: text for grade, text in by_grade.items() if text}


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

    for table in ('monster_spells', 'monster_spell_names', 'monster_spell_levels',
                  'monster_spell_grade_descriptions'):
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
    cursor.execute("""
        CREATE TABLE monster_spell_grade_descriptions (
            spell_ankama_id INTEGER NOT NULL,
            grade INTEGER NOT NULL,
            language TEXT NOT NULL,
            description TEXT NOT NULL,
            PRIMARY KEY (spell_ankama_id, grade, language)
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

    summons = summon_effects(effects, labels['en'])
    named = priced = graded = 0
    for spell_id in sorted(used):
        spell = spells.get(spell_id)
        if not spell:
            continue
        name_id = str(spell.get('nameId'))
        for language in LANGUAGES:
            name = labels[language].get(name_id)
            if not name:
                continue
            reading = (spell, levels, effects, labels[language], monster_names[language],
                       language, summons)
            cursor.execute(
                'INSERT OR REPLACE INTO monster_spell_names VALUES (?, ?, ?, ?)',
                (spell_id, language, clean_display_name(name),
                 clean_description(spell_description(*reading))))
            named += 1
            for grade, text in sorted(grade_descriptions(*reading).items()):
                text = clean_description(text)
                if text:
                    cursor.execute(
                        'INSERT OR REPLACE INTO monster_spell_grade_descriptions '
                        'VALUES (?, ?, ?, ?)', (spell_id, grade, language, text))
                    graded += 1
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
    print('stored %d monster spells, %d names, %d grades, %d grade descriptions'
          % (linked, named, priced, graded))
    if unknown:
        print('skipped %d spell ids the dump does not describe: %s'
              % (len(unknown), ', '.join(str(i) for i in sorted(unknown)[:10])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
