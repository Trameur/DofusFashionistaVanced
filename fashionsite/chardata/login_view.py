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
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.mail import send_mail, BadHeaderError
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from smtplib import SMTPRecipientsRefused
from social_django.models import UserSocialAuth
import hashlib

from chardata.models import UserAlias
from chardata.util import set_response, TESTER_USERS, HttpResponseText
from django.utils.translation import gettext as _

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
    username = request.POST.get('username', None)
    password = request.POST.get('password', None)
    email = request.POST.get('email', None)
    
    users = User.objects.filter(username=username)
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
        send_mail(_('Welcome to The Dofus Fashionista!'),
                  _('Please click the link below to confirm your email and activate your '
                    'account.') + '\n' + link,
                  'DofusFashionistaVanced@gmail.com',
                  [email])
    except (BadHeaderError, SMTPRecipientsRefused) as e:
        raise e
        
    user = User.objects.create_user(username, email, password)
    user.is_active = False
    user.save()
    alias = UserAlias()
    alias.user = user
    alias.alias = username
    alias.save()
    
    return HttpResponseRedirect(reverse('check_your_email'))

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
    users = User.objects.filter(username=username)
    if users:
        return HttpResponseText('username-error')
    return HttpResponseText('ok')
  
def local_login(request):
    username = request.POST.get('username', None)
    password = request.POST.get('password', None)
    user = authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            login(request, user)
            return HttpResponseText('ok')
        else:
            return HttpResponseText('confirm-email')
    else:
        return HttpResponseText('invalid')

def logout_view(request):
    next_url = request.POST.get('next') or request.GET.get('next') or '/'
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = '/'

    logout(request)
    return HttpResponseRedirect(next_url)
        
def change_password(request):
    username = request.POST.get('username', None)
    password = request.POST.get('password', None)
    new_password = request.POST.get('newPassword', None)
    user = authenticate(username=username, password=password)
    if user is not None:
        user.set_password(new_password)
        user.save()
        return HttpResponseText('ok')
    else:
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
        raise SuspiciousOperation

    username = non_social_users[0].username
    password = non_social_users[0].password
    
    link = request.build_absolute_uri(
        reverse('recover_password',
                args=(username, _generate_token_for_password_reset(username, password))))
    try:
        send_mail(_('Password change requested for The Dofus Fashionista'),
                  _('A password reset has been requested for The Dofus Fashionista!\n'
                    'Please click the link below to generate a new one for your account.\n'
                    '{link}\n\n'
                    'If you don\'t want to reset your password, just ignore this email.').format(
                        link=link),
                  'DofusFashionistaVanced@gmail.com',
                  [email])
    except (BadHeaderError, SMTPRecipientsRefused) as e:
        raise e
    return set_response(request,
                        'chardata/recover_password.html', 
                        {'request': request,
                         'email': email,
                         'from_register': from_register})

def recover_password(request, username, recover_token):
    users = User.objects.filter(username=username)
    
    if not users or len(users) != 1:
        raise PermissionDenied
    
    user = users[0]
    current_password = user.password
    correct_token = _generate_token_for_password_reset(username, current_password)
    if correct_token != recover_token:
        raise PermissionDenied
        
    username = user.username
    new_password = User.objects.make_random_password()
    user.set_password(hashlib.sha256(('dofusfashionista' + new_password).encode('utf-8')).hexdigest())
    user.save()
    
    try:
        send_mail(_('Password for The Dofus Fashionista has been reset'),
                  _('Hello, {username}!\n'
                    'The following password has been generated for you:\n\n'
                    '{new_password}\n\n'
                    'Change it to a new one or just keep this email ;-)').format(
                        username=username, new_password=new_password),
                  'DofusFashionistaVanced@gmail.com',
                  [user.email])
    except (BadHeaderError, SMTPRecipientsRefused) as e:
        raise e
        
    return set_response(request,
                        'chardata/password_was_reset.html', 
                        {'request': request,
                         'username': username,
                         'new_password': new_password})

EMAIL_CONFIRMATION_SALT = settings.GEN_CONFIGS["EMAIL_CONFIRMATION_SALT"]
def _generate_token_for_user(username):
    return hashlib.sha256((EMAIL_CONFIRMATION_SALT + username).encode('utf-8')).hexdigest()

PASSWORD_RESET_SALT = settings.GEN_CONFIGS["PASSWORD_RESET_SALT"]
def _generate_token_for_password_reset(username, password):
    return hashlib.sha256((PASSWORD_RESET_SALT + username + password).encode('utf-8')).hexdigest()

def _get_non_social_users_for_email(email):
    non_social_users = []
    for user in User.objects.filter(email=email):
        if not UserSocialAuth.objects.filter(user_id=user.id):
            non_social_users.append(user)
    return non_social_users
