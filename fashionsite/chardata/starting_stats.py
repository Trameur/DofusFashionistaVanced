# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A character's own AP, MP, prospecting, pods and summons, from starting_stats/<version>.json."""
import json
import os

_DIRECTORY = os.path.join(os.path.dirname(__file__), 'starting_stats')
_CACHE = {}

# Hand values: set by the server, stated by no client text of the version
HAND_STATS = {'AP': 6, 'MP': 3, 'Prospecting': 100, 'Pods': 1000, 'Summon': 1}
HAND_LEVEL_AP = {'level': 100, 'AP': 1}


def starting_stats_table(game_version):
    """The version's file, empty when it has none."""
    if not game_version or not game_version.isalnum():
        return {}
    if game_version not in _CACHE:
        path = os.path.join(_DIRECTORY, '%s.json' % game_version)
        try:
            with open(path, encoding='utf-8') as handle:
                _CACHE[game_version] = json.load(handle)
        except (IOError, OSError, ValueError):
            _CACHE[game_version] = {}
    return _CACHE[game_version]


def starting_stats(level, char_class=None, game_version=None):
    table = starting_stats_table(game_version)
    stats = dict(HAND_STATS)
    stats.update(table.get('all') or {})
    stats.update((table.get('classes') or {}).get(char_class) or {})
    level_ap = table.get('level_ap') or HAND_LEVEL_AP
    if level >= level_ap['level']:
        stats['AP'] += level_ap['AP']
    return stats
