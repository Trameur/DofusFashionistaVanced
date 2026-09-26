# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Presets shared by the doors that create a build: quick start styles, default elements, setup boxes."""

from collections import namedtuple

from django.utils.translation import gettext_lazy

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
