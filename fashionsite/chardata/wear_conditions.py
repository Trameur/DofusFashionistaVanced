# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Equip conditions that are not a stat: a class, a spell rank, a level range, a piece worn with another, a sex, a name."""

from django.utils.translation import gettext as _

from chardata.spell_reference import get_spell_reference
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from fashionistapulp.structure import (fits_the_class, fits_the_level,
                                       fits_the_wearer, get_structure,
                                       level_to_wear, name_fits)
from fashionistapulp.translation import get_supported_language


def class_condition_text(classes):
    return _('Class: %(classes)s') % {'classes': ', '.join(
        str(LOCALIZED_CHARACTER_CLASSES.get(char_class, char_class))
        for char_class in classes)}


def _spell_name(game_version, classes, spell_id):
    reference = get_spell_reference(game_version) or {}
    language = get_supported_language()
    for char_class in tuple(classes) or tuple(reference):
        for entry in reference.get(char_class) or ():
            if entry.get('id') == spell_id:
                names = entry.get('name') or {}
                return names.get(language) or names.get('en') or names.get('fr')
    return None


def spell_rank_condition_text(game_version, classes, spell_id, rank):
    name = _spell_name(game_version, classes, spell_id) or '#%d' % spell_id
    return _('The %(spell)s spell must be at level %(rank)s') % {
        'spell': name, 'rank': rank}


def unusable_condition_text():
    return _('Unequippable item')


def max_level_condition_text(level):
    return _('Be level %(level)s or lower') % {'level': level}


def min_level_condition_text(level):
    return _('Be level %(level)s or higher') % {'level': level}


def not_worn_with_condition_text(name):
    return _('Not have the "%(item)s" item equipped') % {'item': name}


def sex_condition_text(sexes):
    return _('Male only') if tuple(sexes) == (0,) else _('Female only')


def name_condition_text(names):
    return _('Name = %(name)s') % {'name': ', '.join(names)}


def other_item_name(game_version, other_id):
    structure = get_structure(game_version)
    other = structure.get_item_by_id(other_id)
    if other is None:
        return None
    return (structure.get_item_name_in_language(other, get_supported_language())
            or other.name)


def condition_texts(game_version, item):
    """The lines of one piece that are not a stat, in the active language."""
    classes = tuple(getattr(item, 'classes', ()))
    texts = []
    if getattr(item, 'unusable', False):
        texts.append(unusable_condition_text())
    if classes:
        texts.append(class_condition_text(classes))
    if getattr(item, 'max_level', None) is not None:
        texts.append(max_level_condition_text(item.max_level))
    for spell_id, rank, _min_level in getattr(item, 'spell_conditions', ()):
        texts.append(spell_rank_condition_text(game_version, classes,
                                               spell_id, rank))
    for other_id in getattr(item, 'own_not_worn_with', ()):
        name = other_item_name(game_version, other_id)
        if name is not None:
            texts.append(not_worn_with_condition_text(name))
    if getattr(item, 'sexes', ()):
        texts.append(sex_condition_text(item.sexes))
    if getattr(item, 'names', ()):
        texts.append(name_condition_text(item.names))
    return texts


def a_new_build_can_wear(item):
    """Not unequippable and asking for no character name."""
    return not getattr(item, 'unusable', False) and not getattr(item, 'names', ())


def reasons_not_worn(game_version, item, char_class=None, level=None,
                     gender=None, char_name=None, beside=()):
    """The lines of the conditions a build does not meet; None leaves a check out."""
    texts = []
    if getattr(item, 'unusable', False):
        texts.append(unusable_condition_text())
    classes = tuple(getattr(item, 'classes', ()))
    if char_class is not None and classes and not fits_the_class(item, char_class):
        texts.append(class_condition_text(classes))
    if level is not None and not fits_the_level(item, level):
        highest = getattr(item, 'max_level', None)
        if highest is not None and level > highest:
            texts.append(max_level_condition_text(highest))
        if level_to_wear(item) > level:
            texts.append(min_level_condition_text(level_to_wear(item)))
    sexes = getattr(item, 'sexes', ())
    if gender is not None and sexes and not fits_the_wearer(item, gender=gender):
        texts.append(sex_condition_text(sexes))
    names = getattr(item, 'names', ())
    if (char_name is not None and names
            and not any(name_fits(char_name, name) for name in names)):
        texts.append(name_condition_text(names))
    for other_id in sorted(set(beside).intersection(getattr(item, 'not_worn_with', ()))):
        name = other_item_name(game_version, other_id)
        if name is not None:
            texts.append(not_worn_with_condition_text(name))
    return texts


def not_locked_text(reasons):
    return _('Not locked, this build cannot wear it: %(reasons)s') % {
        'reasons': '; '.join(reasons)}


def still_locked_text(reasons):
    return _('Still locked, but this build cannot wear it: %(reasons)s') % {
        'reasons': '; '.join(reasons)}


def left_out_text(reasons):
    return _('Left out, this build cannot wear it: %(reasons)s') % {
        'reasons': '; '.join(reasons)}


def reasons_the_build_cannot_wear(char, item, beside=()):
    """reasons_not_worn for a stored build."""
    return reasons_not_worn(getattr(char, 'game_version', None) or 'dofus3', item,
                            getattr(char, 'char_class', None),
                            getattr(char, 'level', None),
                            getattr(char, 'gender', None) or 0,
                            getattr(char, 'char_name', None) or '',
                            beside)
