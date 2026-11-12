# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Counts a page once a browser reports having shown it to someone."""
import logging
from datetime import timedelta
from urllib.parse import urlsplit

from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from chardata.encoded_char_id import decode_char_id
from chardata.middleware import (arrival_source, looks_like_a_robot,
                                 read_seen_token, record_arrival)
from chardata.models import BuildView, Char, PageHit
from chardata.solution_view import get_client_ip

logger = logging.getLogger(__name__)

# A report is a token and a few short fields
MAX_BODY = 4096

ONE_VIEW_PER_ADDRESS_EVERY = timedelta(hours=24)


def _from_our_own_page(request):
    """Browsers say where a report comes from. Other clients can lie: the token and the nginx limit cover those."""
    if request.META.get('HTTP_SEC_FETCH_SITE', 'same-origin') != 'same-origin':
        return False
    origin = request.META.get('HTTP_ORIGIN')
    return not origin or urlsplit(origin).netloc == request.get_host()


def _count_the_page(request, claim):
    key = {'day': timezone.localdate(), 'path': claim['p'], 'game_version': claim['v']}
    updated = PageHit.objects.filter(**key).update(count=F('count') + 1)
    if not updated:
        PageHit.objects.get_or_create(defaults={'count': 1}, **key)


def _count_the_arrival(request, claim):
    record_arrival(
        arrival_source(request.POST.get('us'), request.POST.get('um'),
                       request.POST.get('uc'), request.POST.get('r'),
                       request.get_host()),
        claim['l'], request.META.get('HTTP_CF_IPCOUNTRY') or '')


def _count_the_build_view(request, claim):
    if not claim.get('b'):
        return
    build_id = decode_char_id(claim['b'])
    address = get_client_ip(request)
    if build_id is None or not address:
        return
    window_start = timezone.now() - ONE_VIEW_PER_ADDRESS_EVERY
    views = BuildView.objects.filter(build_id=build_id)
    if views.filter(ip_address=address, viewed_at__gte=window_start).exists():
        return
    # Not char.save(): it rewrites every blob and bumps modified_time
    bumped = (Char.objects.filter(pk=build_id, deleted=False, link_shared=True)
              .update(view_count=F('view_count') + 1))
    if not bumped:
        return
    BuildView.objects.create(build_id=build_id, ip_address=address)
    # cleanup_old_views only runs at deploy, prune here too
    views.filter(viewed_at__lt=window_start).delete()


def _count(request):
    if (not _from_our_own_page(request) or looks_like_a_robot(request)
            or len(request.body) > MAX_BODY):
        return
    claim = read_seen_token(request.POST.get('t', ''))
    if claim is None:
        return
    for counter in (_count_the_page, _count_the_arrival, _count_the_build_view):
        try:
            counter(request, claim)
        except Exception:
            # Warning, not error: ERROR mails the admins on every request
            logger.warning('%s failed', counter.__name__, exc_info=True)


@csrf_exempt
@require_POST
def page_seen(request):
    """Answers the same whatever it makes of the report: a refused one learns nothing."""
    try:
        _count(request)
    except Exception:
        # Warning, not error: ERROR mails the admins on every request
        logger.warning('page report not counted', exc_info=True)
    answer = HttpResponse(status=204)
    # Without a type, nothing downstream reads the session for an empty answer
    del answer['Content-Type']
    return answer
