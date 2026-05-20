from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()


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
