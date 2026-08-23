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
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language

from chardata.model_wrappers import WrappedChar
from chardata.anon_projects import get_anon_char_id
from chardata.models import Char
from chardata.solution import get_solution
from chardata.util import set_response, version_reverse
from chardata.themes import get_needle_URL


def load_projects(request, char_id=0):
    return load_projects_error(request, error=None)

def load_projects_error(request, error):
    """The signed-in visitor's own projects.

    Anonymous visitors see an empty list, so there is nothing here to index --
    yet it was submitted to the sitemap and drew 3795 impressions for 4 clicks.
    noindex rather than robots.txt: the page is already in the index, and a
    disallow would stop Google ever reading the instruction to drop it.
    """
    game_version = getattr(request, 'game_version', 'dofus3')
    chars = []
    if request.user is not None and not request.user.is_anonymous:
        chars = Char.objects.filter(owner=request.user, game_version=game_version)
        chars = chars.exclude(deleted=True)
    has_projects = False
    if len(chars) > 0:
        has_projects = True
    anon_char_id = (get_anon_char_id(request, game_version)
                    if request.user.is_anonymous else None)
    if anon_char_id is not None:
        char = get_object_or_404(Char, pk=anon_char_id)
        chars.append(char)
        has_projects = True

    return set_response(request, 
                        'chardata/load_projects.html',
                        {'chars': [WrappedChar(char) for char in chars],
                         'char_id': 0,
                         'noindex': True,
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
    if request.user.is_anonymous:
        if get_anon_char_id(request, game_version) is not None:
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
    # A 404 means url resolution failed, so the middleware hook that restores
    # the reader's language never ran -- it only fires once a url has matched.
    # Without this the error page is the one page on the site that ignores the
    # language the visitor asked for.
    from chardata.url_language import negotiate_language_for_unmatched_path
    negotiate_language_for_unmatched_path(request)

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
    # settings.SUPPORT_LINKS is a list of {'label', 'url'}.
    support_links = getattr(settings, 'SUPPORT_LINKS', []) or []
    return set_response(request,
                        'chardata/support.html',
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'support_links': support_links})


def donate(request, index='0'):
    """Counts the click, then hands the reader over to the donation page.

    The Ko-fi button has always been there and has always been invisible: a
    third-party widget draws it, so the site never learned whether anyone even
    reaches for it. That number is the one thing worth knowing here -- with
    3 000 monthly readers and one donation received so far, the share who would
    give is the variable that decides whether any of this deserves more work.

    The destination comes from settings, never from the query string. Taking a
    url from a visitor would make this an open redirect: a link that looks like
    it goes to this site and lands anywhere, which is exactly what phishing
    wants and what search engines punish.

    Counting is wrapped: a statistics table that will not write must never cost
    a donation.
    """
    links = getattr(settings, 'SUPPORT_LINKS', []) or []
    try:
        target = links[int(index)]['url']
    except (IndexError, ValueError, KeyError, TypeError):
        raise Http404

    try:
        from django.db.models import F
        from django.utils import timezone as _tz
        from django.utils import translation as _tr
        from chardata.models import SupportClick
        key = {'day': _tz.localdate(), 'language': (_tr.get_language() or '')[:10]}
        if not SupportClick.objects.filter(**key).update(count=F('count') + 1):
            SupportClick.objects.get_or_create(defaults={'count': 1}, **key)
    except Exception:
        pass

    return HttpResponseRedirect(target)


def set_language_and_remember(request):
    """Django's set_language, plus the choice stored on the user's profile."""
    from django.utils.translation import check_for_language
    from django.views.i18n import set_language as django_set_language
    response = django_set_language(request)
    if request.method == 'POST' and request.user.is_authenticated:
        lang = request.POST.get('language')
        if lang and check_for_language(lang):
            from chardata.models import UserAlias
            alias, _created = UserAlias.objects.get_or_create(user=request.user)
            if alias.language != lang:
                alias.language = lang
                alias.save(update_fields=['language'])
    return response
