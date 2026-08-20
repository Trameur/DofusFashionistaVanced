# -*- coding: utf-8 -*-

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

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
import json

from chardata.anon_projects import forget_anon_char, remember_anon_char
from chardata.create_project_view import MAXIMUM_NUMBER_OF_PROJECTS
from chardata.encoded_char_id import decode_char_id
from chardata.models import CharBaseStats, Char
from chardata.util import get_char_or_raise, TESTER_USERS, HttpResponseText, version_reverse


@require_POST
def delete_projects(request):
    projects_json = request.POST.get('projects', None)
    if projects_json is None:
        return HttpResponseText('error')
    try:
        projects = json.loads(projects_json)
    except (ValueError, TypeError):
        return HttpResponseText('error')
    for proj_id in projects:
        char = get_char_or_raise(request, proj_id) 
        char.deleted = True
        char.save()
        forget_anon_char(request, char.pk)
    return HttpResponseText('ok')
        
@require_POST
def duplicate_project(request):
    if request.user is None or request.user.is_anonymous:
        return HttpResponseText('error')

    project_id_json = request.POST.get('project_id', None)
    if project_id_json is None:
        return HttpResponseText('error')
    try:
        proj_id_to_copy = json.loads(project_id_json)
    except (ValueError, TypeError):
        return HttpResponseText('error')
    # get_char_or_raise is what every other route on someone's own build uses.
    get_char_or_raise(request, proj_id_to_copy)
    worked = _unchecked_duplicate_project(request, proj_id_to_copy)
    if worked:
        return HttpResponseText('ok')
    else:
        return HttpResponseText('too_many')

def duplicate_my_project(request, char_id):
    if request.user is None or request.user.is_anonymous:
        raise PermissionDenied

    # "my" was the only thing saying so: the id came straight off the URL and
    # nothing checked the owner. A stranger's build is duplicate_someones_
    # project's business, and only when it is shared by link.
    get_char_or_raise(request, char_id)
    worked = _unchecked_duplicate_project(request, char_id)
    if worked:
        return HttpResponseRedirect(version_reverse(request, 'load_projects'))
    else:
        return HttpResponseRedirect(version_reverse(request, 'load_projects_error',
                                                    'too_many'))

def duplicate_someones_project(request, encoded_char_id):
    char_id = decode_char_id(encoded_char_id)
    if char_id is None:
        raise PermissionDenied

    char = get_object_or_404(Char, pk=char_id)
    if not char.link_shared:
        raise PermissionDenied

    worked = _unchecked_duplicate_project(request, char_id)
    if worked:
        return HttpResponseRedirect(version_reverse(request, 'load_projects'))
    else:
        return HttpResponseRedirect(version_reverse(request, 'load_projects_error',
                                                    'too_many'))

def _unchecked_duplicate_project(request, proj_id_to_copy):
    signed_out = (request.user is None or request.user.is_anonymous)
    
    char_to_copy = get_object_or_404(Char, pk=proj_id_to_copy)
    if not signed_out:
        # The project cap is per game version.
        chars = Char.objects.filter(owner=request.user,
                                    game_version=char_to_copy.game_version)
        chars = chars.exclude(deleted=True)
        if len(chars) >= MAXIMUM_NUMBER_OF_PROJECTS and request.user.email not in TESTER_USERS:
            return False
    
    # Refetched: the copy is made by clearing the pk of this instance.
    char_to_duplicate = get_object_or_404(Char, pk=proj_id_to_copy)
    new_char = char_to_duplicate;
    new_char.owner = None if signed_out else request.user
    new_char.pk = None;
    suffix = ' copy'
    name_limit = Char._meta.get_field('name').max_length
    new_char.name = char_to_duplicate.name[:name_limit - len(suffix)] + suffix
    new_char.link_shared = False
    new_char.save()
    
    stats = CharBaseStats.objects.filter(char_id__exact=proj_id_to_copy)
    if len(stats) > 0:
        for stat in stats:
            new_stat = stat;
            new_stat.pk = None;
            new_stat.char = new_char;
            new_stat.save()
    
    if signed_out:
        remember_anon_char(request, new_char)
    
    return True
