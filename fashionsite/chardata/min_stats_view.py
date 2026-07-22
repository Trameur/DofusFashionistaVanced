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

from chardata.min_stats import get_min_stats, set_min_stats, convert_dict_index_name_to_key
from chardata.stat_icons import get_stat_icon_path
from chardata.util import set_response, safe_int, get_char_or_raise, HttpResponseJson
from fashionistapulp.dofus_constants import STAT_ORDER
from fashionistapulp.structure import get_structure
from django.utils.translation import gettext as _
from static_s3.templatetags.static_s3 import static


def _get_stat_icon_url(stat_key):
    icon_path = get_stat_icon_path(stat_key)
    return static(icon_path) if icon_path else ''


def _get_adv_stat_icon_urls(structure, adv_stat):
    stat_name_to_key = {stat.name: stat.key for stat in structure.get_stats_list()}
    local_name = adv_stat.get('local_name', '')
    ordered_stat_names = list(adv_stat.get('stats', []))

    if local_name and ' + ' in local_name:
        localized_name_to_stat_name = {
            _(stat.name): stat.name for stat in structure.get_stats_list()
        }
        ordered_from_label = []
        for localized_part in local_name.split(' + '):
            stat_name = localized_name_to_stat_name.get(localized_part)
            if stat_name in ordered_stat_names and stat_name not in ordered_from_label:
                ordered_from_label.append(stat_name)
        if len(ordered_from_label) == len(ordered_stat_names):
            ordered_stat_names = ordered_from_label

    if adv_stat.get('key') in ('sum_perc_res', 'sum_res'):
        ordered_stat_names = [
            stat_name for stat_name in ordered_stat_names
            if stat_name not in ('% Neutral Resist', 'Neutral Resist')
        ] + [
            stat_name for stat_name in ordered_stat_names
            if stat_name in ('% Neutral Resist', 'Neutral Resist')
        ]

    icon_urls = []
    for stat_name in ordered_stat_names:
        stat_key = stat_name_to_key.get(stat_name)
        icon_url = _get_stat_icon_url(stat_key)
        if icon_url:
            icon_urls.append(icon_url)
    return icon_urls

def min_stats(request, char_id):
    char = get_char_or_raise(request, char_id)
        
    initial_data = _get_initial_data(char)
    structure = get_structure()
    
    used_stat_keys = structure.get_used_stat_keys()
    stats = []
    for stat in structure.get_stats_list():
        if stat.key == 'vit':
            continue
        # PVP resists only exist in some versions (e.g. retro); show them
        # only where the current version's items actually use them.
        if stat.key.startswith('pvp') and stat.key not in used_stat_keys:
            continue
        stat_to_add = {}
        stat_to_add['key'] = stat.key
        stat_to_add['name'] = _(stat.name)
        stat_to_add['icon_url'] = _get_stat_icon_url(stat.key)
        stats.append(stat_to_add)
    
    stats = [stat for stat in
        sorted(stats, key=lambda stat: STAT_ORDER[stat['key']])]
    
    fixed_fields = []
    ap = {}
    ap['key'] = 'ap'
    ap['name'] = _('AP')
    ap['icon_url'] = _get_stat_icon_url('ap')
    fixed_fields.append(ap)
    mp = {}
    mp['key'] = 'mp'
    mp['name'] = _('MP')
    mp['icon_url'] = _get_stat_icon_url('mp')
    fixed_fields.append(mp)
    rangestat = {}
    rangestat['key'] = 'range'
    rangestat['name'] = _('Range')
    rangestat['icon_url'] = _get_stat_icon_url('range')
    fixed_fields.append(rangestat)
    hp = {}
    hp['key'] = 'hp'
    hp['name'] = _('HP')
    hp['icon_url'] = _get_stat_icon_url('hp')
    fixed_fields.append(hp)
    
    adv_min_fields = structure.get_adv_mins()
    for stat in adv_min_fields:
        stat['icon_urls'] = _get_adv_stat_icon_urls(structure, stat)
        stat['icon_url'] = stat['icon_urls'][0] if stat['icon_urls'] else _get_stat_icon_url(stat.get('key'))
    
    return set_response(request,
                        'chardata/min_stats.html',
                        {'advanced': True,
                         'char_id': char_id,
                         'stats_order': json.dumps(stats),
                         'stats_fixed': json.dumps(fixed_fields),
                         'stats_adv': json.dumps(adv_min_fields),
                         'initial_data': json.dumps(initial_data)},
                        char)


def min_stats_post(request, char_id):
    char = get_char_or_raise(request, char_id)
    structure = get_structure()

    minimum_values = {}
    
    adv_stats = structure.get_adv_mins()
    adv_stat_keys = set([stat['key'] for stat in adv_stats])
    
    for stat in get_structure().get_stats_list():
        field_name = 'min_%s' % stat.key
        if stat.key in adv_stat_keys:
            continue
        if field_name in request.POST:
            minimum = safe_int(request.POST.get(field_name, ''))
            if minimum is not None:
                minimum_values[stat.name] = minimum

    if 'min_hp' in request.POST:
        minimum = safe_int(request.POST.get('min_hp'))
        if minimum is not None:
            minimum_values['HP'] = minimum

    minimum_values['adv_mins'] = {}
    for stat in adv_stats:
        field_name = 'min_%s' % stat['key']
        if field_name in request.POST:
            minimum = safe_int(request.POST.get(field_name, ''))
            if minimum is not None:
                minimum_values['adv_mins'][stat['name']] = minimum
    
    set_min_stats(char, minimum_values)        
    
    return HttpResponseJson(json.dumps(_get_initial_data(char)))
    
def _get_initial_data(char):
    mins = get_min_stats(char)
    mins = convert_dict_index_name_to_key(mins)
    structure = get_structure()
        
    for stat in get_structure().get_stats_list():
        if stat.key not in mins:
            mins[stat.key] = ''
    if 'hp' not in mins:
        mins['hp'] = ''
    adv_mins = structure.get_adv_mins()
    if 'adv_mins' not in mins:
        mins['adv_mins'] = {}
    for stat in adv_mins:
        if stat['key'] not in mins['adv_mins']:
            mins['adv_mins'][stat['key']] = ''
    
    return {'minimum_stats': mins}

