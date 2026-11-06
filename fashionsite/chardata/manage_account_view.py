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
import logging

from django.contrib.auth.models import User
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError, send_mail
from django.core.validators import validate_email
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from chardata.character_look import PREVIEW_SIZES, preview_is_on
from chardata.login_view import _get_from_email
from chardata.models import UserAlias
from chardata.rate_limit import hits, note_hit
from chardata.public_name import (clean_public_name, default_public_name,
                                  public_name_is_taken)
from chardata.util import json_for_script, set_response

logger = logging.getLogger(__name__)


def _get_or_create_alias(user):
    try:
        return user.useralias
    except UserAlias.DoesNotExist:
        return UserAlias.objects.create(user=user)


EMAIL_LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

EMAIL_CHANGE_SALT = 'chardata.email_change'
EMAIL_CHANGE_MAX_AGE = 24 * 60 * 60
EMAIL_CHANGE_WINDOW = 60 * 60
EMAIL_CHANGE_MAX_PER_USER = 3


def _address_fingerprint(address):
    return salted_hmac(EMAIL_CHANGE_SALT, address or '').hexdigest()


def _email_change_token(user, new_address):
    # Bound to the current address: applying it, or any other change, ends the link
    return signing.dumps({'user': user.pk, 'new': new_address,
                          'current': _address_fingerprint(user.email)},
                         salt=EMAIL_CHANGE_SALT)


def _send_email_change_link(request, new_address):
    """Mails the link to the new address and answers the line the account page shows."""
    key = 'email-change:%d' % request.user.pk
    if hits(key, EMAIL_CHANGE_WINDOW) >= EMAIL_CHANGE_MAX_PER_USER:
        return _('Too many address changes requested. Try again in an hour.')
    link = request.build_absolute_uri(
        reverse('confirm_email_change',
                args=(_email_change_token(request.user, new_address),)))
    try:
        send_mail(_('Confirm your new email address for The Dofus Fashionista'),
                  _('Please click the link below to use this address for your account '
                    'on The Dofus Fashionista. The link works for one day.\n'
                    '{link}\n\n'
                    'If you did not ask for this, just ignore this email.').format(link=link),
                  _get_from_email(),
                  [new_address])
    except (BadHeaderError, OSError, ValueError):
        logger.exception('Email change link could not be sent')
        return _('The confirmation email could not be sent. Try again later.')
    note_hit(key, EMAIL_CHANGE_WINDOW)
    return _('We have sent a link to %(address)s. Your email address changes '
             'when you open it.') % {'address': new_address}


def _tell_the_former_address(former_address):
    try:
        send_mail(_('Your email address was changed on The Dofus Fashionista'),
                  _('The email address of your account on The Dofus Fashionista has '
                    'just been changed. If this was not you, reply to this email.'),
                  _get_from_email(),
                  [former_address])
    except (BadHeaderError, OSError, ValueError):
        logger.exception('Email change notice could not be sent')


def confirm_email_change(request, token):
    try:
        change = signing.loads(token, salt=EMAIL_CHANGE_SALT,
                               max_age=EMAIL_CHANGE_MAX_AGE)
        user = User.objects.get(pk=change['user'])
    except (signing.BadSignature, User.DoesNotExist):
        return HttpResponseRedirect(reverse('email_change_result', args=('invalid',)))
    if not constant_time_compare(change['current'], _address_fingerprint(user.email)):
        return HttpResponseRedirect(reverse('email_change_result', args=('invalid',)))
    former_address = user.email
    user.email = change['new']
    user.save(update_fields=['email'])
    if former_address:
        _tell_the_former_address(former_address)
    # The redirect keeps the signed link out of the page's address and its analytics
    return HttpResponseRedirect(reverse('email_change_result', args=('ok',)))


def email_change_result(request, outcome):
    return set_response(request, 'chardata/email_change_result.html',
                        {'request': request, 'changed': outcome == 'ok'})


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
                        {'user_social_name': json_for_script(full_name),
                         'notify_comments_json': json.dumps(notify_comments),
                         'email_language_json': json.dumps(email_language),
                         'preview_size_json': json.dumps(preview_size),
                         'preview_is_on': preview_is_on()})


@require_POST
def save_account(request):
    # The browser maxlength doesn't guard direct POSTs.
    form_alias = request.POST.get('alias', '')
    form_alias = clean_public_name(form_alias, UserAlias._meta.get_field('alias').max_length)
    form_email = request.POST.get('email', '')
    email_limit = User._meta.get_field('email').max_length
    if len(form_email) > email_limit:
        # Not a real email: no change to confirm.
        form_email = ''
    elif form_email:
        try:
            validate_email(form_email)
        except ValidationError:
            # Malformed address: no change to confirm.
            form_email = ''
    # HTML checkboxes only appear in POST when checked.
    form_notify_comments = 'notify_comments' in request.POST

    if request.user is None or request.user.is_anonymous:
        return JsonResponse({'error': 'not authenticated'}, status=403)

    alias = _get_or_create_alias(request.user)
    default_name = default_public_name(request.user)
    wanted_alias = form_alias or default_name
    alias_notice = ''
    if (wanted_alias not in (alias.alias, default_name)
            and public_name_is_taken(wanted_alias, request.user)):
        wanted_alias = alias.alias or default_name
        alias_notice = _('This alias is already taken. Choose another one.')
    alias.alias = wanted_alias
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

    # The stored address only changes from the link mailed to the new one
    email_notice = ''
    if form_email and form_email != request.user.email:
        email_notice = _send_email_change_link(request, form_email)

    return JsonResponse({
        'alias': alias.alias,
        'alias_notice': alias_notice,
        'email': request.user.email,
        'email_notice': email_notice,
        'notify_comments': alias.notify_comments,
        'email_language': alias.language or '',
        'preview_size': alias.preview_size,
    })
