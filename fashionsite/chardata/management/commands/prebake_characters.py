# -*- coding: utf-8 -*-
"""Bake the class bodies and heads ahead of time.

A body is around 540 parts and takes some twenty seconds, which is too long to
do while someone waits for a page. Equipment is a handful of parts and stays
lazy.

    python manage.py prebake_characters
    python manage.py prebake_characters --gear

A piece of gear is only a few seconds, but that few seconds blocks a browser
connection and stalls everything queued behind it, so --gear is worth running
out of band. It walks every version that has character art.
"""
import time

from django.core.management.base import BaseCommand

from chardata import character_assets
from chardata.character_look import (CLASS_TO_BREED, VERSIONS_WITH_ART,
                                     _breed_looks, player_bones)


class Command(BaseCommand):
    help = 'Bake every class body and head into the character preview cache'

    def add_arguments(self, parser):
        parser.add_argument('--gear', action='store_true',
                            help='also bake the skin of every item that has one')

    def handle(self, *args, **options):
        if not character_assets.bundle_dir():
            self.stderr.write('CHARACTER_BUNDLE_DIR is not set, nothing to bake')
            return

        started = time.time()
        for breed in sorted(set(CLASS_TO_BREED.values())):
            bones = player_bones(breed)
            if character_assets.ensure_pose(bones) is None:
                self.stderr.write('no bone bundle for %s' % bones)

        skins = set()
        for entry in _breed_looks().values():
            skins.add(entry['body'])
            if entry.get('head'):
                skins.add(entry['head'])
        if options['gear']:
            skins.update(self._gear_skins())

        done = missing = 0
        for skin_id in sorted(skins):
            if character_assets.ensure_skin(skin_id) is None:
                missing += 1
                continue
            done += 1
            self.stdout.write('%d/%d skins' % (done, len(skins)), ending='\r')
        self.stdout.write('\n%d skins baked, %d missing, %.0f s'
                          % (done, missing, time.time() - started))

    def _gear_skins(self):
        from fashionistapulp.structure import get_structure
        out = set()
        for version in VERSIONS_WITH_ART:
            for item in get_structure(version).get_items_list():
                skin = getattr(item, 'skin', None)
                if skin:
                    out.add(skin)
        return out
