#!/usr/bin/env python

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

import json
import sqlite3

from fashionistapulp.translation import NON_EN_LANGUAGES, LANGUAGES
from fashionistapulp.fashionista_config import (get_items_db_path, load_items_db_from_dump,
                                                save_items_db_to_dump) 


def main(json_file, names_table, entities_table):
    id_to_terms_in_lang, en_name_to_ankama_id_and_type = read_id_to_terms(json_file, entities_table)
    ankama_profile_to_all_dict, en_to_all_dict = convert_to_dicts(id_to_terms_in_lang)
    
    load_items_db_from_dump()
    conn = sqlite3.connect(get_items_db_path())
    c = conn.cursor()
    
    for ankama_profile, other_langs in ankama_profile_to_all_dict.items():
        ankama_id, _ = ankama_profile
        if len(other_langs) != len(NON_EN_LANGUAGES):
            print(('WARNING: item with ankama_id %d missing languages: %s'
                   % (ankama_id, str(other_langs))))
        item_id, _ = get_item_id_and_name_for_ankama_profile(c, entities_table, ankama_profile)
        if item_id is not None:
            store_item_translations(c, names_table, item_id, other_langs)

    for en_term, other_langs in en_to_all_dict.items():
        if len(other_langs) != len(NON_EN_LANGUAGES):
            print('WARNING: %s missing languages: %s' % (en_term, str(other_langs)))
        c.execute('SELECT id, ankama_id FROM %s WHERE name = ?' % entities_table, (en_term,))
        query_result = c.fetchone()
        if query_result is not None:
            ankama_id = query_result[1]
            if ankama_id is None:
                print('ankama_id of %s is None, using en name to update' % en_term)
                item_id = query_result[0]
                store_item_translations(c, names_table, item_id, other_langs)
                ankama_id, ankama_type = en_name_to_ankama_id_and_type[en_term]
                c.execute('UPDATE %s SET ankama_id = ?, ankama_type = ? WHERE ID = ?' % entities_table,
                          (ankama_id, ankama_type, item_id))
        
    conn.commit()
    conn.close()
    save_items_db_to_dump()

def get_item_id_and_name_for_ankama_profile(c, entities_table, ankama_profile, touch=False):
    if ankama_profile[1] == 'set':
        c.execute('SELECT id, name FROM %s WHERE ankama_id = ?' % entities_table,
                  (ankama_profile[0],))
    else:
        if touch:
            c.execute('SELECT id, name FROM %s WHERE ankama_id = ? AND ankama_type = ? and dofustouch = ?' % entities_table,
                      (ankama_profile[0], ankama_profile[1], 1))
        else:
            c.execute('SELECT id, name FROM %s WHERE ankama_id = ? AND ankama_type = ?' % entities_table,
                      (ankama_profile[0], ankama_profile[1]))
    query_result = c.fetchone()
    if query_result is not None:
        return query_result[0], query_result[1]
    else:
        return None, None

def store_item_translations(c, names_table, item_id, other_langs):
    column_name = 'item'
    if names_table == 'set_names':
        column_name = 'item_set'
    
    for lang, term in other_langs.items():
        c.execute('SELECT name FROM %s WHERE %s = ? AND language = ?' % (names_table, column_name),
                  (item_id, lang))

        query_result = c.fetchone()
        if query_result is None:
            c.execute('INSERT INTO %s VALUES (?, ?, ?)' % names_table,
                      (item_id, lang, term))
        else:
            stored_term = query_result[0]
            if stored_term != term:
                c.execute('UPDATE %s SET name = ? WHERE %s = ? AND language = ?' % (names_table, column_name),
                          (term, item_id, lang))
                print('Switching %s name for id %d from %s to %s' % (lang, item_id, stored_term, term))

def read_id_to_terms(filename, table):
    id_to_terms_in_lang = {lang: {} for lang in LANGUAGES}
    en_name_to_ankama_id_and_type = {}
    with open(filename) as f:
        pool = json.load(f)
        for entry in pool:
            url = entry['url']
            term = entry['localized_name']
            pieces = url.split('/')
            lang = pieces[3]
            if lang not in id_to_terms_in_lang:
                continue  # skip unsupported languages (e.g. Italian, removed by Ankama)
            ankama_id = int(pieces[7].split('-')[0])
            item_type = pieces[6]
            if table != 'sets':
                ankama_type = get_ankama_type(lang, item_type)
            else:
                ankama_type = 'set'
            if lang == 'en':
                en_name_to_ankama_id_and_type[term] = (ankama_id, ankama_type)
            id_to_terms_in_lang[lang][(ankama_id, ankama_type)] = term
    return id_to_terms_in_lang, en_name_to_ankama_id_and_type


def get_ankama_type(lang, item_type):
    CONVERTER = {'en':
                 {'pets': 'pet',
                  'mounts': 'mount',
                  'equipment': 'equipment'},
                 'fr':
                 {'familiers': 'pet',
                  'montures': 'mount',
                  'equipements': 'equipment'},
                 'pt':
                 {'mascotes': 'pet',
                  'montarias': 'mount',
                  'equipamentos': 'equipment'},
                 'es':
                 {'mascotas': 'pet',
                  'monturas': 'mount',
                  'equipos': 'equipment'},
                 'de':
                 {'vertraute': 'pet',
                  'reittiere': 'mount',
                  'ausruestung': 'equipment'}}

    return CONVERTER[lang][item_type]
                    
def convert_to_dicts(id_to_terms):
    ankama_profile_to_all_dict = {}
    en_to_all_dict = {}
    for ankama_profile, en_term in id_to_terms['en'].items():
        entry = {}
        for lang in NON_EN_LANGUAGES:
            term_in_lang = id_to_terms[lang].get(ankama_profile)
            if term_in_lang is None:
                print('%s %s does not exist in %s' % (ankama_profile, en_term, lang))
            else:
                entry[lang] = term_in_lang
        en_to_all_dict[en_term] = entry
        if ankama_profile:
            ankama_profile_to_all_dict[ankama_profile] = entry
    return ankama_profile_to_all_dict, en_to_all_dict

if __name__ == '__main__':
    main('itemscraper/rosetta269.json', 'item_names', 'items')
    # main('itemscraper/rosetta_16100_16400.json', 'item_names', 'items')
    # main('itemscraper/rosetta_mounts.json', 'item_names', 'items')
    #main('itemscraper/rosettahoy2.json', 'set_names', 'sets')
