
import re

from django.db.models import F
from django.utils import timezone

from fashionistapulp.structure import set_current_game_version

GAME_VERSION_PREFIXES = {'beta', 'retro', 'touch', 'dofus2'}

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
        parts = request.path_info.lstrip('/').split('/', 1)
        if parts[0] in GAME_VERSION_PREFIXES:
            version = parts[0]
        else:
            version = 'dofus3'
        request.game_version = version
        set_current_game_version(version)
        return self.get_response(request)


def normalise_path(path, version):
    if version != 'dofus3' and path.startswith('/' + version):
        path = path[len(version) + 1:] or '/'
    if HIT_SHARED.match(path):
        return '/s/<build>/'
    parts = []
    for segment in path.split('/'):
        parts.append('<id>' if segment and HIT_IDENT.match(segment) else segment)
    return '/'.join(parts)[:200]


class PageHitMiddleware:
    """One counter per page per day. Never breaks the request it counts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self.count(request, response)
        except Exception:
            pass
        return response

    def count(self, request, response):
        if request.method != 'GET' or response.status_code != 200:
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
