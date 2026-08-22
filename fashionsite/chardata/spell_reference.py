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


def pushing_spell_ids(game_version):
    """Spell ids that push a target hard enough to hurt it on an obstacle.

    From the client's own effects, carried in the reference as `push`: effect 5
    and its forced variants damage on collision, effect 1103 is stated as
    pushing without damage. Reading the description text instead was a proxy
    and a leaky one, it put Noa in this list because its text names the damage
    it waits for.
    """
    if game_version in _PUSHING_CACHE:
        return _PUSHING_CACHE[game_version]
    found = set()
    carries_effects = False
    for entries in (get_spell_reference(game_version) or {}).values():
        for entry in entries or []:
            if entry.get('id') is None:
                continue
            if entry.get('push'):
                carries_effects = True
            for rank in entry.get('push') or []:
                if rank and rank.get('damaging') and rank.get('cells'):
                    found.add(entry['id'])
                    break
    if not carries_effects:
        found = _pushing_from_descriptions(game_version)
    _PUSHING_CACHE[game_version] = found
    return found


# Only dofus3 and the beta are built from the client's own effects. The Dofus 2
# archive carries no spell level at all, and Retro and Touch come from other
# readers, so for those three the description is all there is. It cannot say a
# distance and it cannot tell a damaging push from a harmless one.
_PUSH_WORDS_EN = ('repels', 'pushes back', 'pushes the target back',
                  'pushes targets back')
_PUSH_WORDS_FR = ('repousse', 'repoussent')


def _pushing_from_descriptions(game_version):
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
    return found


def push_info(game_version, spell_id, rank_index=-1):
    """The push a spell makes at that rank, or None.

    {'cells': n, 'damaging': bool} and, when the client gates it on a state,
    'needs': {'state': id, 'present': bool}. The Steamer's Torrent pushes four
    cells at High Tide and attracts six at Low; reading the cells without the
    gate credits it a push it makes half the time.
    """
    for entries in (get_spell_reference(game_version) or {}).values():
        for entry in entries or []:
            if entry.get('id') != spell_id:
                continue
            ranks = entry.get('push') or []
            if not ranks:
                return None
            index = rank_index if -len(ranks) <= rank_index < len(ranks) else -1
            return ranks[index]
    return None


def strips_pushback_resist(game_version, spell_id, rank_index=-1):
    """Pushback resistance this spell takes off its target at that rank.

    A push against a target whose resistance is gone hits harder: the formula
    subtracts that resistance, so removing 60 of it is worth 60 pushback damage
    for that push. Corrosion and Brass Rain are the Steamer's two.
    """
    for entries in (get_spell_reference(game_version) or {}).values():
        for entry in entries or []:
            if entry.get('id') != spell_id:
                continue
            ranks = entry.get('strips_pushback_resist') or []
            if not ranks:
                return 0
            index = rank_index if -len(ranks) <= rank_index < len(ranks) else -1
            return ranks[index] or 0
    return 0


def push_cells(game_version, spell_id, rank_index=-1):
    """Cells that spell pushes at that rank, 0 when it does not push or the
    push is one the game states deals no damage."""
    for entries in (get_spell_reference(game_version) or {}).values():
        for entry in entries or []:
            if entry.get('id') != spell_id:
                continue
            ranks = entry.get('push') or []
            if not ranks:
                return 0
            index = rank_index if -len(ranks) <= rank_index < len(ranks) else -1
            rank = ranks[index]
            if not rank or not rank.get('damaging'):
                return 0
            return rank.get('cells') or 0
    return 0


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
