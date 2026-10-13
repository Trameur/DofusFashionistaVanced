# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A run folder made by another generator version is neither resumed nor shipped, and one of this version is."""
import json
import os
import tempfile

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from chardata import tests_the_weight_table_carries_its_measurement as measured
from chardata import tests_tune_weights_refuses_a_real_database_and_a_repo_out_path as command
from chardata import weight_tuning as tuning

VERSION = 'dofus3'
OLDER = tuning.GENERATOR_VERSION - 1
NEWER = tuning.GENERATOR_VERSION + 1


def _stamp(folder, generator):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'run.json'), 'w', encoding='utf-8') as handle:
        json.dump({'generator_version': generator, 'solver': {}}, handle)


def _write_cell(folder):
    ratios = {'pow': dict(measured._entry(), source='tune'), 'hp': dict(measured._entry(), source='tune')}
    tuning.write_record(folder, measured._record('Iop/str/plain/200', ratios))


class AFolderOfAnotherGeneratorIsRefusedTests(SimpleTestCase):

    def setUp(self):
        parent = tempfile.TemporaryDirectory()
        self.addCleanup(parent.cleanup)
        self.folder = os.path.join(parent.name, 'run-5')
        os.makedirs(self.folder)

    def test_an_older_and_a_newer_generator_are_refused_and_name_both(self):
        for generator in (OLDER, NEWER):
            _stamp(self.folder, generator)
            with self.subTest(generator=generator):
                with self.assertRaisesRegex(ValueError, 'generator %d and this is generator %d' % (
                        generator, tuning.GENERATOR_VERSION)):
                    tuning.refuse_other_generator(self.folder)

    def test_this_generator_a_folder_without_a_stamp_and_a_folder_without_a_file_are_not(self):
        _stamp(self.folder, tuning.GENERATOR_VERSION)
        tuning.refuse_other_generator(self.folder)
        with open(os.path.join(self.folder, 'run.json'), 'w', encoding='utf-8') as handle:
            json.dump({'solver': {}}, handle)
        tuning.refuse_other_generator(self.folder)
        os.remove(os.path.join(self.folder, 'run.json'))
        tuning.refuse_other_generator(self.folder)

    def test_the_table_of_older_records_is_not_stamped_with_the_current_version(self):
        _write_cell(self.folder)
        _stamp(self.folder, OLDER)
        with self.assertRaisesRegex(ValueError, 'generator %d' % OLDER):
            tuning.ship_table(self.folder, VERSION)

    def test_the_table_of_records_of_this_generator_ships_with_its_version(self):
        _write_cell(self.folder)
        _stamp(self.folder, tuning.GENERATOR_VERSION)
        table = tuning.ship_table(self.folder, VERSION)
        self.assertEqual(tuning.GENERATOR_VERSION, table['header']['generator_version'])

    def test_the_table_of_a_folder_without_a_stamp_ships_as_before(self):
        _write_cell(self.folder)
        table = tuning.ship_table(self.folder, VERSION)
        self.assertEqual(tuning.GENERATOR_VERSION, table['header']['generator_version'])


class AResumeOrAShipOfAnotherGeneratorsFolderIsRefusedByTheCommandTests(command._Command):

    def _held_run(self, generator):
        _stamp(self.out, generator)
        cells = os.path.join(self.out, 'cells')
        os.makedirs(cells)
        with open(os.path.join(cells, 'Iop__str__plain__200.json'), 'w') as handle:
            handle.write('{}')

    def test_a_resume_into_the_folder_of_an_older_generator_is_refused_and_leaves_it_as_it_was(self):
        self._held_run(OLDER)
        with self.assertRaisesRegex(CommandError, 'generator %d and this is generator %d' % (
                OLDER, tuning.GENERATOR_VERSION)):
            self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1', '--resume')
        self.assertEqual([], self.runner.calls)
        self.assertEqual(OLDER, tuning.read_meta(self.out)['generator_version'])

    def test_a_resume_into_the_folder_of_this_generator_goes_on(self):
        self._held_run(tuning.GENERATOR_VERSION)
        text = self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1', '--resume')
        self.assertIn('0 of 0 groups finished', text)

    def test_a_ship_of_the_folder_of_an_older_generator_is_refused_and_writes_no_table(self):
        _write_cell(self.out)
        _stamp(self.out, OLDER)
        with self.assertRaisesRegex(CommandError, 'generator %d' % OLDER):
            self.call('--out', self.out, '--ship', self.out)
        self.assertEqual(self.tables_before, self.tables())
