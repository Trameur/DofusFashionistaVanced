# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Transcendence runes of a game version, read from the game files."""
import copy

from django.utils import translation
from django.utils.translation import gettext as _

from static_s3.templatetags.static_s3 import static

from fashionistapulp.structure import get_structure
from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import TRANSCENDENCE_VERSIONS

_ICON_PATH = 'chardata/runes_transcendance/%d.webp'

# Fallback languages: English, then French, the language Ankama writes them in
_REPLI = ('en', 'fr')


def _in_language(texts, language):
    noms = texts or {}
    for candidat in ((language or '').split('-')[0],) + _REPLI:
        if candidat and noms.get(candidat):
            return noms[candidat]
    return ''


def rune_name(rune, language):
    """The name the reader's own client gives this rune."""
    return _in_language(rune.get('names'), language)


def rune_notice(rune, language):
    """The game's own note on this rune in the reader's language, empty when it has none."""
    return _in_language(rune.get('notice'), language)


def icon_url(icon_id):
    """Where the page reads a rune icon: our own domain, never DofusDB's."""
    return static(_ICON_PATH % icon_id)


def get_transcendence_runes(game_version):
    """Deep copies of this version's transcendence runes (empty where it has none)."""
    if game_version not in TRANSCENDENCE_VERSIONS:
        return []
    return [dict(copy.deepcopy(rune), img=icon_url(rune['icon_id']))
            for rune in load_runes(game_version)]


def _stat_label(stat_key, language, structure):
    stat = (structure or get_structure()).get_stat_by_key(stat_key)
    if stat is None:
        return stat_key
    with translation.override(language):
        return _(stat.name)


def get_transcendence_by_stat(game_version, language, structure=None):
    """{stat_key: {'label', 'runes'}} for the UI, in the reader's language."""
    grouped = {}
    for rune in get_transcendence_runes(game_version):
        entry = grouped.setdefault(rune['stat_key'], {
            'label': _stat_label(rune['stat_key'], language, structure),
            'runes': []})
        entry['runes'].append(dict(rune, name=rune_name(rune, language),
                                   notice=rune_notice(rune, language)))
    for entry in grouped.values():
        entry['runes'].sort(key=lambda r: r['rank'])
    return grouped
