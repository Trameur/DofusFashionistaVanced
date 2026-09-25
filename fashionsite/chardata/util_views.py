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

from functools import wraps

from django.conf import settings
from django.shortcuts import render
from django.utils import translation

from chardata.util import set_response


def in_requested_language(view):
    """Serve the view in the ?lang= language when it is one the site speaks."""
    codes = {code for code, _name in settings.LANGUAGES}

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        lang = request.GET.get('lang')
        if lang not in codes:
            return view(request, *args, **kwargs)
        with translation.override(lang):
            response = view(request, *args, **kwargs)
        response['Content-Language'] = lang
        return response
    return wrapped


@in_requested_language
def changelog_content(request):
    return render(request, 'chardata/changelog_content.html')


def error(request, error, error_link, char_id, char):
    return set_response(request, 
                        'chardata/error.html', 
                        {'char_id': char_id,
                         'error': error,
                         'error_link' : error_link},
                        char)    
