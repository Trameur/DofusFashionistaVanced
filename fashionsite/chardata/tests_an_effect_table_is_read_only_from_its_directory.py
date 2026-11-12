# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An effect table name never reads a file outside the table directory."""
import json
import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import item_effects


class AnEffectTableIsReadOnlyFromItsDirectoryTests(SimpleTestCase):

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        tables = os.path.join(scratch.name, 'effect_tables')
        os.mkdir(tables)
        for folder, name in ((tables, 'inside'), (scratch.name, 'outside')):
            with open(os.path.join(folder, name + '.json'), 'w', encoding='utf-8') as handle:
                json.dump({'name': name}, handle)
        for patcher in (mock.patch.object(item_effects, 'TABLE_DIR', tables),
                        mock.patch.object(item_effects, '_tables', {})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_table_in_the_directory_is_read(self):
        self.assertEqual({'name': 'inside'}, item_effects.load_effect_table('inside'))

    def test_a_name_climbing_out_of_the_directory_reads_nothing(self):
        for version in ('../outside', '..' + os.sep + 'outside', 'inside/../../outside'):
            with self.subTest(version=version):
                self.assertIsNone(item_effects.load_effect_table(version))
