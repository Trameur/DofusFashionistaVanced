# -*- coding: utf-8 -*-

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

import logging
import pickle
import random
import re
import sqlite3
import itertools
import threading
from threading import Lock

logger = logging.getLogger(__name__)

from .dofus_constants import (DamageDigest, DAMAGE_TYPES, NEUTRAL,
                             NON_ELEMENTAL_HIT_TYPES, STAT_ORDER,
                             WEIRD_CONDITION_FROM_ID, LIGHT_SET_LIMIT_FROM_ID)
from .dofus_stat import Stat
from .fashion_util import normalize_name, strip_accents
from .fashionista_config import (get_items_db_path, load_items_db_from_dump)
from .game_versions import get_game_version
from .item import Item
from .set import Set
from .translation import NON_EN_LANGUAGES
from .wakfu_db import (ITEM_PICTURE_TABLE, ITEM_RARITY_TABLE,
                       STAT_ELEMENT_COUNT_TABLE)
from .weapon import Weapon, WeaponType
from django.templatetags.i18n import language
from django.utils.translation import gettext as _



# A failed rebuild leaves the previous database in place: keep serving that
# rather than refusing to start.
load_items_db_from_dump(strict=False)


def _with_crit_bonus(hit, crit_bonus):
    """The same hit on the critical line. A row that pulls the target or takes
    its AP counts cells and points, not damage, so the bonus leaves it alone:
    it used to turn "attracts 1 cell" into "attracts 11 cells"."""
    if hit.element in NON_ELEMENTAL_HIT_TYPES:
        return DamageDigest(hit.min_dam, hit.max_dam, hit.element,
                            hit.steals, hit.heals)
    return DamageDigest(hit.min_dam + crit_bonus, hit.max_dam + crit_bonus,
                        hit.element, hit.steals, hit.heals)


lock = Lock()
_structure_singletons = {}
_current_game_version = threading.local()

# The Gelano rows are synthesized, not scraped, and their ids used to be
# max(item id) + 1. That moved every time the item set did, and a build saved
# before the move lost its ring. Fixed ids, far above anything the scrapers
# hand out (mounts sit at 1000000, the duplicates sat at 100000000 and the
# Touch pet variants at 200000000).
GELANO_IDS = {'Gelano (#1)': 990000001, 'Gelano (#2)': 990000011}

# What max(item id) + 1 came out as in the data each version last shipped, so
# the builds saved against it still find the ring. Anything older than that was
# already lost to the same drift, which is what the fixed ids above end.
GELANO_DEPLOYED_IDS = {
    'dofus3': {200014167: 'Gelano (#1)'},
    'beta': {200014167: 'Gelano (#1)'},
    'dofus2': {1029457: 'Gelano (#1)'},
    # 200000226 was the Touch number for two days, while a rebuild had lost a
    # pet and its 226 variants left that slot free. That rebuild never shipped,
    # the numbering is back to 228 variants, and 200000226 is a Water Bwak.
    'touch': {200000228: 'Gelano (#1)'},
    'retro': {10000087: 'Gelano (#1)'},
}


def get_structure(game_version=None):
    global _structure_singletons
    if game_version is None:
        game_version = getattr(_current_game_version, 'version', 'dofus3')
    if game_version not in _structure_singletons:
        with lock:
            if game_version not in _structure_singletons:
                s = Structure(game_version)
                _structure_singletons[game_version] = s
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('Structure [%s] created with %d bytes', game_version, len(pickle.dumps(s)))
    return _structure_singletons[game_version]


def set_current_game_version(version):
    _current_game_version.version = version


def get_current_game_version():
    return getattr(_current_game_version, 'version', 'dofus3')


def invalidate_structure(game_version=None):
    global _structure_singletons
    if game_version is not None:
        _structure_singletons.pop(game_version, None)
    else:
        _structure_singletons.clear()

class Structure:

    def __init__(self, game_version='dofus3'):
        self.game_version = game_version
        self._used_stat_keys = None
        self.legacy_item_ids = {}
        self.conn = sqlite3.connect(get_items_db_path(game_version))
        # A half-written catalogue makes one of these raise, and the
        # close below was never reached: the database file stayed open
        # for the life of the process. On Windows that also makes the
        # file undeletable, which is how a test caught it.
        try:
    
            self.read_sets_table()
            self.read_items_table()
            self.read_types_table()
            self.read_stats_table()
            self.read_weapon_types_table()
            self.read_set_names_table()
            self.read_stats_of_item_table()
            self.read_item_rarity_table()
            self.read_item_picture_table()
            self.read_stat_element_count_table()
            self.read_min_stat_to_equip_table()
            self.read_max_stat_to_equip_table()
            self.read_or_conditions_table()
            self.read_legacy_item_ids_table()
            self.read_weird_conditions_table()
            self.read_extra_lines_table()
            self.read_spell_tooltips_table()
            self.read_item_flags_table()
            self.read_set_bonus_table()
            self.read_set_max_caps_table()
    #       self.read_weapon_is_onehanded_table()
            self.read_weapon_hits_table()
            #self.insert_turquoises()
            self.insert_gelanos()
            self.build_indexes()
            self.separate_items()
            self.read_item_names_table()
            self.post_process_item_names()
            self.post_process_set_names()
        
        finally:
            self.conn.close()
            del(self.conn)

            
    def read_items_table(self):
        c = self.conn.cursor()
        self.items_dict = {}
        self.dt_items_dict = {}
        self.items_dict_name = {}
        self.dt_items_dict_name = {}
        self.items_dict_ankama = {}
        self.dt_items_dict_ankama = {}
        has_skin = any(row[1] == 'skin'
                       for row in c.execute('PRAGMA table_info(items)'))
        columns = ('id, name, level, type, item_set, ankama_id, ankama_type, removed, '
                   'dofustouch' + (', skin' if has_skin else ''))
        for entry in c.execute('SELECT %s FROM items' % columns):
            item_id = entry[0]
            item_name = entry[1]
            item_level = entry[2]
            item_type = entry[3]
            item_set = entry[4]
            ankama_id = entry[5]
            ankama_type = entry[6]
            item_removed = entry[7]
            dofus_touch = entry[8]
            item = Item()
            item.id = item_id
            if item_name == 'Gelano':
                item.name = 'Gelano (#2)'
            else:
                item.name = item_name
            item.level = item_level
            item.type = item_type
            item.set = item_set
            item.ankama_id = ankama_id
            item.ankama_type = ankama_type
            item.removed = bool(item_removed)
            item.dofus_touch = bool(dofus_touch)
            if has_skin:
                item.skin = entry[9]

            if not dofus_touch:
                self.items_dict[item_id] = item
                #assert item.name not in self.items_dict_name, "%s DUPLICATED" % item.name
                self.items_dict_name[item.name] = item
                by_ankama = self.items_dict_ankama
            else:
                self.dt_items_dict[item_id] = item
                #assert item.name not in self.dt_items_dict_name, "%s DUPLICATED" % item.name
                self.dt_items_dict_name[item.name] = item
                by_ankama = self.dt_items_dict_ankama
            if ankama_id is not None:
                # Mounts have their own Ankama id space and reuse equipment ids:
                # on Touch, 42 is both the Twiggy Sword and a Dragoturkey.
                if ankama_type != 'mounts' or ankama_id not in by_ankama:
                    by_ankama[ankama_id] = item
            if item_set is not None:
                if item_set in self.sets_dict:
                    this_item_set = self.sets_dict[item_set]
                elif item_set in self.dt_sets_dict:
                    this_item_set = self.dt_sets_dict[item_set]
                if this_item_set:
                    this_item_set.add_item(item_id)
                else:
                    logger.warning("Could not find set %s", this_item_set)
                
            if item.ankama_id is None:
                logger.debug('%s [%d] is missing Ankama ID', item.name, item.id)
            if item.ankama_type is None:
                logger.debug('%s [%d] is missing Ankama type', item.name, item.id)
                
    def read_types_table(self):
        c = self.conn.cursor()
        self.types_dict = {}
        for entry in c.execute('SELECT id, name FROM item_types'):
            type_id = entry[0]
            type_name = entry[1]
            self.types_dict[type_id] = type_name
    
    def read_sets_table(self):
        c = self.conn.cursor()
        self.sets_dict = {}
        self.dt_sets_dict = {}
        for entry in c.execute('SELECT id, name, ankama_id, dofustouch FROM sets'):
            set_id = entry[0]
            set_name = entry[1]
            set_ankama_id = entry[2]
            dofus_touch = entry[3]
            item_set = Set()
            item_set.id = set_id
            item_set.name = set_name
            item_set.ankama_id = set_ankama_id
            item_set.dofus_touch = bool(dofus_touch)
            if item_set.dofus_touch:
                self.dt_sets_dict[set_id] = item_set
            else:
                self.sets_dict[set_id] = item_set
           
    def read_stats_table(self):
        c = self.conn.cursor()
        self.stat_dict = {}
        self.stat_dict_name = {}
        self.stat_dict_key = {}
        for entry in c.execute('SELECT id, key, name FROM stats'):
            stat_id = entry[0]
            stat_key = entry[1]
            stat_name = entry[2]
            stat = Stat()
            stat.id = stat_id
            stat.key = stat_key
            stat.name = stat_name
            self.stat_dict[stat_id] = stat
            self.stat_dict_name[stat_name] = stat
            self.stat_dict_key[stat_key] = stat
    
    def read_weapon_types_table(self):
        c = self.conn.cursor()
        self.weapon_type_dict = {}
        self.weapon_type_dict_name = {}
        self.weapon_type_dict_key = {}
        for entry in c.execute('SELECT id, key, name FROM weapontype'):
            weapon_type_id = entry[0]
            weapon_type_key = entry[1]
            weapon_type_name = entry[2]
            weapon_type = WeaponType()
            weapon_type.id = weapon_type_id
            weapon_type.key = weapon_type_key
            weapon_type.name = weapon_type_name
            self.weapon_type_dict[weapon_type_id] = weapon_type
            self.weapon_type_dict_name[weapon_type_name] = weapon_type
            self.weapon_type_dict_key[weapon_type_key] = weapon_type
    
    def read_item_names_table(self):
        c = self.conn.cursor()
        or_items = self.get_or_items()
        for entry in c.execute('SELECT item, language, name FROM item_names'):
            item_id = entry[0]         
            lang = entry[1]
            name = entry[2]
            item = self.get_item_by_id(item_id)
            if item:
                item.localized_names[lang] = name
                pass
            for _, item_list in or_items.items():
                for item in item_list:
                    if item.id == item_id:
                        item.localized_names[lang] = name

    def read_set_names_table(self):
        c = self.conn.cursor()
        for entry in c.execute('SELECT item_set, language, name FROM set_names'):
            item_set_id = entry[0]         
            lang = entry[1]
            name = entry[2]
            if item_set_id in self.sets_dict:
                item_set = self.sets_dict[item_set_id]
            elif item_set_id in self.dt_sets_dict:
                item_set = self.dt_sets_dict[item_set_id]
            else:
                logger.warning("Set %d not found", item_set_id)
                return
            item_set.localized_names[lang]= name

    def read_stats_of_item_table(self):
        c = self.conn.cursor()
        # Only the versions built by get_equipments3 carry the roll range.
        has_range = any(row[1] == 'min_value'
                        for row in c.execute('PRAGMA table_info(stats_of_item)'))
        columns = ('item, stat, value, min_value, max_value' if has_range
                   else 'item, stat, value')
        for entry in c.execute('SELECT %s FROM stats_of_item' % columns):
            item_id = entry[0]
            stat_id = entry[1]
            value = entry[2]
            item = self.get_item_by_id(item_id)
            item.stats.append((stat_id, value))
            if has_range and entry[3] is not None and entry[4] is not None:
                item.stat_ranges[stat_id] = (entry[3], entry[4])
            
    def read_item_rarity_table(self):
        """Wakfu's rarity tier. No Dofus version has the table at all."""
        if not self._table_exists(ITEM_RARITY_TABLE):
            return
        c = self.conn.cursor()
        for item_id, rarity in c.execute(
                'SELECT item, rarity FROM %s' % ITEM_RARITY_TABLE):
            item = self.get_item_by_id(item_id)
            if item is not None:
                item.rarity = rarity

    def read_item_picture_table(self):
        """Which drawing a Wakfu item shows. No Dofus version has the table.

        Half the gear shares its artwork with something else, so the picture is
        named by Ankama's gfx id and not by the item.
        """
        if not self._table_exists(ITEM_PICTURE_TABLE):
            return
        c = self.conn.cursor()
        for item_id, gfx in c.execute(
                'SELECT item, gfx FROM %s' % ITEM_PICTURE_TABLE):
            item = self.get_item_by_id(item_id)
            if item is not None:
                item.picture = gfx

    def read_stat_element_count_table(self):
        """How many elements a Wakfu mastery line spreads over.

        The table names the line it qualifies rather than trusting the order
        `stats_of_item` comes back in, so the two can be checked against each
        other. Them disagreeing means the build is half-written, and a planner
        that quietly values the wrong line is worse than one that refuses to
        start.
        """
        if not self._table_exists(STAT_ELEMENT_COUNT_TABLE):
            return
        c = self.conn.cursor()
        for item_id, line, stat_id, value, elements in c.execute(
                'SELECT item, line, stat, value, elements FROM %s'
                ' ORDER BY item, line' % STAT_ELEMENT_COUNT_TABLE):
            item = self.get_item_by_id(item_id)
            if item is None:
                raise ValueError(
                    '%s names item %s, which no items row carries'
                    % (STAT_ELEMENT_COUNT_TABLE, item_id))
            if (stat_id, value) not in item.stats:
                raise ValueError(
                    '%s line %s of item %s reads stat %s = %s, which is not a '
                    'stat that item carries'
                    % (STAT_ELEMENT_COUNT_TABLE, line, item_id, stat_id, value))
            item.element_spread.append((stat_id, value, elements))

    def insert_turquoises(self):
        for value in range(11, 20 + 1):
            if ("Turquoise Dofus (#%d)" % value) not in self.dt_items_dict_name:
                item = Item()
                keys = list(itertools.chain(list(self.dt_items_dict.keys()), list(self.items_dict.keys())))
                if keys:
                    item.id = max(keys) + 1
                else:
                    item.id = 1
                item.name = ("Turquoise Dofus (#%d)" % value)
                item.level = 6
                item.dofus_touch = True
                item.type = self.get_type_id_by_name('Dofus')
                self.dt_items_dict[item.id] = item
                self.dt_items_dict_name[item.name] = item
    
                stat_id = self.get_stat_by_name('Critical Hits').id
                item.stats.append((stat_id, value))   
                
    def insert_gelanos(self):
        # The Gelano is a Dofus ring, synthesized because the scrapers cannot
        # see its exo branch. A game that has no Ring type has no Gelano, and
        # inserting one gave it a null type that separate_items then looked up
        # by name.
        if not get_game_version(self.game_version).dofus:
            return
        for old_id, name in GELANO_DEPLOYED_IDS.get(self.game_version, {}).items():
            self.legacy_item_ids.setdefault(old_id, GELANO_IDS[name])
        if not self.get_set_by_name('Jellix Set', True):
            new_set = Set()
            new_set.name = 'Jellix Set'
            new_set.dofus_touch = True
            if len(list(self.dt_sets_dict.keys())) > 0:
                new_set.id = max(self.dt_sets_dict.keys()) + 1
            else: 
                new_set.id = 1
            self.dt_sets_dict[new_set.id] = new_set
        
        if not self.get_set_by_name('Jellix Set', False):
            new_set = Set()
            new_set.name = 'Jellix Set'
            new_set.dofus_touch = False
            if self.sets_dict.keys():
                new_set.id = max(self.sets_dict.keys()) + 1
            else:
                new_set.id = 1
            self.sets_dict[new_set.id] = new_set
        
        if "Gelano (#1)" not in self.items_dict_name:
            logger.debug('Gelano (#1) not there, inserting')
            item = Item()
            item.id = GELANO_IDS['Gelano (#1)']
            item.name = "Gelano (#1)"
            item.level = 60
            item.type = self.get_type_id_by_name('Ring')
            self.items_dict[item.id] = item
            self.items_dict_name[item.name] = item
            item.set = self.get_set_id_by_name('Jellix Set', False)

            stat_id = self.get_stat_by_name('AP').id
            item.stats.append((stat_id, 1))
            stat_id = self.get_stat_by_name('MP').id
            item.stats.append((stat_id, 1))
            self.sets_dict[item.set].add_item(item.id)
            
        if "Gelano (#1)" not in self.dt_items_dict_name:
            logger.debug('Gelano (#1) not there (dofus touch), inserting')
            item = Item()
            item.id = GELANO_IDS['Gelano (#1)'] + 1
            item.name = "Gelano (#1)"
            item.level = 60
            item.dofus_touch = True
            item.type = self.get_type_id_by_name('Ring')
            self.dt_items_dict[item.id] = item
            self.dt_items_dict_name[item.name] = item
            item.set = self.get_set_id_by_name('Jellix Set', True)

            stat_id = self.get_stat_by_name('AP').id
            item.stats.append((stat_id, 1))
            stat_id = self.get_stat_by_name('MP').id
            item.stats.append((stat_id, 1))
            self.dt_sets_dict[item.set].add_item(item.id)

        if "Gelano (#2)" not in self.items_dict_name:
            logger.debug('Gelano (#2) not there, inserting')
            item = Item()
            item.id = GELANO_IDS['Gelano (#2)']
            item.name = "Gelano (#2)"
            item.level = 60
            item.type = self.get_type_id_by_name('Ring')
            self.items_dict[item.id] = item
            self.items_dict_name[item.name] = item
            item.set = self.get_set_id_by_name('Jellix Set', False)

            stat_id = self.get_stat_by_name('AP').id
            item.stats.append((stat_id, 1))
            self.sets_dict[item.set].add_item(item.id)

        if "Gelano (#2)" not in self.dt_items_dict_name:
            logger.debug('Gelano (#2) not there (dofus touch), inserting')
            item = Item()
            item.id = GELANO_IDS['Gelano (#2)'] + 1
            item.name = "Gelano (#2)"
            item.level = 60
            item.dofus_touch = True
            item.type = self.get_type_id_by_name('Ring')
            self.dt_items_dict[item.id] = item
            self.dt_items_dict_name[item.name] = item
            item.set = self.get_set_id_by_name('Jellix Set', True)

            stat_id = self.get_stat_by_name('AP').id
            item.stats.append((stat_id, 1))
            self.dt_sets_dict[item.set].add_item(item.id)

    def read_min_stat_to_equip_table(self):
        c = self.conn.cursor()
        for entry in c.execute('SELECT item, stat, value FROM min_stat_to_equip'):
            item_id = entry[0]         
            stat_id = entry[1]
            value = entry[2]
            item = self.get_item_by_id(item_id)
            item.min_stats_to_equip.append((stat_id, value))
 
    def read_max_stat_to_equip_table(self):
        c = self.conn.cursor()
        for entry in c.execute('SELECT item, stat, value FROM max_stat_to_equip'):
            item_id = entry[0]         
            stat_id = entry[1]
            value = entry[2]
            item = self.get_item_by_id(item_id)
            item.max_stats_to_equip.append((stat_id, value))

    def read_legacy_item_ids_table(self):
        self.legacy_item_ids = {}
        if not self._table_exists('legacy_item_ids'):
            return
        c = self.conn.cursor()
        for old_id, item_id in c.execute(
                'SELECT old_id, item FROM legacy_item_ids'):
            self.legacy_item_ids[old_id] = item_id

    def read_or_conditions_table(self):
        c = self.conn.cursor()
        if not self._table_exists('item_or_conditions'):
            return
        by_item = {}
        for item_id, branch, stat_id, is_max, value in c.execute(
                'SELECT item, branch, stat, is_max, value FROM item_or_conditions'
                ' ORDER BY item, branch'):
            by_item.setdefault(item_id, {}).setdefault(branch, []).append(
                (stat_id, bool(is_max), value))
        for item_id, branches in by_item.items():
            item = self.get_item_by_id(item_id)
            if item is not None:
                item.or_conditions = [gates for _branch, gates
                                      in sorted(branches.items())]

    def _table_exists(self, name):
        c = self.conn.cursor()
        return c.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                         " AND name = ?", (name,)).fetchone() is not None

    def read_weird_conditions_table(self):
        c = self.conn.cursor()
        for entry in c.execute('SELECT item, condition_id FROM item_weird_conditions'):
            item_id = entry[0]         
            condition_id = entry[1]
            item = self.get_item_by_id(item_id)
            name = WEIRD_CONDITION_FROM_ID[condition_id]
            if name == 'light_set':
                # The set-bonus cap: 2 for "< 3", 1 for the stricter touch "< 2".
                item.weird_conditions['light_set'] = LIGHT_SET_LIMIT_FROM_ID.get(condition_id, 2)
            else:
                item.weird_conditions[name] = True

    def read_extra_lines_table(self):
        c = self.conn.cursor()
        for entry in c.execute('SELECT item, line, language FROM extra_lines'):
            item_id = entry[0]         
            if isinstance(entry[1], str):
                lines = pickle.loads(entry[1].encode())
            else:
                lines = pickle.loads(entry[1])
            language = entry[2]
            assert type(lines) is list
            item = self.get_item_by_id(item_id)
            item.localized_extras[language] = lines
    
    def read_spell_tooltips_table(self):
        """What the spells named in the extra lines do.

        Filled by itemscraper/store_spell_tooltips.py; the table may be absent.
        """
        c = self.conn.cursor()
        try:
            rows = c.execute(
                'SELECT item, language, tooltips FROM spell_tooltips').fetchall()
        except Exception:
            return
        for item_id, language, blob in rows:
            if isinstance(blob, str):
                blob = blob.encode()
            tooltips = pickle.loads(blob)
            assert type(tooltips) is dict
            item = self.get_item_by_id(item_id)
            if item is not None:
                item.spell_tooltips[language] = tooltips

    def read_item_flags_table(self):
        c = self.conn.cursor()
        try:
            for entry in c.execute('SELECT item, flag FROM item_flags'):
                item = self.get_item_by_id(entry[0])
                if item is not None:
                    item.flags.append(entry[1])
        except Exception:
            pass  # old DB without item_flags table

#     def read_weapon_is_onehanded_table(self):
#         c = self.conn.cursor()
#         for entry in c.execute('SELECT item FROM weapon_is_onehanded'):
#             item_id = entry[0]
#             item = self.items_dict[item_id]
#             item.is_one_handed = True
    def _weapon_key(self, item_id, is_dofus_touch, item_name):
        """What makes two rows the same weapon.

        The branches of one item, "(#1)" and "(#2)", share an ankama id and share
        their damage. Retro items that merely share a name (eleven Ecaflip Paws,
        four Bronze Swords of four elements) do not.
        """
        items = self.dt_items_dict if is_dofus_touch else self.items_dict
        item = items.get(item_id)
        ankama_id = getattr(item, 'ankama_id', None) if item is not None else None
        return ankama_id if ankama_id else item_name

    def _get_item_name_and_weapon_by_id(self, item_id):
        is_dofus_touch = self._is_item_dofus_touch(item_id)
        item_name = self.get_item_name_by_id(item_id, is_dofus_touch)
        by_key = (self.dt_weapons_by_key if is_dofus_touch
                  else self.weapons_by_key)
        by_name = (self.dt_weapons_dict_by_name if is_dofus_touch
                   else self.weapons_dict_by_name)
        key = self._weapon_key(item_id, is_dofus_touch, item_name)
        w = by_key.get(key)
        if w is None:
            w = Weapon()
            by_key[key] = w
            by_name.setdefault(item_name, w)
        return item_name, w

    def get_weapon_for_item(self, item):
        """The weapon of this exact item; get_weapon_by_name only ever answers
        for the first item carrying the name."""
        if item is None:
            return None
        is_dofus_touch = self._is_item_dofus_touch(item.id)
        by_key = (self.dt_weapons_by_key if is_dofus_touch
                  else self.weapons_by_key)
        key = self._weapon_key(item.id, is_dofus_touch, item.name)
        return by_key.get(key) or by_key.get(item.name)

    def read_weapon_hits_table(self):
        c = self.conn.cursor()
        self.weapons_dict_by_name = {}
        self.dt_weapons_dict_by_name = {}
        self.weapons_by_key = {}
        self.dt_weapons_by_key = {}
        for entry in c.execute('SELECT item, hit, min_value, max_value, steals, heals, element'
                               ' FROM weapon_hits'):
            item_id = entry[0]
            hit_index = entry[1]
            min_value = entry[2]
            max_value = entry[3]
            steals = entry[4]
            heals = entry[5]
            element = entry[6]
            item_name, w = self._get_item_name_and_weapon_by_id(item_id)
            w.hits_dict[hit_index] = DamageDigest(min_value, max_value, element, steals == 1,
                                                  heals == 1)

        for entry in c.execute('SELECT item, value FROM weapon_crit_bonus'):
            item_id = entry[0]
            crit_bonus = entry[1]
            item_name, w = self._get_item_name_and_weapon_by_id(item_id)
            w.crit_bonus = crit_bonus
            #else:
                #print '%s is missing weapon crit bonus' % item_name

        for entry in c.execute('SELECT item, value FROM weapon_crit_hits'):
            item_id = entry[0]
            crit_chance = entry[1]
            item_name, w = self._get_item_name_and_weapon_by_id(item_id)
            w.crit_chance = crit_chance
            #else:
                #print '%s is missing crit_chance' % item_name

        for entry in c.execute('SELECT item, value FROM weapon_ap'):
            item_id = entry[0]
            ap = entry[1]
            item_name, w = self._get_item_name_and_weapon_by_id(item_id)
            w.ap = ap
                
        # How many swings a turn allows. Retro never limited a weapon, and a
        # dump built before the table exists has none either.
        has_uses = any(row[0] == 'weapon_uses_per_turn' for row in c.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name = 'weapon_uses_per_turn'"))
        if has_uses:
            for entry in c.execute(
                    'SELECT item, value FROM weapon_uses_per_turn'):
                item_id = entry[0]
                item_name, w = self._get_item_name_and_weapon_by_id(item_id)
                w.uses_per_turn = entry[1] or None

        for entry in c.execute('SELECT item, weapontype FROM weapon_weapontype'):
            item_id = entry[0]
            weapon_type = entry[1]
            item_name, w = self._get_item_name_and_weapon_by_id(item_id)
            w.weapon_type = weapon_type
                
        # By key: the name index only holds the first weapon under each name.
        for weapon_name, w in itertools.chain(iter(self.weapons_by_key.items()),
                                              iter(self.dt_weapons_by_key.items())):
            w.has_crits = (w.crit_bonus is not None)
            # Some weapons have no crit or type at all (magnifying glass,
            # fishing rod...).
            if not w.has_crits and w.crit_chance is not None:
                logger.debug('%s is missing crit_bonus', weapon_name)
            if w.crit_chance is None and w.has_crits:
                logger.debug('%s is missing crit_chance', weapon_name)
            if w.ap is None:
                logger.debug('%s is missing ap', weapon_name)
            if w.weapon_type is None:
                logger.debug('%s is missing weapon type', weapon_name)
    
            w.base_hit = []
            if w.has_crits:
                w.crit_base_hit = []
            for i in range(len(w.hits_dict)):
                try:
                    hit = w.hits_dict[i]
                except KeyError:
                    logger.debug('%s is missing hit %d', weapon_name, i)
                    continue
                w.base_hit.append(hit)
                if w.has_crits:
                    w.crit_base_hit.append(_with_crit_bonus(hit, w.crit_bonus))

            w.is_mageable = any([hit.element == NEUTRAL and not hit.steals
                                 for hit in w.base_hit])

            if w.is_mageable:
                w.maged_hit = [DamageDigest(int((hit.min_dam - 1) * 0.85 + 1),
                                            int((hit.min_dam - 1) * 0.85)
                                            + int((hit.max_dam - hit.min_dam + 1) * 0.85),
                                            hit.element,
                                            hit.steals,
                                            hit.heals) for hit in w.base_hit]
                if w.has_crits:
                    w.crit_maged_hit = [_with_crit_bonus(hit, w.crit_bonus)
                                        for hit in w.maged_hit]
                else:
                    w.crit_maged_hit = None
            else:
                w.maged_hit = None
                w.crit_maged_hit = None

            w.non_crit_hits = self.mage_every_way(w.base_hit, w.maged_hit,
                                                  w.is_mageable)

            if w.has_crits:
                w.crit_hits = self.mage_every_way(w.crit_base_hit, w.crit_maged_hit,
                                                  w.is_mageable)
            else:
                w.crit_hits = None

    def mage_every_way(self, non_maged_hits, maged_hits, is_mageable):
        result = {}
        if is_mageable:
            for element_maged in DAMAGE_TYPES:
                result[element_maged] = self.mage(non_maged_hits,
                                                  maged_hits,
                                                  element_maged)
        else:
            for element_maged in DAMAGE_TYPES:
                result[element_maged] = non_maged_hits
        return result

    def mage(self, base_hits, crit_base_hits, element_maged):
        result = []
        for base_hit, maged_hit in zip(base_hits, crit_base_hits):
            if (base_hit.element == NEUTRAL and not base_hit.steals
                and element_maged != NEUTRAL):
                hit = maged_hit
                element = element_maged
            else:
                hit = base_hit
                element = hit.element
            result.append(hit.copy_with_element(element))
        return result

    def read_set_bonus_table(self):
        c = self.conn.cursor()
        for entry in c.execute('SELECT item_set, num_pieces_used, stat, value FROM set_bonus'):
            set_id = entry[0]         
            num_items = entry[1]
            stat_id = entry[2]
            value = entry[3]
            if set_id in self.sets_dict:
                item_set = self.sets_dict[set_id]
            elif set_id in self.dt_sets_dict:
                item_set = self.dt_sets_dict[set_id]
            else:
                logger.warning("Set %d not found", set_id)
                return
            item_set.bonus.append((num_items, stat_id, value))
            stat_key = self.get_stat_by_id(stat_id)
            if stat_key is None:
                logger.warning("No stat found for stat_id %s", stat_id)
                continue
            stat_key = self.get_stat_by_id(stat_id).key
            item_set.bonus_per_num_items.setdefault(num_items, {})[stat_key] = value

    def read_set_max_caps_table(self):
        c = self.conn.cursor()
        try:
            rows = c.execute('SELECT item_set, num_pieces_used, stat, max_value FROM set_max_caps').fetchall()
        except Exception:
            return
        for entry in rows:
            set_id, num_items, stat_id, max_value = entry
            item_set = self.sets_dict.get(set_id) or self.dt_sets_dict.get(set_id)
            if item_set is None:
                continue
            item_set.max_caps.append((num_items, stat_id, max_value))

    def build_indexes(self):
        self.items_list = list(self.items_dict.values())
        self.dt_items_list = list(self.dt_items_dict.values())
        self.available_items_list = list(filter(self._is_item_available, self.items_list))
        self.dt_available_items_list = list(filter(self._is_item_available, self.dt_items_list))
        self.sets_list = list(self.sets_dict.values())
        self.dt_sets_list = list(self.dt_sets_dict.values())
        self.stats_list = list(self.stat_dict.values())
        self.types_list = list(self.types_dict.values())
        if get_game_version(self.game_version).dofus:
            self.stats_list_names_sorted = [stat.name for stat in
                sorted(self.stats_list, key=lambda stat: STAT_ORDER[stat.key])]
        else:
            # STAT_ORDER is the order a Dofus character sheet reads and it
            # names none of Wakfu's characteristics. A game gets its own
            # order, which here is the one its data was written in.
            self.stats_list_names_sorted = [
                stat.name for stat in sorted(self.stats_list,
                                             key=lambda stat: stat.id)]

    def _is_item_available(self, item):
        return not item.removed

    def _is_or_item_available(self, item):
        return not item.removed

    def separate_items(self):
        # The buckets cover the levels this game actually has. Written as
        # 1..200 for years, which is Dofus's range and only Dofus's: every
        # item of all five Dofus versions sits inside it, so reading the range
        # off the data leaves them untouched, while Wakfu runs 0 to 245 and had
        # 1502 items outside it, a fifth of its catalogue.
        levels = {item.level for item in itertools.chain(
            self.items_list, self.dt_items_list)}
        self._level_floor = min([1] + [level for level in levels])
        self._level_ceiling = max([200] + [level for level in levels])
        span = range(self._level_floor, self._level_ceiling + 1)

        self.types = {}
        for x in span:
            self.types[x] = {}
            for t in self.types_list:
                self.types[x][t] = []
        self.dt_types = {}
        for x in span:
            self.dt_types[x] = {}
            for t in self.types_list:
                self.dt_types[x][t] = []
        or_items_set = set()
        dt_or_items_set = set()
        self.or_items = {}    
        self.dt_or_items = {}        
        self._available_or_items = {}
        self._dt_available_or_items = {}

        for item in itertools.chain(self.items_list, self.dt_items_list):
            m = re.match(r"(.*) \(#\d+\)", item.name)             
            if m is not None:
                item_name = m.group(1)
                if not ((item_name in or_items_set and not item.dofus_touch)
                        or (item_name in dt_or_items_set and item.dofus_touch)):
                    new_item = Item()
                    new_item.id = item.id
                    new_item.name = item_name
                    new_item.level = item.level
                    new_item.type = item.type
                    new_item.set = item.set
                    if item.dofus_touch:
                        dt_or_items_set.add(item_name)
                        self.dt_or_items[item_name] = []
                        self.dt_types[new_item.level][self.get_type_name_by_id(new_item.type)].append(new_item)
                    else:
                        or_items_set.add(item_name)
                        self.or_items[item_name] = []
                        self.types[new_item.level][self.get_type_name_by_id(new_item.type)].append(new_item)
                if item.dofus_touch:
                    self.dt_or_items[item_name].append(item)
                else:
                    self.or_items[item_name].append(item)
                item.or_name = item_name
                
                if not item.removed:
                    if item.dofus_touch:
                        if item_name not in self._dt_available_or_items:
                            self._dt_available_or_items[item_name] = []
                        self._dt_available_or_items[item_name].append(item)
                    else:
                        if item_name not in self._available_or_items:
                            self._available_or_items[item_name] = []
                        self._available_or_items[item_name].append(item)
                        
            else:
                if item.dofus_touch:
                    self.dt_types[item.level][self.get_type_name_by_id(item.type)].append(item)
                else:
                    self.types[item.level][self.get_type_name_by_id(item.type)].append(item)
                item.or_name = item.name

        # A level carries everything the levels below it carry.
        climbing = range(self._level_floor + 1, self._level_ceiling + 1)
        for t in self.types_list:
            for level in climbing:
                self.types[level][t] = self.types[level][t] + self.types[level-1][t]
        for t in self.types_list:
            for level in climbing:
                self.dt_types[level][t] = self.dt_types[level][t] + self.dt_types[level-1][t]
     
        self._unique_items_ids_with_type = {}
        for t in self.types_list:
            for item in self.get_unique_items_by_type_and_level(
                    t, self._level_ceiling, False):
                self._unique_items_ids_with_type[item.id] = t
        self._dt_unique_items_ids_with_type = {}
        for t in self.types_list:
            for item in self.get_unique_items_by_type_and_level(t, 200, True):
                self._dt_unique_items_ids_with_type[item.id] = t
        
    def _or_sibling_local_name(self, item, language):
        """A branch added at runtime (the Gelano exo variant) has no row in
        item_names, so borrow the name from a branch that has one."""
        if item.or_name == item.name:
            return None
        group = (self.dt_or_items if item.dofus_touch else self.or_items)
        for sibling in group.get(item.or_name) or []:
            name = sibling.localized_names.get(language)
            if name and not name.startswith('[!] '):
                return self.get_or_item_name(name)
        return None

    def post_process_item_names(self):
        for item in itertools.chain(self.items_list, self.dt_items_list):
            item.localized_names['en'] = item.or_name
            item.accentless_local_names['en'] = item.or_name
            for lang in NON_EN_LANGUAGES:
                if lang not in item.localized_names:
                    sibling_name = self._or_sibling_local_name(item, lang)
                    item.localized_names[lang] = (sibling_name if sibling_name
                                                  else '[!] %s' % item.or_name)
                elif item.or_name != item.name:
                    # The "(#N)" tag only groups the branches of an OR item.
                    item.localized_names[lang] = self.get_or_item_name(
                        item.localized_names[lang])


        for item in itertools.chain(self.items_list, self.dt_items_list):
            for lang in NON_EN_LANGUAGES:
                item.accentless_local_names[lang] = strip_accents(item.localized_names[lang])
        
        
        self._unique_items_names_with_ids = {}
        self._dt_unique_items_names_with_ids = {}
        self._unique_items_names_with_ids['en'] = {}
        self._dt_unique_items_names_with_ids['en'] = {}
        for lang in NON_EN_LANGUAGES:
            self._unique_items_names_with_ids[lang] = {}
            self._dt_unique_items_names_with_ids[lang] = {}
        for t in self.types_list:
            item_list = itertools.chain(self.get_unique_items_by_type_and_level(t, 200, False), 
                                        self.get_unique_items_by_type_and_level(t, 200, True))
            for item in item_list:
                if item.dofus_touch:
                    self._dt_unique_items_names_with_ids['en'][item.name] = item.id
                else:
                    self._unique_items_names_with_ids['en'][item.name] = item.id
                for lang in NON_EN_LANGUAGES:
                    if lang in item.localized_names:
                        if item.dofus_touch:
                            self._dt_unique_items_names_with_ids[lang][item.localized_names[lang]] = item.id
                        else:
                            self._unique_items_names_with_ids[lang][item.localized_names[lang]] = item.id
                    else:
                        item_name = self.get_or_name_in_language(item.name, lang, item.dofus_touch)
                        if item_name is None:
                            if '[!]' in item.name:
                                item_name = item.name
                            else:
                                item_name = '[!] %s' % item.name
                        if item.dofus_touch:
                            self._dt_unique_items_names_with_ids[lang][item_name] = item.id
                        else:
                            self._unique_items_names_with_ids[lang][item_name] = item.id
    
    def post_process_set_names(self):
        for item_set in itertools.chain(self.sets_list, self.dt_sets_list):
            item_set.localized_names['en'] = item_set.name
            for lang in NON_EN_LANGUAGES:
                if lang not in item_set.localized_names:
                    if '[!]' not in item_set.name:
                        item_set.localized_names[lang] = '[!] %s' % item_set.name
                    else:
                        item_set.localized_names[lang] = item_set.name

    def get_unique_items_by_type_and_level(self, item_type, level, dofus_touch=False):
        # TODO: Don't sort every time.
        if dofus_touch:
            return sorted(self.dt_types[level][item_type], key=lambda item: item.name)
        else:
            return sorted(self.types[level][item_type], key=lambda item: item.name)
      
    def get_all_unique_items_ids_with_type(self, dofus_touch=False):
        if dofus_touch:
            return self._dt_unique_items_ids_with_type
        else:
            return self._unique_items_ids_with_type
    
    def get_all_unique_items_names_with_ids(self, language, dofus_touch=False):
        if dofus_touch:
            return self._dt_unique_items_names_with_ids[language]
        else:
            return self._unique_items_names_with_ids[language]
    
    def get_set_names(self, language, dofus_touch=False):
        sets = self.get_sets_list(dofus_touch)
        set_names = [my_set.localized_names[language] for my_set in sets]
        return set_names
      
    # TODO: This is bizarre. Also, it seems Turtle Set does not like this.
    # Update: Turtle set is fixed, but now Gelano doesn't work.
    def get_number_of_items_in_set_by_id(self, set_id):
        item_names = set()
        for item_id in self.get_set_by_id(set_id).items:
            item_names.add(normalize_name(self.get_item_by_id(item_id).name))
        return len(item_names)
      
    def get_complete_sets_list(self, lang, dofus_touch=False):  
        sets = {}
        for s in self.get_sets_list(dofus_touch):
            items = [self.get_item_by_id(item_id).localized_names[lang] for item_id in s.items]
            sets[s.localized_names[lang]] = items
        return sets
      
    def get_items_list(self, dofus_touch=False):
        if dofus_touch:
            return self.dt_items_list
        else:
            return self.items_list
    
    def get_concatenated_items_lists(self):
        return itertools.chain(self.get_items_list(False), self.get_items_list(True))
        
    def get_available_items_list(self, dofus_touch=False):
        if dofus_touch:
            return self.dt_available_items_list
        else:
            return self.available_items_list
        
    def get_sets_list(self, dofus_touch=False):
        if dofus_touch:
            return self.dt_sets_list
        else:
            return self.sets_list

    def get_stats_list(self):
        return self.stats_list

    def get_used_stat_keys(self):
        # Stat keys that appear on an item or set bonus in this version's data
        # (PVP resists exist in retro but not in Dofus 2/3).
        if self._used_stat_keys is None:
            used = set()
            for item in itertools.chain(self.items_list, self.dt_items_list):
                for stat_id, _value in item.stats:
                    stat = self.get_stat_by_id(stat_id)
                    if stat is not None:
                        used.add(stat.key)
            for item_set in itertools.chain(self.sets_list, self.dt_sets_list):
                for _num_items, stat_id, _value in item_set.bonus:
                    stat = self.get_stat_by_id(stat_id)
                    if stat is not None:
                        used.add(stat.key)
            self._used_stat_keys = used
        return self._used_stat_keys
        
    def get_types_list(self):
        return self.types_list

    def get_stats_list_names_sorted(self):
        return self.stats_list_names_sorted
        
    def get_type_id_by_name(self, name):
        for type_id, type_name in self.types_dict.items():
            if type_name == name:
                return type_id
        return None
        
    def get_set_id_by_name(self, name, dofus_touch=False):
        set_list = []
        if dofus_touch:
            set_list = iter(self.dt_sets_dict.items())
        else:
            set_list = iter(self.sets_dict.items())  
        for _, item_set in set_list:
            if item_set.name == name:
                return item_set.id
        return None
        
    def get_stat_by_id(self, stat_id):
        return self.stat_dict.get(stat_id)
        
    def get_stat_by_key(self, key):
        return self.stat_dict_key.get(key)
        
    def get_stat_by_name(self, name):
        return self.stat_dict_name.get(name)
        
    def get_weapon_type_by_id(self, id):
        if id is None:
            return None
        return self.weapon_type_dict[id]
        
    def get_weapon_type_by_key(self, key):
        return self.weapon_type_dict_key[key]
        
    def get_weapon_type_by_name(self, name):
        if name in self.weapon_type_dict_name:
            return self.weapon_type_dict_name[name]
        return None
        
    def get_type_name_by_id(self, type_id):
        return self.types_dict[type_id]
    
    def get_item_name_by_id(self, item_id, dofus_touch=False):
        if dofus_touch:
            return self.dt_items_dict[item_id].name
        else:
            return self.items_dict[item_id].name
    
    def get_item_by_id(self, item_id):
        if item_id in self.dt_items_dict:
            return self.dt_items_dict.get(item_id)
        found = self.items_dict.get(item_id, None)
        if found is None:
            # A build saved when an item's branches were separate rows stored
            # the row it was solved with; that row is one item again now.
            moved = self.legacy_item_ids.get(item_id)
            if moved is not None:
                return self.items_dict.get(moved, None)
        return found

    def get_item_by_ankama_id(self, ankama_id, dofus_touch=False):
        if dofus_touch:
            return self.dt_items_dict_ankama.get(ankama_id)
        return self.items_dict_ankama.get(ankama_id)

    def get_item_by_name(self, name, dofus_touch=False):
        if dofus_touch:
            if name in self.dt_items_dict_name:
                return self.dt_items_dict_name[name]
        else:
            if name in self.items_dict_name:
                return self.items_dict_name[name]
        return None
        
    def get_or_item_by_name(self, name, dofus_touch=False):
        if not dofus_touch:
            if name in self.or_items:
                return self.or_items[name]
        else:
            if name in self.dt_or_items:
                return self.dt_or_items[name]
        return None

    def get_items_by_or_name(self, or_name, dofus_touch=False):
        items = self.get_or_item_by_name(or_name, dofus_touch)
        if items is not None:
            return items
        return [self.get_item_by_name(or_name, dofus_touch)]
    
    def get_items_by_or_id(self, item_id, dofus_touch=False):
        ors = self.get_or_items(dofus_touch)
        for item in ors:
            for each_or in ors[item]:
                if item_id == each_or.id:
                    return ors[item]
        return [self.get_item_by_id(item_id)]

    def get_set_by_id(self, set_id):
        # dt_sets_dict holds the synthetic touch sets (Jellix/Gelano), whose ids
        # collide with real ones: 1 is both the dofus3 Gobball Set and the touch
        # Jellix Set. read_set_bonus_table stores .bonus on the sets_dict object.
        if set_id in self.sets_dict:
            return self.sets_dict.get(set_id)
        return self.dt_sets_dict.get(set_id)
    
    def _is_item_dofus_touch(self, item_id):
        if item_id in self.dt_items_dict:
            return True
        if item_id in self.items_dict: 
            return False
        return None

    def get_set_by_name(self, name, dofus_touch=False):
        set_id = self.get_set_id_by_name(name, dofus_touch)
        return self.get_set_by_id(set_id) if (set_id is not None) else None

    def get_or_items(self, dofus_touch=False):
        if dofus_touch:
            return self.dt_or_items
        else:
            return self.or_items

    def get_available_or_items(self, dofus_touch=False):
        if dofus_touch:
            return self._dt_available_or_items
        else:
            return self._available_or_items

    def get_weapon_by_name(self, name, dofus_touch=False):
        or_items = self.dt_or_items if dofus_touch else self.or_items
        weapons = (self.dt_weapons_dict_by_name if dofus_touch
                   else self.weapons_dict_by_name)
        if name in or_items:
            # An OR item is only stored under its branches ("Ice Daggers (#1)").
            name = or_items[name][0].name
        return weapons.get(name)
        
    def item_exists(self, name, dofus_touch=False):
        if dofus_touch:
            return name in self.dt_items_dict_name or name in self.dt_or_items
        else:
            return name in self.items_dict_name or name in self.or_items
        
    def get_or_item_name(self, item_name):
        m = re.match(r"(.*) \(#\d+\)", item_name)             
        if m is not None:
            return m.group(1)
        return item_name
        
    def update_item_name(self, old_name, new_name, dofus_touch=False):
        if dofus_touch:
            self.dt_items_dict_name[new_name] = self.dt_items_dict_name[old_name]
            del self.dt_items_dict_name[old_name]
        else:
            self.items_dict_name[new_name] = self.items_dict_name[old_name]
            del self.items_dict_name[old_name]
        
    def get_main_stats_list(self):
        main_stats = []        
        main_stats.append(self.get_stat_by_name('Vitality'))
        main_stats.append(self.get_stat_by_name('Wisdom'))
        main_stats.append(self.get_stat_by_name('Intelligence'))
        main_stats.append(self.get_stat_by_name('Agility'))
        main_stats.append(self.get_stat_by_name('Chance'))
        main_stats.append(self.get_stat_by_name('Strength'))
        return main_stats
    
    def get_or_name_in_language(self, or_name, language, dofus_touch=False):
        or_item = self.get_or_item_by_name(or_name, dofus_touch);
        if or_item is None:
            return None
        return or_item[0].localized_names[language]

    def get_item_name_in_language(self, item, language):
        if language in item.localized_names:
            item_name = item.localized_names[language]
        else:
            item_name = self.get_or_name_in_language(item.name, language)
            if item_name is None:
                item_name = '[!] %s' % item.name
        return item_name

    def get_random_item(self, dofus_touch=False):
        number_of_items = len(self.get_available_items_list())
        item_obj = None
        while item_obj is None:
            item_id = random.randrange(1, number_of_items + 1)
            if dofus_touch:
                item_obj = self.get_item_by_id(item_id)
            else:
                item_obj = self.get_item_by_id(item_id)
        return item_obj

    def get_adv_mins(self):
        adv_min_fields = []
        pow_str = {}
        pow_str['key'] = 'powstr'
        pow_str['name'] = 'Power + Strength'
        pow_str['local_name'] = ('%s + %s' % (_('Power'), _('Strength')))
        pow_str['stats'] = []
        pow_str['stats'].append('Strength')
        pow_str['stats'].append('Power')
        adv_min_fields.append(pow_str)
        pow_int = {}
        pow_int['key'] = 'powint'
        pow_int['name'] = 'Power + Intelligence'
        pow_int['local_name'] = ('%s + %s' % (_('Power'), _('Intelligence')))
        pow_int['stats'] = []
        pow_int['stats'].append('Intelligence')
        pow_int['stats'].append('Power')
        adv_min_fields.append(pow_int)
        pow_cha = {}
        pow_cha['key'] = 'powcha'
        pow_cha['name'] = 'Power + Chance'
        pow_cha['local_name'] = ('%s + %s' % (_('Power'), _('Chance')))
        pow_cha['stats'] = []
        pow_cha['stats'].append('Chance')
        pow_cha['stats'].append('Power')
        adv_min_fields.append(pow_cha)
        pow_agi = {}
        pow_agi['key'] = 'powagi'
        pow_agi['name'] = 'Power + Agility'
        pow_agi['local_name'] = ('%s + %s' % (_('Power'), _('Agility')))
        pow_agi['stats'] = []
        pow_agi['stats'].append('Agility')
        pow_agi['stats'].append('Power')
        adv_min_fields.append(pow_agi)
        dam_str = {}
        dam_str['key'] = 'damstr'
        dam_str['name'] = 'Damage + Earth Damage'
        dam_str['local_name'] = ('%s + %s' % (_('Damage'), _('Earth Damage')))
        dam_str['stats'] = []
        dam_str['stats'].append('Damage')
        dam_str['stats'].append('Earth Damage')
        adv_min_fields.append(dam_str)
        dam_int = {}
        dam_int['key'] = 'damint'
        dam_int['name'] = 'Damage + Fire Damage'
        dam_int['local_name'] = ('%s + %s' % (_('Damage'), _('Fire Damage')))
        dam_int['stats'] = []
        dam_int['stats'].append('Damage')
        dam_int['stats'].append('Fire Damage')
        adv_min_fields.append(dam_int)
        dam_cha = {}
        dam_cha['key'] = 'damcha'
        dam_cha['name'] = 'Damage + Water Damage'
        dam_cha['local_name'] = ('%s + %s' % (_('Damage'), _('Water Damage')))
        dam_cha['stats'] = []
        dam_cha['stats'].append('Water Damage')
        dam_cha['stats'].append('Damage')
        adv_min_fields.append(dam_cha)
        dam_agi = {}
        dam_agi['key'] = 'damagi'
        dam_agi['name'] = 'Damage + Air Damage'
        dam_agi['local_name'] = ('%s + %s' % (_('Damage'), _('Air Damage')))
        dam_agi['stats'] = []
        dam_agi['stats'].append('Air Damage')
        dam_agi['stats'].append('Damage')
        adv_min_fields.append(dam_agi)
        sum_perc_res = {}
        sum_perc_res['key'] = 'sum_perc_res'
        sum_perc_res['name'] = 'Sum of all % Resists'
        sum_perc_res['local_name'] = _('Sum of all % Resists')
        sum_perc_res['stats'] = []
        sum_perc_res['stats'].append('% Neutral Resist')
        sum_perc_res['stats'].append('% Earth Resist')
        sum_perc_res['stats'].append('% Fire Resist')
        sum_perc_res['stats'].append('% Water Resist')
        sum_perc_res['stats'].append('% Air Resist')
        adv_min_fields.append(sum_perc_res)
        sum_perc_res_neut = {}
        sum_perc_res_neut['key'] = 'sum_perc_res_but_neut'
        sum_perc_res_neut['name'] = 'Sum of all % Resists except neutral'
        sum_perc_res_neut['local_name'] = _('Sum of all % Resists except neutral')
        sum_perc_res_neut['stats'] = []
        sum_perc_res_neut['stats'].append('% Earth Resist')
        sum_perc_res_neut['stats'].append('% Fire Resist')
        sum_perc_res_neut['stats'].append('% Water Resist')
        sum_perc_res_neut['stats'].append('% Air Resist')
        adv_min_fields.append(sum_perc_res_neut)
        sum_res = {}
        sum_res['key'] = 'sum_res'
        sum_res['name'] = 'Sum of all Linear Resists'
        sum_res['local_name'] = _('Sum of all Linear Resists')
        sum_res['stats'] = []
        sum_res['stats'].append('Neutral Resist')
        sum_res['stats'].append('Earth Resist')
        sum_res['stats'].append('Fire Resist')
        sum_res['stats'].append('Water Resist')
        sum_res['stats'].append('Air Resist')
        adv_min_fields.append(sum_res)
        sum_res_neut = {}
        sum_res_neut['key'] = 'sum_res_but_neut'
        sum_res_neut['name'] = 'Sum of all Linear Resists except neutral'
        sum_res_neut['local_name'] = _('Sum of all Linear Resists except neutral')
        sum_res_neut['stats'] = []
        sum_res_neut['stats'].append('Earth Resist')
        sum_res_neut['stats'].append('Fire Resist')
        sum_res_neut['stats'].append('Water Resist')
        sum_res_neut['stats'].append('Air Resist')
        adv_min_fields.append(sum_res_neut)
        return adv_min_fields
    
    def get_adv_min_stat_by_name(self, name):
        stats = self.get_adv_mins()
        for stat in stats:
            if stat['name'] == name:
                return stat
        return None