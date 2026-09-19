# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Logs what the content security policy would have blocked."""

import json
import logging

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


def _resume(rapport):
    """(directive, blocked origin, page path), truncated."""
    directive = (rapport.get('effective-directive')
                 or rapport.get('violated-directive') or '')[:60]
    bloquee = (rapport.get('blocked-uri') or '')[:200]
    page = (rapport.get('document-uri') or '')
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
    except (ValueError, UnicodeDecodeError):
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
