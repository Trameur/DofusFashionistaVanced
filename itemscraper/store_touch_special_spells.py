#!/usr/bin/env python
# coding=utf-8

"""Add Dofus Touch "special spell" tooltip lines to items_touch.db.

Some items cast a spell at the start of combat (effect 2822, "Lance le sort #1 au
debut du combat" / "Casts spell #1 at the start of combat") -- e.g. several Dofus
and shields. The Touch data carries this as a raw effect whose diceNum is the cast
spell's id, so we resolve the spell name (per language) and store the formatted
line in the extra_lines table, the same place get_equipments3 puts Dofus 3's
"-special spell-" lines. The encyclopedia / solution then show it like any other
version.
"""

import json
import os
import pickle
import sys

import requests

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

from store_item_obtainment import (  # noqa: E402
    get_items_db_path, _open_items_db, _save_db_to_dump, _resolve_item_id, _table_exists)

GAME_VERSION = 'touch'
LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']
RAW_DIR = os.path.join(CURRENT_DIRECTORY, 'touch_raw')
CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json"
FALLBACK_DATA_URL = "https://dt-proxy-production-login.ankama-games.com"
UA = "Dofus/2 CFNetwork"

# effect id -> (field holding the cast spell id, placeholder in the description).
# 722, "Permet l'utilisation du sort: #3", is deliberately absent: the four spell
# ids it points at on the Dofushu and the Cog of Infinity (21952, 24126, 24284,
# 24286) are in none of the 7455 spells the backend serves, so the line could
# only be printed with a bare number in place of a name.
CAST_SPELL_EFFECTS = {2822: ('diceNum', '#1')}

# The class Emblems and a handful of weapons carry no characteristic, only a
# modifier on one named spell, so their page was blank. Same effects as the 1.29
# spell hats; here the backend hands us the sentence in all five languages, so
# nothing has to be worded by hand. The spell id sits in diceNum and the amount
# in value: "Emblème Féca : Héroïsme" reduces spell 6801's cooldown by 2.
SPELL_MODIFIER_EFFECTS = set(range(281, 292))


def _data_url():
    try:
        cfg = requests.get(CONFIG_URL + '?lang=fr', headers={'User-Agent': UA}, timeout=30).json()
        return (cfg.get('dataUrl') or FALLBACK_DATA_URL).rstrip('/')
    except Exception:
        return FALLBACK_DATA_URL


def _fetch(data_url, cls, lang):
    return requests.post(f"{data_url}/data/map", json={'class': cls, 'lang': lang},
                         headers={'User-Agent': UA, 'Accept': 'application/json'},
                         timeout=180).json()


def main():
    items = json.loads(open(os.path.join(RAW_DIR, 'Items_fr.json'), encoding='utf-8').read())
    data_url = _data_url()
    spells = {lang: _fetch(data_url, 'Spells', lang) for lang in LANGUAGES}
    effects = {lang: _fetch(data_url, 'Effects', lang) for lang in LANGUAGES}

    # item ankama id -> {lang: [formatted lines]}
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
                lines_by_item.setdefault(int(ankama_id), {}).setdefault(lang, []).append(line)

    conn = _open_items_db(GAME_VERSION)
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

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    print('[touch] Stored special-spell lines for %d items.' % len(lines_by_item))


if __name__ == '__main__':
    main()
