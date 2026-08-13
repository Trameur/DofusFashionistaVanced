# -*- coding: utf-8 -*-

# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""An item's special spell prints as a heading and the prose under it."""

import re

# Unity rich text for the element icons, on one item, the Dofusteuse. The
# element is named in the words that follow, so the tag says nothing the reader
# loses by not seeing it, and it was printed raw.
_SPRITE = re.compile(r'<sprite\s+name="[^"]*"\s*/?>')
_MARKUP = re.compile(r'<[^<>]{1,40}>')

_BULLETS = ('•', '▪', '●', '·')

# A heading is a name, not a sentence that happens to end in a colon.
_HEAD_LIMIT = 80


def clean_line(line):
    text = _MARKUP.sub('', _SPRITE.sub('', line or ''))
    text = text.strip()
    while text[:1] in _BULLETS:
        text = text[1:].strip()
    return re.sub(r'\s{2,}', ' ', text)


def _is_head(line):
    text = clean_line(line)
    return (bool(text) and len(text) <= _HEAD_LIMIT and text.endswith(':')
            and line.strip()[:1] not in _BULLETS)


def fold_spell_blocks(lines):
    """(lines to keep, {spell name: what it does}).

    The Dofus 3 archive writes an item's special spell as its name on one line
    and the rules under it:

        Droiture de Fallanster :
        - Lorsque le porteur termine son tour en ligne de vue d'un ennemi, ...

    which the reader meets as two lines of prose. Fold the rules into the name
    so the page can print the name and keep the rest for a tooltip. Anything
    that is not under a heading is left exactly as it was.
    """
    kept = []
    tooltips = {}
    heading = None
    body = []

    def close():
        if heading is None:
            return
        name = clean_line(heading).rstrip(':').strip()
        if body and name:
            kept.append(name)
            tooltips[name] = ' '.join(body)
        else:
            kept.append(heading)

    for line in lines or []:
        if _is_head(line):
            close()
            heading, body = line, []
        elif heading is not None:
            text = clean_line(line)
            if text:
                body.append(text)
        else:
            kept.append(line)
    close()
    return kept, tooltips
