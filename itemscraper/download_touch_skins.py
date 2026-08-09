#!/usr/bin/env python3
"""
Download the Dofus Touch character skins.

The Touch client bundle (served at <proxy>/build/script.js) declares
SKIN_PATH="skins/" and BONE_PATH="bones/", at the CDN root and not under gfx/,
which is why every gfx/sprites-style guess came back missing. Each skin is a
sprite strip:

  skin  : <assetsUrl>/skins/<skinId>.png

There is no index, so the roster is found by probing. Measured on assets 3.2.11
(2026-08-09): 3823 skins over ids 10..4188, 23.2 MB in total, median 4.7 KB.
Dofus 3 ships about 5500 bundles for 780 MB, so matching Touch is the cheaper
job of the two.

  python itemscraper/download_touch_skins.py --dest itemscraper/skins_touch

Resumable: files already on disk are skipped unless --force.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json"
FALLBACK_ASSETS_URL = ("https://dofustouch.cdn.ankama.com/assets/"
                       "3.2.11_XmqR,JLRxKAo0jK41tA_EnsXKrTBc47Z")
USER_AGENT = "Mozilla/5.0 Chrome/120"
# The measured range, with room above it: a scan to 5200 found nothing past 4188.
DEFAULT_LAST_ID = 5200


def _get(url, method='GET'):
    request = urllib.request.Request(
        url, headers={'User-Agent': USER_AGENT}, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read() if method == 'GET' else b''


def resolve_assets_url(lang='fr'):
    try:
        config = json.loads(_get('%s?lang=%s' % (CONFIG_URL, lang)))
        return config.get('assetsUrl') or FALLBACK_ASSETS_URL
    except Exception as exc:  # noqa
        print('config.json unreachable (%s), falling back' % exc)
        return FALLBACK_ASSETS_URL


def fetch_skin(args):
    assets_url, skin_id, dest, force = args
    path = dest / ('%d.png' % skin_id)
    if path.exists() and not force:
        return skin_id, 'skipped'
    try:
        payload = _get('%s/skins/%d.png' % (assets_url, skin_id))
    except urllib.error.HTTPError:
        return skin_id, 'absent'      # the CDN answers 403 on a missing key
    except Exception:  # noqa
        return skin_id, 'error'
    path.write_bytes(payload)
    return skin_id, 'written'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', default='itemscraper/skins_touch')
    parser.add_argument('--last-id', type=int, default=DEFAULT_LAST_ID)
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    assets_url = resolve_assets_url()
    print('assets: %s' % assets_url)

    jobs = [(assets_url, skin_id, dest, args.force)
            for skin_id in range(1, args.last_id + 1)]
    tally = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for _skin_id, outcome in pool.map(fetch_skin, jobs):
            tally[outcome] = tally.get(outcome, 0) + 1

    print('skins: %d written, %d already there, %d absent, %d errors'
          % (tally.get('written', 0), tally.get('skipped', 0),
             tally.get('absent', 0), tally.get('error', 0)))
    return 1 if tally.get('error') else 0


if __name__ == '__main__':
    sys.exit(main())
