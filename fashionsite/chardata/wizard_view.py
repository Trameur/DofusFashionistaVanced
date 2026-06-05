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

from django.urls import reverse
from django.http import HttpResponseRedirect
import jsonpickle

from chardata.lock_forbid import get_inclusions_dict, set_item_included, set_excluded
from chardata.min_stats import get_min_stats, set_min_stats
from chardata.models import CharBaseStats
from chardata.options import get_options, set_options, DOFUS_OPTIONS, get_available_options
from chardata.options_view import parse_options_post
from chardata.smart_build import reapply_weights
from chardata.util import set_response, safe_int, get_char_or_raise, HttpResponseJson, version_reverse
from chardata.wizard_sliders import get_wizard_sliders, set_wizard_sliders
from fashionistapulp.dofus_constants import STATS_NAMES, SLOT_NAME_TO_TYPE
from fashionistapulp.structure import get_structure
from static_s3.templatetags.static_s3 import static
from fashionistapulp.translation import get_supported_language
from chardata.themes import get_triangle_URL


CRIT_TARGETS = [50, 45, 40, 35, 30, 25, 20, 15, 10, 5]
STATS_WITH_CONFIG_MINS = ['AP', 'MP', 'Range']

def wizard(request, char_id):
    char = get_char_or_raise(request, char_id)

    wizard_data = Data(char)
    constant_data = ConstantData(char)
    wizard_pic = 'chardata/designs/wizard/%s/myWizard%s%d.png' % (char.char_class,
                                                                  char.char_class,
                                                                  1 + (int(char_id) % 6))

    return set_response(request,
                        'chardata/wizard.html',
                        {'char_id': char_id,
                         'wizard_pic': wizard_pic,
                         'version_options': get_available_options(),
                         'constant_data': jsonpickle.encode(constant_data, unpicklable=False),
                         'wizard_data': jsonpickle.encode(wizard_data, unpicklable=False),
                         'triangle_url': jsonpickle.encode(get_triangle_URL(request), unpicklable=False)},
                        char)

def get_resetted_sliders(request, char_id):
    char = get_char_or_raise(request, char_id)
    reapply_weights(char)
    all_sliders = get_wizard_sliders(char)
    all_sliders_json = jsonpickle.encode(all_sliders)
    return HttpResponseJson(all_sliders_json)

def wizard_post(request, char_id):
    char = get_char_or_raise(request, char_id)

    minimum_values = get_min_stats(char)
    for stat_name in STATS_WITH_CONFIG_MINS:
        minimum = safe_int(request.POST.get('min_%s' % stat_name, ''))
        minimum_values[stat_name] = minimum
        
    set_min_stats(char, minimum_values)
    
    weapon_to_lock = request.POST.get('weapon', None)
    if weapon_to_lock:
        set_item_included(char, weapon_to_lock, 'weapon', True)
    else:
        inclusions = get_inclusions_dict(char)
        weapon = inclusions.get('weapon')
        if weapon:
            set_item_included(char, weapon, 'weapon', False)

    options = get_options(char)
    options.update(parse_options_post(request))
    set_options(char, options)
    
    s = get_structure()
    for (red, item) in DOFUS_OPTIONS.items():
        forbidden = request.POST.get(red) is None
        dofus = s.get_item_by_name(item)
        if dofus is None:
            continue  # dofus not in this version (Retro/Dofus 2)
        set_excluded(char, dofus.id, forbidden)

    set_wizard_sliders(char, request.POST)

    scroll = request.POST.get('scrolling', 'leave')
    if scroll == 'fully':
        _full_scroll_char(char)
    elif scroll == 'clean':
        _clean_scroll_char(char)

    return HttpResponseRedirect(version_reverse(request, 'fashion', char.id))

def _get_third_scroll_option(char):
    stats_scroll_dict = {}
    for element_name, _ in STATS_NAMES:
        basestats_list = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats_list) == 0:
            return None
        else:
            basestats = basestats_list[0]
        stats_scroll_dict[basestats.stat] = basestats.scrolled_value
    all_scrolled = True
    all_empty = True
    for _, scrolled_value in stats_scroll_dict.items():
        if scrolled_value > 0:
            all_empty = False
        if scrolled_value < 100:
            all_scrolled = False
    if all_empty:
        return None
    if all_scrolled:
        return 100
    return stats_scroll_dict

def _full_scroll_char(char):
    for element_name, _ in STATS_NAMES:
        basestats_list = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats_list) == 0:
            basestats = CharBaseStats()
        else:
            basestats = basestats_list[0]
        basestats.char = char
        basestats.stat = element_name
        prev_scroll = 0
        if basestats.scrolled_value:
            prev_scroll = basestats.scrolled_value
        basestats.scrolled_value = 100
        if not basestats.total_value:
            basestats.total_value = 100
        else:
            basestats.total_value = basestats.total_value + 100 - prev_scroll
        basestats.save()  
    char.save()
    return char

def _clean_scroll_char(char):
    for element_name, _ in STATS_NAMES:
        basestats_list = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats_list) == 0:
            basestats = CharBaseStats()
        else:
            basestats = basestats_list[0]
        basestats.char = char
        basestats.stat = element_name
        prev_scroll = 0
        if basestats.scrolled_value:
            prev_scroll = basestats.scrolled_value
        basestats.scrolled_value = 0
        if not basestats.total_value:
            basestats.total_value = 0
        else:
            basestats.total_value = basestats.total_value - prev_scroll
        basestats.save()
    char.save()
    return char

class Mins():
    def __init__(self, char):
        self.mins = {k: v for (k, v) in get_min_stats(char).items()
                     if (k in STATS_WITH_CONFIG_MINS)}


class FullyScrolled():
    def __init__(self, char):
        self.scrolling = _get_third_scroll_option(char)

class Inclusions():
    def __init__(self, char):
        self.weapon = get_inclusions_dict(char).get('weapon', '')

class Options():
    def __init__(self, char):
        self.options = get_options(char)

class Sliders():
    def __init__(self, char):
        self.sliders = get_wizard_sliders(char)

class Data():
    def __init__(self, char):
        self.mins = Mins(char)
        self.inclusions = Inclusions(char)
        self.options = Options(char)
        self.sliders = Sliders(char)
        self.scrolled = FullyScrolled(char)

class ConstantInclusions():
    def __init__(self, char, slots):
        structure = get_structure()     
        self.items_by_type = {}
        self.items_by_type_and_name = {}
        for slot in slots:
            item_type = SLOT_NAME_TO_TYPE[slot]
            self.items_by_type[item_type] = {}
            self.items_by_type_and_name[item_type] = {}
            for item in structure.get_unique_items_by_type_and_level(item_type, char.level):
                item_name = structure.get_item_name_in_language(item, get_supported_language())
                self.items_by_type[item_type][item.id] = item_name
                self.items_by_type_and_name[item_type][item_name] = item.id
            
            self.images_urls={}
            self.images_urls[slot] = static('chardata/'+item_type+'.png')
        self.slot_to_type = SLOT_NAME_TO_TYPE
        
class ConstantOptions():
    def __init__(self, char):
        self.turq_values = list(range(11, 20 + 1))

class ConstantData():
    def __init__(self, char):
        self.inclusions = ConstantInclusions(char, ['weapon'])
        self.options = ConstantOptions(char)
