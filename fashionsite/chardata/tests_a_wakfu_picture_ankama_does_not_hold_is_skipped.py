# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import urllib.error
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'get_item_images_wakfu.py')


def _load():
    spec = importlib.util.spec_from_file_location('get_item_images_wakfu', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AWakfuPictureAnkamaDoesNotHoldIsSkippedTests(SimpleTestCase):

    def _run(self, code):
        module = _load()
        with tempfile.TemporaryDirectory() as folder:
            dump = Path(folder) / 'transformed_wakfu.json'
            dump.write_text(json.dumps({'equipment': [
                {'positions': ['HEAD'], 'gfx_id': 123}]}), encoding='utf-8')
            refused = urllib.error.HTTPError('url', code, 'refused', {}, None)
            output = io.StringIO()
            with mock.patch.object(module, 'STATIC', Path(folder)), \
                    mock.patch.object(module, 'fetch', side_effect=refused), \
                    contextlib.redirect_stdout(output):
                result = module.main(['--dump', str(dump)])
            return result, output.getvalue()

    def test_the_bucket_refusal_counts_as_no_picture(self):
        result, output = self._run(403)
        self.assertEqual(0, result)
        self.assertRegex(output, r'no picture\s+1')

    def test_a_server_error_still_stops_the_step(self):
        with self.assertRaises(urllib.error.HTTPError):
            self._run(500)
