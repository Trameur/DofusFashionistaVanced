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

from chardata.util import set_response, version_reverse
from chardata.create_project_view import is_anon_cant_create, has_too_many_projects
from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, UserAlias
from chardata.views import user_has_projects

from django.core.cache import cache
from django.db.models import Count, Case, When, IntegerField
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from chardata.image_store import get_image_url
from static_s3.templatetags.static_s3 import static


FEATURED_BUILDS_COUNT = 6
FEATURED_BUILDS_CACHE_SECONDS = 30 * 60
_CLASS_AVATAR_DIRS = {'Cra', 'Ecaflip', 'Eliotrope', 'Eniripsa', 'Enutrof', 'Feca',
                      'Foggernaut', 'Huppermage', 'Iop', 'Masqueraider', 'Osamodas',
                      'Ouginak', 'Pandawa', 'Rogue', 'Sacrier', 'Sadida', 'Sram', 'Xelor'}


def _featured_avatar(char):
    cls = char.char_class or ''
    if cls not in _CLASS_AVATAR_DIRS:
        return static('chardata/QuestionMark-lighttheme.png')
    idx = 1 + (int(char.id or 0) % 6)
    return static('chardata/designs/wizard/%s/myWizard%s%d.png' % (cls, cls, idx))


def _get_featured_builds(request, game_version):
    """Top community builds for the current game version, scored by likes +
    favorites + (capped) view count. Cached so the homepage stays fast."""
    cache_key = 'home_featured_builds:%s' % game_version
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qs = (Char.objects
          .filter(link_shared=True, deleted=False, game_version=game_version)
          .select_related('owner')
          .annotate(
              like_count=Count(Case(When(buildvote__vote_type='like', then=1),
                                    output_field=IntegerField())),
              favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1),
                                        output_field=IntegerField())),
          ))
    builds = list(qs)
    owner_ids = [b.owner_id for b in builds if b.owner_id]
    aliases = {a.user_id: a.alias for a in UserAlias.objects.filter(user_id__in=owner_ids) if a.alias}

    scored = []
    for b in builds:
        score = (b.like_count or 0) * 3 + (b.favorite_count or 0) * 5 + min(50, b.view_count or 0)
        creator = aliases.get(b.owner_id) or (b.owner.username if b.owner else _('Anonymous'))
        encoded = encode_char_id(int(b.id))
        char_name = b.char_name or 'shared'
        scored.append({
            'name': b.char_name or b.name,
            'char_class': b.char_class,
            'level': b.level,
            'creator': creator,
            'like_count': b.like_count or 0,
            'favorite_count': b.favorite_count or 0,
            'view_count': b.view_count or 0,
            'link': request.build_absolute_uri(
                version_reverse(request, 'solution_linked', char_name, encoded)),
            'avatar': _featured_avatar(b),
            '_score': score,
        })
    scored.sort(key=lambda x: x['_score'], reverse=True)
    result = scored[:FEATURED_BUILDS_COUNT]
    cache.set(cache_key, result, FEATURED_BUILDS_CACHE_SECONDS)
    return result

def home(request, char_id=0):
    items = []
    for unused in range(13):
        item_row = []
        for unused in range(13):
            item_obj = get_structure().get_random_item()
            item = {}
            item['name'] = item_obj.localized_names[get_supported_language()]
            item['file'] = static(get_image_url(get_structure().get_type_name_by_id(item_obj.type), item_obj.name))
            item_row.append(item)
        items.append(item_row)
    
    buttons = []
    if not is_anon_cant_create(request) and not has_too_many_projects(request) and len(buttons) < 3:
        button = {}
        button['pic'] = static('chardata/LoadProj2.png')
        button['label'] = _('Create a Project')
        button['link'] = version_reverse(request, 'setup')
        button['class'] = get_button_pos(buttons)
        buttons.append(button)
    if user_has_projects(request) and len(buttons) < 3:
        button = {}
        button['pic'] = static('chardata/NewProj1.png')
        button['label'] = _('Load a Project')
        button['link'] = version_reverse(request, 'load_projects')
        button['class'] = get_button_pos(buttons)
        buttons.append(button)
    if request.user.is_anonymous and len(buttons) < 3:
        button = {}
        button['pic'] = static('chardata/Login1.png')
        button['label'] = _('Login')
        button['link'] = version_reverse(request, 'login_page')
        button['class'] = get_button_pos(buttons)
        buttons.append(button)
    if len(buttons) < 3:
        button = {}
        button['pic'] = static('chardata/Faq2.png')
        button['label'] = _('FAQ')
        button['link'] = version_reverse(request, 'faq')
        button['class'] = get_button_pos(buttons)
        buttons.append(button)
    if len(buttons) < 3:
        button = {}
        button['pic'] = static('chardata/About2.png')
        button['label'] = _('Help & About')
        button['link'] = version_reverse(request, 'about')
        button['class'] = get_button_pos(buttons)
        buttons.append(button)
    
    
    game_version = getattr(request, 'game_version', 'dofus3')
    featured_builds = _get_featured_builds(request, game_version)

    return set_response(request,
                        'chardata/home.html',
                        {'request': request,
                         'home': True,
                         'items': items,
                         'buttons': buttons,
                         'featured_builds': featured_builds,
                         'user': request.user,
                         'char_id': char_id})

def random_build(request):
    """Redirect to a random shared build for the current game version.
    Falls back to /sharedbuilds/ if there isn't a single one."""
    game_version = getattr(request, 'game_version', 'dofus3')
    char = (Char.objects
            .filter(link_shared=True, deleted=False, game_version=game_version)
            .order_by('?').first())
    if char is None:
        return HttpResponseRedirect(version_reverse(request, 'shared_builds'))
    encoded = encode_char_id(int(char.id))
    char_name = char.char_name or 'shared'
    return HttpResponseRedirect(
        version_reverse(request, 'solution_linked', char_name, encoded))


def get_button_pos(buttons):
    if len(buttons) == 0:
        return 'first-button'
    if len(buttons) == 1:
        return 'second-button'
    if len(buttons) == 2:
        return 'third-button'

def _process_post(post):
    post['message'] = _process_message(post['message'])
    return post

def _process_message(msg):
    return (msg.replace('[CREATE_PROJECT_LINK]',
                       reverse('setup'))
               .replace('[LOGIN_LINK]',
                       reverse('login_page'))
               .replace('[CONTACT_LINK]',
                       reverse('contact')))
