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

from django.http import HttpResponseRedirect

from chardata.models import CharBaseStats
from chardata.util import set_response, safe_int, get_char_or_raise, HttpResponseJson, version_reverse

from fashionistapulp.dofus_constants import (get_soft_caps_for, STATS_NAMES,
                                             max_scroll_for_version,
                                             scrolls_push_cost_curve)

import json
from chardata.themes import get_theme

MAX_TOTAL_VALUE = 3000


def _bounded(value, ceiling):
    """Clamp to 0..ceiling."""
    return max(0, min(value, ceiling))




def setup_base_stats(request, char_id=0):
    return _page(request, char_id, False)

def save_char(request, char_id):
    char = _post(request, char_id)
    stats = _get_stats(char)
    stats['distrib'] = char.allow_points_distribution
    return HttpResponseJson(json.dumps(stats))

def init_base_stats(request, char_id):
    return _page(request, char_id, True)

def init_base_stats_post(request, char_id):
    char = _post(request, char_id)
    return HttpResponseRedirect(version_reverse(request, 'wizard', char.id))

def _page(request, char_id, is_new_char):
    char = get_char_or_raise(request, char_id)

    stats = _get_stats(char) 
    stats['distrib'] = char.allow_points_distribution  

    soft_caps = get_soft_caps_for(char.game_version, char.char_class)
    lower_soft_caps = {}
    for stat, lis in soft_caps.items():
        new_list = []
        for entry in lis:
            if entry is not None:
                new_list.append(entry + 1)
            else:
                new_list.append(None)
        lower_soft_caps[stat] = new_list

    # The six cost tiers are 1:2, 1:1, 2:1, 3:1, 4:1, 5:1. A tier exists when
    # some stat has a threshold there (a number) or an open-ended one (None);
    # 0 for every stat means the tier does not exist for that class.
    show_tiers = [any((caps[n] is None) or (caps[n] and caps[n] > 0)
                      for caps in soft_caps.values())
                  for n in range(6)]
    last_tier = max((n for n in range(6) if show_tiers[n]), default=1)

    return set_response(request,
                        'chardata/chardata.html',
                        {'char_id': char_id,
                         'is_new_char': json.dumps(is_new_char),
                         'stats_json': json.dumps(stats),
                         'advanced': True,
                         'soft_caps': soft_caps,
                         'lower_soft_caps': lower_soft_caps,
                         'show_tiers': show_tiers,
                         'last_tier': last_tier,
                         'scrolls_push_curve': scrolls_push_cost_curve(char.game_version),
                         'max_scroll': max_scroll_for_version(char.game_version),
                         'theme': get_theme(request)},
                        char)

def _post(request, char_id):
    char = get_char_or_raise(request, char_id)
    max_scroll = max_scroll_for_version(char.game_version)

    for element_name, abr in STATS_NAMES:
        basestats_list = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats_list) == 0:
            basestats = CharBaseStats()
        else:
            basestats = basestats_list[0]
        basestats.char = char
        basestats.stat = element_name
        scrolled = _bounded(safe_int(request.POST.get('scrolled_%s' % abr, 0), 0),
                            max_scroll)
        points = _bounded(safe_int(request.POST.get('points_%s' % abr, 0), 0),
                          MAX_TOTAL_VALUE)
        basestats.total_value = _bounded(points + scrolled, MAX_TOTAL_VALUE)
        basestats.scrolled_value = scrolled
        basestats.save()
        
    # A checkbox posts its value attribute when checked and nothing at all
    # when unchecked: presence is the signal, not the value.
    raw = request.POST.get('choose_stats')
    allow_point_distribution = (raw is not None and
                                str(raw).strip().lower()
                                not in ('false', '0', 'no', 'off'))
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
