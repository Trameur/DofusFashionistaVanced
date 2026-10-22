import contextlib
import importlib.util
import io
import os
import sys
import types

from django.test import SimpleTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for folder in (ROOT, os.path.join(ROOT, 'itemscraper')):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import update_all  # noqa: E402


def orchestrator():
    spec = importlib.util.spec_from_file_location(
        'update_data_wakfu_images_under_test', os.path.join(ROOT, 'update_data_wakfu.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arguments(**changes):
    values = dict(skip_mirror=False, skip_sets=False, skip_spells=False, skip_images=False)
    values.update(changes)
    return types.SimpleNamespace(**values)


class TheWakfuClientImagesAreAPipelineStepAfterTheItemImagesTests(SimpleTestCase):
    def test_the_step_comes_right_after_the_item_images_and_before_the_dump(self):
        labels = orchestrator().steps_after_client(arguments())
        at = labels.index('item-images')
        self.assertEqual(['item-images', 'client-images', 'items/dump'], labels[at:at + 3])

    def test_the_step_is_gone_with_skip_images(self):
        labels = orchestrator().steps_after_client(arguments(skip_images=True))
        self.assertNotIn('client-images', labels)
        self.assertNotIn('item-images', labels)

    def test_the_step_runs_the_script_after_the_item_images_and_not_with_skip_images(self):
        module = orchestrator()
        for flags, expected in (([], True), (['--skip-images'], False)):
            ran = []

            def fake(label, cmd, cwd=None, ran=ran):
                ran.append((label, cmd))
                return True, []

            module.run_step = fake
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, module.main(flags))
            labels = [label for label, _cmd in ran]
            self.assertEqual(expected, 'client-images' in labels, flags)
            if expected:
                self.assertEqual(labels.index('item-images') + 1, labels.index('client-images'))
                self.assertTrue(dict(ran)['client-images'][-1].endswith('get_wakfu_images.py'))

    def test_the_step_is_an_image_step_with_a_title(self):
        self.assertIn('client-images', update_all.IMAGE_STEPS)
        self.assertEqual('Game images', update_all.STEP_TITLES['client-images'])
        self.assertEqual('Game images', update_all.step_title('client-images'))
