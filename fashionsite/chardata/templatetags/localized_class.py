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

"""The character class in the reader's own language.

Char.char_class stores the English name, and a template variable is never
translated on its way out, so a build banner read "Sacrier" to a Spanish player
while the label beside it read "Clase" and the page title already said
"Sacrogrito". Thirteen of the nineteen class names differ in Spanish, ten in
German, six in French and in Portuguese.

Only for text a reader sees: the data-build-cls attributes are matched against
the English name in JS and must keep it.
"""

from django import template

from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES

register = template.Library()


@register.filter
def localized_class(char_class):
    return LOCALIZED_CHARACTER_CLASSES.get(char_class, char_class)
