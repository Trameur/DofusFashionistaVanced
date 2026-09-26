# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Presets shared by the doors that create a build: quick start styles, default elements, setup boxes."""

import pickle
from collections import namedtuple

from django.utils.translation import gettext_lazy

from chardata.models import Char
from chardata.smart_build import get_standard_weights
from fashionistapulp.game_versions import DEFAULT_VERSION


CLASS_DEFAULT_ELEMENT = {
    'Iop': 'str',
    'Cra': 'agi',
    'Sram': 'agi',
    'Xelor': 'cha',
    'Eniripsa': 'int',
    'Feca': 'int',
    'Sacrier': 'agi',
    'Sadida': 'cha',
    'Enutrof': 'cha',
    'Osamodas': 'cha',
    'Ecaflip': 'cha',
    'Pandawa': 'str',
    'Eliotrope': 'cha',
    'Huppermage': 'int',
    'Ouginak': 'agi',
    'Masqueraider': 'agi',
    'Foggernaut': 'int',
    'Rogue': 'agi',
    'Forgelance': 'str',
}
FALLBACK_ELEMENT = 'str'

Style = namedtuple('Style', 'key label build_name_word aspects takes_element')

STYLES = (
    Style('solo_pvm', gettext_lazy('Solo PvM: focus damage'), gettext_lazy('solo PvM'),
          frozenset({'glasscannon'}), True),
    Style('group_pvm', gettext_lazy('Group PvM: tanky / support'), gettext_lazy('group PvM'),
          frozenset({'vit', 'res'}), True),
    Style('pvp', gettext_lazy('PvP: critical hits'), gettext_lazy('PvP'),
          frozenset({'pvp', 'crit'}), True),
    Style('farm', gettext_lazy('Farm / Level-up: Prospecting & Wisdom'), gettext_lazy('farm'),
          frozenset({'wis', 'pp'}), False),
)
STYLE_BY_KEY = {style.key: style for style in STYLES}
DEFAULT_STYLE = 'solo_pvm'

ELEMENT_BOXES = ('str', 'int', 'cha', 'agi', 'omni')
FOCUS_COLUMNS = (('balanced', 'vit', 'glasscannon', 'dam', 'heal', 'aprape', 'mprape', 'crit'),
                 ('res', 'wis', 'pp', 'pods', 'trap', 'summon', 'pushback', 'noncrit'))
FOCUS_LIMIT = 2

ELEMENT_DAMAGE = {'str': 'earthdam', 'int': 'firedam', 'cha': 'waterdam', 'agi': 'airdam'}
SECOND_ELEMENT_SHARE = 0.5

VERSION_PRESETS = {
    'dofus3': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
               'option_boxes': ('pvp', 'duel')},
    'beta': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
             'option_boxes': ('pvp', 'duel')},
    'dofus2': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
               'option_boxes': ('pvp', 'duel')},
    'touch': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
              'option_boxes': ('pvp', 'duel')},
    'retro': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
              'option_boxes': ('pvp', 'duel')},
}


def version_presets(game_version):
    return VERSION_PRESETS.get(game_version, VERSION_PRESETS[DEFAULT_VERSION])


def play_styles(game_version):
    """[(key, label)] the quick start offers on this version."""
    return [(key, STYLE_BY_KEY[key].label)
            for key in version_presets(game_version)['styles']]


def offered_style(style, game_version):
    """The style if this version offers it, else the default one."""
    if style in version_presets(game_version)['styles']:
        return style
    return DEFAULT_STYLE


def default_element(char_class):
    return CLASS_DEFAULT_ELEMENT.get(char_class, FALLBACK_ELEMENT)


def style_aspects(style, char_class=None, element=None):
    """The aspects a style sets, plus the element (the class's own unless given) when the style takes one."""
    preset = STYLE_BY_KEY.get(style)
    aspects = set(preset.aspects) if preset is not None else set()
    if preset is None or preset.takes_element:
        aspects.add(element or default_element(char_class))
    return aspects


def setup_columns(game_version):
    """The four box columns of the setup page; the page itself hides the version's inert aspects."""
    return ([list(ELEMENT_BOXES), list(version_presets(game_version)['option_boxes'])]
            + [list(column) for column in FOCUS_COLUMNS])


def setup_boxes(game_version):
    return {aspect for column in setup_columns(game_version) for aspect in column}


def focus_boxes(aspects):
    return {aspect for column in FOCUS_COLUMNS for aspect in column
            if aspect in aspects and aspect != 'balanced'}


def within_focus_limit(aspects):
    return len(focus_boxes(aspects)) <= FOCUS_LIMIT


def capped_focus(aspects, preferred=()):
    """At most FOCUS_LIMIT focus boxes: the preferred ones first, then column order."""
    focus = focus_boxes(aspects)
    order = [aspect for aspect in preferred if aspect in focus]
    order += [aspect for column in FOCUS_COLUMNS for aspect in column
              if aspect in focus and aspect not in order]
    return (set(aspects) - focus) | set(order[:FOCUS_LIMIT])


def element_stat_points(char_class, level, game_version):
    """{element: {stat key: characteristic points per point}}, as the build weights price them."""
    points = {}
    for element, damage in ELEMENT_DAMAGE.items():
        weights = get_standard_weights(Char(char_class=char_class, level=level,
                                            game_version=game_version,
                                            aspects=pickle.dumps({element})))
        points[element] = {element: 1}
        for stat in (damage, 'neutdam') if element == 'str' else (damage,):
            points[element][stat] = weights.get(stat, 0) / weights[element]
    return points


def gear_elements(structure, item_ids, char_class, level, game_version, overrides=None):
    """Top two elements with SECOND_ELEMENT_SHARE of the main one's points; all four make omni."""
    counted = {element: [(structure.stat_dict_key[key].id, weight)
                         for key, weight in stats.items() if key in structure.stat_dict_key]
               for element, stats in element_stat_points(char_class, level,
                                                         game_version).items()}
    points = dict.fromkeys(counted, 0)
    for item_id in item_ids:
        item = structure.get_item_by_id(item_id)
        if item is None:
            continue
        values = dict(item.stats or ())
        values.update((overrides or {}).get(item_id) or {})
        for element, stats in counted.items():
            points[element] += sum(weight * values.get(stat_id, 0)
                                   for stat_id, weight in stats)
    ranked = sorted(points, key=points.get, reverse=True)
    if points[ranked[0]] <= 0:
        return set()
    strong = [element for element in ranked
              if points[element] >= SECOND_ELEMENT_SHARE * points[ranked[0]]]
    if len(strong) == len(points):
        return set(strong) | {'omni'}
    return set(strong[:2])
