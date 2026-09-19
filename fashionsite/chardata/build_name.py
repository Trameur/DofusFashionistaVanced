# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The name a build shows when its author gave none."""

import re

_VIDE = re.compile(r'^\s*$')

# What the page writes with no character name: spaces, the level, one "copy" per duplicate
_ARTEFACT = re.compile(r'^\s+\d{1,3}(\s+copy)*\s*$')

# Server default when the form lacks the field
_DEFAUT_DU_SERVEUR = 'NoName'


def is_placeholder(name):
    """Whether the page or the server made this name up."""
    name = name or ''
    return bool(_VIDE.match(name)
                or name.strip() == _DEFAUT_DU_SERVEUR
                or _ARTEFACT.match(name))


def fallback_name(char_class, level):
    """Class and level, in the reader's language."""
    from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
    classe = LOCALIZED_CHARACTER_CLASSES.get(char_class, char_class or '')
    niveau = '' if level is None else str(level)
    return ('%s %s' % (classe, niveau)).strip()


def display_name(char):
    """The build name to show, never empty."""
    if char is None:
        return ''
    name = getattr(char, 'name', '') or ''
    if not is_placeholder(name):
        return name
    return fallback_name(getattr(char, 'char_class', ''),
                         getattr(char, 'level', None)) or name.strip()


def cleaned_at_creation(name, char_class, level):
    """The name to store for a new build."""
    if is_placeholder(name):
        return fallback_name(char_class, level)
    return name
