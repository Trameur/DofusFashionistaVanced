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

from django.utils.translation import pgettext
from django.utils.translation import gettext as _

from chardata.smart_build import get_char_aspects, get_elements, param_for_build
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.util import safe_int, remove_cache_for_char
from fashionistapulp.dofus_constants import (MAIN_STATS, DAMAGE_TYPE_TO_MAIN_STAT,
                                             DAMAGE_TYPES, STAT_KEY_TO_NAME)


def get_wizard_sliders(char):
    aspects = get_char_aspects(char)   
    elements = get_elements(aspects)
    race = char.char_class
    game_version = getattr(char, 'game_version', 'dofus3') or 'dofus3'
    
    all_sliders = []
    
    # Offense
    main_offense_slider = Slider('offense', pgettext('Slider section', 'Offense'), True)
    all_sliders.append(main_offense_slider)
    for main_stat in MAIN_STATS:
        if main_stat in elements:
            main_offense_slider.add_subslider(Slider(main_stat, _(STAT_KEY_TO_NAME[main_stat]),
                                                     False))

    main_offense_slider.add_subslider(Slider('pow', _('Power'), False))
    
    for dam_type in DAMAGE_TYPES:
        if DAMAGE_TYPE_TO_MAIN_STAT[dam_type] in elements:
            dam_stat = '%sdam' % dam_type
            main_offense_slider.add_subslider(Slider(dam_stat, _(STAT_KEY_TO_NAME[dam_stat]),
                                                     False))
    
    main_offense_slider.add_subslider(Slider('ch', _('Critical Hits'), False))
    main_offense_slider.add_subslider(Slider('cridam', _('Critical Damage'), False))
    
    if 'pushback' in aspects or param_for_build(race, elements, 'pshdam_importance', game_version=game_version) > 0:
        main_offense_slider.add_subslider(Slider('pshdam', _('Pushback Damage'), False))
        
    if 'trap' in aspects or param_for_build(race, elements, 'traps_are_important', game_version=game_version):
        main_offense_slider.add_subslider(Slider('trapdam', _('Trap Damage'), False))
        main_offense_slider.add_subslider(Slider('trapdamper', _('% Trap Damage'), False))

    # Defense
    main_defense_slider = Slider('defense', pgettext('Slider section', 'Defense'), True)
    all_sliders.append(main_defense_slider)
    main_defense_slider.add_subslider(Slider('vit', _('Vitality'), False))
    main_defense_slider.add_subslider(Slider('perres', _('% Resists'), False))
#     if 'duel' in aspects:
#         main_defense_slider.add_subslider(Slider('pvpperres', _('% Resists in PVP'), False))
#     main_defense_slider.add_subslider(Slider('linres', _('Linear Resists'), False))
#     if 'duel' in aspects:
#         main_defense_slider.add_subslider(Slider('pvplinres', _('Linear Res. in PVP'), False))
    main_defense_slider.add_subslider(Slider('crires', _('Critical Resist'), False))
    
    # Mobility
    main_mobility_slider = Slider('mobility', pgettext('Slider section', 'Mobility'), True)
    all_sliders.append(main_mobility_slider)
    main_mobility_slider.add_subslider(Slider('lock', _('Lock'), False))
    main_mobility_slider.add_subslider(Slider('dodge', _('Dodge'), False))
    if 'pvp' in aspects:
        main_mobility_slider.add_subslider(Slider('apres', _('AP Loss Resist'), False))
        main_mobility_slider.add_subslider(Slider('mpres', _('MP Loss Resist'), False))
    if 'apred' in aspects or param_for_build(race, elements, 'apred_importance', game_version=game_version) > 0:
        main_mobility_slider.add_subslider(Slider('apred', _('AP Reduction'), False))
    if 'mpred' in aspects or param_for_build(race, elements, 'mpred_importance', game_version=game_version) > 0:
        main_mobility_slider.add_subslider(Slider('mpred', _('MP Reduction'), False))
    main_mobility_slider.add_subslider(Slider('init', _('Initiative'), False))

    # Special
    main_special_slider = Slider('special', pgettext('Slider section', 'Special'), True)
    all_sliders.append(main_special_slider)
    if 'heal' in aspects or param_for_build(race, elements, 'heals_importance', game_version=game_version) > 0:
        main_special_slider.add_subslider(Slider('heals', _('Heals'), False))
    if 'summon' in aspects or param_for_build(race, elements, 'summons_are_important', game_version=game_version):
        main_special_slider.add_subslider(Slider('summon', _('Summons'), False))
    main_special_slider.add_subslider(Slider('wis', _('Wisdom'), False))
    main_special_slider.add_subslider(Slider('pp', _('Prospecting'), False))

    # Stats no gear of this version carries: no Critical Damage or AP Reduction
    # in 1.29, no Trap Damage on Touch.
    from chardata.smart_build import VERSION_WEIGHT_TUNING
    dead_stats = set(VERSION_WEIGHT_TUNING.get(game_version, {}).get('zero_stats', ()))
    if dead_stats:
        for slider in all_sliders:
            if slider.subsliders is not None:
                slider.subsliders = [s for s in slider.subsliders
                                     if s.key not in dead_stats]

    weights = get_stats_weights(char)
    for slider in all_sliders:
        slider.calculate(weights)

    return all_sliders

class Slider():
    def __init__(self, slider_key, slider_name, is_section):
        self.key = slider_key
        self.name = slider_name
        self.subsliders = [] if is_section else None
        
    def calculate(self, weights):
        if self.subsliders is not None:
            for slider in self.subsliders:
                slider.calculate(weights)
            self.abs_value = 0
            self.min_value = 0
            self.max_value = 0
        else:
            weight_range = SLIDER_RANGES[self.key]
            self.abs_value = get_slider_value_from_weights(self.key, weights)
            self.min_value = weight_range[0]
            self.max_value = weight_range[1]

    def add_subslider(self, subslider):
        self.subsliders.append(subslider)

def get_slider_value_from_weights(slider_key, weights):
    if slider_key in AGGREGATE_SLIDERS:
        stats_that_compose_slider = AGGREGATE_SLIDERS[slider_key]
        weight = (sum([weights[stat] for stat in stats_that_compose_slider])
                  / len(stats_that_compose_slider))
    else:
        weight = weights[slider_key]

    return weight

def set_wizard_sliders(char, slider_dict):
    weights = get_stats_weights(char)    
    
    for slider_key in SLIDER_RANGES:
        form_field_name = 'slider_%s' % slider_key
        slider_value_string = slider_dict.get(form_field_name, None)
        new_slider_value = safe_int(slider_value_string)
        if new_slider_value is not None:
            set_weights_from_slider_value(slider_key, new_slider_value, weights)

    _post_process_weights(weights)
    set_stats_weights(char, weights)
    remove_cache_for_char(char.id)

def _post_process_weights(weights):
    weights['dam'] = sum([weights['%sdam' % dam_type] for dam_type in DAMAGE_TYPES])

def set_weights_from_slider_value(slider_key, slider_value, weights):
    weight_range = SLIDER_RANGES[slider_key]
    # TODO: Manually setting weights can cause this.
    # assert slider_value >= weight_range[0] and slider_value <= weight_range[1]
    weight = slider_value
    if slider_key in AGGREGATE_SLIDERS:
        for stat in AGGREGATE_SLIDERS[slider_key]:
            weights[stat] = weight
    else:
        weights[slider_key] = weight

SLIDER_RANGES = {
    'vit': (10, 40),
    
    'pow': (0, 200),
    'cridam': (0, 300),
    'ch': (-200, 600),
    'pshdam': (0, 200),
    'trapdam': (0, 300),
    'trapdamper': (0, 100),

    'heals': (0, 400),

    'summon': (0, 1000),

    'perres': (40, 360),
    'linres': (10, 100),
#     'pvpperres': (40, 360),
#     'pvplinres': (10, 100),
    'crires': (0, 150),

    'lock': (0, 200),
    'dodge': (0, 200),
    'apres': (0, 200),
    'mpres': (0, 200),
    'apred': (0, 600),
    'mpred': (0, 600),
    'init': (0, 8),

    'wis': (0, 500),
    'pp': (0, 500),
}

for main_stat in MAIN_STATS:
    SLIDER_RANGES[main_stat] = (0, 140)
for dam_type in DAMAGE_TYPES:
    SLIDER_RANGES['%sdam' % dam_type] = (0, 300)

AGGREGATE_SLIDERS = {
    'perres': ['neutresper', 'earthresper', 'fireresper', 'waterresper', 'airresper'],
    'linres': ['neutres', 'earthres', 'fireres', 'waterres', 'airres'],
#     'pvpperres': ['pvpneutresper', 'pvpearthresper', 'pvpfireresper', 'pvpwaterresper', 'pvpairresper'],
#     'pvplinres': ['pvpneutres', 'pvpearthres', 'pvpfireres', 'pvpwaterres', 'pvpairres'],
}
