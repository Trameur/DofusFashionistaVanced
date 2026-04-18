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

import pickle
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language
from static_s3.templatetags.static_s3 import static
import json

from chardata.aspect_parser import parse_aspects
from chardata.lock_forbid import (remove_invalid_inclusions, get_default_exclusions,
    set_exclusions_list_by_name)
from chardata.models import Char, CharBaseStats
from chardata.options import set_options
from chardata.smart_build import (get_char_aspects, set_char_aspects, ALL_ASPECTS,
                                  ASPECT_TO_NAME)
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from chardata.util import (on_off_to_bool, set_response, safe_int, get_char_or_raise,
                           TESTER_USERS, HttpResponseText, HttpResponseJson,
    get_theme, remove_cache_for_char)
from fashionistapulp.dofus_constants import STATS_NAMES, CHARACTER_CLASSES
from chardata.themes import get_questionmark_URL


MAXIMUM_NUMBER_OF_PROJECTS = 100

def setup(request, char_id=0):
    too_many_projects_problem = False
    is_new_char = (char_id == 0)
    if is_new_char:
        char = Char()
        char.name = ''
        char.level = 200
        char.char_name = ''
        char.char_class = ''
        char.char_build = ''
    else:
        char = get_char_or_raise(request, char_id)
    if is_anon_cant_create(request) and is_new_char:
        can_create = False
        login_problem = True
    else:
        can_create = True
        login_problem = False
    if (is_new_char
        and request.user is not None 
        and not request.user.is_anonymous
        and can_create):
        chars = Char.objects.filter(owner=request.user)
        chars = chars.exclude(deleted=True)
        if len(chars) >= MAXIMUM_NUMBER_OF_PROJECTS and request.user.email not in TESTER_USERS:
            can_create = False
            too_many_projects_problem = True
    
    classes = list(_get_class_to_name().keys())
    
    return set_response(request,
                        'chardata/projdetails.html',
                        {'classes': sorted(classes),
                         'class_to_name': _get_class_to_name(),
                         'can_create': can_create,
                         'login_problem': login_problem,
                         'too_many_projects_problem': too_many_projects_problem,
                         'state': json.dumps(_get_state_from_char(char)),
                         'char_id': char_id,
                         'aspect_to_name': _get_json_aspect_to_name(),
                         'is_new_char_json': json.dumps(is_new_char),
                         'questionmark': json.dumps(get_questionmark_URL(request)),
                         'is_new_char': is_new_char},
                        char)

def is_anon_cant_create(request):
    return request.user.is_anonymous and 'char_id' in request.session

def has_too_many_projects(request):
    too_many_projects_problem = False
    if (request.user is not None 
        and not request.user.is_anonymous):
        chars = Char.objects.filter(owner=request.user)
        chars = chars.exclude(deleted=True)
        if len(chars) >= MAXIMUM_NUMBER_OF_PROJECTS and request.user.email not in TESTER_USERS:
            too_many_projects_problem = True
    return too_many_projects_problem
            
_memoized_aspect_to_name = {}
def _get_json_aspect_to_name():
    language = get_language()
    if language not in _memoized_aspect_to_name:
        _memoized_aspect_to_name[language] = \
            json.dumps({k: str(v) for k, v in ASPECT_TO_NAME.items()})
    return _memoized_aspect_to_name[language]

_memoized_class_to_name = {}
def _get_class_to_name():
    language = get_language()
    if language not in _memoized_class_to_name:
        _memoized_class_to_name[language] = \
            {str(v): k for k, v in LOCALIZED_CHARACTER_CLASSES.items()}
    return _memoized_class_to_name[language]

def save_project(request, char_id=0):
    char_id = int(char_id)
    char = get_char_or_raise(request, char_id)
    
    state = _get_state_from_post(request)

    remove_invalid_inclusions(char, state['char_level'])

    _save_state_to_char(state, char)

    # TODO: Make clear we are resetting weights and mins.
    set_char_aspects(char, state['char_build_aspects_set'],
                     request.POST.get('reapply') == 'reapply')

    char.save()
    if char_id > 0:
        remove_cache_for_char(char_id)

    return HttpResponseJson(json.dumps(_get_state_from_char(char)))

def create_project(request):
    state = _get_state_from_post(request)

    char = Char()
    if not request.user.is_anonymous:
        char.owner = request.user
    char.minimum_stats = pickle.dumps({})
    char.stats_weight = pickle.dumps({})
    char.options = pickle.dumps({})
    char.link_shared = False

    _save_state_to_char(state, char)
    
    
    set_char_aspects(char, state['char_build_aspects_set'], True, state['where_to_go'] == 'wizard')
    set_exclusions_list_by_name(char, get_default_exclusions(char))
    set_options(char, {'ap_exo': char.level >= 200,
                       'mp_exo': char.level >= 200,
                       'turq_dofus': char.level >= 199,
                       'dragoturkey': True,
                       'rhineetle': True,
                       'seemyool': True,
                       'prysmaradite': char.level >= 200})

    char.save()

    for element_name, _ in STATS_NAMES:
        basestats = CharBaseStats()
        basestats.char = char
        basestats.stat = element_name
        basestats.scrolled_value = 100
        basestats.total_value = 100
        basestats.save()
    
    if request.user.is_anonymous:
        request.session['char_id'] = char.pk
    
    if state['where_to_go'] == 'wizard':
        return HttpResponseRedirect(reverse('wizard',
                                            args=(char.id,)))
    else:
        return HttpResponseRedirect(reverse('solution',
                                            args=(char.id, True,)))

# TODO: This state should be a class.
def _get_state_from_char(char):
    aspect_list = get_char_aspects(char)
    aspects_checklist = _get_aspect_checklist(aspect_list)
    return {'proj_name': char.name,
            'char_name': char.char_name,
            'char_level': char.level,
            'char_class': char.char_class,
            'char_build_aspects': aspects_checklist}

def _get_state_from_post(request):
    
    where_to_go = 'solution' if request.POST.get('byhand', None) else 'wizard'
    aspects_set = set()
    for aspect in ALL_ASPECTS:
        if on_off_to_bool(request.POST.get('check_%s' % aspect, 'off')):
            aspects_set.add(aspect)
    return {'proj_name': request.POST.get('project', 'NoName'),
            'char_name': request.POST.get('charname', 'NoName'),
            'char_level': safe_int(request.POST.get('level', 200), 200),
            'char_class': request.POST.get('class', 'NoName'),
            'char_build_aspects_set': aspects_set,
            'where_to_go': where_to_go}

def _save_state_to_char(state, char):
    char.name = state['proj_name']
    char.char_name = state['char_name']
    char.level = state['char_level']
    char.char_class = (state['char_class']
                       if state['char_class'] in CHARACTER_CLASSES
                       else CHARACTER_CLASSES[0])

def _get_aspect_checklist(aspect_list):
    aspect_checklist = {aspect: aspect in aspect_list for aspect in ALL_ASPECTS}
    return aspect_checklist

def understand_build_post(request):
    build_line = request.POST.get('build_line', '')
    aspects = parse_aspects(build_line)
    
    return HttpResponseJson(json.dumps(_get_aspect_checklist(aspects)))

def save_project_to_user(request, char_id=None):
    char_id = char_id or request.session.get('char_id')
    if char_id and not request.user.is_anonymous:
        char = get_object_or_404(Char, pk=char_id)
        if request.user is not None and not request.user.is_anonymous:
            chars = Char.objects.filter(owner=request.user)
            chars = chars.exclude(deleted=True)
            if len(chars) < MAXIMUM_NUMBER_OF_PROJECTS or request.user.email in TESTER_USERS:
                char.owner = request.user
                print('saving char %s to user %s' % (char_id, request.user))
                char.save()
        if 'char_id' in request.session:
            del request.session['char_id']
    return HttpResponseText('ok')
