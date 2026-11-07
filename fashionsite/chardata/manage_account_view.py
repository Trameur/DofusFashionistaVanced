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

from django.contrib.auth import authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError, get_connection, send_mail
from django.core.validators import validate_email
from django.db import DatabaseError, transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from chardata.account_deletion import (destroy_account, forget_the_names,
                                       may_be_deleted, purge_detached_builds)
from chardata.character_look import PREVIEW_SIZES, preview_is_on
from chardata.login_view import (_get_from_email, _get_non_social_users_for_email,
                                 clear_login_failures, login_is_throttled,
                                 note_login_failure)
from chardata.models import Char, UserAlias
from chardata.rate_limit import clear_hits, hits, note_hit
from chardata.public_name import (clean_public_name, default_public_name,
                                  looks_like_an_address, public_name_is_taken)
from chardata.util import get_alias, json_for_script, set_response

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
EMAIL_CHANGE_MAX_PER_ADDRESS = 3
EMAIL_CHANGE_MAX_PER_IP = 10


def _applied_key(user):
    return 'email-change-applied:%d' % user.pk


def _account_fingerprint(user):
    applied = hits(_applied_key(user), EMAIL_CHANGE_MAX_AGE)
    return salted_hmac(EMAIL_CHANGE_SALT,
                       '%s|%s|%d' % (user.email or '', user.password, applied)).hexdigest()


def _email_change_token(user, new_address):
    # A new password or an applied change ends the link, even once the address is back
    return signing.dumps({'user': user.pk, 'new': new_address,
                          'current': _account_fingerprint(user)},
                         salt=EMAIL_CHANGE_SALT)


def _email_change_keys(request, new_address):
    from chardata.solution_view import get_client_ip
    keys = [('email-change:%d' % request.user.pk, EMAIL_CHANGE_MAX_PER_USER),
            ('email-change-to:%s' % new_address.lower()[:120], EMAIL_CHANGE_MAX_PER_ADDRESS)]
    ip = get_client_ip(request)
    if ip:
        keys.append(('email-change-ip:%s' % ip, EMAIL_CHANGE_MAX_PER_IP))
    return keys


def _send_email_change_link(request, new_address):
    """Mails the link to the new address and answers the line the account page shows."""
    keys = _email_change_keys(request, new_address)
    if any(hits(key, EMAIL_CHANGE_WINDOW) >= ceiling for key, ceiling in keys):
        return _('Too many address changes requested. Try again in an hour.')
    link = request.build_absolute_uri(
        reverse('confirm_email_change',
                args=(_email_change_token(request.user, new_address),)))
    try:
        send_mail(_('Confirm your new email address for The Dofus Fashionista'),
                  _('Please click the link below to use this address for the account {username} '
                    'on The Dofus Fashionista. The link works for one day.\n'
                    '{link}\n\n'
                    'If you did not ask for this, just ignore this email.').format(
                        username=request.user.username, link=link),
                  _get_from_email(),
                  [new_address])
    except (BadHeaderError, OSError, ValueError):
        logger.exception('Email change link could not be sent')
        return _('The confirmation email could not be sent. Try again later.')
    for key, _ceiling in keys:
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


def _email_change_outcome(outcome):
    return HttpResponseRedirect(reverse('email_change_result', args=(outcome,)))


def confirm_email_change(request, token):
    try:
        change = signing.loads(token, salt=EMAIL_CHANGE_SALT,
                               max_age=EMAIL_CHANGE_MAX_AGE)
        user = User.objects.get(pk=change['user'])
    except (signing.BadSignature, User.DoesNotExist):
        return _email_change_outcome('invalid')
    if not constant_time_compare(change['current'], _account_fingerprint(user)):
        return _email_change_outcome('invalid')
    if any(other.pk != user.pk for other in _get_non_social_users_for_email(change['new'])):
        return _email_change_outcome('taken')
    # Mail scanners open links: only the button on this page applies the change
    if request.method != 'POST':
        return set_response(request, 'chardata/email_change_confirm.html',
                            {'request': request,
                             'new_address': change['new'],
                             'account': user.username})
    former_address = user.email
    user.email = change['new']
    # The address, its counter and the deletion hold stand or fall together
    with transaction.atomic():
        user.save(update_fields=['email'])
        note_hit(_applied_key(user), EMAIL_CHANGE_MAX_AGE)
        _start_deletion_hold(user)
    if former_address:
        _tell_the_former_address(former_address)
    return _email_change_outcome('ok')


def email_change_result(request, outcome):
    return set_response(request, 'chardata/email_change_result.html',
                        {'request': request,
                         'changed': outcome == 'ok',
                         'taken': outcome == 'taken'})


ACCOUNT_DELETION_SALT = 'chardata.account_deletion'
ACCOUNT_DELETION_MAX_AGE = 60 * 60
ACCOUNT_DELETION_WINDOW = 60 * 60
ACCOUNT_DELETION_MAX_PER_USER = 3
ACCOUNT_DELETION_MAX_PER_IP = 10
ACCOUNT_DELETION_HOLD = 24 * 60 * 60
DELETION_MAIL_TIMEOUT = 10
DELETED_SESSION_KEY = 'account_deleted'


def _deletion_hold_key(user):
    return 'account-deletion-hold:%d' % user.pk


def _start_deletion_hold(user):
    # A hijacked session could change the address and delete at once: wait a day
    key = _deletion_hold_key(user)
    clear_hits(key)
    note_hit(key, ACCOUNT_DELETION_HOLD)


def _deletion_token(user, session_bound=False):
    # A new password or address ends the link, as for an address change
    payload = {'user': user.pk, 'current': _account_fingerprint(user)}
    if session_bound:
        # Made for the session that proved the password: no other session may use it
        payload['bound'] = True
    return signing.dumps(payload, salt=ACCOUNT_DELETION_SALT)


def _deletion_refusal(user):
    if not may_be_deleted(user):
        return 'refused'
    if (hits(_deletion_hold_key(user), ACCOUNT_DELETION_HOLD)
            or hits(_applied_key(user), EMAIL_CHANGE_MAX_AGE)):
        return 'too_soon'
    return None


def _deletion_name(user):
    # A username can hold an address
    return get_alias(user) or default_public_name(user)


def _deletion_keys(request, user):
    from chardata.solution_view import get_client_ip
    keys = [('account-delete:%d' % user.pk, ACCOUNT_DELETION_MAX_PER_USER)]
    ip = get_client_ip(request)
    if ip:
        keys.append(('account-delete-ip:%s' % ip, ACCOUNT_DELETION_MAX_PER_IP))
    return keys


def _send_deletion_link(request, user):
    """Mails the one-hour link to the stored address and answers the outcome."""
    if not user.email:
        return 'no_address'
    keys = _deletion_keys(request, user)
    if any(hits(key, ACCOUNT_DELETION_WINDOW) >= ceiling for key, ceiling in keys):
        return 'too_many'
    link = request.build_absolute_uri(
        reverse('confirm_account_deletion', args=(_deletion_token(user),)))
    try:
        send_mail(_('Confirm the deletion of your account on The Dofus Fashionista'),
                  _('You asked to delete the account {account} on The Dofus Fashionista. '
                    'Your builds, comments, votes and settings would be removed for good.\n'
                    'To go on, open the link below and press the button on that page. '
                    'The link works for one hour.\n'
                    '{link}\n\n'
                    'If you did not ask for this, ignore this email: nothing changes '
                    'without that button. Someone else may be signed in to your '
                    'account.').format(account=_deletion_name(user), link=link),
                  _get_from_email(),
                  [user.email])
    except (BadHeaderError, OSError, ValueError) as error:
        # The text of the error can hold the address
        logger.error('Account deletion link could not be sent: %s', type(error).__name__)
        return 'mail_failed'
    for key, _ceiling in keys:
        note_hit(key, ACCOUNT_DELETION_WINDOW)
    return 'sent'


def _tell_the_deleted_address(address, account):
    if not address:
        return
    try:
        send_mail(_('Your account on The Dofus Fashionista was deleted'),
                  _('The account {account} on The Dofus Fashionista and its builds have '
                    'been deleted. It cannot be restored. If this was not you, reply to '
                    'this email.').format(account=account),
                  _get_from_email(),
                  [address],
                  connection=get_connection(timeout=DELETION_MAIL_TIMEOUT))
    except Exception as error:
        # Whatever fails here, the purge after it must still run
        logger.error('Account deletion notice could not be sent: %s', type(error).__name__)


def _deletion_outcome(outcome):
    return HttpResponseRedirect(reverse('account_deletion_result', args=(outcome,)))


def _to_login():
    return HttpResponseRedirect(reverse('login_page'))


@require_POST
def request_account_deletion(request):
    if request.user.is_anonymous:
        return _to_login()
    return _deletion_outcome(_deletion_refusal(request.user)
                             or _send_deletion_link(request, request.user))


@sensitive_post_parameters('password')
@require_POST
def delete_account_with_password(request):
    if request.user.is_anonymous:
        return _to_login()
    user = request.user
    refusal = _deletion_refusal(user)
    if refusal:
        return _deletion_outcome(refusal)
    if login_is_throttled(request, user.username):
        return _deletion_outcome('too_many')
    # The form posts the same prehashed value as the change password form
    proven = authenticate(username=user.username, password=request.POST.get('password'))
    if proven is None or proven.pk != user.pk:
        note_login_failure(request, user.username)
        return _deletion_outcome('wrong_password')
    clear_login_failures(user.username)
    # The check may have stored a newer hash: token and session follow the fresh row
    update_session_auth_hash(request, proven)
    return HttpResponseRedirect(
        reverse('confirm_account_deletion',
                args=(_deletion_token(proven, session_bound=True),)))


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def confirm_account_deletion(request, token):
    try:
        change = signing.loads(token, salt=ACCOUNT_DELETION_SALT,
                               max_age=ACCOUNT_DELETION_MAX_AGE)
        user = User.objects.get(pk=change['user'])
        current = change['current']
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError):
        return _deletion_outcome('invalid')
    if not constant_time_compare(current, _account_fingerprint(user)):
        return _deletion_outcome('invalid')
    if change.get('bound') and not (request.user.is_authenticated
                                    and request.user.pk == user.pk):
        return _deletion_outcome('invalid')
    refusal = _deletion_refusal(user)
    if refusal:
        return _deletion_outcome(refusal)
    account = _deletion_name(user)
    # Mail scanners open links: only the button on this page deletes
    if request.method != 'POST' or not request.POST.get('understood'):
        return set_response(request, 'chardata/account_deletion_confirm.html',
                            {'request': request,
                             'account': account,
                             'builds': Char.objects.filter(owner=user, deleted=False).count(),
                             'box_missing': request.method == 'POST'})
    # Read before the row goes: the lazy user would look it up again and find nobody
    signed_in_as_it = request.user.is_authenticated and request.user.pk == user.pk
    try:
        removed = destroy_account(user.pk)
    except DatabaseError as error:
        logger.error('Account deletion failed: %s', type(error).__name__)
        return _deletion_outcome('failed')
    if removed is None:
        return _deletion_outcome('invalid')
    if signed_in_as_it:
        logout(request)
    # The result page tells what happened only to the browser that did it
    request.session[DELETED_SESSION_KEY] = True
    try:
        forget_the_names(removed.username, removed.alias, removed.address)
    except DatabaseError as error:
        logger.error('Counters of a deleted account were kept: %s', type(error).__name__)
    _tell_the_deleted_address(removed.address, account)
    purge_detached_builds(removed.build_ids)
    return _deletion_outcome('deleted')


def account_deletion_result(request, outcome):
    address = ''
    if outcome == 'sent':
        if request.user.is_anonymous:
            return _to_login()
        address = request.user.email
    if outcome == 'deleted' and not request.session.get(DELETED_SESSION_KEY):
        outcome = 'invalid'
    return set_response(request, 'chardata/account_deletion_result.html',
                        {'request': request,
                         'outcome': outcome,
                         'address': address,
                         'signed_in_elsewhere': request.user.is_authenticated})


def manage_account(request):
    notify_comments = True
    email_language = ''
    full_name = ''
    preview_size = 100
    deletion_refused = False
    deletion_with_password = False
    if request.user is not None and not request.user.is_anonymous:
        full_name = request.user.get_full_name() or ''
        deletion_refused = not may_be_deleted(request.user)
        deletion_with_password = request.user.has_usable_password()
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
                         'preview_is_on': preview_is_on(),
                         'deletion_refused': deletion_refused,
                         'deletion_with_password': deletion_with_password})


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
    if wanted_alias not in (alias.alias, default_name):
        if looks_like_an_address(wanted_alias):
            alias_notice = _('An alias cannot be an email address.')
        elif public_name_is_taken(wanted_alias, request.user):
            alias_notice = _('This alias is already taken. Choose another one.')
        if alias_notice:
            wanted_alias = alias.alias or default_name
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
