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

from django.http import Http404
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.db.models import Count, Case, When, IntegerField
from django.core.cache import cache
import json

from chardata.encoded_char_id import encode_char_id
from chardata.fashion_action import fashion, get_options
from chardata.lock_forbid import (set_excluded,
                                  set_item_included,
    get_all_inclusions_en_names, get_all_exclusions_en_names,
    get_empty_slots, set_empty_slot, get_stat_overrides)
from chardata.comment_view import get_comments_for_build
from chardata.models import Char, BuildVote, BuildView
import chardata.smart_build
from chardata.solution import get_solution, set_minimal_solution
from django.utils import timezone
from django.utils.translation import gettext as _
from datetime import timedelta
from chardata.solution_result import SolutionResult
from chardata.util import set_response, get_char_or_raise, get_alias, get_char_encoded_or_raise, \
    HttpResponseText, get_base_stats_by_attr, version_reverse
from fashionistapulp.dofus_constants import SLOTS, STAT_ORDER

from static_s3.templatetags.static_s3 import static
from fashionistapulp.structure import get_structure
from chardata.stat_icons import get_stat_icon_path
from fashionistapulp.modelresult import ModelResultMinimal
from chardata.themes import get_ajax_loader_URL, get_external_image_URL
from fashionistapulp.translation import get_supported_language


SHARED_SOLUTION_CACHE_TIMEOUT = 6 * 60 * 60

_SHARE_SLOT_ORDER = ['Weapon', 'Shield', 'Hat', 'Cloak', 'Amulet', 'Ring',
                     'Belt', 'Boots', 'Dofus', 'Pet']


_LOW_ITEM_LEVEL_GAP = 50  # an equipped item this far below char level = upgrade hint


def _build_check(char, solution):
    """Lightweight, fast heuristic build review. Returns a dict with a list of
    equipped items well below the character's level (likely upgradeable) and a
    count of equipped items. Intentionally avoids slot-count math (version
    dependent) — it only surfaces clearly actionable, low-risk hints."""
    low_items = []
    equipped = 0
    char_level = char.level or 0
    for slot, items in solution.items.items():
        for item in items:
            name = getattr(item, 'name', None)
            if not getattr(item, 'item_added', False) or not name or name == 'NoItem':
                continue
            equipped += 1
            item_level = getattr(item, 'level', None)
            if (char_level >= 60 and item_level is not None
                    and item_level <= char_level - _LOW_ITEM_LEVEL_GAP):
                low_items.append({'slot': slot, 'name': name, 'level': item_level})
    return {
        'equipped_count': equipped,
        'low_items': low_items,
        'has_hints': bool(low_items),
    }


def _build_share_text(request, char, solution):
    """Plain-text build summary for pasting into Discord / forums."""
    title = char.char_name or char.name or char.char_class or 'Build'
    lines = ['%s - %s lvl %d' % (title, char.char_class, char.level), '']
    for slot in _SHARE_SLOT_ORDER:
        for item in solution.items.get(slot, []):
            name = getattr(item, 'name', None)
            if getattr(item, 'item_added', False) and name and name != 'NoItem':
                lines.append('%s: %s' % (slot, name))
    try:
        stats = solution.get_stats_total()
        chips = []
        for key, label in [('ap', 'AP'), ('mp', 'MP'), ('range', 'Range'),
                           ('vit', 'Vitality'), ('pow', 'Power')]:
            value = stats.get(key, 0)
            if value:
                chips.append('%s %d' % (label, int(value)))
        if chips:
            lines += ['', ' / '.join(chips)]
    except Exception:
        pass
    lines.append('')
    if char.link_shared:
        lines.append(generate_link(request, char))
    else:
        lines.append('https://dofusfashionista.gg')
    return '\n'.join(lines)

# Classes for which we ship 6 wizard avatars under chardata/designs/wizard/<class>/.
_CLASS_AVATAR_DIRS = {'Cra', 'Ecaflip', 'Eliotrope', 'Eniripsa', 'Enutrof', 'Feca',
                      'Foggernaut', 'Huppermage', 'Iop', 'Masqueraider', 'Osamodas',
                      'Ouginak', 'Pandawa', 'Rogue', 'Sacrier', 'Sadida', 'Sram', 'Xelor'}
_CLASS_AVATAR_COUNT = 6


def _get_class_avatar(char):
    """Stable per-char avatar URL, falling back to a placeholder for classes
    without art (Forgelance) or unknown values."""
    cls = char.char_class or ''
    if cls not in _CLASS_AVATAR_DIRS:
        return static('chardata/QuestionMark-lighttheme.png')
    idx = 1 + (int(char.id or 0) % _CLASS_AVATAR_COUNT)
    return static('chardata/designs/wizard/%s/myWizard%s%d.png' % (cls, cls, idx))


def _get_stat_filter_options():
    structure = get_structure()
    stats = sorted(structure.get_stats_list(), key=lambda stat: STAT_ORDER.get(stat.key, 9999))
    result = []
    for stat in stats:
        if stat.key == 'hp' or stat.key.startswith('pvp'):
            continue
        icon_path = get_stat_icon_path(stat.key)
        result.append({
            'key': stat.key,
            'id': stat.id,
            'label': _(stat.name),
            'icon_url': static(icon_path) if icon_path else None,
        })
    return result


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
        empty_slots = get_empty_slots(char)
        solution = get_solution(char)
        solution_result = SolutionResult(solution,
                                         inclusions,
                                         exclusions,
                                         empty_slots)
        solution_params = solution_result.get_params()

    vote_data = _get_live_vote_data(request, char)
    class_avatar = _get_class_avatar(char)

    share_text = ''
    build_check = None
    try:
        _sol_for_text = get_solution(char)
        if _sol_for_text is not None:
            share_text = _build_share_text(request, char, _sol_for_text)
            build_check = _build_check(char, _sol_for_text)
    except Exception:
        share_text = ''
        build_check = None

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
              'is_dueler': chardata.smart_build.char_has_aspect(char, 'duel'),
              'class_avatar': class_avatar,
              'share_text': share_text,
              'build_check': build_check,
              'stat_filter_options_json': json.dumps(_get_stat_filter_options())}
              
    if char.link_shared:
        params['initial_link'] = generate_link(request, char)
        params['comments'] = get_comments_for_build(char, request.user)
        params['comments_json'] = json.dumps(params['comments'])
    else:
        params['comments'] = []
        params['comments_json'] = '[]'

    params['build_tags'] = [{'id': t.id, 'name': t.display_name, 'slug': t.name}
                            for t in char.tags.all().order_by('created_time')]
    params['can_edit_tags'] = (not is_guest
                               and char.owner_id is not None
                               and request.user.is_authenticated
                               and char.owner_id == request.user.id)

    params.update(vote_data)
    params.update(solution_params)

    if not is_guest:
        raw_overrides = get_stat_overrides(char)
        stat_overrides_json = {str(item_id): {str(stat_id): val for stat_id, val in stats.items()}
                               for item_id, stats in raw_overrides.items()}
        params['stat_overrides_json'] = json.dumps(stat_overrides_json)
        params['base_options_json'] = json.dumps(get_options(request, char_id))

    response = set_response(request,
                            'chardata/solution.html',
                            params,
                            char)
    return response


def get_sharing_link(request, char_id):
    char = get_char_or_raise(request, char_id)

    char.link_shared = True
    char.save()
    
    return HttpResponseText(generate_link(request, char))

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
    if char.game_version != getattr(request, 'game_version', 'dofus3'):
        raise Http404
    
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

def generate_link(request, char):
    encoded_id = encode_char_id(int(char.id))
    char_name = char.char_name or 'shared'
    return request.build_absolute_uri(version_reverse(request, 'solution_linked',
                                                      char_name, encoded_id))

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
    
    return HttpResponseText('ok')

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

    return HttpResponseText('ok')

def set_slot_lock_empty(request, char_id):
    char = get_char_or_raise(request, char_id)

    slot = request.POST.get('slot', None)
    locked = request.POST.get('locked', None)

    assert slot in SLOTS

    set_empty_slot(char, slot, locked == 'true')

    return HttpResponseText('ok')
