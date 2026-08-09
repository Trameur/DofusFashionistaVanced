#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What each Dofus version is running, from its own source. Exits 1 if one moved.

    python itemscraper/check_game_versions.py

Touch publishes no version, so it is watched by the asset bundle its client
config points at. That string is not a version number.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cytrus_cdn

TOUCH_CONFIG = 'https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr'
TAGS = 'https://api.github.com/repos/dofusdude/%s/tags'
USER_AGENT = 'Dofus Fashionista version watch'


def _json(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def cytrus_version(game_version):
    """Strips the client generation prefix."""
    raw = cytrus_cdn.get_version(game_version)
    return raw.split('_', 1)[-1] if '_' in raw else raw


def touch_assets():
    url = _json(TOUCH_CONFIG).get('assetsUrl', '')
    return url.rsplit('/', 1)[-1] if url else ''


def main():
    import fashionista_version as ours

    checks = [
        ('dofus3', ours.FASHIONISTA_VERSION, cytrus_version('dofus3')),
        ('beta', ours.FASHIONISTA_BETA_VERSION, cytrus_version('beta')),
        ('dofus2', ours.FASHIONISTA_DOFUS2_VERSION, cytrus_version('dofus2')),
        ('retro', ours.FASHIONISTA_RETRO_VERSION, cytrus_version('retro')),
    ]
    moved = False
    for name, mine, live in checks:
        same = live.startswith(mine)  # retro ships a longer build string
        moved = moved or not same
        print('%-8s ours %-12s live %-28s %s'
              % (name, mine, live, 'ok' if same else 'MOVED'))

    for name, repo in (('dofus3', 'dofus3-main'), ('beta', 'dofus3-beta')):
        tag = _json(TAGS % repo)[0]['name']
        print('%-8s tag  %s' % (name, tag))

    print('%-8s ours %-12s assets %s'
          % ('touch', ours.FASHIONISTA_TOUCH_VERSION, touch_assets()))
    return 1 if moved else 0


if __name__ == '__main__':
    sys.exit(main())
