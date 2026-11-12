
import logging
import re

from django.core import signing
from django.db.models import F
from django.utils import timezone, translation
from django.utils.html import format_html

from fashionistapulp.structure import set_current_game_version
from static_s3.templatetags.static_s3 import static

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
# /spells_linked/<name>/<id>/ : same, the name is a character name.
HIT_LINKED = re.compile(r'^/spells_linked/.+$')
# These routes carry an account name right after the route word, and an old name can hold a slash.
HIT_NAMED = re.compile(r'^/(user|email_confirmed|confirm_email|do_recover_password)/.+$')
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
    if HIT_LINKED.match(path):
        return '/spells_linked/<build>/'
    named = HIT_NAMED.match(path)
    if named:
        return '/%s/<id>/' % named.group(1)
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
    r'pingdom|lighthouse|headless|phantom|selenium|puppeteer|playwright|lightpanda|'
    r'curl/|wget|python-requests|python-urllib|aiohttp|httpx|okhttp|'
    r'go-http-client|java/|libwww|scrapy|axios|node-fetch|guzzle|'
    r'ahrefs|semrush|mj12|dotbot|petal|bytespider|gptbot|claudebot|ccbot|'
    r'amazonbot|applebot|google-extended|meta-external|yandex|baidu|sogou|'
    r'meta-webindexer|'
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


def arrival_source(utm_source, utm_medium, utm_campaign, referrer, own_host):
    """(source, medium, campaign) when a page view is an arrival, else None."""
    given = (utm_source or '').strip()
    if given:
        return (given[:100].lower(),
                (utm_medium or 'utm').strip()[:40].lower(),
                (utm_campaign or '').strip()[:60].lower())

    referrer = (referrer or '').strip()
    if not referrer:
        return ('direct', 'none', '')

    host = _host_of(referrer)
    if not host or host == _host_of(own_host):
        return None

    if any(host.startswith(s) or ('.' + s) in host for s in _SEARCH_HOSTS):
        return (host.split('.', 1)[0][:100], 'organic', '')
    if host in _ASSISTANT_HOSTS:
        return (host[:100], 'assistant', '')
    return (host[:100], 'referral', '')


# Distinct (source, medium, campaign) a day may open; the rest count as other
VISIT_SOURCES_PER_DAY = 300

OVERFLOW_SOURCE = 'other'


def _source_has_room(day, source, medium, campaign):
    from chardata.models import VisitSource
    today = VisitSource.objects.filter(day=day)
    if today.filter(source=source, medium=medium, campaign=campaign).exists():
        return True
    distinct = today.values('source', 'medium', 'campaign').distinct().count()
    return distinct < VISIT_SOURCES_PER_DAY


def record_arrival(found, language, country):
    """Count one arrival from arrival_source, aggregated by day."""
    if found is None:
        return
    source, medium, campaign = found
    from chardata.models import VisitSource
    key = {
        'day': timezone.localdate(),
        'source': source, 'medium': medium, 'campaign': campaign,
        'language': language[:10],
        # Set by Cloudflare, 'XX' when unknown
        'country': country[:2].upper(),
    }
    updated = VisitSource.objects.filter(**key).update(count=F('count') + 1)
    if not updated:
        if not _source_has_room(key['day'], source, medium, campaign):
            key.update(source=OVERFLOW_SOURCE, medium=OVERFLOW_SOURCE, campaign='')
            if VisitSource.objects.filter(**key).update(count=F('count') + 1):
                return
        VisitSource.objects.get_or_create(defaults={'count': 1}, **key)


class PrivateForSignedInMiddleware:
    """A signed-in reader's page is theirs: no shared cache keeps it for the next visitor."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (not response.has_header('Cache-Control')
                and response.get('Content-Type', '').startswith('text/html')
                and self._signed_in(request)):
            response['Cache-Control'] = 'private, no-store'
        return response

    @staticmethod
    def _signed_in(request):
        from django.conf import settings
        if settings.SESSION_COOKIE_NAME not in request.COOKIES:
            return False
        user = getattr(request, 'user', None)
        return bool(user is not None and user.is_authenticated)


SEEN_SALT = 'chardata.page_seen'

# A later report is a tab left aside or a token kept for replay
SEEN_TOKEN_SECONDS = 3600


def seen_token(path, version, language, build=None):
    """What the server vouches for: it served this page, in this version and language."""
    claim = {'p': path, 'v': version, 'l': language}
    if build:
        claim['b'] = build
    return signing.dumps(claim, salt=SEEN_SALT)


def read_seen_token(token):
    """The claim when the token is ours and recent, else None."""
    try:
        return signing.loads(token, salt=SEEN_SALT, max_age=SEEN_TOKEN_SECONDS)
    except signing.BadSignature:
        return None


class PageHitMiddleware:
    """Hands each countable page the script that reports it. Never breaks the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self.offer_the_report(request, response)
        except Exception:
            # Warning, not error: ERROR mails the admins on every request
            logger.warning('page hit not counted for %s', request.path_info,
                           exc_info=True)
        return response

    def offer_the_report(self, request, response):
        if request.method != 'GET' or response.status_code != 200 or response.streaming:
            return
        if not response.get('Content-Type', '').startswith('text/html'):
            return
        path = request.path_info
        if HIT_SKIP.match(path):
            return
        end_of_body = response.content.rfind(b'</body>')
        if end_of_body < 0:
            return
        version = getattr(request, 'game_version', 'dofus3')
        token = seen_token(normalise_path(path, version), version,
                           translation.get_language() or '',
                           getattr(request, 'seen_build', None))
        script = format_html('<script src="{}" data-seen="{}" defer></script>',
                             static('chardata/seen.js'), token)
        response.content = (response.content[:end_of_body] + script.encode('utf-8')
                            + response.content[end_of_body:])
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
