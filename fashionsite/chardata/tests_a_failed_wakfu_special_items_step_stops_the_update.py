import contextlib
import importlib.util
import io
import os
import types

from django.test import SimpleTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def orchestrator():
    spec = importlib.util.spec_from_file_location(
        'update_data_wakfu_special_under_test', os.path.join(ROOT, 'update_data_wakfu.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(broken):
    module = orchestrator()
    ran = []

    def fake(label, cmd, cwd=None):
        ran.append(label)
        return label not in broken, []
    module.run_step = fake
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = module.main(['--skip-client', '--skip-mirror', '--skip-sets', '--skip-spells',
                            '--skip-images'])
    return code, ran, out.getvalue()


class AFailedWakfuSpecialItemsStepStopsTheUpdateTests(SimpleTestCase):
    def test_the_step_runs_right_after_the_build_and_before_the_recipes(self):
        code, ran, _out = run(set())
        self.assertEqual(
            (0, ['items/build-db', 'items/special', 'items/recipes', 'items/spells',
                 'items/dump']), (code, ran))

    def test_a_failure_skips_every_later_step_and_keeps_the_previous_block(self):
        code, ran, out = run({'items/special'})
        self.assertEqual((1, ['items/build-db', 'items/special']), (code, ran))
        self.assertIn('items/special, items/recipes (skipped), items/spells (skipped), '
                      'items/dump (skipped)', out)
        self.assertIn('the previous block stays', out)

    def test_the_step_is_not_run_when_the_build_failed(self):
        code, ran, _out = run({'items/build-db'})
        self.assertEqual(1, code)
        self.assertNotIn('items/special', ran)
