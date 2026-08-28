
import logging
import re

from django.db.models import F
from django.utils import timezone, translation

from fashionistapulp.structure import set_current_game_version

logger = logging.getLogger(__name__)

GAME_VERSION_PREFIXES = {'beta', 'retro', 'touch', 'dofus2'}

_LANGUAGE_PREFIXES = None


def _language_prefixes():
    """Language codes that can open a path, from settings.LANGUAGES.

    Read once: the set never changes at runtime, and this sits on every
    request.
    """
    global _LANGUAGE_PREFIXES
    if _LANGUAGE_PREFIXES is None:
        from django.conf import settings
        _LANGUAGE_PREFIXES = {code for code, _name in settings.LANGUAGES}
    return _LANGUAGE_PREFIXES

# Not pages anyone reads.
HIT_SKIP = re.compile(r'^/(static|media|api|admin|admin-tools|admin-comment-action|'
                      r'jsi18n|sw\.js|ads\.txt|manifest|favicon|character/)')
# /s/<name>/<id>/ : the name varies per build, so drop the whole tail.
HIT_SHARED = re.compile(r'^/s/.*$')
# An id has a digit or mixed case. Route words are plain lowercase, keep them.
HIT_IDENT = re.compile(r'^(?=.*\d)|^(?=.*[a-z])(?=.*[A-Z])')


class GameVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # The language prefix comes first (/es/dofus2/...), so the version is
        # not always the opening segment. Reading the first segment blindly
        # made every translated page fall back to the default version.
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
    """The shape of a page, for counting hits: ids, versions and languages
    collapsed so one page is one row.

    The language prefix has to go for the same reason the version one does:
    /es/encyclopedia/ and /encyclopedia/ are the same page seen twice, and
    keeping them apart splits every page's history across five rows -- while
    /es/dofus2/encyclopedia/ was worse still, since "dofus2" no longer sat at
    the front and got mistaken for an id.
    """
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


#: Hosts whose visit is a search result rather than a link someone placed.
_SEARCH_HOSTS = ('google.', 'bing.', 'duckduckgo.', 'brave.', 'ecosia.',
                 'yandex.', 'qwant.', 'baidu.', 'yahoo.', 'startpage.',
                 'mojeek.', 'lycos.')

#: Assistants that fetch a page because a reader asked them to. They already
#: send this site more visitors than every social network combined, so they
#: deserve their own line rather than being lost among referrals.
_ASSISTANT_HOSTS = ('chatgpt.com', 'chat.openai.com', 'perplexity.ai',
                    'claude.ai', 'copilot.microsoft.com', 'gemini.google.com')


def _host_of(url):
    """The bare host of a url, without scheme, port, or leading www."""
    host = url.split('//', 1)[-1].split('/', 1)[0].split('?', 1)[0]
    host = host.split('@')[-1].split(':', 1)[0].lower().strip('.')
    return host[4:] if host.startswith('www.') else host


#: What a crawler calls itself. Not a complete list -- no such list exists --
#: but it catches the ones that actually arrive here. A bot is free to lie
#: about its name; the ones that matter do not bother, because they want to be
#: recognised.
_ROBOT = re.compile(
    r'bot\b|bot/|robot|crawl|spider|scrap|slurp|fetch|monitor|uptime|'
    r'pingdom|lighthouse|headless|phantom|selenium|puppeteer|playwright|'
    r'curl/|wget|python-requests|python-urllib|aiohttp|httpx|okhttp|'
    r'go-http-client|java/|libwww|scrapy|axios|node-fetch|guzzle|'
    r'ahrefs|semrush|mj12|dotbot|petal|bytespider|gptbot|claudebot|ccbot|'
    r'amazonbot|applebot|google-extended|meta-external|yandex|baidu|sogou|'
    r'exabot|seznam|dataprovider|feed|rss|preview|validator|archiver|'
    # Link-preview fetchers: they load the page to build the little card shown
    # when someone shares the url in a chat. facebookexternalhit does not call
    # itself a bot, and it was the one that slipped through.
    r'externalhit|whatsapp|telegram|discord|slack|embedly|skypeuri|'
    r'flipboard|nuzzel|vkshare|tumblr|snapchat|pinterest|'
    # Tools that audit this very site. They walk every page in one pass, so a
    # single run buries a month of real reading: one such sweep put 8 420 views
    # into a day whose neighbours hold about thirty.
    r'fashionistaaudit',
    re.I)


def looks_like_a_robot(request):
    """True when the caller announces itself as something other than a reader.

    Without this the count is meaningless: on the first day it recorded 62 130
    arrivals for a site measured at about 16 page views a day, 61 539 of them
    from the United States, all filed as "direct" -- because a crawler sends no
    referrer and every one of them landed in that bucket.

    An empty user agent counts as a robot too. Every browser sends one; a
    client that does not is a script.
    """
    agent = request.META.get('HTTP_USER_AGENT') or ''
    return not agent.strip() or bool(_ROBOT.search(agent))


def arrival_source(request):
    """(source, medium, campaign) when a request is an arrival, else None.

    An arrival is a request that did not come from a link on this site. The
    distinction rests on Django's default referrer policy, `same-origin`: a
    click from one page here to the next carries a referrer on this host, while
    a visitor who typed the address or opened a bookmark carries none. So an
    absent referrer really does mean "came straight here", and a referrer on
    another host really is a link somebody placed somewhere.

    A `utm_source` in the query string wins over the referrer: it is what a
    link handed to a content creator carries, and it is the only way to tell
    apart two visits that a browser reports identically.
    """
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
        return None  # a click inside the site is not a provenance

    if any(host.startswith(s) or ('.' + s) in host for s in _SEARCH_HOSTS):
        return (host.split('.', 1)[0][:100], 'organic', '')
    if host in _ASSISTANT_HOSTS:
        return (host[:100], 'assistant', '')
    return (host[:100], 'referral', '')


def record_arrival(request):
    """Count one arrival, aggregated by day. Stores nothing about the person."""
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
        # Cloudflare puts the country in front of us; 'XX' when it cannot tell.
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
            # Swallowed on purpose: a counter must never take a page down.
            # But swallowed silently, it can stop counting for days without
            # anything saying so -- and a gap in the series is indistinguishable
            # from a day nobody came. Warning, not error: this logger reaches
            # mail_admins at ERROR, and a broken counter would mail on every
            # request.
            logger.warning('page hit not counted for %s', request.path_info,
                           exc_info=True)
        return response

    def count(self, request, response):
        if request.method != 'GET' or response.status_code != 200:
            return
        # A page hit counted a crawler like a reader from the start. The
        # numbers before this change are inflated and cannot be corrected --
        # the user agent was never stored -- but from here they mean what they
        # say.
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
