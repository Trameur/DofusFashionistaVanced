import re

from django.core.cache import cache
from django.db.models import Sum


def site_stats(request):
    # 'site_stats_v2': the shape changed (per-version breakdown), so use a fresh
    # key rather than serve a stale old-format dict from cache after a deploy.
    stats = cache.get('site_stats_v2')
    if stats is None:
        from django.contrib.auth.models import User
        from chardata.models import Char, SolutionCounter
        per_version = []
        for slug, label in ACTIVE_GAME_VERSIONS:
            characters = Char.objects.filter(game_version=slug).count()
            shared = Char.objects.filter(link_shared=True, deleted=False,
                                         game_version=slug).count()
            runs = (SolutionCounter.objects.filter(game_version=slug)
                    .aggregate(t=Sum('get_count'))['t']) or 0
            # Skip versions with no activity so the sidebar stays uncluttered.
            if characters or shared or runs:
                per_version.append({
                    'label': label,
                    'characters': f"{characters:,}",
                    'solver_runs': f"{runs:,}",
                    'shared_builds': f"{shared:,}",
                })
        stats = {
            'stat_users': f"{User.objects.count():,}",
            'stat_per_version': per_version,
        }
        cache.set('site_stats_v2', stats, 600)
    return stats


ACTIVE_GAME_VERSIONS = [
    ('dofus3', 'Dofus 3'),
    ('beta', 'Beta'),
    ('dofus2', 'Dofus 2'),
    ('touch', 'Touch'),
    ('retro', 'Retro'),
]

_GAME_VERSION_LABELS = dict(ACTIVE_GAME_VERSIONS)

# Word inserted between "Dofus" and "Fashionista" for SEO titles/descriptions,
# e.g. "Dofus Retro Fashionista". Empty for the default (dofus3) version so it
# stays "Dofus Fashionista". Distinct from the dropdown label ("Dofus 2") to
# avoid awkward duplication like "Dofus Dofus 2 Fashionista".
_GAME_VERSION_SEO_WORDS = {
    'dofus3': '',
    'beta': 'Beta',
    'dofus2': '2',
    'retro': 'Retro',
    'touch': 'Touch',
}

_VERSION_PREFIXES = ('beta/', 'dofus2/', 'retro/', 'touch/')
_CHAR_ID_RE = re.compile(r'/\d+/')
# Shared / linked build pages ('/s/<name>/<id>/', '/spells_linked/<name>/<id>/')
# are version-specific too, but their char id is encoded (non-numeric), so the
# numeric check above doesn't catch them.
_LINKED_PREFIXES = ('s/', 'spells_linked/')
_VERSION_SWITCH_NUMERIC_SAFE_PREFIXES = ('encyclopedia/',)


def game_version(request):
    path = request.path_info
    base_path = path
    stripped = path.lstrip('/')
    gv = getattr(request, 'game_version', 'dofus3')
    for prefix in _VERSION_PREFIXES:
        if stripped.startswith(prefix):
            base_path = '/' + stripped[len(prefix):]
            break
    base_stripped = base_path.lstrip('/')
    # Char-specific pages don't translate across versions, a build exists in
    # only one game version. Send the version switcher to home instead of a
    # broken URL. Owned pages carry a numeric id; shared/linked pages an encoded one.
    # Encyclopedia pages are public versioned data, so keep their numeric ids.
    safe_numeric_path = base_stripped.startswith(_VERSION_SWITCH_NUMERIC_SAFE_PREFIXES)
    if (not safe_numeric_path
            and (_CHAR_ID_RE.search(base_path)
                 or base_stripped.startswith(_LINKED_PREFIXES))):
        base_path = '/'

    # api_base is the URL prefix for AJAX calls: '' for dofus3, '/beta' for beta, etc.
    api_base = '' if gv == 'dofus3' else f'/{gv}'

    return {
        'current_game_version': gv,
        'current_game_version_label': _GAME_VERSION_LABELS.get(gv, 'Dofus 3'),
        'current_game_version_seo': _GAME_VERSION_SEO_WORDS.get(gv, ''),
        'active_game_versions': ACTIVE_GAME_VERSIONS,
        'version_switch_base_path': base_path,
        'api_base': api_base,
    }
