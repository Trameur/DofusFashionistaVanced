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
from chardata.views import user_has_projects

from django.urls import reverse
from django.utils.translation import gettext as _
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from chardata.image_store import get_image_url
from static_s3.templatetags.static_s3 import static

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
        button['link'] = reverse('faq')
        button['class'] = get_button_pos(buttons)
        buttons.append(button)
    if len(buttons) < 3:
        button = {}
        button['pic'] = static('chardata/About2.png')
        button['label'] = _('Help & About')
        button['link'] = reverse('about')
        button['class'] = get_button_pos(buttons)
        buttons.append(button)
    
    
    return set_response(request, 
                        'chardata/home.html', 
                        {'request': request,
                         'home': True,
                         'items': items,
                         'buttons': buttons,
                         'user': request.user,
                         'char_id': char_id})

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
