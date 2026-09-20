# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The name of a build in a template, never empty; a filter, so the gallery's light objects work too."""

from django import template

from chardata.build_name import display_name

register = template.Library()


@register.filter(name='build_display_name')
def build_display_name(char):
    return display_name(char)
