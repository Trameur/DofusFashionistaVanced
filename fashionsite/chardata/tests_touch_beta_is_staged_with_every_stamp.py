# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Touch Beta is registered as a staged member of the Touch family, with its stamps, and the updater keeps every old choice."""
import contextlib
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

import fashionista_version
import update_all as updater
from fashionistapulp.game_versions import (GAME_VERSIONS, VERSION_ORDER, dofus_versions, family_members,
                                           is_beta, main_of, reader_dofus_versions, switcher_games,
                                           version_keys)

from chardata.tests import itemscraper_module

OLD_TOKENS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu')


class TouchBetaIsAStagedTouchVersionTests(SimpleTestCase):

    def test_it_is_the_beta_channel_of_touch(self):
        touchbeta = GAME_VERSIONS['touchbeta']
        self.assertEqual('touch', main_of('touchbeta'))
        self.assertTrue(is_beta('touchbeta'))
        self.assertTrue(touchbeta.dofus)
        self.assertEqual(('Touch Beta', 'Dofus Touch Beta'), (touchbeta.label, touchbeta.game_name))
        self.assertEqual(('items_touchbeta.db', 'item_db_dumped_touchbeta.dump'),
                         (touchbeta.db_file, touchbeta.dump_file))
        self.assertEqual('touchbeta', touchbeta.prefix)

    def test_it_carries_the_touch_rules(self):
        touch, touchbeta = GAME_VERSIONS['touch'], GAME_VERSIONS['touchbeta']
        for rule in ('temporix', 'extra_slot_types', 'rings_can_double', 'weapon_element_rate',
                     'element_potion_heals', 'exo_per_item'):
            with self.subTest(rule=rule):
                self.assertEqual(getattr(touch, rule), getattr(touchbeta, rule))

    def test_it_sits_after_touch_and_reaches_a_reader_only_once_it_is_not_experimental(self):
        hidden = GAME_VERSIONS['touchbeta'].experimental
        members = ['touch'] if hidden else ['touch', 'touchbeta']
        self.assertEqual(('dofus3', 'beta', 'dofus2', 'touch', 'touchbeta', 'retro', 'retrobeta', 'wakfu'),
                         VERSION_ORDER)
        self.assertIn('touchbeta', dofus_versions())
        self.assertEqual(hidden, 'touchbeta' not in version_keys())
        self.assertEqual(hidden, 'touchbeta' not in reader_dofus_versions())
        self.assertEqual(members, family_members('touch'))
        self.assertIn(('touch', members), switcher_games())


class TouchBetaHasItsStampsTests(SimpleTestCase):

    def test_the_footer_stamp_is_its_own_build(self):
        self.assertEqual(fashionista_version.FASHIONISTA_TOUCHBETA_VERSION, settings.SITE_VERSIONS['touchbeta'])
        self.assertEqual(fashionista_version.FASHIONISTA_TOUCH_VERSION, settings.SITE_VERSIONS['touch'])

    def test_its_timeline_ends_on_its_stamp(self):
        patch = '.'.join(fashionista_version.FASHIONISTA_TOUCHBETA_VERSION.split('.')[:2])
        self.assertEqual(patch, fashionista_version.PATCH_TIMELINE['touchbeta'][-1][1])

    def test_the_rebuild_tools_know_its_files(self):
        self.assertEqual('fashionistapulp/fashionistapulp/items_touchbeta.db',
                         itemscraper_module('check_rebuild').COMMITTED['touchbeta'])
        self.assertTrue(itemscraper_module('store_weapon_uses_per_turn').WORK_DIR['touchbeta']
                        .endswith('touchbeta'))


class TheUpdaterKeepsEveryOldChoiceTests(SimpleTestCase):

    def _rows(self):
        return [{'key': key, 'error': None, 'changed': True} for key in updater.VERSIONS]

    def test_every_old_number_keeps_its_version(self):
        rows = self._rows()
        for number, key in enumerate(OLD_TOKENS, 1):
            with self.subTest(number=number):
                self.assertEqual([key], updater.selection(str(number), rows))
                self.assertEqual([key], updater.restore_keys(str(number)))
        self.assertEqual(['touchbeta'], updater.selection('7', rows))

    def test_the_old_tables_keep_their_values(self):
        self.assertEqual(OLD_TOKENS, updater.VERSIONS[:6])
        self.assertEqual(['Dofus 3', 'Dofus 3 Beta', 'Dofus 2', 'Dofus Touch', 'Dofus Retro', 'Wakfu'],
                         [updater.NAMES[key] for key in OLD_TOKENS])
        self.assertEqual(['update_data', 'update_data_beta', 'update_data_dofus2', 'update_data_touch',
                          'update_data_retro', 'update_data_wakfu'],
                         [updater.PIPELINES[key] for key in OLD_TOKENS])
        self.assertEqual(['FASHIONISTA_VERSION', 'FASHIONISTA_BETA_VERSION', 'FASHIONISTA_DOFUS2_VERSION',
                          'FASHIONISTA_TOUCH_VERSION', 'FASHIONISTA_RETRO_VERSION', None],
                         [updater.METADATA.get(key) for key in OLD_TOKENS])

    def test_all_and_changed_never_pick_the_staged_beta(self):
        rows = self._rows()
        self.assertEqual(['dofus3', 'beta', 'dofus2', 'touch', 'retro'], updater.selection('all', rows))
        self.assertEqual(['dofus3', 'beta', 'dofus2', 'touch', 'retro'], updater.selection('changed', rows))

    def test_the_staged_beta_does_not_turn_the_list_into_a_failure(self):
        rows = [{'key': 'dofus3', 'current': '3.6.11.15', 'available': '3.6.11.15', 'official': '3.6.11.15',
                 'source': {}, 'changed': False, 'warnings': [], 'error': None},
                {'key': 'touchbeta', 'current': '1.75.0', 'available': None, 'official': None, 'source': {},
                 'changed': False, 'warnings': [], 'error': 'staged'}]
        with tempfile.TemporaryDirectory() as root, \
                mock.patch.object(updater, 'REPORTS', Path(root) / 'reports'), \
                mock.patch.object(updater, 'discover', return_value=rows), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, updater.main(['--list', '--running-file', str(Path(root) / 'RUNNING.md')]))
            rows[0]['error'] = 'offline'
            self.assertEqual(1, updater.main(['--list', '--running-file', str(Path(root) / 'RUNNING.md')]))


class TheLoginAddressesComeFromTheChannelsTests(SimpleTestCase):

    def test_every_script_reads_the_login_config_from_touch_channels(self):
        channels = itemscraper_module('touch_channels')
        login = channels.config_url('login')
        self.assertEqual(login + '?lang=fr', updater.TOUCH)
        self.assertEqual(channels.host('login') + '/build/script.js', updater.TOUCH_CLIENT)
        self.assertEqual(login + '?lang=fr', itemscraper_module('check_game_versions').TOUCH_CONFIG)
        self.assertEqual(login, itemscraper_module('download_touch_skins').CONFIG_URL)

    def test_no_script_writes_a_touch_proxy_address_by_hand(self):
        root = Path(__file__).resolve().parents[2]
        scripts = sorted(root.glob('itemscraper/*.py')) + sorted(root.glob('update_*.py'))
        by_hand = [script.name for script in scripts if script.name != 'touch_channels.py'
                   and 'dt-proxy-production' in script.read_text(encoding='utf-8')]
        self.assertEqual([], by_hand)
