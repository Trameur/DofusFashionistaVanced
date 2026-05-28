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

_CLASS_DEFAULT_ELEMENT = {
    'Iop': 'str', 'Cra': 'agi', 'Sram': 'agi', 'Xelor': 'cha', 'Eniripsa': 'int',
    'Feca': 'int', 'Sacrier': 'agi', 'Sadida': 'cha', 'Enutrof': 'cha', 'Osamodas': 'cha',
    'Ecaflip': 'cha', 'Pandawa': 'str', 'Eliotrope': 'cha', 'Huppermage': 'int',
    'Ouginak': 'agi', 'Masqueraider': 'agi', 'Foggernaut': 'int', 'Rogue': 'agi',
    'Forgelance': 'str',
}


def _match_class(tokens, normalized_text):
    for cls in CHARACTER_CLASSES:
        if _normalize(cls) in tokens:
            return cls
    # substring fallback (handles "iop's", "cra,")
    for cls in CHARACTER_CLASSES:
        if _normalize(cls) in normalized_text:
            return cls
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


def parse_build_request(text):
    """Return a dict describing the parsed build, with `matched` flags."""
    normalized = _normalize(text)
    tokens = set(re.findall(r'[a-z0-9]+', normalized))

    char_class = _match_class(tokens, normalized)
    level = _match_level(normalized)
    element = _match_element(tokens)
    style = _match_style(tokens)

    resolved_style = style or 'solo_pvm'
    aspects = set(_STYLE_BASE_ASPECTS.get(resolved_style, set()))
    if resolved_style != 'farm':
        elem = element or (_CLASS_DEFAULT_ELEMENT.get(char_class, 'str') if char_class else 'str')
        aspects.add(elem)

    return {
        'char_class': char_class,
        'level': level if level is not None else 200,
        'element': element,
        'style': resolved_style,
        'aspects': aspects,
        'matched_class': char_class is not None,
        'matched_level': level is not None,
        'matched_element': element is not None,
        'matched_style': style is not None,
    }
