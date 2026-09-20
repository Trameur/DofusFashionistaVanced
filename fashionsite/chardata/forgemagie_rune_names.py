# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The name each game gives a forgemagie rune, in the reader's language; the French key stays the join."""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), 'forgemagie_rune_names.json')
_CACHE = None

# Fallback order when the reader's language has no row: English, then the French key, itself a valid game name
_FALLBACK = ('en', 'fr')


def _load():
    global _CACHE
    if _CACHE is None:
        try:
            with open(_PATH, encoding='utf-8') as handle:
                _CACHE = json.load(handle)
        except (IOError, OSError, ValueError):
            _CACHE = {}
    return _CACHE


def rune_display_name(game_version, french_name, language):
    names = (_load().get(game_version) or {}).get(french_name) or {}
    for candidate in ((language or '').split('-')[0],) + _FALLBACK:
        if candidate and names.get(candidate):
            return names[candidate]
    return french_name


def known_rune_names(game_version):
    """{french name: {language: name}} for one version, for the guards."""
    return _load().get(game_version) or {}
