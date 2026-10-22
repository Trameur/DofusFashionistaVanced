import sys
import tempfile
from pathlib import Path
from unittest import TestCase, mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import update_all


class AFailedLocalPipelineStepIsNotRetriedTests(TestCase):
    def run_step(self, label):
        failed = {'exit_code': 1, 'error': 'x'}
        with mock.patch.object(update_all, 'attempt_step', return_value=(failed, [])) as attempt, \
                mock.patch.object(update_all.time, 'sleep'), mock.patch.object(update_all, 'progress'):
            with tempfile.TemporaryDirectory() as folder:
                log = Path(folder) / 'step.log'
                update_all.run_pipeline_step(label, ['x'], '.', log, 10, label)
        return attempt.call_count

    def test_client_images_runs_once(self):
        self.assertEqual(1, self.run_step('client-images'))

    def test_a_network_image_step_is_still_retried(self):
        self.assertEqual(2, self.run_step('item-images'))
