import json
import re

from django.core.cache import cache
from django.db.models import Sum


def site_stats(request):
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

# Word inserted between "Dofus" and "Fashionista" in SEO titles, e.g. "Dofus
# Retro Fashionista". Empty on dofus3, which stays "Dofus Fashionista".
_GAME_VERSION_SEO_WORDS = {
    'dofus3': '',
    'beta': 'Beta',
    'dofus2': '2',
    'retro': 'Retro',
    'touch': 'Touch',
}

_VERSION_PREFIXES = ('beta/', 'dofus2/', 'retro/', 'touch/')
_CHAR_ID_RE = re.compile(r'/\d+/')
# Shared build pages ('/s/<name>/<id>/', '/spells_linked/<name>/<id>/') carry an
# encoded, non-numeric char id, so _CHAR_ID_RE does not match them.
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
    # A build exists in one game version only, so the switcher falls back to
    # home. Encyclopedia ids are versioned public data, not char ids.
    safe_numeric_path = base_stripped.startswith(_VERSION_SWITCH_NUMERIC_SAFE_PREFIXES)
    if (not safe_numeric_path
            and (_CHAR_ID_RE.search(base_path)
                 or base_stripped.startswith(_LINKED_PREFIXES))):
        base_path = '/'

    # URL prefix for AJAX calls.
    api_base = '' if gv == 'dofus3' else f'/{gv}'

    return {
        'current_game_version': gv,
        'current_game_version_label': _GAME_VERSION_LABELS.get(gv, 'Dofus 3'),
        'current_game_version_seo': _GAME_VERSION_SEO_WORDS.get(gv, ''),
        'active_game_versions': ACTIVE_GAME_VERSIONS,
        'version_switch_base_path': base_path,
        'api_base': api_base,
    }


DEFAULT_AD_CLIENT = 'ca-pub-3961330018791408'

AD_PATH_PREFIXES = ('/encyclopedia/', '/guides/', '/sharedbuilds/', '/s/',
                    '/about/', '/faq/', '/support/', '/license/', '/privacy/')

# Tool pages that carry ads only once their slot id is configured.
OPTIONAL_AD_PATHS = {'/solution/': 'solution', '/spells/': 'solution'}


def _without_version(path, game_version):
    if game_version != 'dofus3' and path.startswith('/' + game_version):
        return path[len(game_version) + 1:] or '/'
    return path


AD_SETTING_KEY = 'adsense'
AD_SETTING_TTL = 30


def ad_config():
    """Ad settings: gen_config.json defaults, admin page on top. The cache is
    local to the worker, so a change takes up to AD_SETTING_TTL to reach all."""
    from django.conf import settings
    config = dict(getattr(settings, 'GEN_CONFIGS', {}).get('adsense') or {})
    stored = cache.get(AD_SETTING_KEY, False)
    if stored is False:
        from chardata.models import SiteSetting
        try:
            row = SiteSetting.objects.filter(key=AD_SETTING_KEY).first()
            stored = json.loads(row.value) if row and row.value else {}
        except Exception:
            stored = {}
        cache.set(AD_SETTING_KEY, stored, AD_SETTING_TTL)
    slots = dict(config.get('slots') or {})
    slots.update({k: v for k, v in (stored.get('slots') or {}).items() if v})
    config.update(stored)
    config['slots'] = slots
    return config


def ads(request):
    config = ad_config()
    if not config.get('enabled', True):
        return {'ads_allowed': False, 'ads_enabled': False, 'ad_slots': {}}
    client = config.get('client', DEFAULT_AD_CLIENT)
    path = _without_version(request.path_info,
                            getattr(request, 'game_version', 'dofus3'))
    slots = config.get('slots') or {}
    opted_in = any(path.startswith(prefix) and slots.get(key)
                   for prefix, key in OPTIONAL_AD_PATHS.items())
    allowed = bool(client) and (path == '/' or opted_in
                                or path.startswith(AD_PATH_PREFIXES))
    return {
        'ads_allowed': allowed,
        'ads_enabled': allowed and bool(slots),
        # data-ad-client on the script tag turns on AdSense automatic placement,
        # which lands on top of the units below.
        'ad_auto': config.get('auto', True),
        'ad_client': client,
        'ad_publisher': client.replace('ca-', '', 1),
        'ad_slots': slots,
    }
