# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The newest changelog entry's key, the msgid of its title, for the footer to mark it as unseen."""

import io
import os
import re

from django.conf import settings

_TITLE = re.compile(r'class="cl-title">\{%\s*trans\s+"((?:[^"\\]|\\.)*)"\s*%\}')
_cache = {}


def changelog_template_path():
    return os.path.join(settings.BASE_DIR, 'chardata', 'templates',
                        'chardata', 'changelog_content.html')


def newest_entry_key():
    if 'key' not in _cache:
        source = io.open(changelog_template_path(), encoding='utf-8').read()
        found = _TITLE.search(source)
        _cache['key'] = found.group(1) if found else ''
    return _cache['key']
