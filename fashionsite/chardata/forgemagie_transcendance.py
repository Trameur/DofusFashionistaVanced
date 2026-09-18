# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Transcendence runes, from scripts/scrape_transcendance_runes.py."""
import json
import os

from static_s3.templatetags.static_s3 import static

from chardata.forgemagie_data import get_ruleset

_PATH = os.path.join(os.path.dirname(__file__), 'forgemagie_transcendance.json')
_ICON_PATH = 'chardata/runes_transcendance/%d.webp'
_CACHE = None

# Fallback languages: English, then French, the language Ankama writes them in
_REPLI = ('en', 'fr')


def rune_name(rune, language):
    """The name the reader's own client gives this rune."""
    noms = rune.get('name') or {}
    for candidat in ((language or '').split('-')[0],) + _REPLI:
        if candidat and noms.get(candidat):
            return noms[candidat]
    return ''


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


# Dofus 2 has them too; Touch and Retro never did
_RULESETS_WITH_TRANSCENDENCE = ('modern', 'dofus2')


def get_transcendence_runes(game_version):
    """List of transcendence runes for this version (empty where it has none)."""
    if get_ruleset(game_version) not in _RULESETS_WITH_TRANSCENDENCE:
        return []
    return _load()['runes']


def get_transcendence_by_stat(game_version, language):
    """{stat_key: {'label', 'runes'}} for the UI; runes are copies, the cache is shared."""
    grouped = {}
    for rune in get_transcendence_runes(game_version):
        entry = grouped.setdefault(
            rune['stat_key'], {'label': rune['stat_label'], 'runes': []})
        entry['runes'].append(dict(rune, name=rune_name(rune, language)))
    for entry in grouped.values():
        entry['runes'].sort(key=lambda r: r['rank'])
    return grouped
