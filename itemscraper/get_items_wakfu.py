#!/usr/bin/env python3
"""Mirror Ankama's Wakfu game data and decode the equipment out of it.

    python get_items_wakfu.py [--out DIR] [--dump FILE] [--version VERSION]
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'fashionistapulp'))
from fashionistapulp.wakfu_slots import (blocks_the_off_hand,  # noqa: E402
                                         exclusivity_of)

CDN = 'https://wakfu.cdn.ankama.com/gamedata'
ICON = 'https://static.ankama.com/wakfu/portal/game/item/%d/%s.png'
ICON_SIZES = (21, 64, 115)
UA = 'DofusFashionista/wakfu-import (+https://dofusfashionista.gg)'

# Builds older than the previous one answer 403, so mirror what we may need later
FILES = (
    'items.json',
    'itemTypes.json',
    'equipmentItemTypes.json',
    'itemProperties.json',
    'actions.json',
    'states.json',
    # Crafting
    'recipes.json',
    'recipeResults.json',
    'recipeIngredients.json',
    'recipeCategories.json',
    'jobsItems.json',
)

LANGS = ('fr', 'en', 'es', 'pt')

# Wakfu has no German, game data falls back to English
FALLBACK = {'de': 'en'}

# 39 and 40 pass the characteristic in params[4], not in the template
CHARACTERISTIC_IN_PARAM = {39: 1, 40: -1}
CHARACTERISTIC_BY_ID = {120: 'ARMOR_GIVEN_PERCENT',
                        121: 'ARMOR_RECEIVED_PERCENT'}
STATE_ACTION = 304

# "Mastery with 2 elements": params[2] is the count, the elements are not in the data
ELEMENT_COUNT_ACTIONS = {1068: 'mastery', 1069: 'resistance'}
ELEMENT_COUNT_PARAM = 2
IGNORED_ACTIONS = (400, 1020)
JOB_ACTIONS = (2001,)

# Slots the optimizer fills (not PET, MOUNT or COSTUME)
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


def characteristic(action_id, description, params):
    """(stat key, value) for one line, or (None, reason) when it is not a stat."""
    if action_id in IGNORED_ACTIONS:
        return None, 'empty'
    if action_id in JOB_ACTIONS:
        return None, 'job'
    if action_id == STATE_ACTION:
        return None, 'state'
    sign = CHARACTERISTIC_IN_PARAM.get(action_id)
    if sign is not None:
        named = int(params[4]) if len(params) > 4 else None
        key = CHARACTERISTIC_BY_ID.get(named)
        if key is None:
            return None, 'characteristic %s not named' % named
        return key, sign * (params[0] if params else 0)
    found = re.search(r'\[#charac ([A-Z_]+)\]', description or '')
    if not found:
        return None, 'no characteristic in the template'
    # A template starting with "-" is a malus (168 is "-[#1]% Critical Hit")
    negative = (description or '').lstrip().startswith('-') or '] -[#1]' in (
        description or '')
    value = params[0] if params else 0
    return found.group(1), -value if negative else value


def titles(node):
    """Title per language, plural template ("Anneau{[~1]?s:}") kept."""
    body = node or {}
    out = {lang: body.get(lang) for lang in LANGS if body.get(lang)}
    for missing, instead in FALLBACK.items():
        if out.get(instead):
            out[missing] = out[instead]
    return out


def decode(target):
    """The normalised equipment dump, and a report of what was in the build."""
    items = load(target, 'items.json')
    actions = {row['definition']['id']: row for row in load(target, 'actions.json')}
    types = {row['definition']['id']: row
             for row in load(target, 'itemTypes.json')}
    equipment = {row['definition']['id']: row
                 for row in load(target, 'equipmentItemTypes.json')}
    states = {row['definition']['id']: row for row in load(target, 'states.json')}

    report = {'items': len(items), 'actions': len(actions),
              'item_types': len(types), 'equipment_types': len(equipment),
              'by_position': collections.Counter(),
              'by_rarity': collections.Counter(),
              'unknown_actions': collections.Counter(),
              'stats': collections.Counter(),
              'element_spread': collections.Counter(),
              'no_stat_lines': 0,
              'two_handed': 0,
              'exclusive': collections.Counter(),
              'not_a_stat': collections.Counter(),
              'languages': collections.Counter(),
              'sets': set()}

    out = []
    for item in items:
        definition = item.get('definition') or {}
        base = (definition.get('item') or {})
        parameters = base.get('baseParameters') or {}
        effects = definition.get('equipEffects') or []
        if not effects:
            # Nation rings and cosmetic sets have no equipEffects
            report['no_stat_lines'] += 1
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
            params = spec.get('params') or []
            english = ((action or {}).get('description') or {}).get('en')
            key, value = characteristic(action_id, english, params)
            line = {'action': action_id, 'params': params,
                    'template': titles((action or {}).get('description'))}
            if key:
                line['stat'] = key
                line['value'] = value
                spread = ELEMENT_COUNT_ACTIONS.get(action_id)
                if spread and len(params) > ELEMENT_COUNT_PARAM:
                    line['elements'] = int(params[ELEMENT_COUNT_PARAM])
                    line['spread'] = spread
                    report['element_spread'][
                        '%s in %d' % (spread, line['elements'])] += 1
                report['stats'][key] += 1
            else:
                line['not_a_stat'] = value
                report['not_a_stat'][value] += 1
                if action_id == STATE_ACTION and params:
                    state = states.get(int(params[0])) or {}
                    line['state'] = titles(state.get('title'))
            lines.append(line)

        for position in positions:
            report['by_position'][position] += 1
        report['by_rarity'][parameters.get('rarity')] += 1
        for lang in titles(item.get('title')):
            report['languages'][lang] += 1
        if parameters.get('itemSetId'):
            report['sets'].add(parameters['itemSetId'])

        two_handed = blocks_the_off_hand(disabled)
        exclusive = exclusivity_of(base.get('properties') or [])
        if two_handed:
            report['two_handed'] += 1
        if exclusive:
            report['exclusive'][exclusive] += 1

        out.append({
            'id': base.get('id'),
            'two_handed': two_handed,
            'exclusive': exclusive,
            'level': base.get('level'),
            'name': titles(item.get('title')),
            'type_id': type_id,
            # itemTypes.json misses some gear types (480, the Torch)
            'type_name': titles(((equipment.get(type_id)
                                  or types.get(type_id)
                                  or {}).get('title'))),
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
    # Notice required by the WAKFU DATA USE LICENSE (personal, non-commercial use)
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
    print('stat lines named: %d across %d characteristics'
          % (sum(report['stats'].values()), len(report['stats'])))
    for reason, count in report['not_a_stat'].most_common():
        print('   not a stat: %-34s %d' % (reason, count))
    print('lines spread over elements the data does not name:')
    for spread, count in sorted(report['element_spread'].items()):
        print('   %-22s %5d' % (spread, count))
    print('languages: %s' % dict(report['languages']))
    print('by slot:')
    for position, count in sorted(report['by_position'].items()):
        mark = '' if position in GEAR_POSITIONS else '   (not gear)'
        print('   %-16s %5d%s' % (position, count, mark))
    print('by rarity: %s' % dict(sorted(report['by_rarity'].items())))
    print('two-handed weapons that block the off hand: %d' % report['two_handed'])
    print('one-at-a-time items: %s' % dict(report['exclusive']))
    print('gear Ankama ships with no stat line at all, dropped: %d'
          % report['no_stat_lines'])
    print('\nwrote %s' % args.dump)
    return 0


if __name__ == '__main__':
    sys.exit(main())
