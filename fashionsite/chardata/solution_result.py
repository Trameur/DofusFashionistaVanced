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

from django.conf import settings
from django.utils.translation import get_language, gettext as _
import json

logger = logging.getLogger(__name__)

# Origins that mean the player imported this set
IMPORT_ORIGINS = ('dofusbook', 'pasted_text')

from chardata.forgemagie_data import MAGEABLE_TYPES
from chardata.image_store import get_image_url
from chardata.item_sources import acquisition_summary, attach_acquisition
from fashionistapulp.dofus_constants import NEUTRAL, STAT_ORDER,\
    SLOT_NAME_TO_TYPE, STAT_KEY_TO_NAME
from fashionistapulp.exo_options import exo_per_item
from fashionistapulp.fashion_util import normalize_name
from fashionistapulp.modelresult import (characteristic_passives,
                                         level_prospecting,
                                         sets_equipped_text,
                                         wisdom_per_ap_mp_dodge_point)
from fashionistapulp.structure import get_structure, get_current_game_version
from chardata.spell_tips import spell_tip_for
from chardata.forgemagie_transcendance import rune_name
from chardata.transcendence_advice import best_transcendence
from chardata.stat_icons import get_stat_icon_path
from chardata.stat_range import format_stat_range
from chardata.weapon_header import format_weapon_header, format_weapon_hit
from chardata.wear_conditions import (class_condition_text,
                                      max_level_condition_text,
                                      name_condition_text,
                                      not_worn_with_condition_text,
                                      other_item_name,
                                      sex_condition_text,
                                      spell_rank_condition_text,
                                      unusable_condition_text)
from fashionistapulp.structure import name_fits
from static_s3.templatetags.static_s3 import static
from .translation_util import LOCALIZED_ELEMENTS, LOCALIZED_WEAPON_TYPES
from chardata.official_site import get_set_link


class SolutionResult:

    def __init__(self, model_result, inclusions={}, exclusions=[], empty_slots=[],
                 weights=None, char_class=None, gender=None, char_name=None):
        self.model_result = model_result
        self.inclusions = inclusions
        self.exclusions_set = set(exclusions)
        self.empty_slots_set = set(empty_slots)
        self.weights = weights
        self.char_class = char_class
        self.gender = gender
        self.char_name = char_name
                   
    def get_params(self):
        r = self.model_result 
        
        item_list_ordered = []
        item_list_ordered.extend(r.items['Weapon'])
        item_list_ordered.extend(r.items['Hat'])
        item_list_ordered.extend(r.items['Cloak'])
        item_list_ordered.extend(r.items['Amulet'])
        item_list_ordered.extend(r.items['Ring'])
        item_list_ordered.extend(r.items['Boots'])
        item_list_ordered.extend(r.items['Belt'])
        item_list_ordered.extend(r.items['Shield'])
        item_list_ordered.extend(r.items['Pet'])
        item_columns = [item_list_ordered[::2], item_list_ordered[1::2]]
        
        dofus_list = r.items['Dofus']
        dofus_columns = [dofus_list[::2], dofus_list[1::2]]
        
        item_sections = [item_columns, dofus_columns]
        all_items = item_list_ordered + dofus_list
        emblem_list = sorted(r.items.get('Emblem') or [],
                             key=lambda result_item: result_item.slot or '')
        if emblem_list:
            item_sections.append([emblem_list[::2], emblem_list[1::2]])
            all_items = all_items + emblem_list
        item_per_slot = {}
        
        # TODO: Grafting this attribute is a hack.
        item_is_locked = {}
        item_is_forbidden = {}
        item_is_empty_locked = {}
        item_names = {}
        translated_item_names = {}
        item_violates = {}
        item_ids = {}
        per_item = exo_per_item(get_current_game_version())
        if per_item:
            r.get_stats_gear()
        for result_item in all_items:
            evolve_result_item(result_item, r, self.char_class,
                               self.gender, self.char_name)
            attach_transcendence(result_item, self.weights)
        attach_acquisition(all_items)

        for result_item in all_items:
            result_item.mageable = (SLOT_NAME_TO_TYPE.get(result_item.slot)
                                    in MAGEABLE_TYPES)
            item_per_slot[result_item.slot] = result_item
            item_is_locked[result_item.slot] = self.is_item_locked(result_item)
            item_is_forbidden[result_item.slot] = self.is_item_forbidden(result_item)
            result_item.is_empty_locked = (not result_item.item_added
                                           and result_item.slot in self.empty_slots_set)
            item_is_empty_locked[result_item.slot] = result_item.is_empty_locked
            item_names[result_item.slot] = (result_item.or_name
                                            if result_item.item_added
                                            else _(SLOT_NAME_TO_TYPE[result_item.slot]))
            translated_item_names[result_item.slot] = (result_item.localized_name
                                            if result_item.item_added
                                            else _(SLOT_NAME_TO_TYPE[result_item.slot]))
            if result_item.item_added and result_item.id is not None:
                item_ids[result_item.slot] = result_item.id
            s = get_structure()
            item_violates[result_item.slot] = False
            if result_item.item_added and len(r.get_violations_on_item(result_item)) > 0:
                item_violates[result_item.slot] = True
                
                
        # TODO: Grafting this attribute is a hack.
        for result_set in r.sets:
            result_set.url = get_set_link(result_set.id, result_set.localized_name,
                                          game_version=get_current_game_version())
            stats_from_result_set = sorted(iter(result_set.get_bonus().items()),
                                           key=lambda x: STAT_ORDER[x[0]])

            result_set.stats_lines = []
            for stat_key, stat_value in stats_from_result_set:
                stat_name = get_structure().get_stat_by_key(stat_key).name
                result_set.stats_lines.append(AttributeLine(stat_key, stat_value, stat_name))

            for stat_key, stat_name, max_value in result_set.get_max_caps():
                result_set.stats_lines.append(CapLine(stat_key, stat_name, max_value))
                           
            # This is a dict to handle cases like Air Bwaks, that can be multiple different
            # items, but we only want to display one.
            result_set.parts = {}
            for result_item in result_set.items:
                if result_item.item_added:
                    item_file = get_image_url(result_item.type, result_item.name)
                    if item_file not in result_set.parts:
                        used_in_set = any([result_item.id == item.id for item in all_items])
                        result_set.parts[item_file] = (normalize_name(result_item.localized_name),
                                                       _(result_item.type),
                                                       used_in_set)

        params = {'item_sections': item_sections,
                  'sets': r.sets,
                  'all_items': all_items,
                  'acquisition_summary': acquisition_summary(all_items),
                  'stats_base_json': json.dumps(r.get_stats_base()),
                  'stats_gear_json': json.dumps(r.get_stats_gear()),
                  'stats_total_json': json.dumps(r.get_stats_total()),
                  'stat_sources_json': json.dumps(stat_sources(r)),
                  'exo_per_item': per_item,
                  'exo_points_json': json.dumps(getattr(r, 'exo_points', None)
                                                if per_item else None),
                  'item_names': json.dumps(item_names),
                  'translated_item_names': json.dumps(translated_item_names),
                  'item_ids': json.dumps(item_ids),
                  'item_is_locked': json.dumps(item_is_locked),
                  'item_is_forbidden': json.dumps(item_is_forbidden),
                  'item_is_empty_locked': json.dumps(item_is_empty_locked),
                  'item_violates': json.dumps(item_violates),
                  'options_json': json.dumps(r.input['options']),
                  # Solved with TemporiX or not, whatever the switch says now
                  'temporix_solve': bool((r.input.get('options') or {}).get(
                      'temporix')),
                  'item_per_slot': item_per_slot,
                  'is_generated': (r.input.get('origin', 'generated') == 'generated'),
                  # An imported set is neither suggested nor empty
                  'is_imported': (r.input.get('origin')
                                  in IMPORT_ORIGINS),}
        return params

    def is_item_locked(self, result_item):
        if result_item.item_added:
            return self.inclusions.get(result_item.slot, '') == result_item.or_name
        
    def is_item_forbidden(self, result_item):
        if result_item.item_added:
            return result_item.or_name in self.exclusions_set


def stat_sources(model_result):
    """Where each stats panel total comes from, one line per source."""
    from fashionistapulp.dofus_constants import BASE_STATS, STAT_KEY_TO_NAME
    # A non-result is a wiring mistake, not a missing piece
    if not hasattr(model_result, 'get_stats_total'):
        raise TypeError('stat_sources needs the model result, got %s'
                        % type(model_result).__name__)
    sources = {}

    def add(stat_key, label, value, kind):
        if not value:
            return
        sources.setdefault(stat_key, []).append(
            {'label': label, 'value': value, 'kind': kind})

    def running(stat_key):
        return sum(line['value'] for line in sources.get(stat_key, []))

    # A partial result still explains what it can
    for result_item in getattr(model_result, 'item_list', None) or []:
        if not result_item.item_added:
            continue
        name = (getattr(result_item, 'localized_name', None)
                or getattr(result_item, 'name', ''))
        for stat_key, value in (result_item.stats or {}).items():
            add(stat_key, name, value, 'item')

    for result_set in getattr(model_result, 'sets', None) or []:
        name = (getattr(result_set, 'localized_name', None)
                or getattr(result_set, 'name', ''))
        for stat_key, value in result_set.get_bonus().items():
            add(stat_key, name, value, 'set')

    model_input = getattr(model_result, 'input', None) or {}
    options = model_input.get('options') or {}
    if exo_per_item(get_current_game_version()):
        _add_exos_per_piece(model_result, add)
    else:
        for stat_key, option in (('ap', 'ap_exo'), ('mp', 'mp_exo'),
                                 ('range', 'range_exo')):
            # mp_exo can hold "gelano" (the ring), which is not a free point
            if options.get(option) is True:
                add(stat_key, _('Exotic bonus'), 1, 'exo')

    base_by_attr = model_input.get('base_stats_by_attr') or {}
    distributed = getattr(model_result, 'stats', None) or {}
    for stat in get_structure().get_stats_list():
        base = base_by_attr.get(stat.name, 0)
        if stat.key in BASE_STATS:
            base += distributed.get(stat.key, 0)
        add(stat.key, _('Base'), base, 'base')

    try:
        total = model_result.get_stats_total()
    except Exception:                                        # noqa: BLE001
        logger.warning('a solution could not total its stats', exc_info=True)
        return sources

    def characteristic(key):
        return _(STAT_KEY_TO_NAME[key])

    version = get_current_game_version()
    wisdom_per_point = wisdom_per_ap_mp_dodge_point(version)
    for stat_key in ('apres', 'mpres', 'apred', 'mpred'):
        add(stat_key, characteristic('wis'),
            total.get('wis', 0) // wisdom_per_point, 'derived')
    for stat_key, from_key, per, gain in characteristic_passives(version):
        add(stat_key, characteristic(from_key),
            total.get(from_key, 0) // per * gain, 'derived')
    add('pp', _('Level'),
        level_prospecting(version, model_input.get('char_level', 0)),
        'derived')
    for from_key in ('str', 'int', 'cha', 'agi'):
        add('init', characteristic(from_key), total.get(from_key, 0), 'derived')
    add('hp', characteristic('vit'), total.get('vit', 0), 'derived')
    add('hp', _('Level'), model_input.get('char_level', 0) * 5 + 50,
        'derived')

    # An active set can cap a stat, so say what was cut
    for result_set in getattr(model_result, 'sets', None) or []:
        name = (getattr(result_set, 'localized_name', None)
                or getattr(result_set, 'name', ''))
        for stat_key, _stat_name, max_cap in result_set.get_max_caps():
            over = running(stat_key) - max_cap
            if over > 0:
                add(stat_key, name, -over, 'cap')

    for lines in sources.values():
        # By signed value, so a malus sorts below the bonuses
        lines.sort(key=lambda line: (line['kind'] == 'cap',
                                     -line['value'], line['label']))
    return sources


def _add_exos_per_piece(model_result, add):
    """One line per exo a worn piece holds, owned or still to forge."""
    place = getattr(model_result, 'place_assumed_exos', None)
    if place is not None:
        place()
    for result_item in getattr(model_result, 'item_list', None) or []:
        if not result_item.item_added:
            continue
        name = (getattr(result_item, 'localized_name', None)
                or getattr(result_item, 'name', ''))
        label = _('%(item)s, exo') % {'item': name}
        for stat_key in getattr(result_item, 'exo_overrides', None) or {}:
            add(stat_key, label, 1, 'exo')
        if getattr(result_item, 'assumed_exo', None):
            add(result_item.assumed_exo, label, 1, 'exo')


def _worn_ids(model_result):
    if not model_result:
        return set()
    return {getattr(result_item, 'id', None)
            for result_items in (getattr(model_result, 'items', None) or {}).values()
            for result_item in result_items
            if getattr(result_item, 'item_added', False)}


def evolve_result_item(result_item, r=None, char_class=None, gender=None, char_name=None):
    if result_item.slot:
        result_item.file = static('chardata/%s.png' % SLOT_NAME_TO_TYPE[result_item.slot])
    if not result_item.item_added:
        if not result_item.file:
            logger.debug('No item and no slot for picture.')
        return
    exo_overrides = getattr(result_item, 'exo_overrides', {}) or {}
    base_stats = getattr(result_item, 'base_stats', None)
    merged_stats = dict(result_item.stats)
    for stat_key, override_val in exo_overrides.items():
        merged_stats[stat_key] = override_val
    stats_from_result_item = sorted(iter(merged_stats.items()),
                                    key=lambda x: STAT_ORDER[x[0]])

    # DofusBook's two marks: a line changed from the catalogue, a line added to it
    result_item.has_exo = base_stats is not None and (bool(exo_overrides) or any(
        value and key not in base_stats
        for key, value in result_item.stats.items()))
    result_item.has_forge = base_stats is not None and any(
        result_item.stats.get(key, 0) != value
        for key, value in base_stats.items())
    assumed_exo = getattr(result_item, 'assumed_exo', None)
    result_item.assumed_exo_label = _(STAT_KEY_TO_NAME[assumed_exo]) if assumed_exo else None

    result_item.stats_lines = []
    # Absent from solutions pickled before the ranges existed.
    stat_ranges = getattr(result_item, 'stat_ranges', None) or {}
    for stat_key, stat_value in stats_from_result_item:
        stat_name = get_structure().get_stat_by_key(stat_key).name
        line = AttributeLine(stat_key, stat_value, stat_name,
                             stat_ranges.get(stat_key))
        if base_stats is not None and line.formatting == '':
            base_val = base_stats.get(stat_key)
            if base_val is None:
                if stat_value != 0:
                    line.formatting = '#b'
            elif stat_value > base_val:
                line.formatting = '#b'
            elif stat_value < base_val:
                line.formatting = '#o'
        result_item.stats_lines.append(line)
    spell_tooltips = getattr(result_item, 'spell_tooltips', None) or {}
    for extra in result_item.extras:
        if isinstance(extra, tuple):
            text, icon_key = extra
            line = ExtraLine(text)
            line.icon_url = static(icon_key) if icon_key else None
        else:
            line = ExtraLine(extra)
        line.spell_tip = spell_tip_for(line.text, spell_tooltips)
        result_item.stats_lines.append(line)

    result_item.condition_lines = []

    min_stats = getattr(result_item, 'min_stats_to_equip', None) or {}
    max_stats = getattr(result_item, 'max_stats_to_equip', None) or {}
    exact = {stat_key for stat_key, stat_value in min_stats.items()
             if max_stats.get(stat_key) == stat_value}
    for stat_key in sorted(exact, key=lambda key: STAT_ORDER[key]):
        stat_name = get_structure().get_stat_by_key(stat_key).name
        result_item.condition_lines.append(
            ExactConditionLine(stat_key, min_stats[stat_key], stat_name, r))

    if hasattr(result_item, 'min_stats_to_equip'):
        min_from_result_item = sorted(iter(result_item.min_stats_to_equip.items()),
                                      key=lambda x: STAT_ORDER[x[0]])
        for stat_key, stat_value in min_from_result_item:
            if stat_key in exact:
                continue
            stat_name = get_structure().get_stat_by_key(stat_key).name
            result_item.condition_lines.append(MinConditionLine(stat_key, stat_value, stat_name, r))

    if hasattr(result_item, 'max_stats_to_equip'):
        max_from_result_item = sorted(iter(result_item.max_stats_to_equip.items()),
                                      key=lambda x: STAT_ORDER[x[0]])
        for stat_key, stat_value in max_from_result_item:
            if stat_key in exact:
                continue
            stat_name = get_structure().get_stat_by_key(stat_key).name
            result_item.condition_lines.append(MaxConditionLine(stat_key, stat_value, stat_name, r))

    if result_item.weird_conditions['light_set']:
        result_item.condition_lines.append(
            LightSetConditionLine(r, result_item.weird_conditions['light_set']))

    sets_equipped = result_item.weird_conditions.get('sets_equipped')
    if sets_equipped:
        result_item.condition_lines.append(
            SetsEquippedConditionLine(r, sets_equipped))

    if result_item.weird_conditions['prysmaradite']:
        result_item.condition_lines.append(PrysmaraditeConditionLine(r))

    if getattr(result_item, 'unusable', False):
        line = TextConditionLine(unusable_condition_text())
        line.formatting = '#r'
        result_item.condition_lines.append(line)
    classes = getattr(result_item, 'classes', ())
    if classes:
        line = TextConditionLine(class_condition_text(classes))
        if char_class and char_class not in classes:
            line.formatting = '#r'
        result_item.condition_lines.append(line)
    max_level = getattr(result_item, 'max_level', None)
    if max_level is not None:
        line = TextConditionLine(max_level_condition_text(max_level))
        if r and (r.input or {}).get('char_level', max_level) > max_level:
            line.formatting = '#r'
        result_item.condition_lines.append(line)
    worn_ids = _worn_ids(r)
    for other_id in getattr(result_item, 'own_not_worn_with', ()):
        name = other_item_name(get_current_game_version(), other_id)
        if name is None:
            continue
        line = TextConditionLine(not_worn_with_condition_text(name))
        if other_id in worn_ids:
            line.formatting = '#r'
        result_item.condition_lines.append(line)
    sexes = tuple(getattr(result_item, 'sexes', ()))
    if sexes:
        line = TextConditionLine(sex_condition_text(sexes))
        if gender is not None and gender not in sexes:
            line.formatting = '#r'
        result_item.condition_lines.append(line)
    names = tuple(getattr(result_item, 'names', ()))
    if names:
        line = TextConditionLine(name_condition_text(names))
        if char_name is not None and not any(name_fits(char_name, name) for name in names):
            line.formatting = '#r'
        result_item.condition_lines.append(line)
    for spell_id, rank, min_level in getattr(result_item, 'spell_conditions', ()):
        line = TextConditionLine(spell_rank_condition_text(
            get_current_game_version(), classes, spell_id, rank))
        if r and (r.input or {}).get('char_level', min_level) < min_level:
            line.formatting = '#r'
        result_item.condition_lines.append(line)

    if hasattr(result_item, 'non_crit_hits'):
        damage_lines = []
        weapon_type_key = result_item.weapon_type
        # Some weapons (magnifying glass, fishing rod...) have no type, so skip
        # the "(type)" prefix for them.
        localized_weapon_type = LOCALIZED_WEAPON_TYPES.get(weapon_type_key)

        header = format_weapon_header(
            get_current_game_version(), localized_weapon_type, result_item.ap,
            result_item.crit_chance, result_item.crit_bonus)
        if header:
            damage_lines.append(header)
        for hit in result_item.non_crit_hits[NEUTRAL]:
            damage_lines.append(format_weapon_hit(get_current_game_version(),
                                                  hit, LOCALIZED_ELEMENTS))
        result_item.damage_text = '<br>'.join(damage_lines)

    result_item.file = static(get_image_url(result_item.type, result_item.name))
    if settings.EXPERIMENTS['ITEM_LINKS']:
        from chardata.encyclopedia_view import _item_page_link
        from fashionistapulp.translation import get_supported_language
        result_item.link = _item_page_link(get_current_game_version(),
                                           result_item.ankama_type,
                                           result_item.ankama_id,
                                           result_item.localized_name,
                                           get_supported_language())


def attach_transcendence(result_item, weights):
    result_item.transcendence = None
    if not result_item.item_added or not weights:
        return
    rune = best_transcendence(get_current_game_version(),
                              getattr(result_item, 'stats', None) or {}, weights,
                              result_item.type)
    if rune is None:
        return
    # Each client names the runes in its own language
    result_item.transcendence = '%s: +%d %s' % (
        rune_name(rune, get_language()), rune['bonus'],
        _(get_structure().get_stat_by_key(rune['stat_key']).name))


class AttributeLine:
    
    def __init__(self, stat_key, stat_value, stat_name, stat_range=None):
        # Round stat value to nearest integer to avoid floating-point precision issues
        rounded_value = int(round(stat_value))
        self.text = ('%d%s%s'
                     % (rounded_value,
                        '' if stat_name.startswith('%') else ' ',
                        _(stat_name)))
        self.range_text = format_stat_range(*stat_range) if stat_range else None
        self.formatting = '#r' if stat_value < 0 else ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None

class ExtraLine:

    def __init__(self, line):
        self.text = line
        self.formatting = ''
        self.icon_url = None
        self.spell_tip = None

class MinConditionLine:
    
    def __init__(self, stat_key, stat_value, stat_name, model_result):
        self.text = ('%s > %d'
                     % (_(stat_name),
                        stat_value - 1))
        self.formatting = ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None
        if model_result:
            s = get_structure()
            stat = s.get_stat_by_name(stat_name)
            if model_result.stats_total[stat.key] < stat_value:
                self.formatting = '#r'

class ExactConditionLine:

    def __init__(self, stat_key, stat_value, stat_name, model_result):
        self.text = '%s = %d' % (_(stat_name), stat_value)
        self.formatting = ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None
        if model_result:
            stat = get_structure().get_stat_by_name(stat_name)
            if model_result.stats_total[stat.key] != stat_value:
                self.formatting = '#r'

class MaxConditionLine:
    
    def __init__(self, stat_key, stat_value, stat_name, model_result):
        self.text = ('%s < %d'
                     % (_(stat_name),
                        stat_value + 1))
        self.formatting = ''
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None
        if model_result:
            s = get_structure()
            stat = s.get_stat_by_name(stat_name)
            if model_result.stats_total[stat.key] > stat_value:
                self.formatting = '#r'

class LightSetConditionLine:

    def __init__(self, model_result, cap=2):
        cap = 2 if cap is True else cap
        self.text = _('Set bonus < 2') if cap <= 1 else _('Set bonus < 3')
        self.formatting = ''
        if model_result:
            if not model_result.check_if_set_is_light():
                self.formatting = '#r'

class SetsEquippedConditionLine:

    def __init__(self, model_result, cap):
        self.text = sets_equipped_text(cap)
        self.formatting = ''
        if model_result and not model_result.check_sets_equipped(cap):
            self.formatting = '#r'

class TextConditionLine:

    def __init__(self, text):
        self.text = text
        self.formatting = ''
        self.icon_url = None


class PrysmaraditeConditionLine:

    def __init__(self, model_result):
        self.text = _('Prysmaradite < 1')
        self.formatting = ''
        if model_result:
            if not model_result.check_if_prysmaradite():
                self.formatting = '#r'


class CapLine:

    def __init__(self, stat_key, stat_name, max_value):
        self.text = _('Max. %(stat)s %(value)d') % {'stat': _(stat_name), 'value': max_value}
        self.formatting = '#r'
        icon_path = get_stat_icon_path(stat_key)
        self.icon_url = static(icon_path) if icon_path else None
