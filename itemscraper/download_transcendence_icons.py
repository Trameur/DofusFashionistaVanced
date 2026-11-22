#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""download_transcendence_icons.py - the icons of the transcendence runes a
version's table lists, into fashionsite/chardata/static/chardata/runes_transcendance/<icon id>.webp.

The picture of a rune is the one the dofusdude item data names for its id (the
image_urls of itemscraper/<work folder>/all_resources_en.json, extracted from
the game client). An icon already on disk is kept. Pictures are stored at
96x96, WEBP quality 90, like the existing ones.

    python itemscraper/download_transcendence_icons.py --game-version beta
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

import requests
from PIL import Image

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY,
             os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

from fashionistapulp.transcendence import DEFAULT_FOLDER  # noqa: E402

ICON_FOLDER = os.path.join(PROJECT_ROOT, 'fashionsite', 'chardata', 'static',
                           'chardata', 'runes_transcendance')
WORK_FOLDER = {'dofus3': CURRENT_DIRECTORY,
               'beta': os.path.join(CURRENT_DIRECTORY, 'beta'),
               'dofus2': os.path.join(CURRENT_DIRECTORY, 'dofus2')}
ICON_PX = 96
REQUEST_TIMEOUT = 30


def _read(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def source_urls(version):
    """{item id: picture url} of the version's resources file."""
    items = _read(os.path.join(WORK_FOLDER[version], 'all_resources_en.json'))
    if isinstance(items, dict):
        items = items.get('items', [])
    urls = {}
    for item in items:
        pictures = item.get('image_urls') or {}
        url = pictures.get('sd') or pictures.get('icon')
        if url:
            urls[item['ankama_id']] = url
    return urls


def missing_icons(version, icon_folder=ICON_FOLDER, table_folder=DEFAULT_FOLDER):
    """[(item id, icon id)] of the table's runes whose icon is not on disk."""
    table = _read(os.path.join(table_folder, '%s.json' % version))
    return [(rune['id'], rune['icon_id']) for rune in table['runes']
            if not os.path.isfile(os.path.join(icon_folder, '%d.webp' % rune['icon_id']))]


def save_icon(data, destination):
    image = Image.open(io.BytesIO(data)).convert('RGBA')
    image = image.resize((ICON_PX, ICON_PX), Image.LANCZOS)
    image.save(destination, 'WEBP', quality=90, method=6)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-version', default='beta', choices=sorted(WORK_FOLDER))
    args = parser.parse_args()
    urls = source_urls(args.game_version)
    failed = 0
    for item_id, icon_id in missing_icons(args.game_version):
        url = urls.get(item_id)
        if url is None:
            print('no picture url for rune %s (icon %s)' % (item_id, icon_id))
            failed += 1
            continue
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            save_icon(response.content, os.path.join(ICON_FOLDER, '%d.webp' % icon_id))
        except (requests.RequestException, OSError) as error:
            print('rune %s (icon %s) failed: %s' % (item_id, icon_id, error))
            failed += 1
            continue
        print('icon %s written' % icon_id)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
