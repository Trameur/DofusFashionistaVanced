#!/usr/bin/env python3
"""Mirror Ankama's Wakfu game data and decode the equipment out of it.

    python get_items_wakfu.py [--out itemscraper/wakfu_raw] [--report]

Wakfu is not a Dofus version, it is another game: other stats, other slots,
other damage rules. This script does the first half of the job only, the half
that is pure data, and writes a normalised dump. Nothing here touches the site.

THE SOURCE (first-party, announced by Ankama on their own forum in 2019):

    https://wakfu.cdn.ankama.com/gamedata/config.json      -> {"version": ...}
    https://wakfu.cdn.ankama.com/gamedata/<version>/<file>.json

Ankama ask that the data be mirrored rather than fetched live, and the files
carry ETag and Last-Modified, so the mirror is refreshed with a conditional
GET. There is no gzip: a full refresh is about 16 MB.

A build cannot be fetched again once it is two versions old (anything older
than the current version and its predecessor answers 403), so every download
is kept under its own version directory. That is the only way a build stays
reproducible.

WHAT THE DATA DOES NOT CARRY, so that nobody looks for it here:

- Sets. 1105 items name an `itemSetId` and 210 distinct sets exist, but no set
  file is published. The official encyclopedia uses the same ids.
- German. Wakfu has no German locale at all; titles carry fr/en/es/pt only.

LICENCE: the data is published under Ankama's "WAKFU DATA USE LICENSE" for
personal, non-commercial use, and requires the notice
"WAKFU MMORPG: (c) 2012-<year> Ankama Studio. All rights reserved."
Mirroring it locally for development is one thing; publishing it on a site
that carries advertising is a decision for the site's owner, not for this
script, which is why this script has no web surface.
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CDN = 'https://wakfu.cdn.ankama.com/gamedata'
ICON = 'https://static.ankama.com/wakfu/portal/game/item/%d/%s.png'
ICON_SIZES = (21, 64, 115)
UA = 'DofusFashionista/wakfu-import (+https://dofusfashionista.gg)'

# The files the equipment needs. The rest of the feed (recipes, jobs, harvest)
# is left alone until something asks for it.
FILES = (
    'items.json',
    'itemTypes.json',
    'equipmentItemTypes.json',
    'itemProperties.json',
    'actions.json',
    'states.json',
)

LANGS = ('fr', 'en', 'es', 'pt')

# A slot the optimizer would have to fill. PET, MOUNT and COSTUME are carried
# through as data but are not gear in the sense the solver means.
GEAR_POSITIONS = (
    'HEAD', 'NECK', 'CHEST', 'SHOULDERS', 'BACK', 'BELT', 'LEGS',
    'LEFT_HAND', 'RIGHT_HAND', 'FIRST_WEAPON', 'SECOND_WEAPON', 'ACCESSORY',
)


def fetch(url, etag=None, modified=None):
    """(body, headers) for a URL, or (None, headers) when it has not changed."""
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    if etag:
        request.add_header('If-None-Match', etag)
    if modified:
        request.add_header('If-Modified-Since', modified)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return None, dict(error.headers)
        raise


def current_version():
    body, _headers = fetch('%s/config.json' % CDN)
    return json.loads(body)['version']


def mirror(version, out_dir):
    """Download the build into out_dir/<version>/, skipping what is current."""
    target = Path(out_dir) / version
    target.mkdir(parents=True, exist_ok=True)
    state_path = target / '_fetch_state.json'
    state = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))

    for name in FILES:
        url = '%s/%s/%s' % (CDN, version, name)
        known = state.get(name) or {}
        path = target / name
        body, headers = fetch(url, known.get('etag'), known.get('modified'))
        if body is None and path.exists():
            print('  %-26s unchanged' % name)
            continue
        if body is None:
            body, headers = fetch(url)
        path.write_bytes(body)
        state[name] = {'etag': headers.get('ETag'),
                       'modified': headers.get('Last-Modified'),
                       'bytes': len(body)}
        print('  %-26s %9d bytes' % (name, len(body)))
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True),
                          encoding='utf-8')
    return target


def load(target, name):
    with io.open(target / name, encoding='utf-8') as handle:
        return json.load(handle)


def titles(node):
    """The four languages, as plain strings, with the plural template kept.

    The template ("Anneau{[~1]?s:}") is Ankama's own and is stripped where the
    name is displayed, not here: this dump stays faithful to the source.
    """
    body = node or {}
    return {lang: body.get(lang) for lang in LANGS if body.get(lang)}


def decode(target):
    """The normalised equipment dump, and a report of what was in the build."""
    items = load(target, 'items.json')
    actions = {row['definition']['id']: row for row in load(target, 'actions.json')}
    types = {row['definition']['id']: row
             for row in load(target, 'itemTypes.json')}
    equipment = {row['definition']['id']: row
                 for row in load(target, 'equipmentItemTypes.json')}

    report = {'items': len(items), 'actions': len(actions),
              'item_types': len(types), 'equipment_types': len(equipment),
              'by_position': collections.Counter(),
              'by_rarity': collections.Counter(),
              'unknown_actions': collections.Counter(),
              'languages': collections.Counter(),
              'sets': set()}

    out = []
    for item in items:
        definition = item.get('definition') or {}
        base = (definition.get('item') or {})
        parameters = base.get('baseParameters') or {}
        effects = definition.get('equipEffects') or []
        if not effects:
            continue
        type_id = parameters.get('itemTypeId')
        slot = equipment.get(type_id) or {}
        positions = (slot.get('definition') or {}).get('equipmentPositions') or []
        disabled = (slot.get('definition') or {}).get(
            'equipmentDisabledPositions') or []

        lines = []
        for entry in effects:
            spec = ((entry.get('effect') or {}).get('definition') or {})
            action_id = spec.get('actionId')
            action = actions.get(action_id)
            if action is None:
                report['unknown_actions'][action_id] += 1
            lines.append({
                'action': action_id,
                'params': spec.get('params') or [],
                'template': titles((action or {}).get('description')),
            })

        for position in positions:
            report['by_position'][position] += 1
        report['by_rarity'][parameters.get('rarity')] += 1
        for lang in titles(item.get('title')):
            report['languages'][lang] += 1
        if parameters.get('itemSetId'):
            report['sets'].add(parameters['itemSetId'])

        out.append({
            'id': base.get('id'),
            'level': base.get('level'),
            'name': titles(item.get('title')),
            'type_id': type_id,
            'type_name': titles((types.get(type_id) or {}).get('title')),
            'positions': positions,
            'disables': disabled,
            'rarity': parameters.get('rarity'),
            'set_id': parameters.get('itemSetId') or None,
            'shard_slots': [parameters.get('minimumShardSlotNumber'),
                            parameters.get('maximumShardSlotNumber')],
            'gfx_id': (base.get('graphicParameters') or {}).get('gfxId'),
            'lines': lines,
        })
    report['sets'] = len(report['sets'])
    return out, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='itemscraper/wakfu_raw',
                        help='where the mirrored builds are kept')
    parser.add_argument('--dump', default='itemscraper/transformed_wakfu.json',
                        help='where the normalised equipment is written')
    parser.add_argument('--version', help='a build to decode instead of the '
                                          'current one (must be mirrored)')
    args = parser.parse_args(argv)

    version = args.version or current_version()
    print('Wakfu build %s' % version)
    target = Path(args.out) / version
    if not args.version:
        target = mirror(version, args.out)
    elif not target.exists():
        parser.error('build %s is not mirrored under %s' % (version, args.out))

    equipment, report = decode(target)
    payload = {'version': version, 'equipment': equipment,
               'notice': 'WAKFU MMORPG: (c) 2012-2026 Ankama Studio. '
                         'All rights reserved.'}
    Path(args.dump).write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True),
        encoding='utf-8')

    print('\nequipment with stat lines: %d of %d items'
          % (len(equipment), report['items']))
    print('stat vocabulary: %d actions, %d unresolved'
          % (report['actions'], len(report['unknown_actions'])))
    print('sets named by an item: %d (no set file is published)'
          % report['sets'])
    print('languages: %s' % dict(report['languages']))
    print('by slot:')
    for position, count in sorted(report['by_position'].items()):
        mark = '' if position in GEAR_POSITIONS else '   (not gear)'
        print('   %-16s %5d%s' % (position, count, mark))
    print('by rarity: %s' % dict(sorted(report['by_rarity'].items())))
    print('\nwrote %s' % args.dump)
    return 0


if __name__ == '__main__':
    sys.exit(main())
