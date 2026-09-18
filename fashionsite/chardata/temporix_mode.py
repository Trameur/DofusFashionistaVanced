# Copyright (C) 2026 The Dofus Fashionista
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

"""Whether a build is played under the Dofus Touch TemporiX rules.

The rules themselves live in fashionistapulp/temporix.py. This only reads the
switch a build carries in its options, for the pages that need to know it:
the minimums, the spell panel, the solution and the gallery.
"""
from chardata.char_blobs import read_char_blob
from fashionistapulp import temporix


def char_uses_temporix(char):
    """The switch as the build carries it now: what its next solve will use."""
    if char is None or not getattr(char, 'options', None):
        return False
    options = read_char_blob(char.options, {}, 'options', char)
    return temporix.is_on(options, getattr(char, 'game_version', 'dofus3'))


def solution_uses_temporix(solution, game_version):
    """Whether a stored solution was solved under the TemporiX rules.

    Not the same question as the switch: a build switched without being solved
    again still shows the values of its last solve, and every page that shows
    those values has to read them the same way.
    """
    options = (getattr(solution, 'input', None) or {}).get('options')
    return temporix.is_on(options, game_version)
