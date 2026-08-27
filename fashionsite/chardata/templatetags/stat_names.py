# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The running version's own word for a stat, for templates.

`{% trans "Power" %}` gives every version the same word, which is wrong for the
two stats the versions do not agree on: Retro reads effect 138 as "Augmente les
dommages de X%" and effect 226 as "+X% de dommages aux pieges", where Dofus 3
reads both as a Power characteristic.

Renaming them in `localized_stat_name` was not enough on its own. Five views
call it and four surfaces did not, so the item pages said one thing and the
weights page another, and the guides that told a Retro reader which row to
weight named a row he could not find. Whatever shows a stat name has to go
through one of the two.
"""
from django import template
from django.utils.translation import gettext

from chardata.translation_util import localized_stat_name

register = template.Library()


@register.simple_tag
def stat_name(name, game_version=None):
    """The stat's name for `game_version`, or for the running version."""
    return localized_stat_name(name, game_version)


@register.simple_tag
def percent_of_stat_name(name, game_version=None):
    """The suffix for a percentage OF a stat, in this version's own words.

    Dofus 3 writes "+20% Power": the percent belongs to the spell, the word to
    the stat. Retro calls that same stat "% Damage", the percent already inside
    the name, so pasting one in front gives "+20% % Damage". Where the version
    renames the stat, its own label replaces the whole construct.

    The decision lives here rather than in the template because a template that
    asks `{% trans %}` for the shared word to compare against it looks exactly
    like a template that forgot the override, and the guard that watches for
    that cannot tell them apart.
    """
    localized = localized_stat_name(name, game_version)
    if str(localized) == gettext(name):
        return '%% %s' % localized
    return ' %s' % localized
