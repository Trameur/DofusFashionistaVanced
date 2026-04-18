from django import template

from chardata.stat_icons import get_stat_icon_path


register = template.Library()


@register.simple_tag
def stat_icon_path(stat_key):
    return get_stat_icon_path(stat_key) or ''