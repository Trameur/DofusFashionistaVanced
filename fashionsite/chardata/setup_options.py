# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ option groups (exos, mounts, Dofus, scrolls, points, item source), stored only for the groups the player changed."""
from chardata.base_stats_view import posted_distribution
from chardata.lock_forbid import get_default_exclusions
from chardata.models import Char
from chardata.options import (DOFUS_OPTIONS, get_available_options, initial_build_options,
                              set_options)
from chardata.options_view import apply_posted_dofus, parse_inventory_options, parse_options_post
from chardata.setup_preview import MAX_LEVEL
from chardata.wizard_view import HUNDRED
from fashionistapulp.dofus_constants import max_scroll_for_version
from fashionistapulp.exo_options import EXO_OPTIONS, exo_count
from fashionistapulp.structure import get_structure

GROUP_FIELD = 'setup_options'
GROUPS = ('exos', 'mounts', 'dofus', 'scrolls', 'points', 'inventory')
EXO_FIELDS = tuple(option for _key, option in EXO_OPTIONS)
MOUNT_FIELDS = ('dragoturkey', 'seemyool', 'rhineetle')
DOFUS_GROUP_OPTIONS = ('prysmaradite', 'trophies')
SCROLL_FIELD = 'scrolling'
POINTS_FIELD = 'choose_stats'
INVENTORY_FIELD = 'inventory_mode'
CHECKED = 'on'


def posted_groups(post):
    return set(post.getlist(GROUP_FIELD)) & set(GROUPS)


def _option_keys(group, available):
    if group == 'exos':
        return EXO_FIELDS
    if group == 'mounts':
        return tuple(name for name in MOUNT_FIELDS if available.get(name))
    if group == 'dofus':
        return tuple(name for name in DOFUS_GROUP_OPTIONS if available.get(name))
    return ()


def apply_option_groups(request, char):
    """Stores each group the player changed as the wizard stores it; a group left alone keeps the new build's defaults."""
    groups = posted_groups(request.POST)
    if not groups:
        return
    available = get_available_options()
    parsed = parse_options_post(request)
    options = {key: parsed[key] for group in sorted(groups)
               for key in _option_keys(group, available) if key in parsed}
    if 'inventory' in groups:
        parse_inventory_options(request, char, options)
    if options:
        set_options(char, options)
    if 'dofus' in groups:
        apply_posted_dofus(request, char)
    if 'points' in groups:
        char.allow_points_distribution = posted_distribution(request.POST)


def creation_scroll(post, full):
    """What every characteristic is scrolled to at creation: fully, unless the player picked less."""
    if 'scrolls' not in posted_groups(post):
        return full
    choice = post.get(SCROLL_FIELD)
    if choice == 'clean':
        return 0
    if choice == 'hundred':
        return min(HUNDRED, full)
    return full


def _exo_value(value, per_item):
    if per_item:
        return str(exo_count(value))
    if value == 'gelano':
        return value
    return 'yes' if value is True else 'no'


def _level_values(game_version, level, available):
    options = initial_build_options(game_version, level)
    values = {name: _exo_value(options.get(name), available['exo_per_item'])
              for name in EXO_FIELDS}
    for name in _option_keys('mounts', available) + _option_keys('dofus', available):
        if name in options:
            values[name] = CHECKED if options[name] else None
    return values


def _ladder(game_version, available):
    ladder = []
    for level in range(1, MAX_LEVEL + 1):
        values = _level_values(game_version, level, available)
        if not ladder or ladder[-1][1] != values:
            ladder.append([level, values])
    return ladder


def defaults_at(table, level):
    """What the untouched groups post at this level; a Dofus above it is greyed out and posts nothing."""
    values = dict(table['base'])
    for start, row in table['ladder']:
        if start > level:
            break
        values.update(row)
    for key, needed in table['levels'].items():
        if needed > level:
            values[key] = None
    return values


def _folders(request, game_version):
    if not request.user.is_authenticated:
        return []
    from chardata.inventory_view import get_user_folders
    return [{'id': folder.id, 'name': folder.name, 'count': folder.items.count()}
            for folder in get_user_folders(request.user, game_version)]


def more_options_context(request, char, game_version):
    """The /setup/ "More options" section, drawn with the defaults of the page's level."""
    available = get_available_options()
    structure = get_structure()
    excluded = set(get_default_exclusions(char))
    dofuses = []
    base = {}
    for entry in available['dofuses']:
        item = structure.get_item_by_name(DOFUS_OPTIONS[entry['key']])
        dofuses.append(dict(entry, level=item.level))
        base[entry['key']] = None if item.id in excluded else CHECKED
    if available['trophies']:
        base['trophies'] = CHECKED
    base[SCROLL_FIELD] = 'fully'
    distributed = Char._meta.get_field('allow_points_distribution').default
    base[POINTS_FIELD] = POINTS_FIELD if distributed else None
    folders = _folders(request, game_version)
    groups = [['exos', list(EXO_FIELDS)],
              ['mounts', list(_option_keys('mounts', available))],
              ['dofus', [entry['key'] for entry in dofuses] + list(_option_keys('dofus', available))],
              ['scrolls', [SCROLL_FIELD]],
              ['points', [POINTS_FIELD]]]
    if folders:
        base[INVENTORY_FIELD] = 'all'
        groups.append(['inventory', [INVENTORY_FIELD]])
    table = {'groups': [group for group in groups if group[1]],
             'base': base,
             'ladder': _ladder(game_version, available),
             'levels': {entry['key']: entry['level'] for entry in dofuses}}
    return {'per_item': available['exo_per_item'],
            'exo_slots': available['exo_slots'],
            'gelano': available['gelano'],
            'mounts': _option_keys('mounts', available),
            'dofuses': dofuses,
            'prysmaradite': available['prysmaradite'],
            'trophies': available['trophies'],
            'hundred': max_scroll_for_version(game_version) > HUNDRED,
            'folders': folders,
            'level': char.level,
            'defaults': defaults_at(table, char.level),
            'table': table}
