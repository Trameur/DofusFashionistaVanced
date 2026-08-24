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

import logging
import pickle
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language
from django.views.decorators.http import require_POST
import json

from chardata.aspect_parser import parse_aspects
from chardata.lock_forbid import (remove_invalid_inclusions, get_default_exclusions,
    set_exclusions_list_and_check_inclusions)
from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.anon_projects import (forget_anon_char, get_anon_char_id,
                                    get_anon_char_ids, remember_anon_char)
from chardata.models import Char, CharBaseStats
from chardata.options import set_options
from chardata.smart_build import (get_char_aspects, set_char_aspects, ALL_ASPECTS,
                                  inert_aspects,
                                  ASPECT_TO_NAME)
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from chardata.util import (on_off_to_bool, set_response, safe_int, get_char_or_raise,
                           TESTER_USERS, HttpResponseText,
                           remove_cache_for_char, version_reverse)
from chardata.version_compat import (filter_classes_for_version,
                                     class_exists_in_version)

logger = logging.getLogger(__name__)
from fashionistapulp.dofus_constants import (STATS_NAMES, CHARACTER_CLASSES,
                                             max_scroll_for_version)
from chardata.themes import get_questionmark_URL


MAXIMUM_NUMBER_OF_PROJECTS = 500

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
        game_version = getattr(request, 'game_version', 'dofus3')
        chars = Char.objects.filter(owner=request.user, game_version=game_version)
        chars = chars.exclude(deleted=True)
        if len(chars) >= MAXIMUM_NUMBER_OF_PROJECTS and request.user.email not in TESTER_USERS:
            can_create = False
            too_many_projects_problem = True
    
    game_version = getattr(request, 'game_version', 'dofus3')
    classes = filter_classes_for_version(_get_class_to_name().keys(), game_version)

    # Un objet apporte depuis sa fiche d'encyclopedie, pour que le bouton
    # "chercher un set autour de cet objet" fasse ce qu'il dit au lieu d'ouvrir
    # un projet vide. Valide ici contre le catalogue : ce qui arrive ensuite
    # dans create_project vient d'un formulaire, donc du lecteur.
    lock_item = _wanted_item(request, game_version)

    return set_response(request,
                        'chardata/projdetails.html',
                        {'classes': sorted(classes),
                         'lock_item': lock_item,
                         'free_versions': _free_versions_for_anon(request),
                         'class_to_name': _get_class_to_name(),
                         'can_create': can_create,
                         'login_problem': login_problem,
                         'too_many_projects_problem': too_many_projects_problem,
                         'state': json.dumps(_get_state_from_char(char)),
                         'char_id': char_id,
                         'aspect_to_name': _get_json_aspect_to_name(),
                         'inert_aspects': json.dumps(inert_aspects(game_version)),
                         'is_new_char_json': json.dumps(is_new_char),
                         'questionmark': json.dumps(get_questionmark_URL(request)),
                         'is_new_char': is_new_char},
                        char)


def _free_versions_for_anon(request):
    """The versions a signed-out visitor can still start a project on."""
    if request.user is None or not request.user.is_anonymous:
        return []
    taken = set(get_anon_char_ids(request))
    free = []
    for slug, label in ACTIVE_GAME_VERSIONS:
        if slug in taken:
            continue
        free.append({'label': label,
                     'url': '/setup/' if slug == 'dofus3' else '/%s/setup/' % slug})
    return free


def is_anon_cant_create(request):
    # One project per version.
    if not request.user.is_anonymous:
        return False
    game_version = getattr(request, 'game_version', 'dofus3')
    return get_anon_char_id(request, game_version) is not None

def has_too_many_projects(request):
    too_many_projects_problem = False
    if (request.user is not None
            and not request.user.is_anonymous):
        game_version = getattr(request, 'game_version', 'dofus3')
        chars = Char.objects.filter(owner=request.user, game_version=game_version)
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

    return JsonResponse(_get_state_from_char(char))

def _wanted_item_from_post(request, game_version):
    """Same check as _wanted_item, on the field the form carries back."""
    brut = (request.POST.get('lock_item') or '').strip()
    if not brut:
        return None
    try:
        ankama_id = int(brut)
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        from fashionistapulp.structure import get_structure
        item = get_structure(game_version).get_item_by_ankama_id(ankama_id)
    except Exception:
        return None
    return ankama_id if item is not None else None


def _wanted_item(request, game_version):
    """The Ankama id of an item the reader asked to build around, or None.

    Checked against the catalogue rather than trusted: it arrives in a query
    string, and it is about to decide what gets locked onto a character.
    """
    brut = (request.GET.get('item') or '').strip()
    if not brut:
        return None
    try:
        ankama_id = int(brut)
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        from fashionistapulp.structure import get_structure
        item = get_structure(game_version).get_item_by_ankama_id(ankama_id)
    except Exception:
        return None
    return ankama_id if item is not None else None


def create_project(request):
    state = _get_state_from_post(request)

    char = Char()
    if not request.user.is_anonymous:
        char.owner = request.user
    char.minimum_stats = pickle.dumps({})
    char.stats_weight = pickle.dumps({})
    char.options = pickle.dumps({})
    char.link_shared = False
    char.game_version = getattr(request, 'game_version', 'dofus3')

    _save_state_to_char(state, char)
    
    
    set_char_aspects(char, state['char_build_aspects_set'], True, state['where_to_go'] == 'wizard')
    set_exclusions_list_and_check_inclusions(char, get_default_exclusions(char))
    set_options(char, {'ap_exo': char.level >= 200,
                       'mp_exo': char.level >= 200,
                       'turq_dofus': char.level >= 199,
                       'dragoturkey': True,
                       'rhineetle': True,
                       'seemyool': True,
                       'prysmaradite': char.level >= 200})

    char.save()

    full_scroll = max_scroll_for_version(char.game_version)
    for element_name, _ in STATS_NAMES:
        basestats = CharBaseStats()
        basestats.char = char
        basestats.stat = element_name
        basestats.scrolled_value = full_scroll
        basestats.total_value = full_scroll
        basestats.save()
    
    if request.user.is_anonymous:
        remember_anon_char(request, char)

    # L'objet vient d'une fiche d'encyclopedie. apply_ankama_ids refuse de
    # lui-meme un identifiant inconnu ou un objet au-dessus du niveau du
    # personnage, et remplace le set plutot que de s'ajouter dessous.
    voulu = _wanted_item_from_post(request, char.game_version)
    if voulu is not None:
        try:
            from fashionistapulp.structure import get_structure
            from chardata.build_import import apply_ankama_ids
            apply_ankama_ids(char, get_structure(char.game_version), [voulu])
        except Exception:
            # Un projet qui se cree vaut mieux qu'une erreur : le lecteur
            # verrouillera l'objet lui-meme si cela a echoue.
            pass
    
    if state['where_to_go'] == 'wizard':
        return HttpResponseRedirect(version_reverse(request, 'wizard', char.id))
    else:
        return HttpResponseRedirect(version_reverse(request, 'solution', char.id, True))

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
            # Clamped like the sibling path in coaching_view.create_build:
        # the value goes straight onto an IntegerField.
        'char_level': max(1, min(safe_int(request.POST.get('level', 200),
                                          200), 230)),
            'char_class': request.POST.get('class', 'NoName'),
            'char_build_aspects_set': aspects_set,
            'where_to_go': where_to_go}

def _save_state_to_char(state, char):
    char.name = state['proj_name']
    char.char_name = state['char_name']
    char.level = state['char_level']
    requested_class = state['char_class']
    char_version = getattr(char, 'game_version', None) or 'dofus3'
    if (requested_class in CHARACTER_CLASSES
            and class_exists_in_version(requested_class, char_version)):
        char.char_class = requested_class
    else:
        available = filter_classes_for_version(CHARACTER_CLASSES, char_version)
        char.char_class = available[0] if available else CHARACTER_CLASSES[0]

def _get_aspect_checklist(aspect_list):
    aspect_checklist = {aspect: aspect in aspect_list for aspect in ALL_ASPECTS}
    return aspect_checklist

@require_POST
def understand_build_post(request):
    build_line = request.POST.get('build_line', '')
    aspects = parse_aspects(build_line)
    
    return JsonResponse(_get_aspect_checklist(aspects))

@require_POST
def save_project_to_user(request, char_id=None):
    if request.user is None or request.user.is_anonymous:
        return HttpResponseText('ok')
    # A signed-out visitor holds one project per version; signing in claims them all.
    char_ids = [char_id] if char_id else list(get_anon_char_ids(request).values())
    for pk in char_ids:
        char = get_object_or_404(Char, pk=pk)
        chars = Char.objects.filter(owner=request.user,
                                    game_version=char.game_version)
        chars = chars.exclude(deleted=True)
        if len(chars) < MAXIMUM_NUMBER_OF_PROJECTS or request.user.email in TESTER_USERS:
            char.owner = request.user
            logger.debug('saving char %s to user %s', pk, request.user)
            char.save()
    forget_anon_char(request)
    return HttpResponseText('ok')
