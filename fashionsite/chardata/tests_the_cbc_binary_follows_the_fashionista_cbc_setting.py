# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""FASHIONISTA_CBC picks the CBC binary and, only when set, tags the cache keys."""
import os
import subprocess
import sys
import tempfile
import types
from unittest import mock

import pulp

from django.test import SimpleTestCase

from fashionistapulp import lpproblem
from fashionistapulp.model import ModelInput

KEY_WITHOUT_TAG = -1301626660202909896
KEY_WITH_GAP_WITHOUT_TAG = 906202011078842801

PROBE = ("import sys\n"
         "from fashionistapulp import lpproblem\n"
         "print(type(lpproblem.SOLVER).__name__, repr(lpproblem.SOLVER_TAG),"
         " 'cbcbox' in sys.modules)\n")


def model_input(**extra):
    return ModelInput(200, {'vit': 1000}, {'Vitality': 500, 'adv_mins': {'x': 1}}, {'1': 2},
                      [5, 3], {'vit': 2, 'str': 1}, {'exo': True}, 'xelor', 12, **extra)


def fake_cbcbox(path):
    return types.SimpleNamespace(cbc_bin_path=lambda: path)


class TheSettingNamesTheSolverTests(SimpleTestCase):

    def test_an_empty_setting_names_no_solver(self):
        self.assertIsNone(lpproblem.solver_from_setting(None))
        self.assertIsNone(lpproblem.solver_from_setting(''))
        self.assertIsNone(lpproblem.solver_from_setting('  '))

    def test_cbcbox_takes_the_binary_the_package_gives(self):
        with mock.patch.dict(sys.modules, {'cbcbox': fake_cbcbox('/opt/cbcbox/cbc')}), \
                mock.patch.object(pulp, '__version__', '4.0.1'):
            solver = lpproblem.solver_from_setting('cbcbox', 45)
        self.assertEqual('COIN_CMD', type(solver).__name__)
        self.assertEqual('/opt/cbcbox/cbc', solver.path)
        self.assertEqual(45, solver.timeLimit)
        self.assertFalse(solver.msg)

    def test_cbcbox_is_refused_while_pulp_is_older_than_4(self):
        with mock.patch.dict(sys.modules, {'cbcbox': fake_cbcbox('/opt/cbcbox/cbc')}), \
                mock.patch.object(pulp, '__version__', '2.9.0'):
            with self.assertRaisesRegex(RuntimeError, 'PuLP 4'):
                lpproblem.solver_from_setting('cbcbox')

    def test_any_other_value_is_the_path_of_a_binary(self):
        with tempfile.NamedTemporaryFile(suffix='.exe') as binary:
            solver = lpproblem.solver_from_setting(binary.name)
        self.assertEqual('COIN_CMD', type(solver).__name__)
        self.assertEqual(binary.name, solver.path)
        self.assertEqual(lpproblem.TIME_LIMIT_SECONDS, solver.timeLimit)

    def test_a_path_that_is_no_file_is_refused(self):
        with self.assertRaises(FileNotFoundError):
            lpproblem.solver_from_setting(os.path.join(tempfile.gettempdir(), 'no', 'cbc'))

    def test_a_run_reads_the_options_of_the_solver_it_copies(self):
        with tempfile.NamedTemporaryFile(suffix='.exe') as binary:
            solver = lpproblem.solver_from_setting(binary.name)
        with mock.patch.object(lpproblem, 'SOLVER', solver):
            copy = lpproblem._solver_for_run(False, seed=4, gap=0.02)
        self.assertEqual(binary.name, copy.path)
        self.assertIn('randomSeed 4', copy.options)
        self.assertEqual(0.02, copy.optionsDict['gapRel'])


class TheSettingAtImportTests(SimpleTestCase):

    def probe(self, setting):
        fake = tempfile.TemporaryDirectory()
        self.addCleanup(fake.cleanup)
        os.mkdir(os.path.join(fake.name, 'cbcbox'))
        with open(os.path.join(fake.name, 'cbcbox', '__init__.py'), 'w') as handle:
            handle.write('def cbc_bin_path():\n    return ""\n')
        environment = dict(os.environ, PYTHONPATH=os.pathsep.join([fake.name] + sys.path))
        environment.pop(lpproblem.CBC_SETTING_NAME, None)
        if setting is not None:
            environment[lpproblem.CBC_SETTING_NAME] = setting
        done = subprocess.run([sys.executable, '-c', PROBE], env=environment, timeout=120,
                              capture_output=True, text=True)
        self.assertEqual(0, done.returncode, done.stderr)
        return done.stdout.split()

    def test_unset_keeps_the_solver_pulp_bundles_and_does_not_import_cbcbox(self):
        if lpproblem.SOLVER_TAG:
            self.skipTest('the setting is set for this run')
        bundled = type(lpproblem.SOLVER).__name__
        self.assertEqual([bundled, "''", 'False'], self.probe(None))
        self.assertEqual([bundled, "''", 'False'], self.probe(''))

    def test_a_path_is_taken_and_tags_the_keys(self):
        with tempfile.NamedTemporaryFile(suffix='.exe') as binary:
            kind, tag, imported = self.probe(binary.name)
        self.assertEqual(('COIN_CMD', repr(binary.name), 'False'), (kind, tag, imported))


class TheCacheKeysCarryTheSolverTagOnlyWhenSetTests(SimpleTestCase):

    def setUp(self):
        if lpproblem.SOLVER_TAG:
            self.skipTest('the setting is set for this run')

    def test_the_key_without_the_setting_is_the_key_the_site_always_made(self):
        self.assertEqual(KEY_WITHOUT_TAG, model_input().cache_key())
        self.assertEqual(KEY_WITH_GAP_WITHOUT_TAG, model_input(gap=0.03).cache_key())

    def test_the_setting_changes_the_key_and_the_hash(self):
        plain, plain_hash = model_input().cache_key(), hash(model_input())
        with mock.patch.object(lpproblem, 'SOLVER_TAG', 'cbcbox'):
            boxed, boxed_hash = model_input().cache_key(), hash(model_input())
        with mock.patch.object(lpproblem, 'SOLVER_TAG', '/opt/other/cbc'):
            other = model_input().cache_key()
        self.assertEqual(3, len({plain, boxed, other}))
        self.assertNotEqual(plain_hash, boxed_hash)
        self.assertEqual(plain, model_input().cache_key())

    def test_the_tag_adds_to_a_key_with_a_gap(self):
        with mock.patch.object(lpproblem, 'SOLVER_TAG', 'cbcbox'):
            self.assertNotEqual(KEY_WITH_GAP_WITHOUT_TAG, model_input(gap=0.03).cache_key())
