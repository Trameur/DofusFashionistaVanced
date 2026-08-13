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

"""Match an item line to the spell it names."""


class SpellTip(object):

    def __init__(self, spell, description):
        self.spell = spell
        self.description = description


def spell_tip_for(line, tooltips):
    """The spell this line is about, or None.

    Names overlap: Retro has both "Bond" and "Bond Felin", so the longest match
    wins.
    """
    if not line or not tooltips:
        return None
    text = str(line)
    best = None
    for spell in tooltips:
        if spell and spell in text:
            if best is None or len(spell) > len(best):
                best = spell
    if best is None:
        return None
    return SpellTip(best, tooltips[best])
