# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The retired set record keeps every set an update removed and drops a set only when the game brings it back."""

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module


def _set(ankama_id, **names):
    row = {'ankama_id': ankama_id}
    for lang, name in names.items():
        row['name_' + lang] = name
    return row


class RetiredSetRecordTests(SimpleTestCase):

    def setUp(self):
        self.record = itemscraper_module('record_retired_sets')
        self.retro = itemscraper_module('get_equipments_retro')
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.path = self.folder / self.record.RETIRED_SETS_FILE

    def _rows(self):
        return json.loads(self.path.read_text(encoding='utf-8'))['sets']

    def test_a_set_the_new_file_lacks_is_recorded_with_its_old_names_and_the_data_version(self):
        old = [_set(1, fr='Un', en='One', de=''), _set(2)]
        added = self.record.record_retired_sets(old, [_set(2)], self.path, '1393')
        self.assertEqual(added, [1])
        self.assertEqual(self._rows(), [
            {'ankama_id': 1, 'names': {'fr': 'Un', 'en': 'One'}, 'removed_in': '1393'}])

    def test_a_later_update_keeps_every_set_already_recorded(self):
        self.record.record_retired_sets([_set(1), _set(2), _set(3)], [_set(1), _set(3)], self.path, '1393')
        self.record.record_retired_sets([_set(1), _set(3)], [_set(3)], self.path, '1400')
        rows = self._rows()
        self.assertEqual([r['ankama_id'] for r in rows], [1, 2])
        self.assertEqual({r['ankama_id']: r['removed_in'] for r in rows}, {1: '1400', 2: '1393'})

    def test_a_set_seen_missing_again_keeps_the_version_that_first_removed_it(self):
        self.record.record_retired_sets([_set(1, fr='Un'), _set(2)], [_set(2)], self.path, '1393')
        added = self.record.record_retired_sets([_set(1, fr='Autre'), _set(2)], [_set(2)], self.path, '1500')
        self.assertEqual(added, [])
        self.assertEqual(self._rows(), [
            {'ankama_id': 1, 'names': {'fr': 'Un'}, 'removed_in': '1393'}])

    def test_a_set_the_game_brings_back_leaves_the_record(self):
        self.record.record_retired_sets(
            [_set(1), _set(2), _set(3)], [_set(3)], self.path, '1393')
        self.record.record_retired_sets([_set(3)], [_set(2), _set(3)], self.path, '1400')
        self.assertEqual([r['ankama_id'] for r in self._rows()], [1])

    def test_an_empty_new_catalogue_records_nothing(self):
        self.assertEqual(self.record.record_retired_sets([_set(1)], [], self.path, '1393'), [])
        self.assertFalse(self.path.exists())

    def test_an_update_that_removes_nothing_writes_no_file(self):
        self.assertEqual(
            self.record.record_retired_sets([_set(1)], [_set(1), _set(2)], self.path, '1393'), [])
        self.assertFalse(self.path.exists())

    def test_the_command_line_writes_the_record_next_to_the_new_file(self):
        old = self.folder / 'old.json'
        new = self.folder / 'transformed_sets.json'
        old.write_text(json.dumps([_set(1, en='One'), _set(2)]), encoding='utf-8')
        new.write_text(json.dumps([_set(2)]), encoding='utf-8')
        code = self.record.main(['--old', str(old), '--new', str(new), '--removed-in', '1393'])
        self.assertEqual(code, 0)
        self.assertEqual([r['ankama_id'] for r in self._rows()], [1])

    def test_the_retro_transform_records_the_sets_its_previous_output_had(self):
        kept, gone = _set(1, en='Kept'), _set(2, en='Gone')
        (self.folder / 'transformed_sets.json').write_text(
            json.dumps([kept, gone]), encoding='utf-8')
        retired = self.retro.write_sets(self.folder, [kept], '1393')
        self.assertEqual(retired, [2])
        self.assertEqual(
            json.loads((self.folder / 'transformed_sets.json').read_text(encoding='utf-8')), [kept])
        self.assertEqual([r['ankama_id'] for r in self._rows()], [2])
