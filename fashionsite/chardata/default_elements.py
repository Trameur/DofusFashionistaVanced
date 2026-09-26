# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each class's default element on a version and level, from default_elements/<version>.json.

    py fashionsite/manage.py store_default_elements --game-version dofus3
"""
import json
import os

DIRECTORY = os.path.join(os.path.dirname(__file__), 'default_elements')
_CACHE = {}


def default_elements_table(game_version):
    """The version's file, empty when it has none."""
    if not game_version or not game_version.isalnum():
        return {}
    if game_version not in _CACHE:
        path = os.path.join(DIRECTORY, '%s.json' % game_version)
        try:
            with open(path, encoding='utf-8') as handle:
                _CACHE[game_version] = json.load(handle)
        except (IOError, OSError, ValueError):
            _CACHE[game_version] = {}
    return _CACHE[game_version]


def nearest_level(levels, level):
    """The reference level closest to `level`, the lower one on a tie; the highest without a level."""
    if level is None:
        return max(levels)
    return min(levels, key=lambda reference: (abs(reference - level), reference))


def version_element(char_class, game_version, level=None):
    """The element the version's table picked for the class at the nearest level, None when it has none."""
    by_level = (default_elements_table(game_version).get('classes') or {}).get(char_class) or {}
    levels = [int(key) for key in by_level if key.isdigit()]
    if not levels:
        return None
    return (by_level[str(nearest_level(levels, level))] or {}).get('element')
