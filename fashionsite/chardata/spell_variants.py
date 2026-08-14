# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Which spells are the two faces of one variant.

A Dofus 3 class spell comes as a pair and the player arms one of the two before
the fight, so one turn can never hold both. Data file: spell_variants.json
(regenerate with itemscraper/store_spell_variants.py). Dofus 2, Touch and Retro
never had variants.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), 'spell_variants.json')
_CACHE = None


def _load():
    global _CACHE
    if _CACHE is None:
        with open(_PATH, encoding='utf-8') as handle:
            _CACHE = json.load(handle)
    return _CACHE


def get_variant_by_spell_id(game_version):
    """{spell id: variant id}, empty for a version without variants."""
    return _load().get(game_version) or {}


def variant_of(game_version, spell_id):
    if spell_id is None:
        return None
    return get_variant_by_spell_id(game_version).get(str(spell_id))
