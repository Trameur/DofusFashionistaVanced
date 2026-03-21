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

from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.db.models import Count, Case, When, IntegerField
from django.core.cache import cache
import json

from chardata.encoded_char_id import encode_char_id
from chardata.fashion_action import fashion, get_options
from chardata.lock_forbid import (set_excluded,
                                  set_item_included,
    get_all_inclusions_en_names, get_all_exclusions_en_names)
from chardata.models import Char, BuildVote, BuildView
import chardata.smart_build
from chardata.solution import get_solution, set_minimal_solution
from django.utils import timezone
from datetime import timedelta
from chardata.solution_result import SolutionResult
from chardata.util import set_response, get_char_or_raise, get_alias, get_char_encoded_or_raise, \
    HttpResponseText, get_base_stats_by_attr
from fashionistapulp.dofus_constants import SLOTS

from static_s3.templatetags.static_s3 import static
from fashionistapulp.structure import get_structure
from fashionistapulp.modelresult import ModelResultMinimal
from chardata.themes import get_ajax_loader_URL, get_external_image_URL
from fashionistapulp.translation import get_supported_language


SHARED_SOLUTION_CACHE_TIMEOUT = 6 * 60 * 60


def _get_shared_solution_cache_key(char):
    modified_marker = 'none'
    if char.modified_time is not None:
        modified_marker = str(int(char.modified_time.timestamp() * 1000000))
    return 'shared-solution-%s-%s-%s' % (char.pk,
                                         modified_marker,
                                         get_supported_language())


def _get_shared_solution_params(char):
    cache_key = _get_shared_solution_cache_key(char)
    cached_params = cache.get(cache_key)
    if cached_params is not None:
        return cached_params

    inclusions = get_all_inclusions_en_names(char)
    exclusions = get_all_exclusions_en_names(char)
    solution = get_solution(char)
    solution_result = SolutionResult(solution,
                                     inclusions,
                                     exclusions)
    cached_params = solution_result.get_params()
    cache.set(cache_key, cached_params, SHARED_SOLUTION_CACHE_TIMEOUT)
    return cached_params


def _get_live_vote_data(request, char):
    vote_data = {
        'like_count': 0,
        'favorite_count': 0,
        'user_liked': False,
        'user_favorited': False,
    }

    if not char.link_shared:
        return vote_data

    try:
        vote_counts = BuildVote.objects.filter(build=char).values('vote_type').annotate(count=Count('id'))
        for vote_count in vote_counts:
            if vote_count['vote_type'] == 'like':
                vote_data['like_count'] = vote_count['count']
            elif vote_count['vote_type'] == 'favorite':
                vote_data['favorite_count'] = vote_count['count']

        if request.user.is_authenticated:
            user_votes = set(BuildVote.objects.filter(user=request.user,
                                                      build=char).values_list('vote_type', flat=True))
            vote_data['user_liked'] = 'like' in user_votes
            vote_data['user_favorited'] = 'favorite' in user_votes
    except Exception as e:
        print(f"Error fetching vote data: {e}")

    return vote_data


def solution(request, char_id, empty=False):
    char = get_char_or_raise(request, char_id)
    solution = get_solution(char)
    if solution is None:
        if not empty:
            return fashion(request, char_id)
        else:
            input_ = {}
            input_['options'] = get_options(request, char_id)
            input_['base_stats_by_attr'] = get_base_stats_by_attr(request, char_id)
            input_['char_level'] = char.level
            set_minimal_solution(char, ModelResultMinimal.generate_empty_solution(input_))
    return _solution(request, char_id, False, char=char)
    
def _solution(request, char_id, is_guest, encoded_char_id=None, char=None):
    if char is None:
        char = get_object_or_404(Char, pk=char_id)

    if is_guest and char.link_shared:
        solution_params = _get_shared_solution_params(char)
    else:
        inclusions = get_all_inclusions_en_names(char)
        exclusions = get_all_exclusions_en_names(char)
        solution = get_solution(char)
        solution_result = SolutionResult(solution,
                                         inclusions,
                                         exclusions)
        solution_params = solution_result.get_params()

    vote_data = _get_live_vote_data(request, char)
    
    params = {'char_id': char_id,
              'lock_item': static('chardata/lock-icon.png'),
              'switch_item': static('chardata/1412645636_Left-right.png'),
              'delete_item': static('chardata/delete-icon.png'),
              'add_item': static('chardata/add-icon.png'),
              'ajax_loader': json.dumps(get_ajax_loader_URL(request)),
              'link_external_image': json.dumps(get_external_image_URL(request)),
              'is_guest': is_guest,
              'is_guest_json': json.dumps(is_guest),
              'encoded_char_id': encoded_char_id,
              'link_shared': char.link_shared,
              'owner_alias': get_alias(char.owner),
              'is_dueler': chardata.smart_build.char_has_aspect(char, 'duel')}
              
    if char.link_shared:
        params['initial_link'] = generate_link(char)

    params.update(vote_data)
    params.update(solution_params)

    response = set_response(request, 
                            'chardata/solution.html',
                            params, 
                            char)
    return response


def get_sharing_link(request, char_id):
    char = get_char_or_raise(request, char_id)

    char.link_shared = True
    char.save()
    
    return HttpResponseText(generate_link(char))

def hide_sharing_link(request, char_id):
    char = get_char_or_raise(request, char_id)

    char.link_shared = False
    char.save()
        
    return HttpResponseText('hid')

def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def solution_linked(request, char_name, encoded_char_id):
    char = get_char_encoded_or_raise(encoded_char_id)
    
    # Increment view count only once per IP per 24 hours
    try:
        ip_address = get_client_ip(request)
        if ip_address:  # Only track if we can get an IP
            twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
            
            # Check if this IP has viewed this build in the last 24 hours
            recent_view = BuildView.objects.filter(
                build=char,
                ip_address=ip_address,
                viewed_at__gte=twenty_four_hours_ago
            ).exists()
            
            if not recent_view:
                # Record the view
                BuildView.objects.create(build=char, ip_address=ip_address)
                # Increment counter
                char.view_count += 1
                char.save()
    except Exception as e:
        # If view tracking fails, log it but don't break the page
        print(f"View tracking error: {e}")
    
    return _solution(request, char.pk, True, encoded_char_id, char=char)

def generate_link(char):
    encoded_id = encode_char_id(int(char.id))
    char_name = char.char_name or 'shared'
    return ('https://fashionistavanced.com'
            + reverse('solution_linked',
                      args=(char_name, encoded_id)))

def set_item_locked(request, char_id):
    char = get_char_or_raise(request, char_id)
        
    slot = request.POST.get('slot', None)
    item_name = request.POST.get('equip', None)
    locked = request.POST.get('locked', None)
    
    
    assert slot in SLOTS
    
    structure = get_structure()
    item = structure.get_item_by_name(item_name)
    if item is None:
        or_item = structure.get_or_item_by_name(item_name)
        item_id = or_item[0].id
    else:
        item_id = structure.get_item_by_name(item_name).id
    if locked == 'true':
        set_item_included(char, item_id, slot, True)
    elif locked == 'false':
        set_item_included(char, item_id, slot, False)
    
    return HttpResponseText('char_id %s, slot %s, equip %s, locked %s'
            % (char_id, slot, item_name, str(locked)))

def set_item_forbidden(request, char_id):
    char = get_char_or_raise(request, char_id)
        
    slot = request.POST.get('slot', None)
    item_name = request.POST.get('equip', None)
    forbidden = request.POST.get('forbidden', None)
    
    structure = get_structure()
    item = structure.get_item_by_name(item_name)
    if item is None:
        or_item = structure.get_or_item_by_name(item_name)
        item_id = or_item[0].id
    else:
        item_id = structure.get_item_by_name(item_name).id
    
    if forbidden == 'true':
        set_excluded(char, item_id, True)
    elif forbidden == 'false':
        set_excluded(char, item_id, False)

    return HttpResponseText('char_id %s, slot %s, equip %s, forbidden %s'
            % (char_id, slot, item_name, str(forbidden)))
