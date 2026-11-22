# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Transcendence runes of a game version, read from per-version JSON."""

import json
import os
from functools import lru_cache

DEFAULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'transcendence')


@lru_cache(maxsize=None)
def _read(version, folder):
    path = os.path.join(folder, '%s.json' % version)
    if not os.path.isfile(path):
        return ()
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    return tuple(data.get('runes', ()))


def load_runes(version, folder=None):
    """The version's transcendence runes as a list of dicts, empty when it has no file."""
    return list(_read(version, folder or DEFAULT_FOLDER))


def clear_cache():
    _read.cache_clear()
