from django import template
from django.urls import resolve, reverse, NoReverseMatch, Resolver404

register = template.Library()


def _resolves(path):
    try:
        resolve(path)
        return True
    except Resolver404:
        return False


@register.simple_tag(takes_context=True)
def game_url(context, url_name, *args, **kwargs):
    """Like {% url %} but auto-prefixes with the current game version namespace.

    Already-namespaced names (e.g. 'auth:logout') are passed through unchanged.
    For names not registered in the version namespace (e.g. 'about', 'faq'),
    falls back to the global URL.
    """
    game_version = context.get('current_game_version', 'dofus3')
    if ':' not in url_name and game_version != 'dofus3':
        try:
            return reverse(f'{game_version}:{url_name}', args=args, kwargs=kwargs)
        except NoReverseMatch:
            pass
    return reverse(url_name, args=args, kwargs=kwargs)


@register.simple_tag(takes_context=True)
def version_switch_href(context, version_key):
    """The header switcher's link to `version_key` for the current page.

    A hub (/encyclopedia/, /encyclopedia/sets/ ...) exists in every version, so
    the same path is re-prefixed, as before. A page about one entity does not:
    ids are not shared across versions, and re-prefixing the path fabricated a
    404 for every version lacking the entity -- 39% of header links on a sample
    of entity pages. The page already computed which versions carry the same
    entity (other_versions, monster_version_links); this reuses that answer and
    falls back to the version's encyclopedia hub, so the reader always lands
    somewhere alive.
    """
    prefix = context.get('version_switch_language_prefix', '') or ''
    version_prefix = '' if version_key == 'dofus3' else '/' + version_key
    base_path = context.get('version_switch_base_path', '/') or '/'
    current = context.get('current_game_version', 'dofus3')
    if version_key == current:
        return prefix + version_prefix + base_path
    if not context.get('version_switch_is_entity'):
        # Guides are routed once per language, login exists in one version only
        candidate = prefix + version_prefix + base_path
        if _resolves(candidate):
            return candidate
        candidate = version_prefix + base_path
        if _resolves(candidate):
            return candidate
        hub = '/encyclopedia/' if base_path.startswith('/encyclopedia/') else '/'
        return prefix + version_prefix + hub
    labels = dict(context.get('active_game_versions') or ())
    wanted_label = labels.get(version_key)
    for entry in (list(context.get('other_versions') or ())
                  + list(context.get('monster_version_links') or ())):
        key = entry.get('game_version')
        if key is None and entry.get('label') == wanted_label:
            key = version_key
        if key == version_key and entry.get('url'):
            # The slug names the language, a prefixed entity address redirects
            return entry['url']
    return prefix + version_prefix + '/encyclopedia/'
