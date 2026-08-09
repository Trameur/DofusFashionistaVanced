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
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, NoReverseMatch
from django.utils.translation import get_language
import json
import logging
import random
import requests as http_requests


def version_reverse(request, url_name, *args, **kwargs):
    """Like reverse() but auto-prefixes with the current game version namespace."""
    game_version = getattr(request, 'game_version', 'dofus3')
    if game_version != 'dofus3':
        try:
            return reverse(f'{game_version}:{url_name}', args=args, kwargs=kwargs)
        except NoReverseMatch:
            pass
    return reverse(url_name, args=args, kwargs=kwargs)

def recaptcha_ok(request):
    secret = settings.GEN_CONFIGS.get('url_captcha_secret')
    answer = request.POST.get('g-recaptcha-response', '')
    try:
        r = http_requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={'secret': secret, 'response': answer},
            timeout=10,
        )
        r.raise_for_status()
        return bool(r.json().get('success'))
    except (http_requests.RequestException, ValueError) as e:
        logging.getLogger(__name__).warning('captcha verification failed: %s', e)
        return False

from chardata.encoded_char_id import decode_char_id
from chardata.model_wrappers import WrappedChar
from chardata.models import Char, UserAlias, CharBaseStats
from fashionistapulp.dofus_constants import STATS_NAMES, TYPE_NAMES
from fashionistapulp.structure import get_structure
from chardata.themes import get_css_for_theme, get_theme, check_theme,\
    get_css_static_for_theme, get_ajax_loader_URL, get_all_images_URLs
from fashionsite.settings import DEFAULT_THEME
import jsonpickle


ALLOWED_THEMES = {'auto', 'lighttheme', 'darktheme'}
ALLOWED_CURRENT_AUTO = {'lighttheme', 'darktheme'}


def _sanitize_cookie_choice(value, allowed_values, default_value):
    if value in allowed_values:
        return value
    return default_value


def get_base_stats_by_attr(request, char_id):
    char = get_char_or_raise(request, char_id)
    base_stats_by_attr = {}
    base_stats_by_attr['AP'] = 7 if char.level >= 100 else 6
    base_stats_by_attr['MP'] = 3
    base_stats_by_attr['Prospecting'] = 100
    base_stats_by_attr['Pods'] = 1000
    base_stats_by_attr['Summon'] = 1

    for element_name, _ in STATS_NAMES:
        basestats = CharBaseStats.objects.filter(char=char, stat=element_name)
        if len(basestats) == 0:
            base_stats_by_attr[element_name] = 0
        else:
            if char.allow_points_distribution:
                base_stats_by_attr[element_name] = basestats[0].scrolled_value
            else:
                base_stats_by_attr[element_name] = basestats[0].total_value
    return base_stats_by_attr

def get_stats(char):
    stats = {element_name: 0 for element_name, _ in STATS_NAMES}
    for bs in CharBaseStats.objects.filter(char=char):
        if bs.stat in stats:
            stats[bs.stat] = bs.total_value - bs.scrolled_value
    return stats

def get_scrolled_stats(char):
    stats = {element_name: 0 for element_name, _ in STATS_NAMES}
    for bs in CharBaseStats.objects.filter(char=char):
        if bs.stat in stats:
            stats[bs.stat] = bs.scrolled_value
    return stats

def safe_int(val, default=None):
    try:
        return int(val)
    except TypeError:
        return default
    except ValueError:
        return default
        
def safe_str(val, default=None):
    if val.isalpha:
        return val
    else:
        return default

def safe_float(val, default=None):
    try:
        return float(val)
    except TypeError:
        return default
    except ValueError:
        return default
     
def on_off_to_bool(val):
    return val == 'on'
    
def get_alias(user):
    aliases = []
    if user is not None and not user.is_anonymous:
        aliases = UserAlias.objects.filter(user=user)
    alias = []
    if len(aliases) > 0:
        alias = aliases[0]
        return alias.alias
    return None
    
def set_response(request, path, params, char=None):
    params['debug_mode'] = settings.DEBUG
    params['language'] = get_language()
    params['experiments'] = settings.EXPERIMENTS
    params['useralias'] = get_alias(request.user)
    if char:    
        params['char'] = char
        params['wrapped_char'] = WrappedChar(char)
    params['useraliasjson'] = json.dumps(params['useralias'])
    params['is_super_user'] = request_by_super_user(request)

    params['ajaxloader'] = json.dumps(get_ajax_loader_URL(request))
    params['themeimages'] = json.dumps(get_all_images_URLs(request))
    params['css_files'] = get_css_for_theme(get_theme(request), request)
    params['theme'] = get_theme(request)
    params['google_analytics_id'] = settings.GEN_CONFIGS['google_analytics_id']
    
    no_pic = True
    if 'pic' in request.COOKIES:    
        params['pic'] = request.COOKIES['pic']
        no_pic = False
    else:
        i = random.randint(1, 75)
        char_pic = "chardata/designs/%d.png" % i
        params['pic'] = char_pic
    response = render(request, path, params)
    if no_pic:
        response.set_cookie("pic", params['pic'], max_age=3600)
    check_theme(request, response)
    return response

TESTER_USERS = settings.GEN_CONFIGS['TESTER_USERS_EMAILS']
SUPER_USERS = settings.GEN_CONFIGS['SUPER_USERS_EMAILS']

def request_by_super_user(request):
    return (not request.user.is_anonymous and request.user.email in SUPER_USERS)

def char_belongs_to_user(request, char):
    if request.user.is_anonymous:
        from chardata.anon_projects import owns_anon_char
        if owns_anon_char(request, char.pk):
            return True
    if (not request_by_super_user(request) and
        (char.owner != request.user or char.deleted)):
        return False
    return True

def get_or_none(model, **kwargs):
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        return None

def get_char_or_raise(request, char_id):
    # The compare_sets route matches ".+", so crawlers hand this things like
    # "robots.txt"; the ORM raises ValueError on a non-numeric pk before
    # get_object_or_404 can turn it into a 404.
    try:
        char_id = int(char_id)
    except (TypeError, ValueError):
        raise Http404
    char = get_object_or_404(Char, pk=char_id)
    current_version = getattr(request, 'game_version', 'dofus3')
    if char.game_version != current_version:
        raise Http404
    if char_belongs_to_user(request, char):
        return char
    else:
        raise PermissionDenied

def get_char_encoded_or_raise(encoded_char_id):
    char_id = decode_char_id(encoded_char_id)
    if char_id is None:
        raise Http404('Could not decode char id: %s' % encoded_char_id)

    char = get_object_or_404(Char, pk=char_id)
    if not char.link_shared:
        raise PermissionDenied
    else:
        return char

def get_char_possibly_encoded_or_raise(request, char_id_possibly_encoded):
    if char_id_possibly_encoded.startswith('s'):
        encoded_char_id = char_id_possibly_encoded[1:]
        return get_char_encoded_or_raise(encoded_char_id)
    else:
        return get_char_or_raise(request, char_id_possibly_encoded)

# Returns (char_id, was_encoded) or (None, None) if encoding was wrong.
def get_char_id_possibly_encoded(char_id_possibly_encoded):
    if char_id_possibly_encoded.startswith('s'):
        encoded_char_id = char_id_possibly_encoded[1:]
        char_id = decode_char_id(encoded_char_id)
        if char_id is None:
            return None, None
        return char_id, True
    else:
        return int(char_id_possibly_encoded), False

class HttpResponseText(HttpResponse):
    def __init__(self, text, **kwargs):
        return HttpResponse.__init__(self, text, content_type='text/plain; charset=utf-8', **kwargs)

class HttpResponseJson(HttpResponse):
    def __init__(self, text, **kwargs):
        return HttpResponse.__init__(self, text, content_type='application/json', **kwargs)
    
def remove_cache_for_char(char_id):
    s = get_structure()
    for slot in TYPE_NAMES:
        item_type = s.get_type_id_by_name(slot)
        cache_key = ('%s-%s--true' % (char_id, item_type))
        cache.delete(cache_key)
        cache_key = ('%s-%s--false' % (char_id, item_type))
        cache.delete(cache_key)
        
def set_theme(request):
    theme = request.POST.get('theme', None)
    theme = _sanitize_cookie_choice(theme, ALLOWED_THEMES, DEFAULT_THEME)
    theme_files = get_css_static_for_theme(theme, request)
    theme_files_json = jsonpickle.encode(theme_files)
    response = HttpResponseJson(theme_files_json)
    max_age_theme = 365 * 24 * 60 * 60  #one year
    response.set_cookie("theme", theme, max_age=max_age_theme)
    return response

def set_current_auto(request):
    current = request.POST.get('current', None)
    current = _sanitize_cookie_choice(current, ALLOWED_CURRENT_AUTO, 'darktheme')
    response_string = jsonpickle.encode('abc')
    response = HttpResponseJson(response_string)
    max_age_current_auto = 12 * 60 * 60  #twelve hours
    response.set_cookie("current_auto", current, max_age=max_age_current_auto)
    return response
