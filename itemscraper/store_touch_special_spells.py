#!/usr/bin/env python
# coding=utf-8

"""Add Dofus Touch "special spell" tooltip lines to items_touch.db.

Effect 2822 ("Casts spell #1 at the start of combat") carries the cast spell's
id in diceNum. The resolved line is stored per language in extra_lines, where
get_equipments3 also puts Dofus 3's "-special spell-" lines.
"""

import argparse
import json
import os
import pickle
import re
import sys

import requests

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

from store_item_obtainment import (  # noqa: E402
    get_items_db_path, _open_items_db, _save_db_to_dump, _resolve_item_id, _table_exists)
from get_equipments_touch import _top_level_parts  # noqa: E402
import touch_channels  # noqa: E402
from untranslated_tag import clean_display_name  # noqa: E402

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']
CONFIG_URL = touch_channels.config_url('login')
FALLBACK_DATA_URL = touch_channels.fallback_data_url('login')
UA = "Dofus/2 CFNetwork"

# effect id -> (field holding the cast spell id, placeholder in the description).
# Effect 722's spell ids (Dofushu, Cog of Infinity) are in no backend spell,
# so it has no entry here.
CAST_SPELL_EFFECTS = {2822: ('diceNum', '#1')}

# Modifiers on one named spell (the class Emblems, a few weapons): spell id in
# diceNum, amount in value.
SPELL_MODIFIER_EFFECTS = set(range(281, 292))

# Equip condition "Pt=<spell level id>": the spell must be at that rank
SPELL_RANK_CRITERION = re.compile(r'\s*Pt\s*=\s*(\d+)\s*')


def _data_url(channel=touch_channels.DEFAULT_CHANNEL):
    try:
        cfg = requests.get(touch_channels.config_url(channel) + '?lang=fr',
                           headers={'User-Agent': UA}, timeout=30).json()
        return (cfg.get('dataUrl') or touch_channels.fallback_data_url(channel)).rstrip('/')
    except Exception:
        return touch_channels.fallback_data_url(channel)


def _fetch(data_url, cls, lang):
    return requests.post(f"{data_url}/data/map", json={'class': cls, 'lang': lang},
                         headers={'User-Agent': UA, 'Accept': 'application/json'},
                         timeout=180).json()


def spell_rank_conditions(items, spells, spell_levels):
    """{item ankama id: [(spell id, rank, player level of that rank)]} from the Pt= parts."""
    out = {}
    for ankama_id, it in items.items():
        if not isinstance(it, dict):
            continue
        for part in _top_level_parts(str(it.get('criteria') or '')):
            match = SPELL_RANK_CRITERION.fullmatch(part)
            if not match:
                continue
            level_id = int(match.group(1))
            spell_level = spell_levels.get(str(level_id)) or {}
            spell = spells.get(str(spell_level.get('spellId'))) or {}
            ranks = [int(rank) for rank in spell.get('spellLevels') or []]
            if level_id not in ranks:
                print('  ! item %s asks for spell level %s, which no spell lists'
                      % (ankama_id, level_id))
                continue
            out.setdefault(int(ankama_id), []).append(
                (int(spell['id']), ranks.index(level_id) + 1,
                 int(spell_level.get('minPlayerLevel') or 1)))
    return out


def store_spell_rank_conditions(cursor, conditions):
    cursor.execute("DROP TABLE IF EXISTS item_spell_conditions")
    cursor.execute("CREATE TABLE item_spell_conditions (item INTEGER, spell INTEGER,"
                   " rank INTEGER, min_level INTEGER)")
    stored = 0
    for ankama_id, rows in sorted(conditions.items()):
        item_id = _resolve_item_id(cursor, ankama_id, 'equipment')
        if item_id is None:
            continue
        for spell_id, rank, min_level in rows:
            cursor.execute("INSERT INTO item_spell_conditions VALUES (?, ?, ?, ?)",
                           (item_id, spell_id, rank, min_level))
            stored += 1
    return stored


def special_spell_lines(items, spells, effects):
    """{item ankama id: {lang: [lines]}} of the cast-spell and spell-modifier effects."""
    lines_by_item = {}
    for ankama_id, it in items.items():
        if not isinstance(it, dict):
            continue
        for pe in (it.get('possibleEffects') or []):
            effect_id = pe.get('effectId')
            spec = CAST_SPELL_EFFECTS.get(effect_id)
            is_modifier = effect_id in SPELL_MODIFIER_EFFECTS
            if not spec and not is_modifier:
                continue
            field, placeholder = spec if spec else ('diceNum', '#1')
            spell_id = str(pe.get(field) or '')
            for lang in LANGUAGES:
                spell = (spells[lang].get(spell_id) or {}).get('nameId')
                template = (effects[lang].get(str(effect_id)) or {}).get('descriptionId')
                if not spell or not template:
                    continue
                line = template.replace(placeholder, spell)
                if is_modifier:
                    line = line.replace('#3', str(pe.get('value') or 0))
                lines_by_item.setdefault(int(ankama_id), {}).setdefault(lang, []).append(
                    clean_display_name(line))
    return lines_by_item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    touch_channels.add_channel_argument(parser)
    args = parser.parse_args(argv)
    game_version = touch_channels.game_version(args.channel)
    raw_dir = touch_channels.raw_dir(args.channel)
    items = json.loads(open(os.path.join(raw_dir, 'Items_fr.json'), encoding='utf-8').read())
    data_url = _data_url(args.channel)
    spells = {lang: _fetch(data_url, 'Spells', lang) for lang in LANGUAGES}
    effects = {lang: _fetch(data_url, 'Effects', lang) for lang in LANGUAGES}
    spell_levels = _fetch(data_url, 'SpellLevels', 'fr')
    lines_by_item = special_spell_lines(items, spells, effects)

    conn = _open_items_db(game_version)
    cursor = conn.cursor()
    if not _table_exists(cursor, 'extra_lines'):
        cursor.execute("CREATE TABLE extra_lines (item INTEGER, line text, language text)")

    stored = 0
    for ankama_id, by_lang in lines_by_item.items():
        item_id = _resolve_item_id(cursor, ankama_id, 'equipment')
        if item_id is None:
            continue
        cursor.execute("DELETE FROM extra_lines WHERE item = ?", (item_id,))
        for lang, lines in by_lang.items():
            cursor.execute("INSERT INTO extra_lines VALUES (?, ?, ?)",
                           (item_id, pickle.dumps(lines), lang))
            stored += 1

    ranks_stored = store_spell_rank_conditions(
        cursor, spell_rank_conditions(items, spells['fr'], spell_levels))

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(game_version), game_version)
    print('[%s] Stored special-spell lines for %d items.' % (game_version, len(lines_by_item)))
    print('[%s] Stored %d spell rank conditions.' % (game_version, ranks_stored))


if __name__ == '__main__':
    main()
