#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""store_transcendence_runes.py - the transcendence runes of a client dump, into
fashionistapulp/fashionistapulp/transcendence/<version>.json.

A transcendence rune is an item of type 211 (Dofus 3 and Dofus 2 alike). It
carries effect 2826 (its weight), effect 2827 (100% on application), effect
2825 (no further smithmagic) and one stat effect whose diceNum is the bonus.
The stat key comes from the client's effects.json: the English text of the
effect, matched against the site's own STAT_NAME_TO_KEY. The rank label is the
first word of the French name after "Rune" (Ta, Pata, Rata, Gata), the rank its
position in RANK_LABELS. A rune whose importantNoticeId text says it is
available in the beta alone gets beta_only and the notice in each language.

    python itemscraper/store_transcendence_runes.py --game-version beta --tag 3.8.2.3
    python itemscraper/store_transcendence_runes.py path/to/raw/3.7.14.18 --game-version dofus3
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import tempfile
from pathlib import Path

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY,
             os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

import fashionista_version  # noqa: E402
from data_file_ops import replace_file  # noqa: E402
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY  # noqa: E402
from fashionistapulp.transcendence import DEFAULT_FOLDER  # noqa: E402
from get_spells import (  # noqa: E402
    LANGUAGES, _load_datacenter_table, _load_translations, effect_id_of)
from store_weapon_conversions import _modern_items  # noqa: E402

VERSIONS = ('dofus3', 'beta', 'dofus2')
DEFAULT_TAG = {
    'dofus3': fashionista_version.FASHIONISTA_VERSION,
    'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
    'dofus2': fashionista_version.FASHIONISTA_DOFUS2_VERSION,
}

RUNE_TYPE_ID = 211
WEIGHT_EFFECT = 2826
MARKER_EFFECTS = (2825, 2827)
RANK_LABELS = ('Ta', 'Pata', 'Rata', 'Gata')
NAME_LANGUAGE = 'fr'
BETA_NOTICE_WORDS = ('beta', 'bêta')

_STAT_ALIASES = {
    '% critical': 'critical hits', 'pod': 'pods', 'heal': 'heals',
    'summons': 'summon', 'ap parry': 'ap loss resist', 'mp parry': 'mp loss resist',
}
_STAT_KEY_BY_NAME = {name.lower(): key for name, key in STAT_NAME_TO_KEY.items()}
_MARKUP = re.compile(r'\{+[^}]*\}+|#\d')


def _text_folder(folder):
    """The folder holding <lang>.json: the dump itself, or its languages folder."""
    folder = Path(folder)
    if (folder / 'fr.json').exists() or not (folder / 'languages' / 'fr.json').exists():
        return folder
    return folder / 'languages'


def _translations(folder):
    root = _text_folder(folder)
    return _load_translations(root, [lang for lang in LANGUAGES
                                     if (root / ('%s.json' % lang)).exists()])


def _texts(text_id, translations):
    if text_id in (None, '', 0, '0'):
        return {}
    names = {lang: texts[str(text_id)] for lang, texts in translations.items()
             if texts.get(str(text_id))}
    return dict(sorted(names.items()))


def stat_key(effect_id, effects, english):
    """The site stat key of a rune's stat effect, or None when the text names no known stat."""
    effect = effects.get(effect_id)
    text = english.get(str(effect.get('descriptionId'))) if effect else None
    if not text:
        return None
    name = ' '.join(_MARKUP.sub('', text).split()).lower()
    name = re.sub(r'\bresistance\b', 'resist', name)
    return _STAT_KEY_BY_NAME.get(_STAT_ALIASES.get(name, name))


def _float32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def normalize_rate(rate):
    """The shortest decimal that reads back as the same float32 as the rate."""
    target = _float32(rate)
    for digits in range(1, 10):
        candidate = float('%.*g' % (digits, rate))
        if _float32(candidate) == target:
            return candidate
    return rate


def _density(effect_id, effects):
    """The effectPowerRate of an effect, an int when integral, None when absent."""
    rate = (effects.get(effect_id) or {}).get('effectPowerRate')
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        return None
    rate = normalize_rate(float(rate))
    return int(rate) if rate.is_integer() else rate


def _rank(names):
    match = re.match(r'Rune (\S+) ', names.get(NAME_LANGUAGE, ''))
    label = match.group(1) if match else None
    return (RANK_LABELS.index(label) + 1, label) if label in RANK_LABELS else (None, label)


def _is_beta_notice(notice):
    return any(word in text.lower() for text in notice.values() for word in BETA_NOTICE_WORDS)


def scan(folder):
    """The runes read, the count of type 211 items and the count skipped."""
    folder = Path(folder)
    translations = _translations(folder)
    effects = _load_datacenter_table(folder / 'effects.json')
    items, _flag = _modern_items(folder)
    english = translations.get('en', {})
    runes = []
    total = 0
    for item_id, (record, lines, _weapon) in sorted(items.items()):
        if record.get('typeId') != RUNE_TYPE_ID:
            continue
        total += 1
        by_action = {}
        for line in lines:
            by_action.setdefault(effect_id_of(line), line)
        stats = [action for action in by_action
                 if action != WEIGHT_EFFECT and action not in MARKER_EFFECTS]
        if WEIGHT_EFFECT not in by_action or len(stats) != 1:
            print('warning: rune %s has effects %s, skipped' % (item_id, sorted(by_action)))
            continue
        action = stats[0]
        key = stat_key(action, effects, english)
        if key is None:
            print('warning: rune %s, effect %s names no known stat, skipped' % (item_id, action))
            continue
        density = _density(action, effects)
        if density is None:
            print('warning: rune %s, effect %s has no effectPowerRate, skipped' % (item_id, action))
            continue
        names = _texts(record.get('nameId'), translations)
        rank, label = _rank(names)
        if rank is None:
            print('warning: rune %s, name %r has no known rank, skipped'
                  % (item_id, names.get(NAME_LANGUAGE)))
            continue
        stat_line = by_action[action]
        rune = {'id': item_id, 'names': names, 'action': action, 'stat_key': key,
                'bonus': max(stat_line.get('diceNum') or 0, stat_line.get('diceSide') or 0),
                'weight': by_action[WEIGHT_EFFECT].get('value'), 'density': density,
                'level': record.get('level'), 'rank': rank, 'rank_label': label,
                'icon_id': record.get('iconId')}
        notice = _texts(record.get('importantNoticeId'), translations)
        rune['beta_only'] = bool(notice) and _is_beta_notice(notice)
        if notice:
            rune['notice'] = notice
        runes.append(rune)
    return runes, total, total - len(runes)


def read_runes(folder):
    """The transcendence runes of a dump."""
    return scan(folder)[0]


def build(folder, tag):
    """The table to write, None when the dump has no rune, an error when one was skipped."""
    runes, total, skipped = scan(folder)
    if skipped:
        raise RuntimeError('%d of %d transcendence runes in %s could not be read, nothing written'
                           % (skipped, total, folder))
    if not runes:
        return None
    return {'source_tag': tag, 'count': len(runes), 'runes': runes}


def _is_rune_table(path):
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and 'source_tag' in data and isinstance(data.get('runes'), list)


def write(folder, tag, version, output_folder=None):
    """The path written, or None when the dump has no rune."""
    if version in ('', '.', '..') or os.path.basename(version) != version:
        raise ValueError('not a version name: %r' % version)
    table = build(folder, tag)
    output_folder = output_folder or DEFAULT_FOLDER
    path = os.path.join(output_folder, '%s.json' % version)
    if table is None:
        if os.path.exists(path) and _is_rune_table(path):
            os.remove(path)
            print('warning: no transcendence rune in %s, removed the stale %s' % (folder, path))
        return None
    os.makedirs(output_folder, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=output_folder, prefix='.%s.' % version, suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as handle:
            json.dump(table, handle, indent=1, ensure_ascii=False)
            handle.write('\n')
        replace_file(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('raw_dir', nargs='?',
                        help='datacenter dump to read, default itemscraper/raw/<tag>')
    parser.add_argument('--game-version', default='beta', choices=VERSIONS)
    parser.add_argument('--tag', help='default the version\'s current tag')
    parser.add_argument('--output-folder')
    args = parser.parse_args()

    folder = args.raw_dir or os.path.join(
        CURRENT_DIRECTORY, 'raw', args.tag or DEFAULT_TAG[args.game_version])
    name = os.path.basename(os.path.normpath(folder))
    tag = args.tag or (name[4:] if name.startswith('raw_') else name)
    try:
        path = write(folder, tag, args.game_version, args.output_folder)
    except RuntimeError as error:
        print('error: %s' % error)
        return 1
    if path is None:
        print('no transcendence rune in %s, nothing written' % folder)
    else:
        print('wrote %s' % path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
