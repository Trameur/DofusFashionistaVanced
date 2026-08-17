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

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail, BadHeaderError
from django.core.validators import validate_email
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.db import IntegrityError
from django.core.signing import (BadSignature, SignatureExpired,
                                 TimestampSigner)
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import url_has_allowed_host_and_scheme
from smtplib import SMTPRecipientsRefused, SMTPException
from social_django.models import UserSocialAuth
import hashlib
import logging
import requests as http_requests

from chardata.models import UserAlias
from chardata.util import set_response, HttpResponseText, recaptcha_ok
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


# login.js posts SHA256('dofusfashionista' + password), so every stored password
# is make_password(<that hash>). The reset form posts the raw password.
def _prehash_password(raw_password):
    return hashlib.sha256(('dofusfashionista' + raw_password).encode('utf-8')).hexdigest()


# Nothing limited how many passwords could be tried against an account: both
# local_login and change_password call authenticate() with whatever is posted.
# The counters live in the cache, which is per process in production, so a
# worker pool multiplies the real ceiling by its size. That still turns an
# unbounded guessing loop into a slow one, and it costs no table.
LOGIN_FAIL_WINDOW = 15 * 60
LOGIN_FAIL_MAX_PER_USER = 10
LOGIN_FAIL_MAX_PER_IP = 30


def _login_fail_keys(request, username):
    from chardata.solution_view import get_client_ip
    keys = []
    if username:
        keys.append(('login-fail-user:%s' % username.lower()[:80],
                     LOGIN_FAIL_MAX_PER_USER))
    ip = get_client_ip(request)
    if ip:
        keys.append(('login-fail-ip:%s' % ip, LOGIN_FAIL_MAX_PER_IP))
    return keys


def login_is_throttled(request, username):
    from django.core.cache import cache
    for key, ceiling in _login_fail_keys(request, username):
        if (cache.get(key) or 0) >= ceiling:
            return True
    return False


def note_login_failure(request, username):
    from django.core.cache import cache
    for key, _ceiling in _login_fail_keys(request, username):
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, LOGIN_FAIL_WINDOW)


def clear_login_failures(request, username):
    from django.core.cache import cache
    for key, _ceiling in _login_fail_keys(request, username):
        cache.delete(key)

def _get_from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', None) or settings.EMAIL_HOST_USER or 'DofusFashionistaVanced@gmail.com'

def login_page(request, char_id=0):
    return _login_page_generic(request, False, None, char_id, False)

def _login_page_generic(request, from_confirmation, prefilled_user, char_id, already_confirmed):
    return set_response(request, 
                        'chardata/login.html',
                        {'request': request,
                         'user': request.user,
                         'char_id': char_id,
                         'from_confirmation': from_confirmation,
                         'prefilled_user': prefilled_user,
                         'already_confirmed': already_confirmed == 'yes'})

def register(request):
    if request.method != 'POST':
        ns = request.resolver_match.namespace
        target = f'{ns}:login_page' if ns else 'login_page'
        return HttpResponseRedirect(reverse(target))

    if not settings.DEBUG and not recaptcha_ok(request):
        raise PermissionDenied

    username = request.POST.get('username', None)
    password = request.POST.get('password', None)
    email = request.POST.get('email', None)

    # The username has to fit UserAlias.alias (50), not just auth_user (150).
    max_username = UserAlias._meta.get_field('alias').max_length
    max_email = User._meta.get_field('email').max_length
    if (not username or len(username) > max_username
            or not email or len(email) > max_email):
        raise PermissionDenied
    try:
        validate_email(email)
    except ValidationError:
        raise PermissionDenied

    # MySQL's username index is case-insensitive.
    users = User.objects.filter(username__iexact=username)
    if users:
        raise PermissionDenied
        
    if _get_non_social_users_for_email(email):
    #if _get_non_social_users_for_email(email) and email not in TESTER_USERS:
        return HttpResponseRedirect(
            reverse('recover_password_page_from_register',
                    args=(email,)))

    link = request.build_absolute_uri(
        reverse('confirm_email',
                args=(username, _generate_token_for_user(username))))
    try:
        user = User.objects.create_user(username, email, password)
    except IntegrityError:
        raise PermissionDenied
    user.is_active = False
    user.save()
    alias = UserAlias()
    alias.user = user
    alias.alias = username
    alias.save()

    try:
        send_mail(_('Welcome to The Dofus Fashionista!'),
                  _('Please click the link below to confirm your email and activate your '
                    'account.') + '\n' + link,
                  _get_from_email(),
                  [email])
    except (BadHeaderError, SMTPRecipientsRefused, SMTPException):
        logger.exception('Registration email could not be sent to %s', email)
        user.delete()
        return set_response(request,
                            'chardata/recover_password.html',
                            {'request': request,
                             'email': email,
                             'from_register': False,
                             'email_send_failed': True})
    
    ns = request.resolver_match.namespace
    target = f'{ns}:check_your_email' if ns else 'check_your_email'
    return HttpResponseRedirect(reverse(target))

def check_your_email(request):
    return set_response(request,
                        'chardata/check_your_email.html', 
                        {'request': request})

def confirm_email(request, username, confirmation_token):
    if confirmation_token != _generate_token_for_user(username):
        return HttpResponseText('invalid token')
    
    users = User.objects.filter(username=username)

    if not users or len(users) != 1:
        return HttpResponseText('invalid token')
    
    user = users[0]
    if user.is_active:
        return HttpResponseRedirect(reverse('email_confirmed_page',
                                            args=(username, 'yes')))
    
    user.is_active = True
    user.save()
    return HttpResponseRedirect(reverse('email_confirmed_page',
                                        args=(username, 'no')))

def email_confirmed_page(request, username, already_confirmed):
    return _login_page_generic(request, True, username, 0, already_confirmed)

def check_if_taken(request):
    username = request.POST.get('username', None)
    users = User.objects.filter(username__iexact=username)
    if users:
        return HttpResponseText('username-error')
    return HttpResponseText('ok')
  
def local_login(request):
    username = request.POST.get('username', None)
    password = request.POST.get('password', None)
    if login_is_throttled(request, username):
        return HttpResponseText('too-many')
    user = authenticate(username=username, password=password)
    if user is not None:
        clear_login_failures(request, username)
        if user.is_active:
            login(request, user)
            return HttpResponseText('ok')
        else:
            return HttpResponseText('confirm-email')
    else:
        note_login_failure(request, username)
        return HttpResponseText('invalid')

def logout_view(request):
    next_url = request.POST.get('next') or request.GET.get('next')
    
    # Validate the redirect URL - only use if safe, otherwise default to '/'
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        safe_url = next_url
    else:
        safe_url = '/'

    logout(request)
    return HttpResponseRedirect(safe_url)
        
def change_password(request):
    username = request.POST.get('username', None)
    password = request.POST.get('password', None)
    new_password = request.POST.get('newPassword', None)
    if login_is_throttled(request, username):
        return HttpResponseText('too-many')
    user = authenticate(username=username, password=password)
    if user is not None:
        clear_login_failures(request, username)
        user.set_password(new_password)
        user.save()
        return HttpResponseText('ok')
    else:
        note_login_failure(request, username)
        return HttpResponseText('invalid')

def recover_password_email_page(request):
    return set_response(request, 
                        'chardata/pw_recovery_email.html', 
                        {'request': request})
    
    
def recover_password_page_from_register(request, email):
    return _recover_password_page(request, email, from_register=True)
    
def recover_password_page(request):
    email = request.POST.get('email', None)
    return _recover_password_page(request, email, from_register=False)
    
def _recover_password_page(request, email, from_register):
    non_social_users = _get_non_social_users_for_email(email)
    
    if not non_social_users:
        return set_response(request,
                            'chardata/recover_password.html',
                            {'request': request,
                             'email': email,
                             'from_register': from_register,
                             'email_send_failed': False})

    username = non_social_users[0].username
    password = non_social_users[0].password
    
    link = request.build_absolute_uri(
        reverse('recover_password',
                args=(username, _generate_token_for_password_reset(username, password))))
    try:
        send_mail(_('Password change requested for The Dofus Fashionista'),
                  _('A password reset has been requested for The Dofus Fashionista!\n'
                    'Your username is: {username}\n'
                    'Please click the link below to generate a new one for your account.\n'
                    '{link}\n\n'
                    'If you don\'t want to reset your password, just ignore this email.').format(
                        username=username, link=link),
                  _get_from_email(),
                  [email])
    except (BadHeaderError, SMTPRecipientsRefused, SMTPException):
        logger.exception('Password recovery email could not be sent to %s', email)
        return set_response(request,
                            'chardata/recover_password.html',
                            {'request': request,
                             'email': email,
                             'from_register': from_register,
                             'email_send_failed': True})
    return set_response(request,
                        'chardata/recover_password.html', 
                        {'request': request,
                         'email': email,
                         'from_register': from_register,
                         'email_send_failed': False})

def recover_password(request, username, recover_token):
    users = User.objects.filter(username=username)
    
    if not users or len(users) != 1:
        raise PermissionDenied
    
    user = users[0]
    current_password = user.password
    if not _password_reset_token_is_valid(username, current_password, recover_token):
        raise PermissionDenied

    username = user.username
    if request.method != 'POST':
        return set_response(request,
                            'chardata/password_reset_form.html',
                            {'request': request,
                             'username': username,
                             'recover_token': recover_token})

    new_password = request.POST.get('new_password', None)
    confirm_password = request.POST.get('confirm_password', None)
    error_message = None

    if not new_password:
        error_message = _('You need to enter a new password.')
    elif new_password != confirm_password:
        error_message = _('The passwords do not match.')

    if error_message:
        return set_response(request,
                            'chardata/password_reset_form.html',
                            {'request': request,
                             'username': username,
                             'recover_token': recover_token,
                             'error_message': error_message})

    user.set_password(_prehash_password(new_password))
    # Completing the reset proves the email, and local_login rejects inactive
    # accounts.
    user.is_active = True
    user.save()

    return set_response(request,
                        'chardata/password_was_reset.html',
                        {'request': request,
                         'username': username})

EMAIL_CONFIRMATION_SALT = settings.GEN_CONFIGS["EMAIL_CONFIRMATION_SALT"]
def _generate_token_for_user(username):
    return salted_hmac(EMAIL_CONFIRMATION_SALT, username).hexdigest()

PASSWORD_RESET_SALT = settings.GEN_CONFIGS["PASSWORD_RESET_SALT"]


def _password_reset_hmac(username, password):
    return salted_hmac(PASSWORD_RESET_SALT, username + password).hexdigest()


def _generate_token_for_password_reset(username, password):
    """A reset token that stops working.

    The bare HMAC never expired: a reset mail stayed a working key to the
    account for as long as the password was unchanged, which is to say for
    years in an old inbox. Signing it with a timestamp puts Django's
    PASSWORD_RESET_TIMEOUT on it, three days by default. The password hash
    stays inside, so a completed reset still kills every older link at once.
    """
    return TimestampSigner(salt=PASSWORD_RESET_SALT).sign(
        _password_reset_hmac(username, password))


def _password_reset_token_is_valid(username, password, token):
    try:
        signed = TimestampSigner(salt=PASSWORD_RESET_SALT).unsign(
            token, max_age=settings.PASSWORD_RESET_TIMEOUT)
    except (BadSignature, SignatureExpired):
        return False
    return constant_time_compare(signed, _password_reset_hmac(username, password))

def _get_non_social_users_for_email(email):
    non_social_users = []
    for user in User.objects.filter(email=email):
        if not UserSocialAuth.objects.filter(user_id=user.id):
            non_social_users.append(user)
    return non_social_users
