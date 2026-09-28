# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Equip conditions that are not a stat: a class, a spell rank."""

from django.utils.translation import gettext as _

from chardata.spell_reference import get_spell_reference
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
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


def condition_texts(game_version, item):
    """The class and spell rank lines of one piece, in the active language."""
    classes = tuple(getattr(item, 'classes', ()))
    texts = []
    if classes:
        texts.append(class_condition_text(classes))
    for spell_id, rank, _min_level in getattr(item, 'spell_conditions', ()):
        texts.append(spell_rank_condition_text(game_version, classes,
                                               spell_id, rank))
    return texts
