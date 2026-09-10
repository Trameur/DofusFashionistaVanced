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
from social_core.exceptions import (AuthCanceled, AuthMissingParameter,
                                    AuthStateMissing, AuthStateForbidden,
                                    SocialAuthBaseException)
from django.urls import reverse
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)

# Cancelled or malformed OAuth callbacks: denied consent, crawlers hitting
# /complete/, stale or CSRF-failed redirects. Client noise, not server errors.
BENIGN_OAUTH_EXCEPTIONS = (AuthCanceled, AuthMissingParameter,
                           AuthStateMissing, AuthStateForbidden)

# Le marqueur que la page de connexion lit pour dire au lecteur que Google
# n'a pas abouti. Un parametre plutot que le cadre `messages`: la page ne
# l'affiche pas, et c'est exactement ce qui a fait durer la faute ci-dessous.
SOCIAL_FAILED_PARAM = 'social'
SOCIAL_FAILED_VALUE = 'failed'


class SocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def process_exception(self, request, exception):
        if isinstance(exception, BENIGN_OAUTH_EXCEPTIONS):
            return HttpResponseRedirect(reverse('login_page'))
        # Google injoignable pendant la connexion. Le 28 aout 2026 a 13h43,
        # un lecteur argentin a eu la meme page <<Internal Server Error>>:
        # la poignee de main TLS avec accounts.google.com a depasse les 5 s
        # de social_core, qui n'emballe que `requests.ConnectionError` (en
        # AuthConnectionError) et laisse passer `ReadTimeout` et tout autre
        # `RequestException`, dont un HTTPError d'un statut qu'il ne connait
        # pas. Seulement dans les vues sociales, reconnues a la strategie
        # que le decorateur `psa` pose sur la requete: une panne reseau
        # ailleurs sur le site n'est pas un echec de connexion.
        if (isinstance(exception, requests.RequestException)
                and getattr(request, 'social_strategy', None) is not None):
            backend = getattr(getattr(request, 'backend', None), 'name',
                              'unknown-backend')
            logger.error('Social login could not reach the provider on %s: '
                         '%s: %s', backend, type(exception).__name__,
                         exception, exc_info=exception)
            return HttpResponseRedirect('%s?%s=%s' % (
                reverse('login_page'), SOCIAL_FAILED_PARAM,
                SOCIAL_FAILED_VALUE))
        if isinstance(exception, SocialAuthBaseException):
            # Le 8 septembre 2026 a 21h37, un lecteur espagnol a eu une page
            # <<Internal Server Error>> en se connectant avec Google: le
            # point userinfo de Google a repondu 401, social_core l'a
            # emballe en AuthForbidden, et le middleware de la bibliotheque
            # n'a rien fait de plus qu'un `messages.error` que personne
            # n'affiche, parce que SOCIAL_AUTH_LOGIN_ERROR_URL n'est pas
            # defini: sans adresse, il rend None et l'exception traverse.
            #
            # Le lecteur retourne a la page de connexion avec une phrase, et
            # l'erreur reste journalisee au niveau ERROR, donc envoyee par
            # mail comme avant: une seule connexion Google qui echoue n'est
            # pas une panne, mais toutes qui echouent en est une, et c'est
            # ce mail qui l'a fait voir.
            backend = getattr(getattr(request, 'backend', None), 'name',
                              'unknown-backend')
            logger.error('Social login failed on %s: %s: %s', backend,
                         type(exception).__name__, exception,
                         exc_info=exception)
            return HttpResponseRedirect('%s?%s=%s' % (
                reverse('login_page'), SOCIAL_FAILED_PARAM,
                SOCIAL_FAILED_VALUE))
        return super().process_exception(request, exception)