#!/usr/bin/env python
# coding=utf-8

"""Store what the spells named on an item do, into spell_tooltips.

    python store_spell_tooltips.py --game-version dofus3|beta|dofus2|retro|touch
"""

import argparse
import json
import os
import pickle
import re
import sys
from functools import lru_cache

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY,
             os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

from fashionistapulp.game_versions import dofus_versions  # noqa: E402
from store_item_obtainment import (  # noqa: E402
    get_items_db_path, _open_items_db, _save_db_to_dump, _resolve_item_id,
    _table_exists)

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']

# Equipment dump directory per version
EQUIPMENT_DIR = {'dofus3': '', 'beta': 'beta', 'dofus2': 'dofus2'}


def _load(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def _items_of(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get('items') or list(payload.values())
    return []


@lru_cache(maxsize=4096)
def _names_it(name):
    """The name as a whole word."""
    return re.compile(r'(?<!\w)%s(?!\w)' % re.escape(name))


def _clean(text):
    """A description worth showing, or None. "[!]" tags an untranslated one."""
    text = (text or '').strip()
    if not text or text.startswith('[!]'):
        return None
    return re.sub(r'\s*\n\s*', ' ', text)


def _datacenter_spells(raw_dir):
    """{spell id: {lang: (name, description)}} from a Dofus 3 style archive."""
    from get_spells import _load_datacenter_table, _load_translations
    from pathlib import Path
    root = Path(raw_dir)
    spells = _load_datacenter_table(root / 'spells.json')
    texts = _load_translations(root, LANGUAGES)
    out = {}
    for spell_id, spell in spells.items():
        by_lang = {}
        for lang in LANGUAGES:
            entries = texts.get(lang) or {}
            name = entries.get(str(spell.get('nameId')))
            description = _clean(entries.get(str(spell.get('descriptionId'))))
            if name and description:
                by_lang[lang] = (name, description)
        if by_lang:
            out[spell_id] = by_lang
    return out


def _dofus2_spells(raw_dir):
    """Same, for the 2.73 archive: a flat spell list and a 'texts' map."""
    spells = _load(os.path.join(raw_dir, 'spells.json'))
    if isinstance(spells, dict):
        spells = spells.get('spells') or list(spells.values())
    texts = {}
    for lang in LANGUAGES:
        payload = _load(os.path.join(raw_dir, '%s.json' % lang))
        texts[lang] = payload.get('texts') or {}
    out = {}
    for spell in spells:
        if not isinstance(spell, dict) or spell.get('id') is None:
            continue
        by_lang = {}
        for lang in LANGUAGES:
            entries = texts[lang]
            name = entries.get(str(spell.get('nameId')))
            description = _clean(entries.get(str(spell.get('descriptionId'))))
            if name and description:
                by_lang[lang] = (name, description)
        if by_lang:
            out[int(spell['id'])] = by_lang
    return out


def _dofusdude_tooltips(game_version, spells_by_id):
    """{item ankama id: {lang: {spell name: description}}}"""
    directory = os.path.join(CURRENT_DIRECTORY, EQUIPMENT_DIR[game_version])
    tooltips = {}
    for lang in LANGUAGES:
        path = os.path.join(directory, 'all_equipment_%s.json' % lang)
        if not os.path.exists(path):
            continue
        for item in _items_of(_load(path)):
            if not isinstance(item, dict):
                continue
            ankama_id = item.get('ankama_id')
            if ankama_id is None:
                continue
            for effect in item.get('effects') or []:
                # int_minimum is reused by the API, 0 means no spell (not Punch)
                spell_id = effect.get('int_minimum')
                if not spell_id:
                    continue
                entry = (spells_by_id.get(spell_id) or {}).get(lang)
                if not entry:
                    continue
                name, description = entry
                # The sentence must name the spell (de: Nahkampf is also a plain word)
                if not _names_it(name).search(effect.get('formatted') or ''):
                    continue
                (tooltips.setdefault(int(ankama_id), {})
                         .setdefault(lang, {}))[name] = description
    return tooltips


def _retro_tooltips():
    from pathlib import Path
    from get_equipments_retro import SPELL_EFFECT_TEMPLATES, _hex
    raw_dir = Path(CURRENT_DIRECTORY) / 'retro_raw'
    spells = {}
    for lang in LANGUAGES:
        path = raw_dir / ('spells_%s.json' % lang)
        if not path.exists():
            continue
        for sid, spell in (json.loads(path.read_text(encoding='utf-8'))
                           .get('S') or {}).items():
            if not isinstance(spell, dict):
                continue
            name, description = spell.get('n'), _clean(spell.get('d'))
            if not name or not description:
                continue
            try:
                spells.setdefault(int(sid), {})[lang] = (name, description)
            except (TypeError, ValueError):
                continue

    # items_<lang>.json carries no istats; they live in itemstats_<lang>.json.
    stats = _load(raw_dir / 'itemstats_fr.json')['ISTA']
    tooltips = {}
    for ankama_id, ista in stats.items():
        for part in (ista or '').split(','):
            fields = part.split('#')
            if _hex(fields[0]) not in SPELL_EFFECT_TEMPLATES:
                continue
            spell_id = _hex(fields[1]) if len(fields) > 1 and fields[1] else None
            for lang, (name, description) in (spells.get(spell_id) or {}).items():
                try:
                    item_id = int(ankama_id)
                except (TypeError, ValueError):
                    continue
                (tooltips.setdefault(item_id, {})
                         .setdefault(lang, {}))[name] = description
    return tooltips


# Words a trigger adds to a Touch spell row; rows with other triggers than I are skipped
TOUCH_TRIGGER_TAILS = {
    'DI': {'fr': 'de la part des invocations', 'en': 'from summons',
           'es': 'de las invocaciones', 'pt': 'das invocações',
           'de': 'durch Beschwörungen'},
}


def touch_spell_effects(spell, spell_levels, effects, monster_names, text_lang):
    """Text for a Touch spell with no description, from its first grade, or None."""
    from store_monster_spells import _SUMMON_EFFECTS, render_effect
    level_ids = spell.get('spellLevels') or []
    level = spell_levels.get(str(level_ids[0])) if level_ids else None
    rendered = []
    for row in (level or {}).get('effects') or []:
        trigger = row.get('triggers') or 'I'
        if row.get('hidden') or (trigger != 'I'
                                 and trigger not in TOUCH_TRIGGER_TAILS):
            continue
        effect_id = row.get('effectId')
        template = (effects.get(str(effect_id)) or {}).get('descriptionId')
        if not template or ('#1' in template and not row.get('diceNum')):
            continue
        names = monster_names if effect_id in _SUMMON_EFFECTS else None
        line = render_effect(template, row.get('diceNum'), row.get('diceSide'),
                             names)
        if not line:
            continue
        if trigger != 'I':
            line = '%s %s' % (line, TOUCH_TRIGGER_TAILS[trigger][text_lang])
        if row.get('random'):
            line = '%s (%d%%)' % (line, row['random'])
        if line not in rendered:
            rendered.append(line)
    return ', '.join(rendered) or None


def _touch_tooltips():
    import requests
    from download_touch_data import served_languages
    from store_touch_special_spells import (
        CAST_SPELL_EFFECTS, SPELL_MODIFIER_EFFECTS, _data_url, _fetch)
    items = _load(os.path.join(CURRENT_DIRECTORY, 'touch_raw', 'Items_fr.json'))
    data_url = _data_url()
    spells = {lang: _fetch(data_url, 'Spells', lang) for lang in LANGUAGES}
    # Touch answers unserved languages in English: read serverLanguages first
    served = served_languages()
    loaded = {}

    def effects_of(spell, lang):
        text_lang = lang if not served or lang in served else 'en'
        if 'levels' not in loaded:
            loaded['levels'] = _fetch(data_url, 'SpellLevels', 'fr')
        if lang not in loaded:
            monsters = _load(os.path.join(CURRENT_DIRECTORY, 'touch_raw',
                                          'Monsters_%s.json' % text_lang))
            loaded[lang] = (_fetch(data_url, 'Effects', lang), {
                int(monster_id): monster['nameId']
                for monster_id, monster in monsters.items()
                if isinstance(monster, dict) and monster.get('nameId')})
        effects, monster_names = loaded[lang]
        return touch_spell_effects(spell, loaded['levels'], effects,
                                   monster_names, text_lang)

    tooltips = {}
    for ankama_id, item in items.items():
        if not isinstance(item, dict):
            continue
        for effect in item.get('possibleEffects') or []:
            effect_id = effect.get('effectId')
            if (effect_id not in CAST_SPELL_EFFECTS
                    and effect_id not in SPELL_MODIFIER_EFFECTS):
                continue
            spell_id = str(effect.get('diceNum') or '')
            for lang in LANGUAGES:
                spell = spells[lang].get(spell_id) or {}
                name = spell.get('nameId')
                description = _clean(spell.get('descriptionId'))
                if name and not description:
                    description = effects_of(spell, lang)
                if not name or not description:
                    continue
                (tooltips.setdefault(int(ankama_id), {})
                         .setdefault(lang, {}))[name] = description
    return tooltips


def collect(game_version, tag=None):
    if game_version in ('dofus3', 'beta'):
        raw = os.path.join(CURRENT_DIRECTORY, 'raw', tag or _archive_tag(game_version))
        return _dofusdude_tooltips(game_version, _datacenter_spells(raw))
    if game_version == 'dofus2':
        raw = os.path.join(CURRENT_DIRECTORY, 'raw', tag or _archive_tag(game_version))
        return _dofusdude_tooltips(game_version, _dofus2_spells(raw))
    if game_version == 'retro':
        return _retro_tooltips()
    if game_version == 'touch':
        return _touch_tooltips()
    raise SystemExit('unknown game version: %s' % game_version)


def _archive_tag(game_version):
    """The archive this version is on. Beta and Dofus 3 share raw/."""
    import fashionista_version
    return {'dofus3': fashionista_version.FASHIONISTA_VERSION,
            'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
            'dofus2': fashionista_version.FASHIONISTA_DOFUS2_VERSION}[game_version]


def _lines_of(cursor, item_id, language):
    rows = cursor.execute(
        'SELECT line FROM extra_lines WHERE item = ? AND language = ?',
        (item_id, language)).fetchall()
    lines = []
    for row in rows:
        blob = row[0]
        if isinstance(blob, str):
            blob = blob.encode()
        try:
            lines.extend(pickle.loads(blob))
        except Exception:
            continue
    return lines


def store(game_version, tooltips):
    conn = _open_items_db(game_version)
    cursor = conn.cursor()
    if not _table_exists(cursor, 'spell_tooltips'):
        cursor.execute('CREATE TABLE spell_tooltips '
                       '(item INTEGER, language text, tooltips text)')
    cursor.execute('DELETE FROM spell_tooltips')
    stored = items = 0
    for ankama_id, by_lang in tooltips.items():
        item_id = _resolve_item_id(cursor, ankama_id, 'equipment')
        if item_id is None:
            continue
        kept_any = False
        for lang, by_name in by_lang.items():
            # Only spells a line names
            text = '\n'.join(_lines_of(cursor, item_id, lang))
            kept = {name: description for name, description in by_name.items()
                    if name in text}
            if not kept:
                continue
            cursor.execute('INSERT INTO spell_tooltips VALUES (?, ?, ?)',
                           (item_id, lang, pickle.dumps(kept)))
            stored += 1
            kept_any = True
        items += 1 if kept_any else 0
    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(game_version), game_version)
    return items, stored


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=dofus_versions())
    parser.add_argument('--tag', default=None,
                        help='archive under itemscraper/raw to read')
    args = parser.parse_args(argv)
    tooltips = collect(args.game_version, args.tag)
    items, stored = store(args.game_version, tooltips)
    print('[%s] Stored spell tooltips for %d items, %d rows (%d items had a '
          'spell to look up).' % (args.game_version, items, stored, len(tooltips)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
