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

from django.conf import settings
from django.utils import translation


NON_EN_LANGUAGES = ['fr', 'pt', 'es', 'de']
LANGUAGES = ['en'] + NON_EN_LANGUAGES
SUPPORTED_LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']


def get_supported_language():
    if not settings.EXPERIMENTS['TRANSLATION']:
        return 'en'
    
    lang = translation.get_language()
    if lang not in SUPPORTED_LANGUAGES:
        lang = 'en'
    return lang
