# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The versions a build can be copied to, and the report of a copy just made."""
from django import template

register = template.Library()


@register.simple_tag
def copy_targets(game_version):
    from chardata.version_copy import copy_targets as targets
    return targets(game_version or 'dofus3')


@register.simple_tag(takes_context=True)
def version_copy_report(context, char):
    from chardata.version_copy import take_report
    from fashionistapulp.game_versions import get_game_version
    report = take_report(context.get('request'), char)
    if report is None:
        return None
    try:
        report['from_name'] = get_game_version(report['from']).game_name
    except KeyError:
        report['from_name'] = report['from']
    return report


@register.simple_tag
def game_name(game_version):
    from fashionistapulp.game_versions import get_game_version
    try:
        return get_game_version(game_version or 'dofus3').game_name
    except KeyError:
        return game_version
