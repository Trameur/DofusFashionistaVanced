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

from social_django.middleware import SocialAuthExceptionMiddleware
from social_core.exceptions import (AuthCanceled, AuthMissingParameter,
                                    AuthStateMissing, AuthStateForbidden)
from django.urls import reverse
from django.http import HttpResponseRedirect

# OAuth callbacks that arrive cancelled, malformed, or with a missing/forbidden state
# token (denied consent, crawlers hitting /complete/, stale or CSRF-failed redirects)
# are normal client-side noise, not server errors. Redirect them to login quietly
# instead of 500ing + emailing the admins on every bot hit. Real auth failures
# (AuthFailed, AuthForbidden, AuthAlreadyAssociated…) still fall through to the parent.
BENIGN_OAUTH_EXCEPTIONS = (AuthCanceled, AuthMissingParameter,
                           AuthStateMissing, AuthStateForbidden)

class SocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def process_exception(self, request, exception):
        if isinstance(exception, BENIGN_OAUTH_EXCEPTIONS):
            return HttpResponseRedirect(reverse('login_page'))
        return super().process_exception(request, exception)