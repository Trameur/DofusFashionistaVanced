# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A version without a runes file gets the smithmagic tool as it was: no Dracorune block, no reference card, no config key, and an endpoint that offers nothing."""
import json
import re

from django.test import TestCase

from fashionistapulp import game_versions
from fashionistapulp.model import readable_runes
from fashionistapulp.structure import get_structure, set_current_game_version


def prefix(version):
    return '' if version == 'dofus3' else '/%s' % version


def config_of(html):
    found = re.search(r'id="fm-config" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(found.group(1))


class TheSmithmagicToolShowsNoDracoruneWithoutARunesFileTests(TestCase):

    def versions(self):
        found = [version for version in game_versions.reader_dofus_versions() if readable_runes(version) is None]
        self.assertIn('dofus3', found)
        return found

    def hat_of(self, version):
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        found = get_structure(version)
        return next(item for item in sorted(found.get_available_items_list(), key=lambda one: one.id)
                    if found.get_type_name_by_id(item.type) == 'Hat' and item.stats)

    def test_the_page_has_no_dracorune_markup_or_config(self):
        for version in self.versions():
            hat = self.hat_of(version)
            response = self.client.get('%s/forgemagie/' % prefix(version),
                                       {'item': hat.id, 'dracorune': 'power'})
            self.assertEqual(200, response.status_code, version)
            html = response.content.decode('utf-8')
            self.assertNotIn('id="fm-draco', html, version)
            config = config_of(html)
            self.assertNotIn('dracorunes', config, version)
            self.assertNotIn('dracorune', config.get('preload', {}), version)

    def test_the_endpoint_answers_not_eligible(self):
        for version in self.versions():
            hat = self.hat_of(version)
            response = self.client.get('%s/forgemagie/dracorunes/' % prefix(version),
                                       {'item': hat.id, 'line': 'str:100'})
            self.assertEqual({'eligible': False, 'variants': []}, response.json(), version)
