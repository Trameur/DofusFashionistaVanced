# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Builds leaving the site, counted per day, destination, site and version."""

import contextlib
import hashlib
import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.db import Error as DatabaseErrors, transaction
from django.db.models import F
from django.utils import timezone

from chardata.middleware import looks_like_a_robot
from chardata.models import ExportHit
from chardata.text_build_view import (ATTEMPT_SECONDS, UNKNOWN_SITES_PER_DAY,
                                      _site_name)

logger = logging.getLogger(__name__)

DOFUSBOOK = 'dofusbook'
JSON = 'json'
API = 'api'


def counts(request):
    """Browsers only; every browser's user agent starts with Mozilla/."""
    agent = (request.META.get('HTTP_USER_AGENT') or '').lstrip()
    return (request.method != 'HEAD' and agent.startswith('Mozilla/')
            and not looks_like_a_robot(request))


_CRAWLER = re.compile(
    r'bot\b|bot/|crawl|spider|slurp|ahrefs|semrush|mj12|petal|bytespider|'
    r'yandex|baidu|sogou|exabot|seznam|dataprovider|archiver|'
    r'facebookexternalhit|lighthouse|headless|pingdom|uptime|monitor|preview',
    re.I)


def counts_pull(request):
    """Every API caller but a crawler: another site's server pulls builds too."""
    agent = request.META.get('HTTP_USER_AGENT') or ''
    return request.method != 'HEAD' and not _CRAWLER.search(agent)


def requesting_site(request):
    """The domain in Origin, else in Referer, subdomains dropped, or ''."""
    for header in ('HTTP_ORIGIN', 'HTTP_REFERER'):
        site = _site_name((request.META.get(header) or '').strip())
        if site:
            return site
    return ''


def _visitor(request):
    """The session of a build's owner, else the calling address."""
    from chardata.fashionista_build_view import _caller
    session = getattr(request, 'session', None)
    return ((session.session_key if session is not None else None)
            or request.COOKIES.get(settings.CSRF_COOKIE_NAME)
            or _caller(request))


def _add_one(day, version, destination, host):
    key = {'day': day, 'destination': destination, 'host': host,
           'game_version': version}
    plus_one = {'count': F('count') + 1}
    if ExportHit.objects.filter(**key).update(**plus_one):
        return
    if host:
        sites = (ExportHit.objects.filter(day=day, destination=destination)
                 .exclude(host='').values('host'))
        if (not sites.filter(host=host).exists()
                and sites.distinct().count() >= UNKNOWN_SITES_PER_DAY):
            key['host'] = ''
            if ExportHit.objects.filter(**key).update(**plus_one):
                return
    row, created = ExportHit.objects.get_or_create(defaults={'count': 1}, **key)
    if not created:
        ExportHit.objects.filter(pk=row.pk).update(**plus_one)


def _add(day, version, destination, host):
    """False when the database refused, never raised."""
    guard = (transaction.atomic() if transaction.get_connection().in_atomic_block
             else contextlib.nullcontext())
    try:
        with guard:
            _add_one(day, version, destination, host)
    except DatabaseErrors:
        logger.warning('export not counted', exc_info=True)
        return False
    return True


def count(request, destination, char_id, version, host='', rule=counts):
    """One export of the build unless this visitor sent it to that destination lately."""
    if not rule(request):
        return
    trace = '\n'.join((_visitor(request), destination, str(char_id)))
    key = 'exporthit:' + hashlib.sha256(trace.encode('utf-8')).hexdigest()
    if cache.add(key, True, ATTEMPT_SECONDS):
        if not _add(timezone.localdate(), version, destination, host):
            cache.delete(key)
