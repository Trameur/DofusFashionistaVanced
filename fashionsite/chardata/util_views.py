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

from django.shortcuts import render

from chardata.util import set_response


def changelog_content(request):
    """Changelog entries, fetched when the modal is first opened. Kept out of
    every page: it was ~23KB of markup on each one."""
    return render(request, 'chardata/changelog_content.html')


def error(request, error, error_link, char_id, char):
    return set_response(request, 
                        'chardata/error.html', 
                        {'char_id': char_id,
                         'error': error,
                         'error_link' : error_link},
                        char)    
