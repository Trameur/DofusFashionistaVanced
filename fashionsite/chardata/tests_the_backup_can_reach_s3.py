# -*- coding: utf-8 -*-
"""The database backup has to be able to reach the bucket.

`backup_db.py` called `bucket.new_key(name).set_contents_from_filename(path)`.
That is boto2. `s3_fashionista.get_s3_bucket` returns a **boto3** Bucket, whose
whole action list is Create, Delete, DeleteObjects and PutObject -- read out of
the resource model shipped in boto3 1.43.61, the version this project pins.
There is no `new_key` anywhere in that package.

So every run dumped the database, gzipped it, raised AttributeError, and left
the file in /tmp. Nothing ever reached S3, and nothing said so.

The bucket here exposes only what a real boto3 Bucket exposes, which is what
makes the test worth anything: the old call raises on it exactly as it did in
production.
"""
import importlib.util
import os
import sys
import unittest
from unittest import mock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                    '..', '..'))


def load_backup_module():
    """Import backup_db.py, which lives at the repository root.

    manage.py runs from fashionsite/, so the root is not on sys.path and a
    plain import would not find it.
    """
    path = os.path.join(REPO, 'backup_db.py')
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location('backup_db_under_test', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault('s3_fashionista', mock.MagicMock())
    spec.loader.exec_module(module)
    return module


class ABoto3Bucket(object):
    """Only the surface a real boto3 Bucket has."""

    def __init__(self):
        self.uploaded = []

    def upload_file(self, Filename, Key, Callback=None, **kwargs):
        self.uploaded.append((Filename, Key))
        if Callback:
            Callback(1234)

    def put_object(self, **kwargs):
        raise AssertionError('put_object is not how this script uploads')


class TheBackupCanReachS3(unittest.TestCase):

    def setUp(self):
        self.backup = load_backup_module()
        if self.backup is None:
            self.skipTest('backup_db.py is not in this checkout')

    def test_it_uploads_through_an_api_boto3_has(self):
        bucket = ABoto3Bucket()
        self.backup.upload(bucket, '/tmp/x.dump.gz', 'x.dump.gz')
        self.assertEqual([('/tmp/x.dump.gz', 'x.dump.gz')], bucket.uploaded)

    def test_the_old_boto2_call_would_have_failed_here(self):
        """The positive control: this is the bug, reproduced.

        Without it, the test above would pass against a bucket mock that
        accepts anything, and prove nothing about the real client.
        """
        bucket = ABoto3Bucket()
        with self.assertRaises(AttributeError):
            bucket.new_key('x.dump.gz')

    def test_a_missing_bucket_is_named_not_crashed_through(self):
        with self.assertRaises(RuntimeError) as caught:
            self.backup.upload(None, '/tmp/x.gz', 'x.gz')
        self.assertIn('credentials', str(caught.exception))

    def test_a_failed_dump_stops_the_run(self):
        """A short dump used to be uploaded as if it were a backup."""
        with mock.patch.object(self.backup.subprocess, 'call', return_value=1):
            with mock.patch('builtins.open', mock.mock_open()):
                with self.assertRaises(RuntimeError) as caught:
                    self.backup.dump_database('/tmp/whatever.dump')
        self.assertIn('nothing was backed up', str(caught.exception))

    def test_a_suspiciously_small_dump_stops_the_run(self):
        with mock.patch.object(self.backup.subprocess, 'call', return_value=0):
            with mock.patch('builtins.open', mock.mock_open()):
                with mock.patch.object(self.backup.os.path, 'getsize',
                                       return_value=42):
                    with self.assertRaises(RuntimeError) as caught:
                        self.backup.dump_database('/tmp/whatever.dump')
        self.assertIn('42 bytes', str(caught.exception))
