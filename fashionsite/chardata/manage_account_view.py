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
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse

from chardata.character_look import PREVIEW_SIZES, preview_is_on
from chardata.models import UserAlias
from chardata.util import set_response


def _get_or_create_alias(user):
    try:
        return user.useralias
    except UserAlias.DoesNotExist:
        return UserAlias.objects.create(user=user)


EMAIL_LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def manage_account(request):
    notify_comments = True
    email_language = ''
    full_name = ''
    preview_size = 100
    if request.user is not None and not request.user.is_anonymous:
        full_name = request.user.get_full_name() or ''
        try:
            notify_comments = bool(request.user.useralias.notify_comments)
            email_language = request.user.useralias.language or ''
            preview_size = request.user.useralias.preview_size
        except UserAlias.DoesNotExist:
            notify_comments = True

    return set_response(request,
                        'chardata/manage_account.html',
                        {'user_social_name': json.dumps(full_name),
                         'notify_comments_json': json.dumps(notify_comments),
                         'email_language_json': json.dumps(email_language),
                         'preview_size_json': json.dumps(preview_size),
                         'preview_is_on': preview_is_on()})


def save_account(request):
    # The browser maxlength doesn't guard direct POSTs.
    form_alias = request.POST.get('alias', '')
    form_alias = form_alias[:UserAlias._meta.get_field('alias').max_length]
    form_email = request.POST.get('email', '')
    email_limit = User._meta.get_field('email').max_length
    if len(form_email) > email_limit:
        # Not a real email, keep the stored one.
        form_email = ''
    elif form_email:
        try:
            validate_email(form_email)
        except ValidationError:
            # Malformed address, keep the stored one.
            form_email = ''
    # HTML checkboxes only appear in POST when checked.
    form_notify_comments = 'notify_comments' in request.POST

    if request.user is None or request.user.is_anonymous:
        return JsonResponse({'error': 'not authenticated'}, status=403)

    alias = _get_or_create_alias(request.user)
    alias.alias = form_alias
    alias.notify_comments = form_notify_comments
    if 'email_language' in request.POST:
        form_email_language = request.POST['email_language']
        if form_email_language in EMAIL_LANGUAGES:
            alias.language = form_email_language
        elif form_email_language == '':
            # "Automatic": clear the choice, the login backfill takes over.
            alias.language = None
    if 'preview_size' in request.POST:
        try:
            wanted = int(request.POST['preview_size'])
        except (TypeError, ValueError):
            wanted = 100
        alias.preview_size = wanted if wanted in PREVIEW_SIZES else 100
    alias.save()

    if form_email:
        request.user.email = form_email
        request.user.save()

    return JsonResponse({
        'alias': alias.alias,
        'email': request.user.email,
        'notify_comments': alias.notify_comments,
        'email_language': alias.language or '',
        'preview_size': alias.preview_size,
    })
