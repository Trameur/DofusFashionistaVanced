# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""A ceiling on the solves a host runs at once, and on the solves one client starts.

A solve holds a gunicorn worker for as long as the search runs. Without a ceiling a
handful of parallel requests keeps every worker busy and the pages wait behind them.

    with solver_turn(request, char):
        ... solve ...

raises SolverRefused when no slot is free or the client has asked for too many solves,
and refused_response() turns that into the page the player sees.

The slots are lock files, so every worker of the host shares them and the operating
system frees a slot when its holder dies. A host that sets no slot count has no
ceiling at all.
"""
import contextlib
import logging
import os
import tempfile

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:
    fcntl = None
    import msvcrt

RETRY_AFTER_SECONDS = 15

CLIENT_WINDOW = 600
SOLVES_PER_CLIENT = 40
SOLVES_PER_ADDRESS = 120

BUSY = 'busy'
TOO_MANY = 'too_many'


class SolverRefused(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def slot_count():
    value = getattr(settings, 'SOLVER_SLOTS', None)
    if value in (None, ''):
        value = os.environ.get('SOLVER_SLOTS', 0)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _slot_directory():
    return getattr(settings, 'SOLVER_SLOT_DIR', None) or tempfile.gettempdir()


def _try_lock(descriptor):
    try:
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    except OSError:
        return False
    return True


def _unlock(descriptor):
    if fcntl is not None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    else:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)


def _take_slot(slots):
    """The descriptor of a slot now held, None when every slot is taken."""
    directory = _slot_directory()
    os.makedirs(directory, exist_ok=True)
    for number in range(slots):
        descriptor = os.open(os.path.join(directory, 'solver-slot-%d.lock' % number),
                             os.O_RDWR | os.O_CREAT, 0o600)
        if _try_lock(descriptor):
            return descriptor
        os.close(descriptor)
    return None


def _release_slot(descriptor):
    try:
        _unlock(descriptor)
    finally:
        os.close(descriptor)


def _client_ceilings(request):
    from chardata.fashionista_build_view import _caller
    ceilings = []
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        ceilings.append(('solve-user:%s' % user.pk, SOLVES_PER_CLIENT))
    else:
        session = getattr(request, 'session', None)
        session_key = getattr(session, 'session_key', None)
        if session_key:
            ceilings.append(('solve-session:%s' % session_key, SOLVES_PER_CLIENT))
    address = _caller(request)
    if address != 'unknown':
        ceilings.append(('solve-address:%s' % address, SOLVES_PER_ADDRESS))
    return ceilings


@contextlib.contextmanager
def solver_turn(request, char):
    """Holds a solver slot for the length of the block; blocks must not nest."""
    slots = slot_count()
    if not slots:
        yield
        return
    from chardata.rate_limit import hits, note_hit
    ceilings = _client_ceilings(request)
    if any(hits(key, CLIENT_WINDOW) >= ceiling for key, ceiling in ceilings):
        raise SolverRefused(TOO_MANY)
    try:
        descriptor = _take_slot(slots)
    except OSError:
        logger.warning('the solver slots could not be opened in %s; solving without a ceiling',
                       _slot_directory(), exc_info=True)
        descriptor = False
    if descriptor is False:
        yield
        return
    if descriptor is None:
        raise SolverRefused(BUSY)
    try:
        for key, _ceiling in ceilings:
            note_hit(key, CLIENT_WINDOW)
        yield
    finally:
        _release_slot(descriptor)


def refused_response(request, char, reason):
    """The 429 page: a GET route refreshes itself, a POST route points back at the build."""
    from chardata.util import set_response, version_reverse
    again_by_itself = request.method == 'GET' and reason == BUSY
    if request.method == 'GET':
        retry_url = request.get_full_path()
    else:
        retry_url = version_reverse(request, 'solution_2', char.id)
    response = set_response(request, 'chardata/solver_busy.html',
                            {'request': request,
                             'user': request.user,
                             'char_id': 0,
                             'noindex': True,
                             'reason': reason,
                             'retry_url': retry_url,
                             'refresh_seconds': RETRY_AFTER_SECONDS if again_by_itself else 0})
    response.status_code = 429
    response['Retry-After'] = str(CLIENT_WINDOW if reason == TOO_MANY
                                  else RETRY_AFTER_SECONDS)
    response['Cache-Control'] = 'no-store'
    return response
