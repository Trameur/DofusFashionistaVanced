# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The count and the names of the readable versions, for sentences that list them."""
from django import template

from chardata import readable_versions

register = template.Library()


@register.simple_tag
def readable_version_count():
    return readable_versions.count_word()


@register.simple_tag
def readable_version_names(short=False, conjunction='and', native=False):
    return readable_versions.version_names(short=short, conjunction=conjunction, native=native)
