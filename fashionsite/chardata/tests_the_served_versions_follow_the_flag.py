# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The versions the site answers for follow the Wakfu switch."""
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from chardata.middleware import GameVersionMiddleware
from chardata.served_versions import served_versions, version_by_prefix
from fashionistapulp.game_versions import GAME_VERSIONS, version_keys
from fashionistapulp.structure import set_current_game_version


def _flag(on):
    return override_settings(EXPERIMENTS=dict(settings.EXPERIMENTS, WAKFU=on))


def _version_of(path):
    request = RequestFactory().get(path)
    try:
        GameVersionMiddleware(lambda request: HttpResponse())(request)
    finally:
        set_current_game_version('dofus3')
    return request.game_version


class TheServedVersionsFollowTheFlagTests(SimpleTestCase):
    def test_with_the_flag_off_the_site_serves_the_reader_versions(self):
        with _flag(False):
            self.assertEqual(version_keys(), served_versions())
            self.assertEqual(
                {GAME_VERSIONS[key].prefix: key for key in version_keys()
                 if GAME_VERSIONS[key].prefix}, version_by_prefix())
            self.assertEqual({'beta', 'dofus2', 'touch', 'retro'}, set(version_by_prefix()))

    def test_with_the_flag_on_the_site_serves_wakfu_after_them(self):
        with _flag(True):
            self.assertEqual(version_keys() + ['wakfu'], served_versions())
            self.assertEqual('wakfu', version_by_prefix()['wakfu'])

    def test_the_middleware_maps_the_wakfu_prefix_with_the_flag_on(self):
        with _flag(True):
            self.assertEqual('wakfu', _version_of('/wakfu/'))
            self.assertEqual('wakfu', _version_of('/de/wakfu/x/'))
            self.assertEqual('beta', _version_of('/beta/'))

    def test_the_middleware_leaves_the_wakfu_prefix_to_dofus3_with_the_flag_off(self):
        with _flag(False):
            self.assertEqual('dofus3', _version_of('/wakfu/'))
            self.assertEqual('dofus3', _version_of('/de/wakfu/x/'))
            self.assertEqual('retro', _version_of('/retro/'))
