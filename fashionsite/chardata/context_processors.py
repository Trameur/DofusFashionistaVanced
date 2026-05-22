import re

ACTIVE_GAME_VERSIONS = [
    ('dofus3', 'Dofus 3'),
    ('beta', 'Beta'),
]

_VERSION_PREFIXES = ('beta/', 'retro/', 'touch/')
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
