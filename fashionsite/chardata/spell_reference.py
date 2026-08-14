# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the game itself says about a class spell: its description, its cost,
its range and how often a turn allows it.

One file per version under spell_reference/, written by
itemscraper/store_spell_reference.py. Dofus 2 is the poor relation: its archive
ships no spell level, so its entries carry the text and nothing else.
"""
import json
import os

_DIRECTORY = os.path.join(os.path.dirname(__file__), 'spell_reference')
_CACHE = {}


def get_spell_reference(game_version):
    """{class name: [spell entry, ...]} for one version, empty when unknown."""
    if game_version not in _CACHE:
        path = os.path.join(_DIRECTORY, '%s.json' % game_version)
        try:
            with open(path, encoding='utf-8') as handle:
                _CACHE[game_version] = json.load(handle)
        except (IOError, OSError, ValueError):
            _CACHE[game_version] = {}
    return _CACHE[game_version]


def reference_by_spell_id(game_version, char_class):
    """{spell id: entry} for one class, in the order the game lists them."""
    classes = get_spell_reference(game_version)
    return {entry['id']: entry
            for entry in classes.get(char_class) or []
            if entry.get('id') is not None}


def localized(entry, key, language):
    """One localized field of an entry, falling back to English then French."""
    values = entry.get(key) or {}
    for candidate in (language, (language or '').split('-')[0], 'en', 'fr'):
        if values.get(candidate):
            return values[candidate]
    return ''
