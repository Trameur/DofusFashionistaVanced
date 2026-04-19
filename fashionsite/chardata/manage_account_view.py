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

import json
from django.http import JsonResponse

from chardata.models import UserAlias
from chardata.util import set_response


def manage_account(request):
    return set_response(request,
                        'chardata/manage_account.html',
                        {'user_social_name': json.dumps(request.user.get_full_name())})

def save_account(request):
    form_alias = request.POST.get('alias', '')
    form_email = request.POST.get('email', '')
    
    aliases = []
    if request.user is not None and not request.user.is_anonymous:
        aliases = UserAlias.objects.filter(user=request.user)
    alias = None
    if len(aliases) > 0:
        alias = aliases[0]
    else:
        alias = UserAlias()
        alias.user = request.user
    alias.alias = form_alias
    alias.save()
    if form_email:
        request.user.email = form_email
        request.user.save()
        
    return JsonResponse({'alias': alias.alias, 'email': request.user.email})