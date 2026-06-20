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

from chardata.models import CharBaseStats
from chardata.util import set_response, safe_int, get_char_or_raise, HttpResponseJson, version_reverse

from fashionistapulp.dofus_constants import SOFT_CAPS, STATS_NAMES

import json
from chardata.themes import get_theme




def setup_base_stats(request, char_id=0):
    return _page(request, char_id, False)

def save_char(request, char_id):
    char = _post(request, char_id)        
    return HttpResponseJson(json.dumps(_get_stats(char)))

def init_base_stats(request, char_id):
    return _page(request, char_id, True)

def init_base_stats_post(request, char_id):
    char = _post(request, char_id)
    return HttpResponseRedirect(version_reverse(request, 'wizard', char.id))

def _page(request, char_id, is_new_char):
    char = get_char_or_raise(request, char_id)

    stats = _get_stats(char) 
    stats['distrib'] = char.allow_points_distribution  

    lower_soft_caps = {}
    for stat, lis in SOFT_CAPS[char.char_class].items():
        new_list = []
        for entry in lis:
            if entry is not None:
                new_list.append(entry + 1)
            else:
                new_list.append(None)
        lower_soft_caps[stat] = new_list
    
    return set_response(request,
                        'chardata/chardata.html',
                        {'char_id': char_id,
                         'is_new_char': json.dumps(is_new_char),
                         'stats_json': json.dumps(stats),
                         'advanced': True,
                         'soft_caps': SOFT_CAPS[char.char_class],
                         'lower_soft_caps': lower_soft_caps,
                         'theme': get_theme(request)},
                        char)

def _post(request, char_id):
    char = get_char_or_raise(request, char_id)
    
    for element_name, abr in STATS_NAMES:
        basestats_list = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats_list) == 0:
            basestats = CharBaseStats()
        else:
            basestats = basestats_list[0]
        basestats.char = char
        basestats.stat = element_name
        basestats.total_value = (safe_int(request.POST.get('points_%s' % abr, 0), 0) + 
                                 safe_int(request.POST.get('scrolled_%s' % abr, 0), 0))
        basestats.scrolled_value = safe_int(request.POST.get('scrolled_%s' % abr, 0), 0)
        assert 0 <= basestats.total_value and basestats.total_value <= 3000
        assert 0 <= basestats.scrolled_value and basestats.scrolled_value <= 101
        basestats.save()
        
    allow_point_distribution = str(request.POST.get('choose_stats', '')).strip().lower() in ('true', 'on', '1', 'yes')
    char.allow_points_distribution = allow_point_distribution
    char.save()
    
    return char

def _get_stats(char):
    stats = {}
    for element_name, abr in STATS_NAMES:
        basestats_list = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats_list) == 0:
            stats['total_%s' % abr] = 0
            stats['scrolled_%s' % abr] = 0
        else:
            basestats = basestats_list[0]
            stats['total_%s' % abr] = basestats.total_value
            stats['scrolled_%s' % abr] = basestats.scrolled_value       
    return stats
