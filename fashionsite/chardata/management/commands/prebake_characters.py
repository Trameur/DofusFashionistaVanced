# -*- coding: utf-8 -*-
"""Bake the class bodies and heads ahead of time.

A body is around 540 parts and takes some twenty seconds, which is too long to
do while someone waits for a page. Equipment is a handful of parts and stays
lazy.

    python manage.py prebake_characters
"""
import time

from django.core.management.base import BaseCommand

from chardata import character_assets
from chardata.character_look import PLAYER_BONES, _breed_looks


class Command(BaseCommand):
    help = 'Bake every class body and head into the character preview cache'

    def handle(self, *args, **options):
        if not character_assets.bundle_dir():
            self.stderr.write('CHARACTER_BUNDLE_DIR is not set, nothing to bake')
            return

        started = time.time()
        if character_assets.ensure_pose(PLAYER_BONES) is None:
            self.stderr.write('no bone bundle for %d' % PLAYER_BONES)

        skins = set()
        for entry in _breed_looks().values():
            skins.add(entry['body'])
            if entry.get('head'):
                skins.add(entry['head'])

        done = missing = 0
        for skin_id in sorted(skins):
            if character_assets.ensure_skin(skin_id) is None:
                missing += 1
                continue
            done += 1
            self.stdout.write('%d/%d skins' % (done, len(skins)), ending='\r')
        self.stdout.write('\n%d skins baked, %d missing, %.0f s'
                          % (done, missing, time.time() - started))
