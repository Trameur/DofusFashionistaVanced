# -*- coding: utf-8 -*-
"""The static file upload must go through the boto3 Bucket it gets, from the folder collectstatic fills."""
import csv
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import boto3
from botocore.awsrequest import AWSResponse
from django.conf import settings

from chardata.tests_the_backup_can_reach_s3 import REPO, ABoto3Bucket


def load_upload_module():
    path = os.path.join(REPO, 'upload_static_files.py')
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location('upload_static_files_under_test', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault('s3_fashionista', mock.MagicMock())
    spec.loader.exec_module(module)
    return module


class TheStaticUploadCanReachS3(unittest.TestCase):

    def setUp(self):
        self.upload = load_upload_module()
        if self.upload is None:
            self.skipTest('upload_static_files.py is not in this checkout')

    def test_it_uploads_through_an_api_boto3_has(self):
        bucket = ABoto3Bucket()
        self.upload.upload(bucket, 'chardata/common.0123abcd.css', 'chardata/common.0123abcd.css')
        self.assertEqual([('chardata/common.0123abcd.css', 'chardata/common.0123abcd.css')],
                         bucket.uploaded)

    def test_the_old_boto2_call_would_have_failed_here(self):
        bucket = ABoto3Bucket()
        with self.assertRaises(AttributeError):
            bucket.new_key('chardata/common.0123abcd.css')

    def test_it_walks_the_folder_collectstatic_writes_to(self):
        self.assertEqual(os.path.normcase(os.path.abspath(settings.STATIC_ROOT)),
                         os.path.normcase(os.path.abspath(self.upload.STATIC_ROOT)))


class AnEmptyBody(object):

    def stream(self, **kwargs):
        return iter([b''])


class TheStaticUploadSendsTheContentType(unittest.TestCase):

    def setUp(self):
        self.upload = load_upload_module()
        if self.upload is None:
            self.skipTest('upload_static_files.py is not in this checkout')
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def _headers_sent_for(self, file_name):
        session = boto3.session.Session(aws_access_key_id='test', aws_secret_access_key='test',
                                        region_name='eu-north-1')
        bucket = session.resource('s3').Bucket('fashionistavanced')
        sent = []

        def answer_without_the_network(request, **kwargs):
            sent.append(request)
            return AWSResponse(request.url, 200, {}, AnEmptyBody())

        bucket.meta.client.meta.events.register('before-send.s3.PutObject',
                                                answer_without_the_network)
        local_path = os.path.join(self.folder, file_name)
        with open(local_path, 'wb') as handle:
            handle.write(b'body { color: black; }')
        with mock.patch.object(self.upload, '_update_progress', lambda amount: None):
            self.upload.upload(bucket, local_path, 'chardata/' + file_name)
        self.assertEqual(1, len(sent))
        return sent[0].headers

    def test_a_stylesheet_goes_up_as_text_css(self):
        self.assertEqual(b'text/css',
                         self._headers_sent_for('common.0123abcd.css').get('Content-Type'))

    def test_an_svg_goes_up_as_an_svg_image(self):
        self.assertEqual(b'image/svg+xml',
                         self._headers_sent_for('logo.0123abcd.svg').get('Content-Type'))

    def test_a_hashed_file_is_cached_like_nginx_caches_it(self):
        self.assertEqual(b'public, max-age=2592000, no-transform',
                         self._headers_sent_for('common.0123abcd.css').get('Cache-Control'))


class TheStaticUploadSendsTheCurrentFiles(unittest.TestCase):

    MANIFEST = {'chardata/common.css': 'chardata/common.2222bbbb.css',
                'chardata/logo.svg': 'chardata/logo.3333cccc.svg'}

    def setUp(self):
        self.upload = load_upload_module()
        if self.upload is None:
            self.skipTest('upload_static_files.py is not in this checkout')
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        self.static_root = os.path.join(self.folder, 'staticfiles')
        os.makedirs(os.path.join(self.static_root, 'chardata'))
        for name in ('common.1111aaaa.css', 'common.2222bbbb.css', 'common.css',
                     'logo.3333cccc.svg', 'logo.svg'):
            with open(os.path.join(self.static_root, 'chardata', name), 'w') as handle:
                handle.write(name)
        with open(os.path.join(self.static_root, 'staticfiles.json'), 'w') as handle:
            json.dump({'paths': self.MANIFEST, 'version': '1.1', 'hash': '0'}, handle)
        self.config_dir = os.path.join(self.folder, 'config')
        os.makedirs(self.config_dir)
        with open(os.path.join(self.config_dir, 'serve_static'), 'w') as handle:
            handle.write('True')
        self.map_path = os.path.join(self.folder, 'static_file_map.csv')
        self.old_rows = [['chardata/common.css', 'chardata/common.1111aaaa.css'],
                         ['chardata/logo.svg', 'chardata/logo.3333cccc.svg']]
        with open(self.map_path, 'w', newline='', encoding='utf-8') as handle:
            csv.writer(handle).writerows(self.old_rows)
        self.commands = []
        self.bucket = ABoto3Bucket()

    def _run(self):
        with mock.patch.object(self.upload, 'STATIC_ROOT', self.static_root), \
                mock.patch.object(self.upload, 'STATIC_FILE_MAP', self.map_path), \
                mock.patch.object(self.upload, 'CONFIG_DIR', self.config_dir), \
                mock.patch.object(self.upload, 'call',
                                  lambda command, **kwargs: self.commands.append(command)), \
                mock.patch.object(self.upload.s3_fashionista, 'get_s3_bucket',
                                  lambda name: self.bucket), \
                mock.patch.object(self.upload, '_update_progress', lambda amount: None), \
                mock.patch('builtins.print'):
            self.upload.main()

    def _map_rows(self):
        with open(self.map_path, newline='', encoding='utf-8') as handle:
            return [row for row in csv.reader(handle) if row]

    def test_collectstatic_leaves_the_served_folder_in_place(self):
        self._run()
        self.assertEqual(1, len(self.commands))
        self.assertIn('collectstatic', self.commands[0])
        self.assertNotIn('--clear', self.commands[0])

    def test_the_map_is_the_manifest(self):
        self._run()
        self.assertEqual(sorted([original, hashed] for original, hashed in self.MANIFEST.items()),
                         self._map_rows())

    def test_only_the_changed_file_goes_up_and_a_stale_copy_never_does(self):
        self._run()
        self.assertEqual([(os.path.join(self.static_root, 'chardata/common.2222bbbb.css'),
                           'chardata/common.2222bbbb.css')], self.bucket.uploaded)

    def test_without_a_manifest_nothing_is_rewritten_or_sent(self):
        os.remove(os.path.join(self.static_root, 'staticfiles.json'))
        with self.assertRaises(SystemExit):
            self._run()
        self.assertEqual(self.old_rows, self._map_rows())
        self.assertEqual([], self.bucket.uploaded)
