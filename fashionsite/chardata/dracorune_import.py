# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Dracorunes a link's pieces wear: checked against the build's version, put on the saved solution, counted in the build's option."""

from chardata.char_blobs import read_char_blob
from chardata.options import get_options, set_setup_choices
from chardata.solution import set_minimal_solution
from fashionistapulp import dracorune_terms, dracorunes
from fashionistapulp.model import dracorune_count, readable_runes
from fashionistapulp.structure import (get_current_game_version, get_structure,
                                       set_current_game_version)


def checked(build, version):
    """([(item id, variant key)] this version still takes, [item ids left unread]) for a link's runes."""
    wanted = list(build.get('dracorunes') or [])
    unread = list(build.get('dracorunes_unread') or [])
    if not wanted:
        return [], unread
    runes = readable_runes(version)
    structure = get_structure(version)
    valid = []
    for item_id, key in wanted:
        item = structure.get_item_by_id(item_id)
        try:
            takes = (runes is not None and item is not None
                     and dracorune_terms.is_eligible(item, structure, runes)
                     and any(variant.key == key for variant
                             in dracorune_terms.item_variants(item, runes, structure)))
        except (KeyError, TypeError, ValueError):
            takes = False
        if takes:
            valid.append((item_id, key))
        else:
            unread.append(item_id)
    return valid, unread


def rejected_as_rolls(build, version):
    """The build with the sheet lines of every rune this version rejects put back among its rolls."""
    saved = build.get('dracorune_rolls') or {}
    if not saved:
        return build
    valid, _unread = checked(build, version)
    kept = {item_id for item_id, _key in valid}
    rolls = dict(build.get('rolls') or {})
    for item_id, lines in saved.items():
        if item_id not in kept:
            rolls[item_id] = list(rolls.get(item_id) or []) + list(lines)
    return dict(build, rolls=rolls)


def rune_names(pairs, version, language):
    """['Rune name (item name)'] for the pairs, the rune named by the game in the language."""
    runes = readable_runes(version)
    structure = get_structure(version)
    names = []
    for item_id, key in pairs:
        item = structure.get_item_by_id(item_id)
        rune = dracorunes.rune_of(key, runes)
        names.append('%s (%s)' % (
            dracorunes.rune_name(rune, language) or key,
            structure.get_item_name_in_language(item, language) or item.name
            if item is not None else item_id))
    return names


def item_names(item_ids, version, language):
    structure = get_structure(version)
    names = []
    for item_id in item_ids:
        item = structure.get_item_by_id(item_id)
        names.append(structure.get_item_name_in_language(item, language) or item.name
                     if item is not None else str(item_id))
    return names


def put_on_solution(char, build):
    """Writes the link's runes on the char's saved solution and raises its option to their count; call after the gear is placed."""
    valid, _unread = checked(build, char.game_version)
    if not valid:
        return 0
    previous = get_current_game_version()
    set_current_game_version(char.game_version)
    try:
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        if minimal is None:
            return 0
        minimal.place_dracorunes(valid)
        count = len(minimal.dracorunes or {})
        if not count:
            return 0
        options = get_options(char)
        options['dracorunes'] = max(dracorune_count(options), count)
        if isinstance(getattr(minimal, 'input', None), dict):
            minimal.input['options'] = dict(minimal.input.get('options') or {},
                                            dracorunes=options['dracorunes'])
        set_setup_choices(char, {'dracorunes': options['dracorunes']})
        set_minimal_solution(char, minimal)
        return count
    finally:
        set_current_game_version(previous)
