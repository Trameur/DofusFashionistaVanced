# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each version reads its own combat record, the Touch and Retro betas their main game's; no other version reads another's, a file holding another version's record is refused."""
import json
import os
import shutil
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp.combat import rules as combat_rules
from fashionistapulp.combat.rules import RecordError, load_rules, read_record, record_path
from fashionistapulp.game_versions import main_game, version_keys

OWN_RECORDS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
MAIN_RECORD_BETAS = ('touchbeta', 'retrobeta')


class EachVersionsOwnRecordTests(SimpleTestCase):

    def test_each_main_version_and_beta_load_records_of_their_own_name(self):
        for version in OWN_RECORDS:
            with self.subTest(version=version):
                self.assertEqual(version, load_rules(version).version)
                self.assertEqual('%s.json' % version, os.path.basename(record_path(version)))
                self.assertEqual(version, read_record(record_path(version))['version'])

    def test_beta_never_falls_back_on_the_dofus3_record(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        shutil.copy(record_path('dofus3'), os.path.join(folder, 'dofus3.json'))
        with mock.patch.object(combat_rules, 'RECORD_DIR', folder), \
                mock.patch.dict(combat_rules._LOADED, clear=True):
            self.assertIsNone(load_rules('beta'))
            self.assertEqual('dofus3', load_rules('dofus3').version)

    def test_the_touch_and_retro_betas_read_their_main_games_record(self):
        for beta in MAIN_RECORD_BETAS:
            main = main_game(beta)
            with self.subTest(version=beta):
                self.assertNotEqual(beta, main)
                self.assertEqual(main, load_rules(beta).version)
                self.assertIs(load_rules(main), load_rules(beta))
                self.assertEqual(record_path(main), record_path(beta))

    def test_every_other_version_reads_only_its_own_record(self):
        for version in version_keys(include_experimental=True):
            rules = load_rules(version)
            if rules is None or version in MAIN_RECORD_BETAS:
                continue
            with self.subTest(version=version):
                self.assertEqual(version, rules.version)
        for version in OWN_RECORDS + MAIN_RECORD_BETAS:
            self.assertIsNotNone(load_rules(version))

    def test_a_main_version_never_falls_back_on_another_record(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        shutil.copy(record_path('dofus3'), os.path.join(folder, 'dofus3.json'))
        with mock.patch.object(combat_rules, 'RECORD_DIR', folder), \
                mock.patch.dict(combat_rules._LOADED, clear=True):
            for version in ('dofus2', 'touch', 'retro') + MAIN_RECORD_BETAS:
                with self.subTest(version=version):
                    self.assertIsNone(load_rules(version))
        for beta in MAIN_RECORD_BETAS:
            folder = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, folder, True)
            shutil.copy(record_path(main_game(beta)), os.path.join(folder, '%s.json' % beta))
            with mock.patch.object(combat_rules, 'RECORD_DIR', folder), \
                    mock.patch.dict(combat_rules._LOADED, clear=True):
                with self.subTest(version=beta):
                    self.assertIsNone(load_rules(beta))

    def test_a_file_holding_another_versions_record_is_refused(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        shutil.copy(record_path('dofus3'), os.path.join(folder, 'beta.json'))
        with mock.patch.object(combat_rules, 'RECORD_DIR', folder), \
                mock.patch.dict(combat_rules._LOADED, clear=True):
            with self.assertRaises(RecordError):
                load_rules('beta')

    def test_a_version_without_a_record_has_no_rules(self):
        for version in ('wakfu',):
            self.assertFalse(os.path.exists(record_path(version)))
            with self.subTest(version=version):
                self.assertIsNone(load_rules(version))

    def test_the_two_records_differ_only_where_their_client_tags_do(self):
        own = read_record(record_path('dofus3'))
        beta = read_record(record_path('beta'))
        self.assertNotEqual(own['verified_on_tag'], beta['verified_on_tag'])
        self.assertEqual(own['enabled_stages'], beta['enabled_stages'])
        for record in (own, beta):
            self.assertIn(record['verified_on_tag'], json.dumps(record['sources']))
