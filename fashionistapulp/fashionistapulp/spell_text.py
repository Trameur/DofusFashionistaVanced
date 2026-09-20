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

"""Fold an item's special spell block into its name and its description."""

import re

# Unity rich text for the element icons.
_SPRITE = re.compile(r'<sprite\s+name="[^"]*"\s*/?>')
_MARKUP = re.compile(r'<[^<>]{1,40}>')

_BULLETS = ('•', '▪', '●', '·')

# A heading is a name, not a sentence that happens to end in a colon.
_HEAD_LIMIT = 80


# Ankama's cross-reference with the name inside, {{spell,8395,1::Pourpre Profond}}: the client resolves it, the archive stores it raw
_TEMPLATE = re.compile(r'\{\{[^{}]*?::([^{}]*?)\}\}')


def resolve_templates(text):
    """The name the template carries, in place of the template itself."""
    return _TEMPLATE.sub(lambda match: match.group(1), text or '')


def clean_line(line):
    text = _MARKUP.sub('', _SPRITE.sub('', line or ''))
    text = resolve_templates(text).strip()
    while text[:1] in _BULLETS:
        text = text[1:].strip()
    return re.sub(r'\s{2,}', ' ', text)


def _is_head(line):
    text = clean_line(line)
    return (bool(text) and len(text) <= _HEAD_LIMIT and text.endswith(':')
            and line.strip()[:1] not in _BULLETS)


def fold_spell_blocks(lines):
    """(lines to keep, {spell name: what it does}); a special spell is its name on one line and its rules under it"""
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
            kept.append(resolve_templates(heading))

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
