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

import json

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language

from chardata.model_wrappers import WrappedChar
from chardata.models import Char
from chardata.solution import get_solution
from chardata.util import set_response, get_theme, version_reverse
from static_s3.templatetags.static_s3 import static
from chardata.themes import get_needle_URL


def load_projects(request, char_id=0):
    return load_projects_error(request, error=None)

def load_projects_error(request, error):
    game_version = getattr(request, 'game_version', 'dofus3')
    chars = []
    if request.user is not None and not request.user.is_anonymous:
        chars = Char.objects.filter(owner=request.user, game_version=game_version)
        chars = chars.exclude(deleted=True)
    has_projects = False
    if len(chars) > 0:
        has_projects = True
    if request.user.is_anonymous and 'char_id' in request.session:
        char = get_object_or_404(Char, pk=request.session['char_id'])
        if char.game_version == game_version:
            chars.append(char)
            has_projects = True

    return set_response(request, 
                        'chardata/load_projects.html',
                        {'chars': [WrappedChar(char) for char in chars],
                         'char_id': 0,
                         'has_projects': has_projects,
                         'compare_preselect': request.GET.get('compare') or '',
                         'needle': json.dumps(get_needle_URL(request)),
                         'error_msg': error})

def user_has_projects(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    chars = []
    if request.user is not None and not request.user.is_anonymous:
        chars = Char.objects.filter(owner=request.user, game_version=game_version)
        chars = chars.exclude(deleted=True)
    has_projects = False
    if len(chars) > 0:
        has_projects = True
    if request.user.is_anonymous and 'char_id' in request.session:
        char = get_object_or_404(Char, pk=request.session['char_id'])
        if char.game_version == game_version:
            has_projects = True
    return has_projects

def load_a_project(request, char_id):
    char = get_object_or_404(Char, pk=char_id)
    if get_solution(char) is not None:
        return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))
    return HttpResponseRedirect(version_reverse(request, 'wizard', char.id))
                                              
def infeasible(request, char_id=0):
    char = get_object_or_404(Char, pk=char_id)
    return set_response(request, 
                        'chardata/infeasible.html', 
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'mins_link': version_reverse(request, 'min_stats', char_id),
                         'weights_link': version_reverse(request, 'stats', char_id),
                         'lock_link': version_reverse(request, 'inclusions', char_id),
                         'exo_link': version_reverse(request, 'options', char_id)},
                        char)
                                                         
def forbidden(request, exception=None, char_id=0):
    response = set_response(request, 
                        'chardata/403.html', 
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'noindex': True})
    response.status_code = 403
    return response
                         
def not_found(request, exception=None, char_id=0):
    response = set_response(request, 
                        'chardata/404.html', 
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'noindex': True})
    response.status_code = 404
    return response
                                                        
def app_error(request, char_id=0):
    response = set_response(request, 
                        'chardata/500.html', 
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'noindex': True})
    response.status_code = 500
    return response
                                                        
def contact(request, char_id=0):
    return set_response(request, 
                        'chardata/contact.html', 
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id})

def about(request, char_id=0):
    language_code = (get_language() or settings.LANGUAGE_CODE or 'en').split('-')[0]
    language_name = dict(settings.LANGUAGES).get(language_code, 'English')

    # Keep known translator credits and fall back to Trameur when missing.
    about_authors = {
        'fr': 'Mr-quifaitmal, Naturalglyphs, Edrolys, Praesugatus, Hyd-x, Bouzouw, Elbisiap et Trameur',
        'es': 'Nelson-Magno',
    }
    language_author = about_authors.get(language_code, '') or 'Trameur'

    return set_response(request, 
                        'chardata/about.html', 
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'site_version': settings.SITE_VERSION,
                         'about_language_name': language_name,
                         'about_language_author': language_author})

def license_page(request, char_id=0):
    return set_response(request, 
                        'chardata/license.html', 
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id})

def faq(request, char_id=0):
    return set_response(request,
                        'chardata/faq.html',
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id})

def privacy(request, char_id=0):
    return set_response(request,
                        'chardata/privacy.html',
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id})

def support(request, char_id=0):
    # Donation links are opt-in via settings.SUPPORT_LINKS = [{'label','url'}].
    # When none are configured the page still works, showing the free ways to help.
    support_links = getattr(settings, 'SUPPORT_LINKS', []) or []
    return set_response(request,
                        'chardata/support.html',
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'support_links': support_links})
