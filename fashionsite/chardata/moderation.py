# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Link and profanity filtering for user-submitted text."""

import re
import unicodedata

from django.utils.translation import gettext_lazy as _


ALLOWED_HOSTS = {
    'dofusfashionista.gg',
    'www.dofusfashionista.gg',
    'fashionistavanced.com',
    'www.fashionistavanced.com',
}

# Matches bare hostnames as well as full URLs.
_URL_RE = re.compile(
    r'\b(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/[^\s]*)?',
    re.IGNORECASE,
)

# Entries must be lowercased and ASCII-folded. Short ones must not collide with
# class names (Cra, Iop, Sram) or stat words.
_PROFANITY_WORDS = {
    # French insults
    'putain', 'pute', 'putes', 'merde', 'merdique', 'connard', 'connards',
    'connasse', 'connasses', 'salope', 'salopes', 'encule', 'encules',
    'enculer', 'enculee', 'enculees', 'fdp', 'ntm', 'tg', 'pd', 'pede',
    'pedes', 'tarlouze', 'tapette', 'petasse', 'petasses', 'batard',
    'batards', 'cul', 'couille', 'couilles', 'fiotte', 'fiottes',
    # English insults
    'fuck', 'fucking', 'fucker', 'fuckers', 'shit', 'shitty', 'bitch',
    'bitches', 'asshole', 'assholes', 'cunt', 'cunts', 'dick', 'dicks',
    'whore', 'whores', 'slut', 'sluts', 'retard', 'retards', 'retarded',
    # Spanish insults
    'mierda', 'mierdas', 'joder', 'puta', 'putas', 'puto', 'putos', 'cabron',
    'cabrones', 'cabrona', 'cabronas', 'gilipollas', 'polla', 'pollas',
    'cono', 'conos', 'maricon', 'maricones', 'marica', 'maricas', 'mariconazo',
    'pendejo', 'pendejos', 'pendeja', 'pendejas', 'culero', 'culeros',
    'chinga', 'chingar', 'chingada', 'chingadera', 'chingate', 'pinche',
    'verga', 'vergas', 'mamon', 'mamones', 'imbecil', 'imbeciles',
    'zorra', 'zorras', 'perra', 'perras', 'puton', 'putones',
    # Portuguese insults
    'porra', 'caralho', 'caralhos', 'merdas', 'viado', 'viados', 'bicha',
    'bichas', 'cuzao', 'cuzoes', 'babaca', 'babacas', 'corno', 'cornos',
    'corna', 'cornas', 'vagabunda', 'vagabundas', 'vagabundo', 'vagabundos',
    'buceta', 'bucetas', 'piranha', 'piranhas', 'foda', 'foder', 'fodase',
    'fodam', 'fodido', 'fodida', 'fodidos', 'fodidas', 'caralha', 'porras', 'pqp',
    'puta que pariu', 'arrombado', 'arrombados', 'otario', 'otarios',
    # Slurs (multi-lang), strict
    'faggot', 'faggots', 'fag', 'nigger', 'niggers', 'nigga', 'niggas',
    'kike', 'spic', 'chink', 'gook',
}


def _normalize(text):
    """Lowercase and strip accents."""
    folded = unicodedata.normalize('NFKD', text)
    folded = ''.join(c for c in folded if not unicodedata.combining(c))
    return folded.lower()


def _extract_hosts(content):
    hosts = []
    for match in _URL_RE.finditer(content):
        url = match.group(0).lower()
        # Strip the scheme if present
        url_no_scheme = re.sub(r'^https?://', '', url)
        host = url_no_scheme.split('/', 1)[0]
        hosts.append(host)
    return hosts


def check_links(content):
    """Return list of non-allowed hosts found in content."""
    return [h for h in _extract_hosts(content) if h not in ALLOWED_HOSTS]


def check_profanity(content):
    """Return True if a banned word is found (with word boundaries)."""
    text = _normalize(content)
    for word in _PROFANITY_WORDS:
        if re.search(r'\b' + re.escape(word) + r'\b', text):
            return True
    return False


def validate_comment(content):
    """Validate a comment's content. Returns (is_clean, error_message)."""
    bad_hosts = check_links(content)
    if bad_hosts:
        return False, _("Please remove external links. Only dofusfashionista.gg links are allowed.")
    if check_profanity(content):
        return False, _("Please keep your comment respectful.")
    return True, ''
