# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the character who wears a build cannot wear: level, class, sex, name."""

from django.utils.translation import gettext as _

from .structure import (fits_the_level, fits_the_wearer, get_structure,
                        level_to_wear)
from .translation import get_supported_language
from .violation import Violation


class Wearer:
    """The character a build is worn by; a fact left at None is not checked."""

    def __init__(self, level=None, char_class=None, gender=None, char_name=None):
        self.level = level
        self.char_class = char_class
        self.gender = gender
        self.char_name = char_name

    @classmethod
    def of(cls, char):
        return cls(getattr(char, 'level', None) or None,
                   getattr(char, 'char_class', None) or None,
                   getattr(char, 'gender', None),
                   getattr(char, 'char_name', None))

    def reasons(self, item, worn_ids=()):
        """(kind, text) for each condition of this worn piece the character does not meet."""
        reasons = []
        if getattr(item, 'unusable', False):
            reasons.append(('wear_unusable', _('Unequippable item')))
        classes = tuple(getattr(item, 'classes', ()))
        if classes and self.char_class is not None and self.char_class not in classes:
            reasons.append(('wear_class', _('Class: %(classes)s') % {
                'classes': ', '.join(_(name) for name in classes)}))
        if self.level is not None and not fits_the_level(item, self.level):
            needed = level_to_wear(item)
            if needed > self.level:
                reasons.append(('wear_level_min', _('Be level %(level)s or higher')
                                % {'level': needed}))
            highest = getattr(item, 'max_level', None)
            if highest is not None and self.level > highest:
                reasons.append(('wear_level_max', _('Be level %(level)s or lower')
                                % {'level': highest}))
        sexes = tuple(getattr(item, 'sexes', ()))
        if (sexes and self.gender is not None
                and not fits_the_wearer(item, gender=self.gender)):
            reasons.append(('wear_sex', _('Male only') if sexes == (0,)
                            else _('Female only')))
        names = tuple(getattr(item, 'names', ()))
        if (names and self.char_name is not None
                and not fits_the_wearer(item, char_name=self.char_name)):
            reasons.append(('wear_name', _('Name = %(name)s')
                            % {'name': ', '.join(names)}))
        structure = get_structure()
        for other_id in getattr(item, 'own_not_worn_with', ()):
            other = structure.get_item_by_id(other_id) if other_id in worn_ids else None
            if other is not None:
                reasons.append(('wear_not_with', _('Not have the "%(item)s" item equipped')
                                % {'item': structure.get_item_name_in_language(
                                    other, get_supported_language())}))
        return reasons

    def violations_on(self, result_item, worn_ids=()):
        violations = []
        for kind, text in self.reasons(result_item, worn_ids):
            violation = Violation()
            violation.item_name = result_item.localized_name
            violation.stat_name = text
            violation.condition_type = kind
            violation.is_red = True
            violation.cant_equip = True
            violations.append(violation)
        return violations
