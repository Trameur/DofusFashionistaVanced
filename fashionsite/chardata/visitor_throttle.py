# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Ceilings per session and per address for what a visitor can start.

    if reached(request, 'import-post', 3600, 40, 120): ...
    note(request, 'import-post', 3600, 40, 120)

A request without a session cookie is counted by its CSRF cookie, and with
neither only by its address.
"""
import hashlib

from django.conf import settings

from chardata.rate_limit import hits, note_hit


def _visitor(request):
    session = getattr(request, 'session', None)
    token = (getattr(session, 'session_key', None)
             or request.COOKIES.get(settings.CSRF_COOKIE_NAME))
    if not token:
        return None
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:24]


def _keys(request, name, per_session, per_address):
    from chardata.fashionista_build_view import _caller
    keys = [('%s-address:%s' % (name, _caller(request)), per_address)]
    visitor = _visitor(request)
    if visitor:
        keys.append(('%s-session:%s' % (name, visitor), per_session))
    return keys


def reached(request, name, window, per_session, per_address):
    return any(hits(key, window) >= ceiling
               for key, ceiling in _keys(request, name, per_session, per_address))


def note(request, name, window, per_session, per_address):
    session = getattr(request, 'session', None)
    if session is not None and session.session_key is None and session.modified:
        session.save()
    for key, _ceiling in _keys(request, name, per_session, per_address):
        note_hit(key, window)
