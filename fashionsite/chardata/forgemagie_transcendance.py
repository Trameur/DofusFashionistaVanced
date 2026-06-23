# Copyright (C) 2026 The Dofus Fashionista — LGPL (see COPYING.LESSER)
"""Loader for the transcendence-rune catalogue (scraped from DofusDB).

Transcendence runes finalise an item at 100% success and then PREVENT any
further forgemagie ("Empêche les futures forgemagies"). They exist only on the
modern client (Dofus 2/3 — Songes Infinis), so they are gated to the 'modern'
ruleset. Data file: forgemagie_transcendance.json (regenerate with
scripts/scrape_transcendance_runes.py). Stat keys match forgemagie_data.py.
"""
import json
import os

from chardata.forgemagie_data import get_ruleset

_PATH = os.path.join(os.path.dirname(__file__), 'forgemagie_transcendance.json')
_CACHE = None


def _load():
    global _CACHE
    if _CACHE is None:
        with open(_PATH, encoding='utf-8') as handle:
            _CACHE = json.load(handle)
    return _CACHE


def get_transcendence_runes(game_version):
    """List of transcendence runes for this version (empty outside 'modern')."""
    if get_ruleset(game_version) != 'modern':
        return []
    return _load()['runes']


def get_transcendence_by_stat(game_version):
    """{stat_key: {'label': ..., 'runes': [rune, ...sorted by rank]}} for the UI."""
    grouped = {}
    for rune in get_transcendence_runes(game_version):
        entry = grouped.setdefault(
            rune['stat_key'], {'label': rune['stat_label'], 'runes': []})
        entry['runes'].append(rune)
    for entry in grouped.values():
        entry['runes'].sort(key=lambda r: r['rank'])
    return grouped
