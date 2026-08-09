#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What each Dofus version is running, from its own source. Exits 1 if one moved.

    python itemscraper/check_game_versions.py

Dofus 3, the beta and Dofus 2 are watched on the version they publish. Retro
and Touch never move theirs, 1.48 and 1.73, so they are watched on their real
build instead: Retro's full Cytrus string and the asset bundle Touch's client
config points at. Neither is a version number, and both live in
fashionista_version.py as WATCHED_* so the footer keeps showing the short one.
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

    # Retro and Touch keep the same public number across content patches, so
    # they are watched on their real build instead. Comparing only the public
    # number let Retro 1.48.20 -> 1.48.21 through unnoticed.
    checks = [
        ('dofus3', ours.FASHIONISTA_VERSION, cytrus_version('dofus3'), None),
        ('beta', ours.FASHIONISTA_BETA_VERSION, cytrus_version('beta'), None),
        ('dofus2', ours.FASHIONISTA_DOFUS2_VERSION, cytrus_version('dofus2'), None),
        ('retro', ours.FASHIONISTA_RETRO_VERSION, cytrus_version('retro'),
         ours.WATCHED_RETRO_BUILD),
        ('touch', ours.FASHIONISTA_TOUCH_VERSION, touch_assets(),
         ours.WATCHED_TOUCH_ASSETS),
    ]
    moved = []
    for name, shown, live, watched in checks:
        same = live == (watched if watched is not None else shown)
        if not same:
            moved.append((name, live))
        print('%-8s ours %-12s live %-40s %s'
              % (name, shown, live, 'ok' if same else 'MOVED'))

    for name, repo in (('dofus3', 'dofus3-main'), ('beta', 'dofus3-beta')):
        tag = _json(TAGS % repo)[0]['name']
        print('%-8s tag  %s' % (name, tag))

    for name, live in moved:
        if name in ('retro', 'touch'):
            print('after re-scraping %s, set WATCHED_%s_%s = "%s"'
                  % (name, name.upper(),
                     'ASSETS' if name == 'touch' else 'BUILD', live))
    return 1 if moved else 0


if __name__ == '__main__':
    sys.exit(main())
