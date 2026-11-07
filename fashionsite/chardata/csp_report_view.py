# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Logs what the content security policy would have blocked."""

import json
import logging
import re

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

# A browser report is a few hundred bytes
MAX_CORPS = 8192

# Log lines per minute for one violation
MAX_PAR_MINUTE = 5

# Length of the counting window
FENETRE = 60


_CONTROL_CHARACTERS = re.compile(r'[\x00-\x1f\x7f-\x9f\u2028\u2029]')


def _clean_text(value, limit):
    """The field when it is a string, without control characters, cut short."""
    if not isinstance(value, str):
        return ''
    return _CONTROL_CHARACTERS.sub('', value)[:limit]


def _resume(rapport):
    """(directive, blocked origin, page path), truncated."""
    directive = (_clean_text(rapport.get('effective-directive'), 60)
                 or _clean_text(rapport.get('violated-directive'), 60))
    bloquee = _clean_text(rapport.get('blocked-uri'), 200)
    page = _clean_text(rapport.get('document-uri'), 2000)
    # Path only: the query string may carry what the reader searched
    if '://' in page:
        reste = page.split('://', 1)[1]
        page = '/' + reste.split('/', 1)[1] if '/' in reste else '/'
    page = page.split('?')[0][:120]
    return directive, bloquee, page


@csrf_exempt
@require_POST
def csp_report(request):
    """The browser posts here what the policy would have refused."""
    corps = request.body[:MAX_CORPS + 1]
    if len(corps) > MAX_CORPS:
        return HttpResponseBadRequest('too large')
    try:
        charge = json.loads(corps.decode('utf-8'))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return HttpResponseBadRequest('unreadable')

    rapport = charge.get('csp-report') if isinstance(charge, dict) else None
    if not isinstance(rapport, dict):
        return HttpResponseBadRequest('not a report')

    directive, bloquee, page = _resume(rapport)
    if not directive and not bloquee:
        return HttpResponseBadRequest('empty report')

    cle = 'csp:%s:%s' % (directive, bloquee)
    try:
        vus = cache.get_or_set(cle, 0, FENETRE)
        cache.set(cle, vus + 1, FENETRE)
    except Exception:
        vus = 0
    if vus < MAX_PAR_MINUTE:
        logger.warning('csp would have blocked %s on %s (page %s)',
                       bloquee or '(inline)', directive or '(unknown)', page)

    # 204: the browser expects nothing
    return HttpResponse(status=204)
