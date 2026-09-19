import json
import logging
import re

from django.core.cache import cache
from django.db.models import Sum

from fashionistapulp.game_versions import GAME_VERSIONS, version_keys

logger = logging.getLogger(__name__)


def site_stats(request):
    # v3: counts also as ints, the template needs them for plural forms
    stats = cache.get('site_stats_v3')
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
                    'characters_n': characters,
                    'solver_runs': f"{runs:,}",
                    'solver_runs_n': runs,
                    'shared_builds': f"{shared:,}",
                    'shared_builds_n': shared,
                })
        users = User.objects.count()
        stats = {
            'stat_users': f"{users:,}",
            'stat_users_n': users,
            'stat_per_version': per_version,
        }
        cache.set('site_stats_v3', stats, 600)
    return stats


# version_keys() already drops the experimental versions
ACTIVE_GAME_VERSIONS = [(key, GAME_VERSIONS[key].label)
                        for key in version_keys()]

_GAME_VERSION_LABELS = dict(ACTIVE_GAME_VERSIONS)

# Word between "Dofus" and "Fashionista" in SEO titles, empty on dofus3
_GAME_VERSION_SEO_WORDS = {
    'dofus3': '',
    'beta': 'Beta',
    'dofus2': '2',
    'retro': 'Retro',
    'touch': 'Touch',
}

_VERSION_PREFIXES = ('beta/', 'dofus2/', 'retro/', 'touch/')
_CHAR_ID_RE = re.compile(r'/\d+/')
# Shared build pages carry an encoded char id that _CHAR_ID_RE misses
_LINKED_PREFIXES = ('s/', 'spells_linked/')
_VERSION_SWITCH_NUMERIC_SAFE_PREFIXES = ('encyclopedia/',)

# Entity ids differ between versions: the switcher asks the page for its links
_VERSION_SWITCH_ENTITY_RE = re.compile(
    r'^encyclopedia/(?:(?:item|resource)/[^/]+/|(?:set|monster)/)\d+')


def game_version(request):
    # The language prefix comes before the version: /es/beta/, never /beta/es/
    from chardata.url_language import split_language_prefix
    language_prefix, path = split_language_prefix(request.path_info)
    base_path = path
    stripped = path.lstrip('/')
    gv = getattr(request, 'game_version', 'dofus3')
    for prefix in _VERSION_PREFIXES:
        if stripped.startswith(prefix):
            base_path = '/' + stripped[len(prefix):]
            break
    base_stripped = base_path.lstrip('/')
    # A build exists in one game version only: fall back to home
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
        'version_switch_language_prefix': language_prefix,
        'version_switch_base_path': base_path,
        'version_switch_is_entity': bool(
            _VERSION_SWITCH_ENTITY_RE.match(base_stripped)),
        'api_base': api_base,
    }


DEFAULT_AD_CLIENT = 'ca-pub-3961330018791408'

# No ads on the funnel: /setup/, /quickstart/, /smartbuild/
AD_PATH_PREFIXES = ('/encyclopedia/', '/guides/', '/sharedbuilds/', '/s/',
                    '/forgemagie/', '/about/', '/faq/', '/support/',
                    '/license/', '/privacy/')

# Tool pages that carry ads only once their slot id is configured.
OPTIONAL_AD_PATHS = {'/solution/': 'solution', '/spells/': 'solution',
                     '/spells_linked/': 'solution'}


def _without_version(path, game_version):
    if game_version != 'dofus3' and path.startswith('/' + game_version):
        return path[len(game_version) + 1:] or '/'
    return path


AD_SETTING_KEY = 'adsense'
AD_SETTING_TTL = 30


def ad_config():
    """Ad settings: gen_config.json defaults, admin page on top, cached per worker."""
    from django.conf import settings
    config = dict(getattr(settings, 'GEN_CONFIGS', {}).get('adsense') or {})
    stored = cache.get(AD_SETTING_KEY, False)
    if stored is False:
        from chardata.models import SiteSetting
        try:
            row = SiteSetting.objects.filter(key=AD_SETTING_KEY).first()
            stored = json.loads(row.value) if row and row.value else {}
        except Exception:
            # Not ERROR: broken JSON fails every request, one admin mail per page view
            logger.warning('the stored ad setting could not be read, so no '
                           'advertising is served', exc_info=True)
            return {'enabled': False, 'read_failed': True}
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
    # The language prefix sits in front of the version (/es/beta/guides/)
    from chardata.url_language import split_language_prefix
    _language_prefix, path = split_language_prefix(request.path_info)
    path = _without_version(path, getattr(request, 'game_version', 'dofus3'))
    slots = config.get('slots') or {}
    opted_in = any(path.startswith(prefix) and slots.get(key)
                   for prefix, key in OPTIONAL_AD_PATHS.items())
    allowed = bool(client) and (path == '/' or opted_in
                                or path.startswith(AD_PATH_PREFIXES))
    return {
        'ads_allowed': allowed,
        'ads_enabled': allowed and bool(slots),
        # data-ad-client on the script tag turns on AdSense auto ads
        'ad_auto': config.get('auto', True),
        'ad_client': client,
        'ad_publisher': client.replace('ca-', '', 1),
        'ad_slots': slots,
    }


def build_sites(request):
    """Which other build sites the pages may name (chardata/build_sites.py)."""
    from chardata import build_sites as sites
    return {'build_sites': {
        'dofusbook': sites.enabled(sites.DOFUSBOOK),
        'dofus_stuffer': sites.enabled(sites.DOFUS_STUFFER),
        'dofuscreator': sites.enabled(sites.DOFUSCREATOR),
        'links': sites.any_enabled(),
    }}


def changelog(request):
    """The key of the newest changelog entry, for the footer mark."""
    from chardata.changelog_state import newest_entry_key
    return {'changelog_latest': newest_entry_key()}
