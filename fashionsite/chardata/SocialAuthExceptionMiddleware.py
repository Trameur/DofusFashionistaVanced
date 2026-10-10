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

import logging

import requests
from social_django.middleware import SocialAuthExceptionMiddleware
from social_core.exceptions import (AuthCanceled, AuthInputError,
                                    AuthProviderError, AuthSessionError,
                                    SocialAuthBaseException)
from django.urls import reverse
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)

# Denied consent, stale or CSRF-failed redirects: client noise
BENIGN_OAUTH_EXCEPTIONS = (AuthCanceled, AuthSessionError)
# Crawlers on /complete/ without the state or code parameter
BENIGN_INPUT_CODES = ('missing_parameter',)

# Query parameter the login page reads to say the social login failed
SOCIAL_FAILED_PARAM = 'social'
SOCIAL_FAILED_VALUE = 'failed'


class SocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def process_exception(self, request, exception):
        if isinstance(exception, BENIGN_OAUTH_EXCEPTIONS) or (
                isinstance(exception, AuthInputError)
                and exception.code in BENIGN_INPUT_CODES):
            return HttpResponseRedirect(reverse('login_page'))
        # Provider unreachable; social_core wraps its own requests, a raw one can still escape
        if isinstance(exception, AuthProviderError) or (
                isinstance(exception, requests.RequestException)
                and getattr(request, 'social_strategy', None) is not None):
            backend = getattr(getattr(request, 'backend', None), 'name',
                              'unknown-backend')
            cause = exception.__cause__ or exception
            logger.error('Social login could not reach the provider on %s: '
                         '%s: %s', backend, type(cause).__name__,
                         cause, exc_info=exception)
            return HttpResponseRedirect('%s?%s=%s' % (
                reverse('login_page'), SOCIAL_FAILED_PARAM,
                SOCIAL_FAILED_VALUE))
        if isinstance(exception, SocialAuthBaseException):
            # No SOCIAL_AUTH_LOGIN_ERROR_URL, so the library would render its bare error page
            backend = getattr(getattr(request, 'backend', None), 'name',
                              'unknown-backend')
            logger.error('Social login failed on %s: %s %s: %s %s', backend,
                         type(exception).__name__, exception.code, exception,
                         exception.detail, exc_info=exception)
            return HttpResponseRedirect('%s?%s=%s' % (
                reverse('login_page'), SOCIAL_FAILED_PARAM,
                SOCIAL_FAILED_VALUE))
        return super().process_exception(request, exception)