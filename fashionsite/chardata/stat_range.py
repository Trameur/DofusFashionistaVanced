# -*- coding: utf-8 -*-
"""The roll range of a stat, worded the same way everywhere it is shown.

The number the site displays is always the best roll, because that is what the
solver optimises on. The range is what a looted one can really be, which is the
whole difference between "40 Wisdom" and "a 40 Wisdom that usually drops at 26".
Retro carries no range at all: in 1.29 equipment stats are fixed values.
"""
from fashionistapulp.translation import get_supported_language

RANGE_PATTERNS = {
    'en': '%(low)s to %(high)s',
    'fr': '%(low)s à %(high)s',
    'es': '%(low)s a %(high)s',
    'pt': '%(low)s a %(high)s',
    'de': '%(low)s bis %(high)s',
}


def get_stat_range(item, stat_id):
    """(low, high) when that stat really varies, None when it is a fixed value
    or when the version has no range data."""
    low, high = (getattr(item, 'stat_ranges', {}) or {}).get(stat_id, (None, None))
    if low is None or high is None or low == high:
        return None
    return low, high


def format_stat_range(low, high):
    language = get_supported_language()
    pattern = RANGE_PATTERNS.get(language, RANGE_PATTERNS['en'])
    return pattern % {'low': low, 'high': high}
