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

import unidecode

def normalize_name(s):
    if '(' in s and s.endswith(')'):
        return s.split('(')[0].strip()
    else:
        return s


def safe_icon_name(s):
    """Icon filenames must be materializable on every platform; strip the
    characters Windows forbids (e.g. the '?' in "Wand Else?")."""
    return ''.join(c for c in s if c not in '<>:"/\\|?*').strip()


def strip_accents(s):
    return unidecode.unidecode(s)