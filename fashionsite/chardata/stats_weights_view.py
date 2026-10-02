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

from chardata.presets import default_build_weights
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.temporix_mode import char_uses_temporix
from chardata.util import set_response, safe_int, get_char_or_raise, HttpResponseJson
from chardata.weights_minimums import (combined_open, combined_rows, edit_sections,
                                       merge_minimum_fields, other_saved_rows, page_state)
from chardata.wizard_sliders import _shown_value, apply_weight_fields
from django.db import transaction
from django.views.decorators.http import require_POST
from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS
from fashionistapulp.structure import get_structure


def weights_and_minimums_page(request, char, focus):
    sections = edit_sections(char)
    default_keys = {row['key'] for section in sections for row in section['rows']
                    if row['weight'] and not row['aggregate']}
    defaults = default_build_weights(char)
    return set_response(request,
                        'chardata/weights_minimums.html',
                        {'char_id': char.id,
                         'advanced': True,
                         'focus': focus,
                         'sections': sections,
                         'combined': combined_rows(char),
                         'combined_open': combined_open(char),
                         'others': other_saved_rows(char),
                         'temporix_on': char_uses_temporix(char),
                         'wm_state': page_state(char),
                         'wm_defaults': {key: _shown_value(defaults.get(key, 0))
                                         for key in sorted(default_keys)}},
                        char)


def stats(request, char_id):
    return weights_and_minimums_page(request, get_char_or_raise(request, char_id), 'weights')


@require_POST
def stats_post(request, char_id):
    char = get_char_or_raise(request, char_id)

    from chardata.stat_availability import stats_not_worth_offering
    game_version = getattr(request, 'game_version', 'dofus3')
    hidden = stats_not_worth_offering(game_version)
    # A hidden or absent row posts nothing, and reading it as 0 would quietly
    # wipe a weight the reader set before, or on another page. Keep what is
    # stored.
    stored = get_stats_weights(char)
    stats_weight = {key: stored[key] for key in NON_STAT_WEIGHT_KEYS
                    if key in stored}
    for stat in get_structure().get_stats_list():
        field_name = 'weight_%s' % stat.key
        if stat.key in hidden or field_name not in request.POST:
            stats_weight[stat.key] = stored.get(stat.key, 0)
            continue
        stats_weight[stat.key] = safe_int(request.POST.get(field_name, 0), 0)
    set_stats_weights(char, stats_weight)
    
    return HttpResponseJson(json.dumps(get_stats_weights(char)))


@require_POST
@transaction.atomic
def weights_mins_post(request, char_id):
    char = get_char_or_raise(request, char_id)
    base = default_build_weights(char) if request.POST.get('weights_reset') == '1' else None
    apply_weight_fields(char, request.POST, 'weight_', base)
    merge_minimum_fields(char, request.POST)
    return HttpResponseJson(json.dumps(page_state(char)))
