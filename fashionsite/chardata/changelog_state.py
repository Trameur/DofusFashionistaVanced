# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the newest changelog entry is, for the footer to mark it as unseen.

The changelog opens from a footer link that looked the same whether or not
anything had been added since the reader's last visit. On 2026-09-11 the
four entries of September, sixteen features, sat behind a link nothing
pointed at. The footer now carries the key of the newest entry; the
browser keeps the key it last opened the changelog on, and shows a mark
while the two differ.

The key is the msgid of the newest entry's title: the same in every
language, stable across translations, and it changes exactly when an entry
is added on top. Read once per process from the template source, which is
the changelog itself and not a copy of it.
"""

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
