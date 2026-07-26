# -*- coding: utf-8 -*-
"""Roll range of a stat, worded the same way in the encyclopedia and the picker."""
from fashionistapulp.translation import get_supported_language

RANGE_PATTERNS = {
    'en': '%(low)s to %(high)s',
    'fr': '%(low)s à %(high)s',
    'es': '%(low)s a %(high)s',
    'pt': '%(low)s a %(high)s',
    'de': '%(low)s bis %(high)s',
}


def get_stat_range(item, stat_id):
    """(low, high), or None on a fixed stat or a version without range data."""
    low, high = (getattr(item, 'stat_ranges', {}) or {}).get(stat_id, (None, None))
    if low is None or high is None or low == high:
        return None
    return low, high


def format_stat_range(low, high):
    language = get_supported_language()
    pattern = RANGE_PATTERNS.get(language, RANGE_PATTERNS['en'])
    return pattern % {'low': low, 'high': high}
