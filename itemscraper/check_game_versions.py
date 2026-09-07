#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What each Dofus version is running, from its own source. Exits 1 if item data moved.

    python itemscraper/check_game_versions.py

Dofus 3, the beta and Dofus 2 are watched on the version they publish. Touch
does not publish a useful public version, so it is watched on the asset bundle
its client config points at. Retro's public version and client build are not
enough: its item data comes from the lang CDN, so the lang category versions are
the release gate and the client build is only printed as a diagnostic.
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


def retro_lang_versions():
    """{category: version} for the lang files the item pipeline reads."""
    import fashionista_version as ours
    from download_retro_langs import fetch_manifest
    live = fetch_manifest('fr')
    return {name: str(live.get(name, 'missing'))
            for name in ours.WATCHED_RETRO_LANG}


def touch_assets():
    url = _json(TOUCH_CONFIG).get('assetsUrl', '')
    return url.rsplit('/', 1)[-1] if url else ''


def main():
    import fashionista_version as ours

    # Touch keeps the same public number across content patches, so it is
    # watched on its asset bundle. Retro is handled below through lang files.
    checks = [
        ('dofus3', ours.FASHIONISTA_VERSION, cytrus_version('dofus3'), None),
        ('beta', ours.FASHIONISTA_BETA_VERSION, cytrus_version('beta'), None),
        ('dofus2', ours.FASHIONISTA_DOFUS2_VERSION, cytrus_version('dofus2'), None),
        ('touch', ours.FASHIONISTA_TOUCH_VERSION, touch_assets(),
         ours.WATCHED_TOUCH_ASSETS),
    ]
    moved = []
    for name, shown, live, watched in checks:
        compared = watched if watched is not None else shown
        same = live == compared
        if not same:
            moved.append((name, live))
        # Print what was compared. Showing the frozen public number beside a
        # different live build, followed by ok, reads as a contradiction.
        print('%-8s ours %-40s live %-40s %s%s'
              % (name, compared, live, 'ok' if same else 'MOVED',
                 '' if watched is None else '   (public number %s)' % shown))

    retro_build = cytrus_version('retro')
    print('%-8s build %-40s live %-40s %s   (public number %s; item data watches lang)'
          % ('retro', ours.WATCHED_RETRO_BUILD, retro_build,
             'ok' if retro_build == ours.WATCHED_RETRO_BUILD else 'changed',
             ours.FASHIONISTA_RETRO_VERSION))

    for name, repo in (('dofus3', 'dofus3-main'), ('beta', 'dofus3-beta')):
        tag = _json(TAGS % repo)[0]['name']
        print('%-8s tag  %s' % (name, tag))

    import fashionista_version as watched
    live_lang = retro_lang_versions()
    lang_moved = sorted(name for name, version in live_lang.items()
                        if version != watched.WATCHED_RETRO_LANG[name])
    print('%-8s lang %s'
          % ('retro', ', '.join('%s=%s' % (name, live_lang[name])
                                for name in sorted(live_lang))))
    if lang_moved:
        moved.append(('retro lang', ', '.join(lang_moved)))
        print('retro lang MOVED on %s, re-scrape retro and update '
              'WATCHED_RETRO_LANG' % ', '.join(lang_moved))

    for name, live in moved:
        if name == 'touch':
            print('after re-scraping %s, set WATCHED_%s_%s = "%s"'
                  % (name, name.upper(),
                     'ASSETS', live))
    if retro_build != ours.WATCHED_RETRO_BUILD and not lang_moved:
        print('retro build moved but lang data is unchanged; no item re-scrape required')
    return 1 if moved else 0


if __name__ == '__main__':
    sys.exit(main())
