# -*- coding: utf-8 -*-
"""The container refuses to start with a public default secret, and says only which keys."""
import contextlib
import io
import json
import os
import tempfile

from unittest import mock

from django.test import SimpleTestCase

import check_docker_secrets
from merge_docker_config import DEFAULT_CONFIG

PRIVATE = {
    'SECRET_KEY': 'k-7f3a91',
    'PASSWORD_RESET_SALT': 's-1c22d0',
    'EMAIL_CONFIRMATION_SALT': 's-9ab044',
    'char_id_SECRET_PART_1': 'p-5e6b12',
    'char_id_SECRET_PART_2': 'p-0d83c7',
}


class TheBootCheck(SimpleTestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def write(self, config, debug='False'):
        with open(os.path.join(self.folder.name, 'gen_config.json'), 'w') as handle:
            json.dump(config, handle)
        with open(os.path.join(self.folder.name, 'debug_mode'), 'w') as handle:
            handle.write(debug + '\r\n')

    def run_check(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            status = check_docker_secrets.main(self.folder.name)
        return status, errors.getvalue()

    def private_config(self, **changes):
        config = dict(DEFAULT_CONFIG)
        config.update(PRIVATE)
        config.update(changes)
        return config

    def test_a_config_with_five_private_secrets_boots(self):
        self.write(self.private_config())
        self.assertEqual(self.run_check()[0], 0)

    def test_each_guarded_key_on_its_default_stops_the_boot_and_is_named(self):
        for key in check_docker_secrets.GUARDED_KEYS:
            with self.subTest(key=key):
                self.write(self.private_config(**{key: DEFAULT_CONFIG[key]}))
                status, message = self.run_check()
                self.assertEqual(status, 1)
                self.assertIn(key, message)

    def test_the_message_never_holds_a_value(self):
        self.write(self.private_config(SECRET_KEY=DEFAULT_CONFIG['SECRET_KEY']))
        message = self.run_check()[1]
        for value in list(PRIVATE.values()) + [DEFAULT_CONFIG['SECRET_KEY']]:
            self.assertNotIn(value, message)

    def test_every_default_at_once_names_all_five_keys(self):
        self.write(dict(DEFAULT_CONFIG))
        message = self.run_check()[1]
        for key in check_docker_secrets.GUARDED_KEYS:
            self.assertIn(key, message)

    def test_debug_on_lets_the_defaults_boot(self):
        self.write(dict(DEFAULT_CONFIG), debug='True')
        self.assertEqual(self.run_check()[0], 0)

    def test_an_optional_key_on_its_default_or_missing_does_not_stop_the_boot(self):
        config = self.private_config(mysql_PASSWORD=DEFAULT_CONFIG['mysql_PASSWORD'])
        del config['google_analytics_id']
        del config['TESTER_USERS_EMAILS']
        self.write(config)
        self.assertEqual(self.run_check()[0], 0)

    def test_a_guarded_key_missing_from_the_file_is_not_this_checks_to_judge(self):
        config = self.private_config()
        del config['char_id_SECRET_PART_2']
        self.write(config)
        self.assertEqual(self.run_check()[0], 0)

    def test_an_unreadable_config_stops_the_boot(self):
        with open(os.path.join(self.folder.name, 'gen_config.json'), 'w') as handle:
            handle.write('{not json')
        self.assertEqual(self.run_check()[0], 1)

    def test_the_folder_comes_from_the_settings_variable_when_it_is_set(self):
        self.write(dict(DEFAULT_CONFIG))
        with mock.patch.dict(os.environ, {'FASHIONISTA_CONFIG_DIR': self.folder.name}):
            self.assertEqual(check_docker_secrets.main(), 1)
        self.write(self.private_config())
        with mock.patch.dict(os.environ, {'FASHIONISTA_CONFIG_DIR': self.folder.name}):
            self.assertEqual(check_docker_secrets.main(), 0)

    def test_without_the_variable_the_image_folder_is_read(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('FASHIONISTA_CONFIG_DIR', None)
            self.assertEqual(check_docker_secrets.configured_dir(),
                             check_docker_secrets.CONFIG_DIR)

    def test_the_guarded_keys_all_have_a_public_default_to_compare_with(self):
        for key in check_docker_secrets.GUARDED_KEYS:
            self.assertIn(key, DEFAULT_CONFIG)
