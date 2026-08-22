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
_STATES_DIRECTORY = os.path.join(os.path.dirname(__file__), 'spell_states')
_CACHE = {}
_STATE_CACHE = {}


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


_PUSHING_CACHE = {}

# Ankama's own wording for a push, in the two languages the reference always
# carries. A push is not damage on its own: it only hurts when the target hits
# an obstacle, and the damage scales with the push distance left over. So this
# says which spells CAN cause pushback damage, never that they will.
# "pushback damage" and "dommages de poussee" are deliberately absent: those
# phrases describe SUFFERING the damage, and matching them flagged Noa itself,
# whose whole text is about a target that gets pushed by something else.
_PUSH_WORDS_EN = ('repels', 'pushes back', 'pushes the target back',
                  'pushes targets back')
_PUSH_WORDS_FR = ('repousse', 'repoussent')


def pushing_spell_ids(game_version):
    """Spell ids whose own description says the spell pushes a target."""
    if game_version in _PUSHING_CACHE:
        return _PUSHING_CACHE[game_version]
    found = set()
    for entries in (get_spell_reference(game_version) or {}).values():
        for entry in entries or []:
            if entry.get('id') is None:
                continue
            description = entry.get('description') or {}
            english = (description.get('en') or '').lower()
            french = (description.get('fr') or '').lower()
            if (any(word in english for word in _PUSH_WORDS_EN)
                    or any(word in french for word in _PUSH_WORDS_FR)):
                found.add(entry['id'])
    _PUSHING_CACHE[game_version] = found
    return found


def get_spell_states(game_version):
    """{state id: {lang: name}} for one version, empty when the source has none.

    Only dofus3 and beta: the 2.73 archive ships no state file, and Retro and
    Touch build no state-gated damage row.
    """
    if game_version not in _STATE_CACHE:
        path = os.path.join(_STATES_DIRECTORY, '%s.json' % game_version)
        try:
            with open(path, encoding='utf-8') as handle:
                _STATE_CACHE[game_version] = json.load(handle)
        except (IOError, OSError, ValueError):
            _STATE_CACHE[game_version] = {}
    return _STATE_CACHE[game_version]


def state_name(game_version, state_id, language):
    """The name the game gives a state, or '' when the version has no table."""
    entry = get_spell_states(game_version).get(str(state_id))
    if not entry:
        return ''
    return localized({'name': entry}, 'name', language)


def localized(entry, key, language):
    """One localized field of an entry, falling back to English then French."""
    values = entry.get(key) or {}
    for candidate in (language, (language or '').split('-')[0], 'en', 'fr'):
        if values.get(candidate):
            return values[candidate]
    return ''
