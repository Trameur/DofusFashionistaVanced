# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each version reads its own combat record; a beta never reads its main game's, a file holding another version's record is refused."""
import json
import os
import shutil
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp.combat import rules as combat_rules
from fashionistapulp.combat.rules import RecordError, load_rules, read_record, record_path


class EachVersionsOwnRecordTests(SimpleTestCase):

    def test_dofus3_and_beta_load_records_of_their_own_name(self):
        for version in ('dofus3', 'beta'):
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

    def test_a_file_holding_another_versions_record_is_refused(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        shutil.copy(record_path('dofus3'), os.path.join(folder, 'beta.json'))
        with mock.patch.object(combat_rules, 'RECORD_DIR', folder), \
                mock.patch.dict(combat_rules._LOADED, clear=True):
            with self.assertRaises(RecordError):
                load_rules('beta')

    def test_a_version_without_a_record_has_no_rules(self):
        for version in ('dofus2', 'touch', 'retro', 'touchbeta', 'retrobeta'):
            if os.path.exists(record_path(version)):
                continue
            with self.subTest(version=version):
                self.assertIsNone(load_rules(version))

    def test_the_two_records_differ_only_where_their_client_tags_do(self):
        own = read_record(record_path('dofus3'))
        beta = read_record(record_path('beta'))
        self.assertNotEqual(own['verified_on_tag'], beta['verified_on_tag'])
        self.assertEqual(own['enabled_stages'], beta['enabled_stages'])
        for record in (own, beta):
            self.assertIn(record['verified_on_tag'], json.dumps(record['sources']))
