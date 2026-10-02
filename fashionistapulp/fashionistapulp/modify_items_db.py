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

import pickle
import sqlite3

from fashionistapulp.fashionista_config import save_items_db_to_dump, get_items_db_path
from fashionistapulp.structure import get_structure, invalidate_structure
from fashionistapulp.translation import NON_EN_LANGUAGES
from fashionistapulp.dofus_constants import WEIRD_CONDITIONS, WEIRD_CONDITION_TO_ID


def update_item(old, new, new_weapon, invalidate):
    structure = get_structure()
    
    if new.ankama_id:
        if int(new.ankama_id) != old.ankama_id:
            print('Changing %s\'s Ankama ID from %s to %s' % (old.name,
                                                              old.ankama_id,
                                                              new.ankama_id))
            modify_item_ankama_id(old.id, new.ankama_id)
    
    if new.ankama_type != old.ankama_type:
        print('Changing %s\'s Ankama type from %s to %s' % (old.name,
                                                            old.ankama_type,
                                                            new.ankama_type))
        modify_item_ankama_type(old.id, new.dofus_touch)
        
    if new.dofus_touch != old.dofus_touch:
        if new.dofus_touch:
            print(' %s is now a Dofus Touch item' % (old.name))
        else:
            print(' %s is no longer a Dofus Touch item' % (old.name))
        modify_item_dofus_touch(old.id, new.dofus_touch)
    
    if new.name != old.name:
#         filetomod = open('NameChanges.txt','a') 
#  
#         filetomod.write('%s: %s\n' % (old.name.encode('utf-8'), new.name.encode('utf-8'))) 
#          
#         print '%s TURNED INTO %s' % (old.name.encode('utf-8'), new.name.encode('utf-8'))
# 
#         filetomod.close() 
        exists = structure.get_item_by_name(new.name, new.dofus_touch)
        still_exists = False
        if exists:
            still_exists = exists.dofus_touch == new.dofus_touch
        if still_exists:
            print('The item %s already exists in the database' % (new.name))
            return False
        
    if int(new.level) != old.level:
        print('Changing %s\'s level from %d to %s' % (old.name, old.level, new.level))
        modify_item_level(old.id, new.level)
    
    if new.removed != old.removed:
        if new.removed == True:
            print('Setting %s as removed' % (new.name))
            fake_delete_item(old.id, True)
        else:
            print('Setting %s as not removed' % (new.name))
            fake_delete_item(old.id, False)
       
    if new.type != old.type:
        print('Changing %s\'s type from %s to %s' % (old.name, 
                                                      structure.get_type_name_by_id(old.type), 
                                                      structure.get_type_name_by_id(new.type)))
        modify_item_type(old.id, new.type)
        if structure.get_type_name_by_id(old.type) == 'Weapon':
            print('Removing weapon data from %s' % (old.name))
            delete_weapon(old.id)
       
    if new.set != old.set:
        old_set_name = structure.get_set_by_id(old.set).name if old.set else 'None'
        new_set_name = structure.get_set_by_id(new.set).name if new.set else 'None'
        print('Changing %s\'s set from %s to %s' % (old.name, 
                                                     old_set_name,
                                                     new_set_name))
        modify_item_set(old.id, new.set)
    if new.set == '' and old.set != None:
        print('Removing set from %s' % (old.name))
        modify_item_set(old.id, None)
    
    for wc in WEIRD_CONDITIONS:
        if new.weird_conditions[wc] != old.weird_conditions[wc]:
            modify_weird_condition(old.id, wc, new.weird_conditions[wc])
    
    for stat, stat_value in new.stats:
        old_value = _check_and_get_old_stat(old, stat)
        if old_value:
            if stat_value != old_value:
                print('Changing %s\'s  %s from %d to %s' % (old.name, 
                                                            structure.get_stat_by_id(stat).name,
                                                            old_value, 
                                                            stat_value))
                modify_item_stat(old.id, stat, stat_value)
        else:
            print('Adding %s %s to %s' % (stat_value,
                                          structure.get_stat_by_id(stat).name,
                                          old.name))
            add_item_stat(old.id, stat, stat_value)
    for old_stat, _ in old.stats:
        if not _check_if_new_has_stat(new, old_stat):
            if structure.get_stat_by_id(old_stat):
                print('Removing %s from %s' % (structure.get_stat_by_id(old_stat).name,
                                               old.name))
            else:
                print('Removing a stat from %s' % old.name)
            remove_item_stat(old.id, old_stat)
    
    for stat, value in new.min_stats_to_equip:
        old_value = _check_and_get_old_condition(old, stat, True)
        new_value = value
        if old_value:
            if new_value != old_value:
                print('Modifying %s\'s condition' % (old.name))
                modify_item_cond(old.id, stat, True, new_value)
        else:
            print('Adding condition to %s' % (old.name))
            add_item_cond(old.id, stat, True, new_value)
    for old_stat, _ in old.min_stats_to_equip:
        if not _check_if_new_has_condition(new, old_stat, True):
            print('Removing condition from %s' % (old.name))
            remove_item_cond(old.id, old_stat, True)
    for stat, value in new.max_stats_to_equip:
        old_value = _check_and_get_old_condition(old, stat, False)
        new_value = value
        if old_value:
            if new_value != old_value:
                print('Modifying %s\'s condition' % (old.name))
                modify_item_cond(old.id, stat, False, new_value)
        else:
            print('Adding condition to %s' % (old.name))
            add_item_cond(old.id, stat, False, new_value)
    for old_stat, _ in old.max_stats_to_equip:
        if not _check_if_new_has_condition(new, old_stat, False):
            print('Removing condition from %s' % (old.name))
            remove_item_cond(old.id, old_stat, False)
        
    for lang in NON_EN_LANGUAGES:
        if new.localized_names.get(lang) != old.localized_names.get(lang):
            print(('Localized name for %s in %s changed from %s to %s'
                   % (old.name,
                      lang,
                      old.localized_names.get(lang),
                      new.localized_names.get(lang))))
            modify_localized_name('item_names', 'item', old.id, lang,
                                  new.localized_names.get(lang))
    
    if new.localized_extras != old.localized_extras:
        print('Modifying %s\'s localized extras' % (old.name))
        modify_extras(old, new)
        
    if structure.get_type_name_by_id(new.type) == 'Weapon':
        if not structure.get_type_name_by_id(old.type) == 'Weapon':
            conn, cursor = _open_conn_get_cursor()
            _insert_weapon(new, new_weapon, old.id, cursor)
            _finish_editing(conn)
        else:
            old_weapon = structure.get_weapon_by_name(old.name, new.dofus_touch)
            
            if old_weapon == None:
                return 
            if new_weapon.ap != old_weapon.ap:
                print('Changing %s\'s AP cost from %d to %d' % (old.name, 
                                                               old_weapon.ap, 
                                                               new_weapon.ap))
                modify_item_ap(old.id, new_weapon.ap)
                
            if new_weapon.crit_chance != old_weapon.crit_chance:
                print('Changing %s\'s critical hit rate from %d to %d' % (old.name, 
                                                                         old_weapon.crit_chance if old_weapon.crit_chance else 0, 
                                                                         new_weapon.crit_chance if new_weapon.crit_chance else 0))
                modify_weapon_ch_rate(old.id, new_weapon.crit_chance)
            
            if new_weapon.crit_bonus != old_weapon.crit_bonus:
                print('Changing %s\'s critical hit bonus from %d to %d' % (old.name, 
                                                                          old_weapon.crit_bonus if old_weapon.crit_bonus else 0, 
                                                                          new_weapon.crit_bonus if new_weapon.crit_bonus else 0))
                modify_weapon_ch_bonus(old.id, new_weapon.crit_bonus)
            
#             if new.is_one_handed != old.is_one_handed:
#                 print 'Changing whether %s is one handed: from %r to %r' % (old.name, 
#                                                                            old.is_one_handed, 
#                                                                            new.is_one_handed)
#                 modify_one_handness(old.id, new.is_one_handed)
                
            if new_weapon.weapon_type != old_weapon.weapon_type:
                print('Changing %s\'s type from %s to %s' % (old.name, 
                                                            structure.get_weapon_type_by_id(old_weapon.weapon_type).name, 
                                                            structure.get_weapon_type_by_id(new_weapon.weapon_type).name))
                modify_weapon_type(old.id, new_weapon.weapon_type)
            
            last_index = 0;
            for index, hit in new_weapon.hits_dict.items():
                if index > last_index:
                    last_index = index
                if index in old_weapon.hits_dict:
                    if old_weapon.hits_dict[index].min_dam != new_weapon.hits_dict[index].min_dam:
                        print('Changing %s\'s hit number %d: minimum damage going from %d to %d' % (old.name, 
                                                                                                   index,
                                                                                                   old_weapon.hits_dict[index].min_dam, 
                                                                                                   new_weapon.hits_dict[index].min_dam))
                        modify_min_hit(old.id, index, new_weapon.hits_dict[index].min_dam)
                    if old_weapon.hits_dict[index].max_dam != new_weapon.hits_dict[index].max_dam:
                        print('Changing %s\'s hit number %d: maximum damage going from %d to %d' % (old.name, 
                                                                                                   index,
                                                                                                   old_weapon.hits_dict[index].max_dam, 
                                                                                                   new_weapon.hits_dict[index].max_dam))
                        modify_max_hit(old.id, index, new_weapon.hits_dict[index].max_dam)
                    if old_weapon.hits_dict[index].element != new_weapon.hits_dict[index].element:
                        print('Changing %s\'s hit number %d: element changing from %s to %s' % (old.name, 
                                                                                               index,
                                                                                               old_weapon.hits_dict[index].element, 
                                                                                               new_weapon.hits_dict[index].element))
                        modify_hit_element(old.id, index, new_weapon.hits_dict[index].element)
                    if old_weapon.hits_dict[index].heals != new_weapon.hits_dict[index].heals:
                        print('Changing %s\'s hit number %d: heals going from %r to %r' % (old.name, 
                                                                                          index,
                                                                                          old_weapon.hits_dict[index].heals, 
                                                                                          new_weapon.hits_dict[index].heals))
                        modify_hit_heals(old.id, index, new_weapon.hits_dict[index].heals)
                    if old_weapon.hits_dict[index].steals != new_weapon.hits_dict[index].steals:
                        print('Changing %s\'s hit number %d: steals going from %r to %r' % (old.name, 
                                                                                          index,
                                                                                          old_weapon.hits_dict[index].steals, 
                                                                                          new_weapon.hits_dict[index].steals))
                        modify_hit_steals(old.id, index, new_weapon.hits_dict[index].steals)
                else:
                    print('Adding hit number %d to %s:\nminimum damage: %d\nmaximum damage: %d\nelement: %s\nheals: %r\nsteals: %r' % (index,
                                              old.name,
                                              new_weapon.hits_dict[index].min_dam,
                                              new_weapon.hits_dict[index].max_dam, 
                                              new_weapon.hits_dict[index].element, 
                                              new_weapon.hits_dict[index].heals, 
                                              new_weapon.hits_dict[index].steals))     
                    add_hit(old.id, 
                            index, 
                            new_weapon.hits_dict[index].min_dam, 
                            new_weapon.hits_dict[index].max_dam, 
                            new_weapon.hits_dict[index].element, 
                            new_weapon.hits_dict[index].heals, 
                            new_weapon.hits_dict[index].steals)                           
            for index, hit in old_weapon.hits_dict.items():
                if index > last_index:
                    print('Removing hit number %d from %s' % (index, old.name))
                    remove_hit(old.id, index)
            
    if new.name != old.name:
        print('Changing %s\'s  name to %s' % (old.name, new.name))
        modify_item_name(old.id, new.name)
    
    if invalidate:
        invalidate_structure()
    return True

def modify_item_name(item_id, new_name):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET name = ? WHERE ID = ?', (new_name, item_id))   
    _finish_editing(conn)

def modify_item_level(item_id, new_level):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET level = ? WHERE ID = ?', (new_level, item_id))   
    _finish_editing(conn)

def modify_item_ankama_id(item_id, new_ankama_id):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET ankama_id = ? WHERE ID = ?', (new_ankama_id, item_id))   
    _finish_editing(conn)

def modify_item_ankama_type(item_id, new_ankama_type):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET ankama_type = ? WHERE ID = ?', (new_ankama_type, item_id))   
    _finish_editing(conn)
    
def modify_item_dofus_touch(item_id, dofus_touch):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET dofustouch = ? WHERE ID = ?', (1 if dofus_touch else None, item_id))   
    _finish_editing(conn)

def modify_item_type(item_id, new_type):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET type = ? WHERE ID = ?', (new_type, item_id))   
    _finish_editing(conn)
    
def modify_item_set(item_id, new_set):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET item_set = ? WHERE ID = ?', (new_set, item_id))   
    _finish_editing(conn)

def modify_weird_condition(item_id, weird_condition, new_value):
    conn, c = _open_conn_get_cursor()
    modify_weird_condition_with_cursor(c, item_id, weird_condition, new_value)
    _finish_editing(conn)

def modify_weird_condition_with_cursor(c, item_id, weird_condition, new_value):
    weird_condition_id = WEIRD_CONDITION_TO_ID[weird_condition]
    if new_value:
        c.execute('INSERT INTO item_weird_conditions VALUES (?, ?)',
                  (item_id, weird_condition_id))   
    else:
        c.execute('DELETE FROM item_weird_conditions WHERE item = ? AND condition_id = ?',
                  (item_id, weird_condition_id))

def modify_localized_name(table, key_column, object_id, lang, new_name):
    conn, c = _open_conn_get_cursor()
    if not new_name:
        c.execute('DELETE FROM %s WHERE %s = ? AND language = ?' % (table, key_column),
                  (object_id, lang))
    else:
        c.execute('SELECT * FROM %s WHERE %s = ? AND language = ?' % (table, key_column),
                  (object_id, lang))
        if c.fetchone() is None:
            c.execute('INSERT INTO %s VALUES (?, ?, ?)' % table, (object_id, lang, new_name))   
        else:
            c.execute('UPDATE %s SET name = ? WHERE %s = ? AND language = ?' % (table, key_column),
                      (new_name, object_id, lang))
    _finish_editing(conn)

def modify_extras(old, new):
    for lang, new_value in new.localized_extras.items():
        old_value = old.localized_extras.get(lang)
        if old_value:
            if new_value != old_value and new_value != None:
                print('Changing %s\'s  %s extra lines from "%s" to "%s"' % (old.name, 
                                                                            lang,
                                                                            old_value, 
                                                                            new_value))
                _modify_extra_for_lang(old.id, lang, new_value)
        elif new_value != None:
            print('Adding extra lines "%s" to %s in %s' % (new_value,
                                                           old.name,
                                                           lang))
            _add_extra_for_lang(old.id, lang, new_value)
    for lang, old_value in old.localized_extras.items():
        if new.localized_extras.get(lang) is None:
            print('Removing extra lines "%s" from %s in %s' % (old_value,
                                                               old.name,
                                                               lang))
            _remove_extra_for_lang(old.id, lang)

def _modify_extra_for_lang(item_id, lang, new_extras):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE extra_lines SET line = ? WHERE item = ? AND language = ?',
              (sqlite3.Binary(pickle.dumps(new_extras)), item_id, lang))
    _finish_editing(conn)

def _add_extra_for_lang(item_id, lang, new_extras):
    conn, c = _open_conn_get_cursor()
    c.execute('INSERT INTO extra_lines VALUES (?, ?, ?)',
              (item_id, sqlite3.Binary(pickle.dumps(new_extras)), lang)) 
    _finish_editing(conn)

def _remove_extra_for_lang(item_id, lang):
    conn, c = _open_conn_get_cursor()
    c.execute('DELETE FROM extra_lines WHERE item = ? AND language = ?',
              (item_id, lang)) 
    _finish_editing(conn)

def modify_item_stat(item_id, stat_id, value):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE stats_of_item SET value = ? WHERE item = ? AND stat = ?',
              (value, item_id, stat_id))   
    _finish_editing(conn)
    
def add_item_stat(item_id, stat_id, value):
    conn, c = _open_conn_get_cursor()
    c.execute("INSERT INTO stats_of_item (item, stat, value) VALUES (?,?,?)", (item_id, stat_id, value))
    _finish_editing(conn)
    
def remove_item_stat (item_id, stat_id):
    conn, c = _open_conn_get_cursor()
    c.execute('DELETE from stats_of_item WHERE item = ? AND stat = ?', (item_id, stat_id))   
    _finish_editing(conn)
    
def modify_item_cond(item_id, stat_id, is_min, value):
    conn, c = _open_conn_get_cursor()
    if is_min:
        c.execute('UPDATE min_stat_to_equip SET value = ? WHERE item = ? AND stat = ?', (value, item_id, stat_id))     
    else:
        c.execute('UPDATE max_stat_to_equip SET value = ? WHERE item = ? AND stat = ?', (value, item_id, stat_id)) 
    _finish_editing(conn)
    
def add_item_cond(item_id, stat_id, is_min, value):
    conn, c = _open_conn_get_cursor()
    if is_min:
        c.execute('INSERT INTO min_stat_to_equip (item, stat, value) VALUES (?,?,?)', (item_id, stat_id, value))     
    else:
        c.execute('INSERT INTO max_stat_to_equip (item, stat, value) VALUES (?,?,?)', (item_id, stat_id, value))
    _finish_editing(conn)
    
def remove_item_cond(item_id, stat_id, is_min):
    conn, c = _open_conn_get_cursor()
    if is_min:
        c.execute('DELETE from min_stat_to_equip WHERE item = ? AND stat = ?', (item_id, stat_id))     
    else:
        c.execute('DELETE from max_stat_to_equip WHERE item = ? AND stat = ?', (item_id, stat_id))     
    _finish_editing(conn)
    
def modify_item_ap(item_id, ap):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_ap SET value = ? WHERE item = ?', (ap, item_id))   
    _finish_editing(conn)
    
def modify_weapon_ch_rate(item_id, chance):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_crit_hits SET value = ? WHERE item = ?', (chance, item_id))   
    _finish_editing(conn)
    
def modify_weapon_ch_bonus(item_id, bonus):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_crit_bonus SET value = ? WHERE item = ?', (bonus, item_id))   
    _finish_editing(conn)
    
# def modify_one_handness(item_id, is_one_handed):
#     conn, c = _open_conn_get_cursor()
#     if is_one_handed:
#         c.execute('INSERT INTO weapon_is_onehanded (item, value) VALUES (?,?)', (item_id, 1))   
#     else:
#         c.execute('DELETE from weapon_is_onehanded WHERE item = ?', (item_id,)) 
#     _finish_editing(conn)
    
def modify_min_hit(item_id, hit_index, value):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_hits SET min_value = ? WHERE item = ? AND hit = ?', (value, item_id, hit_index))   
    _finish_editing(conn)
    
def modify_max_hit(item_id, hit_index, value):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_hits SET max_value = ? WHERE item = ? AND hit = ?', (value, item_id, hit_index))   
    _finish_editing(conn)

def modify_hit_element(item_id, hit_index, element):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_hits SET element = ? WHERE item = ? AND hit = ?', (element, item_id, hit_index))
    _finish_editing(conn)
    
def modify_hit_heals(item_id, hit_index, is_heals):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_hits SET heals = ? WHERE item = ? AND hit = ?', (1 if is_heals else 0, item_id, hit_index))
    _finish_editing(conn)
    
def modify_hit_steals(item_id, hit_index, is_steals):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_hits SET steals = ? WHERE item = ? AND hit = ?', (1 if is_steals else 0, item_id, hit_index))
    _finish_editing(conn)

def add_hit(item_id, hit_index, min_hit, max_hit, element, is_heals, is_steals):
    conn, c = _open_conn_get_cursor()
    c.execute("INSERT INTO weapon_hits (item, hit, min_value, max_value, element, heals, steals) VALUES (?,?,?,?,?,?,?)",
              (item_id, hit_index, min_hit, max_hit, element, 1 if is_heals else 0, 1 if is_steals else 0))   
    _finish_editing(conn)
    
def remove_hit(item_id, hit_index):
    conn, c = _open_conn_get_cursor()
    c.execute('DELETE from weapon_hits WHERE item = ? AND hit = ?', (item_id, hit_index)) 
    _finish_editing(conn)
    
def modify_weapon_type(item_id, weapon_type):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE weapon_weapontype SET weapontype = ? WHERE item = ? ', (weapon_type, item_id))
    _finish_editing(conn)

def delete_item(item_id):
    conn, c = _open_conn_get_cursor()
    c.execute('DELETE from items WHERE ID = ?', (item_id,))
    c.execute('DELETE from stats_of_item WHERE item = ?', (item_id,))
    c.execute('DELETE from min_stat_to_equip WHERE item = ?', (item_id,))
    c.execute('DELETE from max_stat_to_equip WHERE item = ?', (item_id,))
    c.execute('DELETE from min_align_level_to_equip WHERE item = ?', (item_id,))
    c.execute('DELETE from min_prof_level_to_equip WHERE item = ?', (item_id,))
    c.execute('DELETE from min_rank_to_equip WHERE item = ?', (item_id,))
    c.execute('DELETE from item_names WHERE item = ?', (item_id,))
    c.execute('DELETE from extra_lines WHERE item = ?', (item_id,))
    c.execute('DELETE from item_weird_conditions WHERE item = ?', (item_id,))
    _finish_editing(conn)
    
    delete_weapon(item_id)

def fake_delete_item(item_id, delete):
    conn, c = _open_conn_get_cursor()
    c.execute('UPDATE items SET removed = ? WHERE ID = ?', (1 if delete else None, item_id))
    _finish_editing(conn)
    

def delete_weapon(item_id):
    conn, c = _open_conn_get_cursor()
    c.execute('DELETE from weapon_ap WHERE item = ?', (item_id,)) 
    c.execute('DELETE from weapon_crit_bonus WHERE item = ?', (item_id,)) 
    c.execute('DELETE from weapon_crit_hits WHERE item = ?', (item_id,)) 
    c.execute('DELETE from weapon_hits WHERE item = ?', (item_id,))
    c.execute('DELETE from weapon_is_onehanded WHERE item = ?', (item_id,))  
    c.execute('DELETE from weapon_weapontype WHERE item = ?', (item_id,))  
    for table in ('weapon_uses_per_turn', 'weapon_range'):
        if c.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                     (table,)).fetchone():
            c.execute('DELETE FROM %s WHERE item = ?' % table, (item_id,))
    _finish_editing(conn)
    
def insert_item(item, weapon):
    conn, c = _open_conn_get_cursor()

    item_id = _insert_item(item, c)
    
    if weapon is not None:
        _insert_weapon(item, weapon, item_id, c)
        
    _finish_editing(conn)

def _insert_item(item, c):
    c.execute("INSERT INTO items (name, level, type, item_set, ankama_id, ankama_type, removed, dofustouch) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (item.name, item.level, item.type, item.set, item.ankama_id, item.ankama_type, item.removed, item.dofus_touch))
    item_id = c.lastrowid
    
    for stat_id, stat_value in item.stats:
        c.execute("INSERT INTO stats_of_item (item, stat, value) VALUES (?, ?, ?)",
                  (item_id, stat_id, stat_value))
    
    for stat_id, stat_value in item.min_stats_to_equip:
        c.execute("INSERT INTO min_stat_to_equip (item, stat, value) VALUES (?, ?, ?)",
                  (item_id, stat_id, stat_value))
    
    for stat_id, stat_value in item.max_stats_to_equip:
        c.execute("INSERT INTO max_stat_to_equip (item, stat, value) VALUES (?, ?, ?)",
                  (item_id, stat_id, stat_value))

    if item.localized_extras:
        for language, localized_extras in item.localized_extras.items():
            new_extras_serial = sqlite3.Binary(pickle.dumps(localized_extras))
            c.execute('INSERT INTO extra_lines VALUES (?, ?, ?)',
                      (item_id, new_extras_serial, language))

    for wc, value in item.weird_conditions.items():
        if value:
            modify_weird_condition_with_cursor(c, item_id, wc, True)

    for lang in NON_EN_LANGUAGES:
        if item.localized_names.get(lang):
            c.execute('INSERT INTO item_names VALUES (?, ?, ?)', (item_id, lang, item.localized_names.get(lang))) 

    return item_id

def _insert_weapon(item, weapon, item_id, c):
#     if item.is_one_handed:
#         c.execute("INSERT INTO weapon_is_onehanded (item, value) VALUES (?, ?)",
#                   (item_id, 1))

    if weapon.crit_chance:
        c.execute("INSERT INTO weapon_crit_hits (item, value) VALUES (?, ?)",
                  (item_id, weapon.crit_chance))
        c.execute("INSERT INTO weapon_crit_bonus (item, value) VALUES (?, ?)",
                  (item_id, weapon.crit_bonus))

    c.execute("INSERT INTO weapon_ap (item, value) VALUES (?, ?)",
              (item_id, weapon.ap))
    c.execute("INSERT INTO weapon_weapontype (item, weapontype) VALUES (?, ?)",
              (item_id, weapon.weapon_type))

    for hit_index, hit in weapon.hits_dict.items():
        c.execute("INSERT INTO weapon_hits "
                  "(item, hit, min_value, max_value, steals, heals, element) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (item_id,
                   hit_index,
                   hit.min_dam,
                   hit.max_dam,
                   1 if hit.steals else 0,
                   1 if hit.heals else 0,
                   hit.element))

def _check_and_get_old_stat(old_item, stat_id):
    for stat, value in old_item.stats:
        if stat == stat_id:
            return value
    return False

def _check_if_new_has_stat(new_item, stat_id):
    stats = new_item.stats
    for stat,_ in stats:
        if stat == stat_id:
            return True
    return False
    
def _check_and_get_old_condition(old, stat_id, is_min):
    if is_min:
        cond_list = old.min_stats_to_equip
    else: 
        cond_list = old.max_stats_to_equip
        
    for stat, value in cond_list:
        if stat == stat_id:
            return value
    return False
    
def _check_if_new_has_condition(new, stat_id, is_min):
    cond_list = new.min_stats_to_equip if is_min else new.max_stats_to_equip
    for stat, _ in cond_list:
        if stat == stat_id:
                return True
    return False
    
def insert_set(s):
    conn, c = _open_conn_get_cursor()
    c.execute("INSERT INTO sets (name, ankama_id, dofustouch) VALUES (?, ?, ?)", (s.name, s.ankama_id, 1 if s.dofus_touch else None))
    set_id = c.lastrowid
    for num_items, stat_id, stat_value in s.bonus:
        c.execute('''INSERT INTO set_bonus (item_set, num_pieces_used, stat, value)
                     VALUES (?, ?, ?, ?)''', 
                  (set_id, num_items, stat_id, stat_value)) 
    _finish_editing(conn)
    return set_id
    
def delete_set(set_id):
    conn, c = _open_conn_get_cursor()
    c.execute('DELETE from sets WHERE ID = ?', (set_id,))
    c.execute('DELETE from set_bonus WHERE item_set = ?', (set_id,))
    c.execute('DELETE from set_names WHERE item_set = ?', (set_id,))
    c.execute('UPDATE items SET item_set = ? WHERE ID = ?', (None, set_id))
    _finish_editing(conn)

def update_set(set_id, new, invalidate=True):
    if set_id:
        print('Updating set with id %d' % set_id)    
    else:
        print('Adding set with name %s' % new.name)    
    
    if set_id == None:
        my_id = insert_set(new)
        return my_id
    
    structure = get_structure()
    old = structure.get_set_by_id(set_id)
    
    if new.name != old.name:
        exists = structure.get_set_by_name(new.name)
        if exists != None:
            print('The set %s already exists in the database' % (new.name))
            return False
    
    if new.name != old.name:
        print('Changing %s\'s name to %s' % (old.name, new.name))
        conn, c = _open_conn_get_cursor()
        c.execute('UPDATE sets SET name = ? WHERE ID = ?', (new.name, set_id))   
        _finish_editing(conn)   
        
    if new.dofus_touch != old.dofus_touch:
        print('Changing %s\'s dofus_touch to %s' % (new.name, new.dofus_touch))
        conn, c = _open_conn_get_cursor()
        c.execute('UPDATE sets SET dofustouch = ? WHERE ID = ?', (new.name, 1 if new.dofus_touch else None))   
        _finish_editing(conn)
    
    if new.ankama_id != old.ankama_id:
        print('Updating %s\'s Ankama ID' % (new.name))
        conn, c = _open_conn_get_cursor()
        c.execute('UPDATE sets SET ankama_id = ? WHERE ID = ?', (new.ankama_id, set_id))   
        _finish_editing(conn)
    
    for lang in NON_EN_LANGUAGES:
        if new.localized_names.get(lang) != old.localized_names.get(lang):
            print(('Localized name for %s in %s changed from %s to %s'
                   % (old.name,
                      lang,
                      old.localized_names.get(lang),
                      new.localized_names.get(lang))))
            modify_localized_name('set_names', 'item_set', old.id, lang,
                                  new.localized_names.get(lang))

    conn, c = _open_conn_get_cursor()
    for num_items, stat_id, new_value in new.bonus:
        stat_name = structure.get_stat_by_id(stat_id).name
        old_value = _check_and_get_old_stat_in_set(old, stat_id, num_items)
        if old_value:
            if new_value != old_value:
                print('Changing %s\'s  %s from %d to %s with %d items' % (old.name, 
                                                                          stat_name,
                                                                          old_value, 
                                                                          new_value,
                                                                          num_items))
                c.execute('UPDATE set_bonus SET value = ? WHERE item_set = ? AND stat = ? '
                          'AND num_pieces_used = ?', (new_value, set_id, stat_id, num_items))   
        else:
            print('Adding %s %s to %s at %d items' % (new_value,
                                                      stat_name,
                                                      old.name,
                                                      num_items))
            c.execute('INSERT INTO set_bonus (item_set, num_pieces_used, stat, value)'
                      'VALUES (?, ?, ?, ?)', 
                      (set_id, num_items, stat_id, new_value)) 
    _finish_editing(conn)
    
    conn, c = _open_conn_get_cursor()
    for num_items, stat_id, _ in old.bonus:
        stat_name = structure.get_stat_by_id(stat_id).name
        if not _check_if_new_set_has_stat(new, stat_id, num_items):
            print('Removing %s from %s at %d items' % (stat_name, old.name, num_items))
            c.execute('DELETE from set_bonus WHERE item_set = ? AND stat = ? '
                      'AND num_pieces_used = ?', (set_id, stat_id, num_items))
    _finish_editing(conn)

    if invalidate:
        invalidate_structure()

    return new.id

def _check_and_get_old_stat_in_set(s, stat_id, num_items):
    for cand_num_items, cand_stat_id, cand_stat_value in s.bonus:
        if cand_num_items == num_items and cand_stat_id == stat_id:
            return cand_stat_value
    return False

def _check_if_new_set_has_stat(s, stat_id, num_items):
    for cand_num_items, cand_stat_id, _ in s.bonus:
        if cand_num_items == num_items and cand_stat_id == stat_id:
            return True
    return False

def _open_conn_get_cursor():
    ITEM_DB_PATH = get_items_db_path()
    conn = sqlite3.connect(ITEM_DB_PATH)
    c = conn.cursor()
    return conn, c

def _finish_editing(conn):
    conn.commit()
    conn.close()
    save_items_db_to_dump()
