#!/usr/bin/env python3
"""store_dofus2_spell_icons.py - the spell icons Dofus 2 cannot borrow.

The Dofus 2 release carries no spell image archive at all (2.73.3.14 ships
items_images and mounts_images and nothing else), so the site sends Dofus 2 to
the Dofus 3 spell directory. That works for the spells both versions still
share, and breaks for the eleven 2.x names Dofus 3 renamed: no file is stored
under the old name, so a Dofus 2 Cra build shows broken icons.

The art itself is not lost. Icons are addressed by iconId, and the Dofus 2
release does publish the spell records with their iconId, so the id from the
2.73 lang picks the right image straight out of the Dofus 3 icon pool. Both
halves stay first hand and no rename table is written down.

Only what the shared directory cannot serve is stored here. A full Dofus 2
directory would cover 465 of the 514 spells and leave the other 49 worse off
than they are today, since their icon id is absent from the pool; chardata's
_spell_image_url falls back to the shared file for exactly that reason.

    python itemscraper/store_dofus2_spell_icons.py

The pool comes from the Dofus 3 image step (download_spell_images.py), which
extracts itemscraper/spell_images/96 from the release archive.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTANTS = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'dofus_constants_dofus2.py'
POOL = ROOT / 'itemscraper' / 'spell_images' / '96'
SHARED = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata' / 'spells'
STATIC_DIRS = (SHARED / 'dofus2',
               ROOT / 'fashionsite' / 'staticfiles' / 'chardata' / 'spells' / 'dofus2')


def damage_spell_names():
    spec = importlib.util.spec_from_file_location('dofus2_constants', CONSTANTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = set()
    for spells in getattr(module, 'DAMAGE_SPELLS', {}).values():
        for spell in spells:
            name = getattr(spell, 'name', None)
            if name:
                names.add(name.strip())
    if not names:
        raise SystemExit('DAMAGE_SPELLS is empty in %s' % CONSTANTS)
    return names


def icons_by_name(raw_dir):
    """Spell name -> the icon ids the Dofus 2 release gives it."""
    with open(raw_dir / 'spells.json', encoding='utf-8') as fh:
        spells = json.load(fh)
    with open(raw_dir / 'en.json', encoding='utf-8') as fh:
        texts = json.load(fh)['texts']
    out = {}
    for spell in spells:
        name = texts.get(str(spell.get('nameId')))
        icon = spell.get('iconId')
        if name and icon:
            out.setdefault(name, []).append(icon)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', help='the 2.73 dump; the newest one by default')
    parser.add_argument('--pool', default=str(POOL))
    args = parser.parse_args()

    raw_root = ROOT / 'itemscraper' / 'raw'
    if args.raw_dir:
        raw_dir = Path(args.raw_dir)
    else:
        candidates = sorted(p for p in raw_root.iterdir()
                            if p.is_dir() and p.name.startswith('2.'))
        if not candidates:
            raise SystemExit('no Dofus 2 dump under %s' % raw_root)
        raw_dir = candidates[-1]

    pool = Path(args.pool)
    if not pool.is_dir():
        # The pool belongs to the Dofus 3 image step, so a Dofus 2 rebuild on a
        # machine that never ran it keeps the committed icons instead of failing.
        print('WARNING: no icon pool at %s (Dofus 3 spell-images step); '
              'the committed icons stay as they are.' % pool)
        return

    wanted = damage_spell_names()
    by_name = icons_by_name(raw_dir)
    for directory in STATIC_DIRS:
        directory.mkdir(parents=True, exist_ok=True)

    written = borrowed = unnamed = no_icon = 0
    missing = []
    for name in sorted(wanted):
        if (SHARED / ('%s.png' % name)).exists():
            borrowed += 1
            continue
        ids = by_name.get(name)
        if not ids:
            unnamed += 1
            missing.append('%s (not in the %s lang)' % (name, raw_dir.name))
            continue
        source = next((pool / ('%d.png' % icon) for icon in ids
                       if (pool / ('%d.png' % icon)).exists()), None)
        if source is None:
            no_icon += 1
            missing.append('%s (icon %s absent from the pool)' % (name, ids[0]))
            continue
        for directory in STATIC_DIRS:
            shutil.copy2(source, directory / ('%s.png' % name))
        written += 1

    print('dofus2 spell icons: %d written, %d served by the shared directory,'
          ' %d without a 2.73 name, %d without an icon in the pool'
          % (written, borrowed, unnamed, no_icon))
    for line in missing:
        print('   missing: %s' % line)


if __name__ == '__main__':
    main()
