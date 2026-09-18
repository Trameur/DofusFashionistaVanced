
import logging
import re

from django.db.models import F
from django.utils import timezone, translation

from fashionistapulp.structure import set_current_game_version

logger = logging.getLogger(__name__)

GAME_VERSION_PREFIXES = {'beta', 'retro', 'touch', 'dofus2'}

_LANGUAGE_PREFIXES = None


def _language_prefixes():
    """Language codes from settings.LANGUAGES, read once."""
    global _LANGUAGE_PREFIXES
    if _LANGUAGE_PREFIXES is None:
        from django.conf import settings
        _LANGUAGE_PREFIXES = {code for code, _name in settings.LANGUAGES}
    return _LANGUAGE_PREFIXES

# Not pages anyone reads.
HIT_SKIP = re.compile(r'^/(static|media|api|admin|admin-tools|admin-comment-action|'
                      r'jsi18n|sw\.js|offline/|ads\.txt|manifest|favicon|character/)')
# /s/<name>/<id>/ : the name varies per build, so drop the whole tail.
HIT_SHARED = re.compile(r'^/s/.*$')
# An id has a digit or mixed case. Route words are plain lowercase, keep them.
HIT_IDENT = re.compile(r'^(?=.*\d)|^(?=.*[a-z])(?=.*[A-Z])')


class GameVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Language prefix comes first: /es/dofus2/...
        parts = request.path_info.lstrip('/').split('/')
        if parts and parts[0] in _language_prefixes():
            parts = parts[1:]
        if parts and parts[0] in GAME_VERSION_PREFIXES:
            version = parts[0]
        else:
            version = 'dofus3'
        request.game_version = version
        set_current_game_version(version)
        return self.get_response(request)


def normalise_path(path, version):
    """Path for hit counting, ids, version and language collapsed."""
    parts = path.lstrip('/').split('/', 1)
    if parts and parts[0] in _language_prefixes():
        path = '/' + (parts[1] if len(parts) > 1 else '')
    if version != 'dofus3' and path.startswith('/' + version):
        path = path[len(version) + 1:] or '/'
    if HIT_SHARED.match(path):
        return '/s/<build>/'
    parts = []
    for segment in path.split('/'):
        parts.append('<id>' if segment and HIT_IDENT.match(segment) else segment)
    return '/'.join(parts)[:200]


# Search engines
_SEARCH_HOSTS = ('google.', 'bing.', 'duckduckgo.', 'brave.', 'ecosia.',
                 'yandex.', 'qwant.', 'baidu.', 'yahoo.', 'startpage.',
                 'mojeek.', 'lycos.')

# AI assistants, counted apart from referrals
_ASSISTANT_HOSTS = ('chatgpt.com', 'chat.openai.com', 'perplexity.ai',
                    'claude.ai', 'copilot.microsoft.com', 'gemini.google.com')


def _host_of(url):
    """The bare host of a url, without scheme, port, or leading www."""
    host = url.split('//', 1)[-1].split('/', 1)[0].split('?', 1)[0]
    host = host.split('@')[-1].split(':', 1)[0].lower().strip('.')
    return host[4:] if host.startswith('www.') else host


# Crawler user agents, not exhaustive
_ROBOT = re.compile(
    r'bot\b|bot/|robot|crawl|spider|scrap|slurp|fetch|monitor|uptime|'
    r'pingdom|lighthouse|headless|phantom|selenium|puppeteer|playwright|'
    r'curl/|wget|python-requests|python-urllib|aiohttp|httpx|okhttp|'
    r'go-http-client|java/|libwww|scrapy|axios|node-fetch|guzzle|'
    r'ahrefs|semrush|mj12|dotbot|petal|bytespider|gptbot|claudebot|ccbot|'
    r'amazonbot|applebot|google-extended|meta-external|yandex|baidu|sogou|'
    r'exabot|seznam|dataprovider|feed|rss|preview|validator|archiver|'
    # Link previews, facebookexternalhit doesn't say bot
    r'externalhit|whatsapp|telegram|discord|slack|embedly|skypeuri|'
    r'flipboard|nuzzel|vkshare|tumblr|snapchat|pinterest|'
    # Our own site audits
    r'fashionistaaudit',
    re.I)


def looks_like_a_robot(request):
    """True for a crawler user agent or an empty one."""
    agent = request.META.get('HTTP_USER_AGENT') or ''
    return not agent.strip() or bool(_ROBOT.search(agent))


def arrival_source(request):
    """(source, medium, campaign) when a request is an arrival, else None."""
    given = (request.GET.get('utm_source') or '').strip()
    if given:
        return (given[:100].lower(),
                (request.GET.get('utm_medium') or 'utm').strip()[:40].lower(),
                (request.GET.get('utm_campaign') or '').strip()[:60].lower())

    referrer = (request.META.get('HTTP_REFERER') or '').strip()
    if not referrer:
        return ('direct', 'none', '')

    host = _host_of(referrer)
    if not host or host == _host_of(request.get_host()):
        return None

    if any(host.startswith(s) or ('.' + s) in host for s in _SEARCH_HOSTS):
        return (host.split('.', 1)[0][:100], 'organic', '')
    if host in _ASSISTANT_HOSTS:
        return (host[:100], 'assistant', '')
    return (host[:100], 'referral', '')


def record_arrival(request):
    """Count one arrival, aggregated by day."""
    if looks_like_a_robot(request):
        return
    found = arrival_source(request)
    if found is None:
        return
    source, medium, campaign = found
    from chardata.models import VisitSource
    key = {
        'day': timezone.localdate(),
        'source': source, 'medium': medium, 'campaign': campaign,
        'language': (translation.get_language() or '')[:10],
        # Set by Cloudflare, 'XX' when unknown
        'country': (request.META.get('HTTP_CF_IPCOUNTRY') or '')[:2].upper(),
    }
    updated = VisitSource.objects.filter(**key).update(count=F('count') + 1)
    if not updated:
        VisitSource.objects.get_or_create(defaults={'count': 1}, **key)


class PageHitMiddleware:
    """One counter per page per day. Never breaks the request it counts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self.count(request, response)
        except Exception:
            # Warning, not error: ERROR mails the admins on every request
            logger.warning('page hit not counted for %s', request.path_info,
                           exc_info=True)
        return response

    def count(self, request, response):
        if request.method != 'GET' or response.status_code != 200:
            return
        if looks_like_a_robot(request):
            return
        if not response.get('Content-Type', '').startswith('text/html'):
            return
        path = request.path_info
        if HIT_SKIP.match(path):
            return
        from chardata.models import PageHit
        version = getattr(request, 'game_version', 'dofus3')
        key = {'day': timezone.localdate(), 'path': normalise_path(path, version),
               'game_version': version}
        updated = PageHit.objects.filter(**key).update(count=F('count') + 1)
        if not updated:
            PageHit.objects.get_or_create(defaults={'count': 1}, **key)
        record_arrival(request)
