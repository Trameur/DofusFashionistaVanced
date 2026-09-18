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

import math

from django.utils.translation import pgettext
from django.utils.translation import gettext as _
from chardata.translation_util import localized_stat_name

from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.util import safe_int, remove_cache_for_char
from fashionistapulp.dofus_constants import (MAIN_STATS, DAMAGE_TYPES,
                                             ELEMENT_KEY_TO_NAME, STAT_KEY_TO_NAME)


def _element_keys(pattern):
    return [pattern % damage_type for damage_type in DAMAGE_TYPES]


def _unreachable_stats(game_version):
    """Stats no item or set bonus of this version carries: a slider on one of
    them would move nothing, so the wizard does not offer it."""
    from chardata.smart_build import VERSION_WEIGHT_TUNING
    from chardata.stat_availability import stats_with_no_source
    zeroed = VERSION_WEIGHT_TUNING.get(game_version, {}).get('zero_stats', ())
    return set(stats_with_no_source(game_version)) | set(zeroed)


def _damage_is_derived(unreachable):
    """Where gear carries elemental damage, the plain Damage weight is their
    sum. Retro gear carries plain damage only, so there it has its own slider,
    and summing zeros into it would wipe it."""
    return not all(key in unreachable for key in _element_keys('%sdam'))


def _sections(game_version):
    """(section key, label, slider keys) for every stat a weight can steer."""
    unreachable = _unreachable_stats(game_version)
    offense = list(MAIN_STATS) + ['pow']
    if not _damage_is_derived(unreachable):
        offense.append('dam')
    offense += _element_keys('%sdam') + [
        'ch', 'cridam', 'permedam', 'perrandam', 'perweadam', 'perspedam',
        'pshdam', 'trapdam', 'trapdamper']
    defense = (['vit', 'hp', 'perres'] + _element_keys('%sresper')
               + ['linres'] + _element_keys('%sres')
               + ['crires', 'pshres', 'respermee', 'resperran', 'resperwea',
                  'pvpperres'] + _element_keys('pvp%sresper')
               + ['pvplinres'] + _element_keys('pvp%sres'))
    sections = [
        ('apmprange', pgettext('Slider section', 'AP, MP and Range'),
         ['ap', 'mp', 'range']),
        ('offense', pgettext('Slider section', 'Offense'), offense),
        ('defense', pgettext('Slider section', 'Defense'), defense),
        ('mobility', pgettext('Slider section', 'Mobility'),
         ['lock', 'dodge', 'init', 'apres', 'mpres', 'apred', 'mpred']),
        ('special', pgettext('Slider section', 'Special'),
         ['heals', 'summon', 'wis', 'pp', 'pod', 'ref']),
    ]
    offered = []
    for section_key, label, keys in sections:
        kept = [key for key in keys
                if (_members(key, unreachable) if key in AGGREGATE_SLIDERS
                    else key not in unreachable)]
        offered.append((section_key, label, kept))
    return offered


def _members(slider_key, unreachable):
    return [stat for stat in AGGREGATE_SLIDERS[slider_key]
            if stat not in unreachable]


def _label(key, game_version):
    labels = {
        'ap': _('AP'), 'mp': _('MP'), 'range': _('Range'),
        'pow': localized_stat_name('Power', game_version),
        'dam': _('Damage'),
        'ch': _('Critical Hits'), 'cridam': _('Critical Damage'),
        'permedam': _('% Melee Damage'), 'perrandam': _('% Ranged Damage'),
        'perweadam': _('% Weapon Damage'), 'perspedam': _('% Spells Damage'),
        'pshdam': _('Pushback Damage'), 'trapdam': _('Trap Damage'),
        'trapdamper': localized_stat_name('% Trap Damage', game_version),
        'vit': _('Vitality'), 'hp': _('HP'),
        'perres': _('All % Resists'), 'linres': _('All Resists'),
        'pvpperres': _('All % Resists (PvP)'), 'pvplinres': _('All Resists (PvP)'),
        'crires': _('Critical Resist'), 'pshres': _('Pushback Resist'),
        'respermee': _('% Melee Resist'), 'resperran': _('% Ranged Resist'),
        'resperwea': _('% Weapon Resist'),
        'lock': _('Lock'), 'dodge': _('Dodge'), 'init': _('Initiative'),
        'apres': _('AP Loss Resist'), 'mpres': _('MP Loss Resist'),
        'apred': _('AP Reduction'), 'mpred': _('MP Reduction'),
        'heals': _('Heals'), 'summon': _('Summons'), 'wis': _('Wisdom'),
        'pp': _('Prospecting'), 'pod': _('Pods'), 'ref': _('Reflects'),
    }
    for damage_type in DAMAGE_TYPES:
        element = ELEMENT_KEY_TO_NAME[damage_type]
        labels['%sresper' % damage_type] = _('%% %s Resist' % element)
        labels['%sres' % damage_type] = _('%s Resist' % element)
        labels['pvp%sresper' % damage_type] = _('%% %s Resist (PvP)' % element)
        labels['pvp%sres' % damage_type] = _('%s Resist (PvP)' % element)
    if key in labels:
        return labels[key]
    return _(STAT_KEY_TO_NAME[key])


def get_wizard_sliders(char):
    game_version = getattr(char, 'game_version', 'dofus3') or 'dofus3'
    unreachable = _unreachable_stats(game_version)
    all_sliders = []
    for section_key, label, keys in _sections(game_version):
        section = Slider(section_key, label, True)
        for key in keys:
            members = (_members(key, unreachable) if key in AGGREGATE_SLIDERS
                       else None)
            section.add_subslider(Slider(key, _label(key, game_version), False,
                                         members))
        all_sliders.append(section)

    weights = get_stats_weights(char)
    for slider in all_sliders:
        slider.calculate(weights)

    return all_sliders

class Slider():
    def __init__(self, slider_key, slider_name, is_section, members=None):
        self.key = slider_key
        self.name = slider_name
        self.subsliders = [] if is_section else None
        # The stats an aggregate slider sets together, None on a plain one.
        self.members = members

    def calculate(self, weights):
        if self.subsliders is not None:
            for slider in self.subsliders:
                slider.calculate(weights)
            self.abs_value = 0
            self.min_value = 0
            self.max_value = 0
        else:
            # A weight typed on the Characteristics Weights page can lie
            # outside the usual range; the slider widens to show it instead of
            # clamping it, which the next save would have written back.
            low, high = SLIDER_RANGES[self.key]
            self.abs_value = get_slider_value_from_weights(self.key, weights,
                                                           self.members)
            self.min_value = min(low, int(math.floor(self.abs_value)))
            self.max_value = max(high, int(math.ceil(self.abs_value * 1.5)))

    def add_subslider(self, subslider):
        self.subsliders.append(subslider)

def get_slider_value_from_weights(slider_key, weights, members=None):
    if slider_key in AGGREGATE_SLIDERS:
        stats_that_compose_slider = members or AGGREGATE_SLIDERS[slider_key]
        weight = (sum([weights[stat] for stat in stats_that_compose_slider])
                  / len(stats_that_compose_slider))
    else:
        weight = weights[slider_key]

    return weight

def _shown_value(value):
    """The value the page's slider starts on: JavaScript's Math.round."""
    return int(math.floor(value + 0.5))

def set_wizard_sliders(char, slider_dict):
    weights = get_stats_weights(char)
    # What the page showed, before an aggregate below changes its members.
    shown = dict(weights)
    game_version = getattr(char, 'game_version', 'dofus3') or 'dofus3'
    unreachable = _unreachable_stats(game_version)
    offered = [key for _key, _name, keys in _sections(game_version)
               for key in keys]
    # Aggregates first, so a single resist moved on its own wins over them.
    offered.sort(key=lambda key: key not in AGGREGATE_SLIDERS)

    for slider_key in offered:
        form_field_name = 'slider_%s' % slider_key
        slider_value_string = slider_dict.get(form_field_name, None)
        new_slider_value = safe_int(slider_value_string)
        if new_slider_value is None:
            continue
        members = (_members(slider_key, unreachable)
                   if slider_key in AGGREGATE_SLIDERS else None)
        # A slider left where it started keeps the weights under it: an
        # aggregate would otherwise level five different resists to their
        # average on every save.
        current = get_slider_value_from_weights(slider_key, shown, members)
        if new_slider_value == _shown_value(current):
            continue
        set_weights_from_slider_value(slider_key, new_slider_value, weights,
                                      members)

    if _damage_is_derived(unreachable):
        _post_process_weights(weights)
    set_stats_weights(char, weights)
    remove_cache_for_char(char.id)

def _post_process_weights(weights):
    weights['dam'] = sum([weights['%sdam' % dam_type] for dam_type in DAMAGE_TYPES])

def set_weights_from_slider_value(slider_key, slider_value, weights, members=None):
    weight = slider_value
    if slider_key in AGGREGATE_SLIDERS:
        for stat in members or AGGREGATE_SLIDERS[slider_key]:
            weights[stat] = weight
    else:
        weights[slider_key] = weight

SLIDER_RANGES = {
    'ap': (0, 6000),
    'mp': (0, 6000),
    'range': (0, 5000),

    'vit': (10, 40),
    'hp': (0, 40),

    'pow': (0, 200),
    'dam': (0, 3000),
    'cridam': (0, 300),
    'ch': (-200, 600),
    'permedam': (0, 1500),
    'perrandam': (0, 1500),
    'perweadam': (0, 1500),
    'perspedam': (0, 1500),
    'pshdam': (0, 200),
    'trapdam': (0, 300),
    'trapdamper': (0, 100),

    'heals': (0, 400),

    'summon': (0, 1000),

    'perres': (40, 360),
    'linres': (10, 100),
    'pvpperres': (0, 360),
    'pvplinres': (0, 100),
    'crires': (0, 150),
    'pshres': (0, 100),
    'respermee': (0, 2000),
    'resperran': (0, 2000),
    'resperwea': (0, 2000),

    'lock': (0, 200),
    'dodge': (0, 200),
    'apres': (0, 200),
    'mpres': (0, 200),
    'apred': (0, 600),
    'mpred': (0, 600),
    'init': (0, 8),

    'wis': (0, 500),
    'pp': (0, 500),
    'pod': (0, 100),
    'ref': (0, 300),
}

for main_stat in MAIN_STATS:
    SLIDER_RANGES[main_stat] = (0, 140)
for dam_type in DAMAGE_TYPES:
    SLIDER_RANGES['%sdam' % dam_type] = (0, 300)
    SLIDER_RANGES['%sresper' % dam_type] = (0, 360)
    SLIDER_RANGES['%sres' % dam_type] = (0, 100)
    SLIDER_RANGES['pvp%sresper' % dam_type] = (0, 360)
    SLIDER_RANGES['pvp%sres' % dam_type] = (0, 100)

AGGREGATE_SLIDERS = {
    'perres': ['neutresper', 'earthresper', 'fireresper', 'waterresper', 'airresper'],
    'linres': ['neutres', 'earthres', 'fireres', 'waterres', 'airres'],
    'pvpperres': ['pvpneutresper', 'pvpearthresper', 'pvpfireresper', 'pvpwaterresper', 'pvpairresper'],
    'pvplinres': ['pvpneutres', 'pvpearthres', 'pvpfireres', 'pvpwaterres', 'pvpairres'],
}
