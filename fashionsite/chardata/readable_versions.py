# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The versions readers can reach, counted and named for prose in the five languages."""
import re

from django.utils.translation import get_language

from fashionistapulp.game_versions import GAME_VERSIONS, reader_dofus_versions

_NUMBERS = {
    'en': ('two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'),
    'fr': ('deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix'),
    'de': ('zwei', 'drei', 'vier', 'fünf', 'sechs', 'sieben', 'acht', 'neun', 'zehn'),
    'es': ('dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez'),
    'pt': ('dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove', 'dez'),
}
_ACCENTED = {'fr': (('Beta', 'Bêta'),)}
_ACCENTED_RETRO = {'fr': (('Retro', 'Rétro'),)}
_CONJUNCTIONS = {
    'and': {'en': 'and', 'fr': 'et', 'de': 'und', 'es': 'y', 'pt': 'e'},
    'or': {'en': 'or', 'fr': 'ou', 'de': 'oder', 'es': 'o', 'pt': 'ou'},
}


def _language(language):
    code = (language or get_language() or 'en').split('-')[0].lower()
    return code if code in _NUMBERS else 'en'


def readable_keys():
    """The Dofus versions a reader can reach, in page order, experimental ones left out."""
    return reader_dofus_versions()


def native_name(key, language=None):
    """The game name of a version key in the reader's language."""
    return _accented(GAME_VERSIONS[key].game_name, _language(language), _ACCENTED)


def count_word(language=None):
    """How many versions readers can reach, as a word: 'five', 'cinq', 'fünf'."""
    count = len(readable_keys())
    words = _NUMBERS[_language(language)]
    return words[count - 2] if 2 <= count <= len(words) + 1 else str(count)


def _accented(name, language, pairs):
    for plain, accented in pairs.get(language, ()):
        name = re.sub(r'\b%s\b' % plain, accented, name)
    return name


def join_names(names, language=None, conjunction='and'):
    """Names as one list, the last one after the conjunction; commas only when conjunction is empty."""
    if not conjunction or len(names) < 2:
        return ', '.join(names)
    word = _CONJUNCTIONS[conjunction][_language(language)]
    return '%s %s %s' % (', '.join(names[:-1]), word, names[-1])


def version_names(language=None, short=False, conjunction='and', native=False, labels=None, retro=False):
    """The readable versions as one list: 'Dofus 3, Dofus 3 Beta and Dofus Touch'; native writes Beta with the language's accent, retro does the same for Retro."""
    language = _language(language)
    names = []
    for key in readable_keys():
        version = GAME_VERSIONS[key]
        name = (labels or {}).get(key) or (version.label if short else version.game_name)
        if native:
            name = _accented(name, language, _ACCENTED)
        if retro:
            name = _accented(name, language, _ACCENTED_RETRO)
        names.append(name)
    return join_names(names, language, conjunction)
