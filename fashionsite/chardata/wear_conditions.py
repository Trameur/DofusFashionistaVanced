# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Equip conditions that are not a stat: a class, a spell rank, a level range, a piece worn with another."""

from django.utils.translation import gettext as _

from chardata.spell_reference import get_spell_reference
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from fashionistapulp.structure import get_structure
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


def not_worn_with_condition_text(name):
    return _('Not have the "%(item)s" item equipped') % {'item': name}


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
    others = getattr(item, 'own_not_worn_with', ())
    if others:
        structure = get_structure(game_version)
        language = get_supported_language()
        for other_id in others:
            other = structure.get_item_by_id(other_id)
            if other is not None:
                texts.append(not_worn_with_condition_text(
                    structure.get_item_name_in_language(other, language)
                    or other.name))
    return texts
