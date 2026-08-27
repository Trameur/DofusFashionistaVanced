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

from chardata.translation_util import localized_stat_name

register = template.Library()


@register.simple_tag
def stat_name(name, game_version=None):
    """The stat's name for `game_version`, or for the running version."""
    return localized_stat_name(name, game_version)
