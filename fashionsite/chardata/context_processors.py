import re

from django.core.cache import cache
from django.db.models import Sum


def site_stats(request):
    stats = cache.get('site_stats')
    if stats is None:
        from django.contrib.auth.models import User
        from chardata.models import Char, SolutionCounter
        solver_runs = SolutionCounter.objects.aggregate(t=Sum('get_count'))['t'] or 0
        stats = {
            'stat_users': f"{User.objects.count():,}",
            'stat_characters': f"{Char.objects.count():,}",
            'stat_solver_runs': f"{solver_runs:,}",
            'stat_shared_builds': f"{Char.objects.filter(link_shared=True, deleted=False).count():,}",
        }
        cache.set('site_stats', stats, 600)
    return stats


ACTIVE_GAME_VERSIONS = [
    ('dofus3', 'Dofus 3'),
    ('beta', 'Beta'),
    ('dofus2', 'Dofus 2'),
    ('retro', 'Retro'),
]

_VERSION_PREFIXES = ('beta/', 'dofus2/', 'retro/', 'touch/')
_CHAR_ID_RE = re.compile(r'/\d+/')


def game_version(request):
    path = request.path_info
    base_path = path
    stripped = path.lstrip('/')
    gv = getattr(request, 'game_version', 'dofus3')
    for prefix in _VERSION_PREFIXES:
        if stripped.startswith(prefix):
            base_path = '/' + stripped[len(prefix):]
            break
    # Char-specific pages (containing a numeric ID) don't translate across versions.
    # Send the version switcher to home instead of a broken URL.
    if _CHAR_ID_RE.search(base_path):
        base_path = '/'

    # api_base is the URL prefix for AJAX calls: '' for dofus3, '/beta' for beta, etc.
    api_base = '' if gv == 'dofus3' else f'/{gv}'

    return {
        'current_game_version': gv,
        'active_game_versions': ACTIVE_GAME_VERSIONS,
        'version_switch_base_path': base_path,
        'api_base': api_base,
    }
