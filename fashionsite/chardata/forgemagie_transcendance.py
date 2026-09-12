# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Loader for the transcendence-rune catalogue (scraped from DofusDB).

Transcendence runes finalise an item at 100% success and then PREVENT any
further forgemagie ("Empêche les futures forgemagies"). They exist only on the
modern client (Dofus 2/3, Songes Infinis), so they are gated to the 'modern'
ruleset. Data file: forgemagie_transcendance.json (regenerate with
scripts/scrape_transcendance_runes.py). Stat keys match forgemagie_data.py.

The icons are mirrored under our own static files and the catalogue holds no
address: it carries `icon_id`, and `img` is built here, once per process. The
file used to carry the DofusDB address of each icon, and the page handed it
straight to the reader's browser, which fetched 81 images from a third party
the privacy policy never named. Neither third-party guard could see it: both
read source text, and this address arrived from data.
"""
import json
import os

from static_s3.templatetags.static_s3 import static

from chardata.forgemagie_data import get_ruleset

_PATH = os.path.join(os.path.dirname(__file__), 'forgemagie_transcendance.json')
_ICON_PATH = 'chardata/runes_transcendance/%d.webp'
_CACHE = None


def icon_url(icon_id):
    """Where the page reads a rune icon: our own domain, never DofusDB's."""
    return static(_ICON_PATH % icon_id)


def _load():
    global _CACHE
    if _CACHE is None:
        with open(_PATH, encoding='utf-8') as handle:
            data = json.load(handle)
        for rune in data['runes']:
            rune['img'] = icon_url(rune['icon_id'])
        _CACHE = data
    return _CACHE


# The 2.x client ships the Ta/Pata/Rata names too; Touch forked before them and
# Retro never had them.
_RULESETS_WITH_TRANSCENDENCE = ('modern', 'dofus2')


def get_transcendence_runes(game_version):
    """List of transcendence runes for this version (empty where it has none)."""
    if get_ruleset(game_version) not in _RULESETS_WITH_TRANSCENDENCE:
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
