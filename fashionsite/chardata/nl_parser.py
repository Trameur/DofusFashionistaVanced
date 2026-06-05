# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Keyword-based natural-language build request parser.

Turns a free-text query like "Iop 200 terre PvM" or "Cra agi pvp niveau 150"
into structured build parameters. No LLM — pure multilingual keyword matching
(FR / EN / ES / PT), so it works offline, instantly and for free.

Output: dict with char_class, level, element_aspect (str/int/cha/agi/omni or
None), style (solo_pvm / group_pvm / pvp / farm) and the derived aspect set.
"""

import re
import unicodedata

from fashionistapulp.dofus_constants import CHARACTER_CLASSES


def _normalize(text):
    folded = unicodedata.normalize('NFKD', text or '')
    folded = ''.join(c for c in folded if not unicodedata.combining(c))
    return folded.lower()


# Element keyword (normalized, accent-folded) -> elemental aspect.
# Dofus mapping: Earth=Strength, Fire=Intelligence, Water=Chance, Air=Agility.
_ELEMENT_WORDS = {
    'str': ['terre', 'earth', 'tierra', 'terra', 'force', 'strength', 'fuerza', 'forca'],
    'int': ['feu', 'fire', 'fuego', 'fogo', 'intelligence', 'intelligence', 'inteligencia', 'int'],
    'cha': ['eau', 'water', 'agua', 'chance', 'luck', 'suerte', 'sorte', 'cha'],
    'agi': ['air', 'aire', 'ar', 'agilite', 'agility', 'agilidad', 'agilidade', 'agi'],
    'omni': ['omni', 'multi', 'multielement', 'multielemento', 'omnielement', 'polyvalent'],
}

# Style keyword -> coaching style key.
_STYLE_WORDS = {
    'pvp': ['pvp', 'kolizeum', 'koli', 'arene', 'arena', 'duel', 'duelo'],
    'group_pvm': ['tank', 'tanky', 'tanky', 'tanque', 'support', 'soutien', 'soin', 'heal',
                  'healer', 'soigneur', 'sanador', 'curandeiro', 'group', 'groupe', 'grupo',
                  'donjon', 'dungeon', 'mazmorra', 'masmorra'],
    'farm': ['farm', 'farming', 'drop', 'prospection', 'prospecting', 'pp', 'xp', 'exp',
             'level', 'leveling', 'levelup', 'rush', 'sagesse', 'wisdom', 'recolte'],
    'solo_pvm': ['pvm', 'pve', 'solo', 'dps', 'damage', 'degats', 'dmg', 'mono'],
}

_STYLE_BASE_ASPECTS = {
    'solo_pvm': {'glasscannon'},
    'group_pvm': {'vit', 'res'},
    'pvp': {'pvp', 'crit'},
    'farm': {'wis', 'pp'},
}

# Explicit focus keywords -> extra build aspects, layered on top of the style's
# base aspects. Lets "osa invocation", "sram pièges", "eni soin", "pvp pp" steer
# the build beyond the four coarse styles. Keys must stay valid smart_build
# aspects (ASPECT_TO_SHORT_NAME / ALL_ASPECTS_LIST).
_ASPECT_WORDS = {
    'heal': ['heal', 'heals', 'healer', 'soin', 'soins', 'soigneur', 'sanador',
             'curandeiro', 'cura'],
    'summon': ['summon', 'summons', 'summoner', 'invocation', 'invocations',
               'invoc', 'invocateur', 'invocador', 'invocador'],
    'trap': ['trap', 'traps', 'piege', 'pieges', 'trampa', 'trampas',
             'armadilha', 'armadilhas'],
    'pushback': ['pushback', 'poussee', 'repousse', 'empuje', 'empurrao'],
    'crit': ['crit', 'crits', 'critique', 'critiques', 'critico', 'critica',
             'critical'],
    'res': ['res', 'resistance', 'resistances', 'resist', 'resistencia',
            'resistencias'],
    'vit': ['vit', 'vita', 'vitalite', 'vitality', 'vitalidad', 'vitalidade',
            'tank', 'tanky', 'tanque'],
    'pp': ['pp', 'prospection', 'prospecting', 'prospeccion', 'drop'],
    'wis': ['wis', 'wisdom', 'sagesse', 'sabiduria', 'sabedoria'],
    'pods': ['pods', 'pod', 'pano'],
}

_CLASS_DEFAULT_ELEMENT = {
    'Iop': 'str', 'Cra': 'agi', 'Sram': 'agi', 'Xelor': 'cha', 'Eniripsa': 'int',
    'Feca': 'int', 'Sacrier': 'agi', 'Sadida': 'cha', 'Enutrof': 'cha', 'Osamodas': 'cha',
    'Ecaflip': 'cha', 'Pandawa': 'str', 'Eliotrope': 'cha', 'Huppermage': 'int',
    'Ouginak': 'agi', 'Masqueraider': 'agi', 'Foggernaut': 'int', 'Rogue': 'agi',
    'Forgelance': 'str',
}


# Extra class aliases on top of the canonical English names: official French
# names (which differ for several classes) and the abbreviations players
# actually type. All normalized/accent-folded at index build time.
_EXTRA_CLASS_ALIASES = {
    'Cra': ['craa', 'archer'],
    'Ecaflip': ['eca', 'ecaf', 'eca'],
    'Eliotrope': ['elio', 'eliot'],
    'Eniripsa': ['eni', 'enni', 'enirispa'],
    'Enutrof': ['enu', 'enutrofe'],
    'Feca': ['fec', 'feka'],
    'Foggernaut': ['fog', 'fogger', 'steamer'],          # FR: Steamer
    'Forgelance': ['forge', 'forgel'],
    'Huppermage': ['hupper', 'hupp', 'huppe'],
    'Iop': [],
    'Masqueraider': ['masque', 'masq', 'masqu', 'zobal'],  # FR: Zobal
    'Osamodas': ['osa', 'osamo'],
    'Ouginak': ['ougi', 'ougie'],
    'Pandawa': ['panda', 'panda'],
    'Rogue': ['roub', 'roublard'],                         # FR: Roublard
    'Sacrier': ['sacri', 'sacrieur', 'sacro', 'sacra'],    # FR: Sacrieur
    'Sadida': ['sadi', 'sadid'],
    'Sram': ['srama'],
    'Xelor': ['xel', 'xelors'],
}


def _build_class_alias_index():
    index = {}
    for cls in CHARACTER_CLASSES:
        index[_normalize(cls)] = cls
    for cls, aliases in _EXTRA_CLASS_ALIASES.items():
        for alias in aliases:
            index[_normalize(alias)] = cls
    return index


_CLASS_ALIAS_INDEX = _build_class_alias_index()
_MIN_PREFIX_LEN = 4  # avoid matching short noise words on the prefix pass


def _match_class(tokens):
    # 1. Exact whole-token match against any known name/alias.
    for token in tokens:
        cls = _CLASS_ALIAS_INDEX.get(token)
        if cls is not None:
            return cls
    # 2. Prefix match: a token like "sacrie" / "masquer" that uniquely begins
    #    (or is begun by) a single class's name/alias. Only fire when it points
    #    at exactly one class, so ambiguous fragments stay unmatched.
    for token in tokens:
        if len(token) < _MIN_PREFIX_LEN:
            continue
        candidates = {cls for alias, cls in _CLASS_ALIAS_INDEX.items()
                      if alias.startswith(token) or token.startswith(alias)}
        if len(candidates) == 1:
            return next(iter(candidates))
    return None


def _match_level(normalized_text):
    # Prefer a number near a level keyword, else any 1-3 digit number.
    m = re.search(r'(?:niveau|level|nivel|nivel|lvl|niv)\s*[:.]?\s*(\d{1,3})', normalized_text)
    if m:
        return _clamp_level(int(m.group(1)))
    nums = re.findall(r'\b(\d{1,3})\b', normalized_text)
    for n in nums:
        val = int(n)
        if 1 <= val <= 230:
            return _clamp_level(val)
    return None


def _clamp_level(v):
    return max(1, min(v, 230))


def _match_element(tokens):
    for aspect, words in _ELEMENT_WORDS.items():
        for w in words:
            if w in tokens:
                return aspect
    return None


def _match_style(tokens):
    # Priority order: pvp > farm > group_pvm > solo_pvm.
    for style in ('pvp', 'farm', 'group_pvm', 'solo_pvm'):
        for w in _STYLE_WORDS[style]:
            if w in tokens:
                return style
    return None


def _match_aspect_words(tokens):
    extra = set()
    for aspect, words in _ASPECT_WORDS.items():
        if any(w in tokens for w in words):
            extra.add(aspect)
    return extra


def parse_build_request(text):
    """Return a dict describing the parsed build, with `matched` flags."""
    normalized = _normalize(text)
    tokens = set(re.findall(r'[a-z0-9]+', normalized))

    char_class = _match_class(tokens)
    level = _match_level(normalized)
    element = _match_element(tokens)
    style = _match_style(tokens)
    extra_aspects = _match_aspect_words(tokens)

    resolved_style = style or 'solo_pvm'
    aspects = set(_STYLE_BASE_ASPECTS.get(resolved_style, set()))
    if resolved_style != 'farm':
        elem = element or (_CLASS_DEFAULT_ELEMENT.get(char_class, 'str') if char_class else 'str')
        aspects.add(elem)
    aspects |= extra_aspects

    return {
        'char_class': char_class,
        'level': level if level is not None else 200,
        'element': element,
        'style': resolved_style,
        'aspects': aspects,
        'extra_aspects': extra_aspects,
        'matched_class': char_class is not None,
        'matched_level': level is not None,
        'matched_element': element is not None,
        'matched_style': style is not None,
    }
