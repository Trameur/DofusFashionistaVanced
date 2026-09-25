# -*- coding: utf-8 -*-
"""The backup must name the database host, not connect through a local unix socket the container has none of."""
import os
import unittest
from unittest import mock

from chardata.tests_the_backup_can_reach_s3 import load_backup_module


class TheDumpConnectsWhereTheSiteConnects(unittest.TestCase):

    def setUp(self):
        self.backup = load_backup_module()
        if self.backup is None:
            self.skipTest('backup_db.py is not in this checkout')

    def _command_for(self, environment):
        """The argv mysqldump would be called with, and the env it would see."""
        seen = {}

        def fake_call(command, stdout=None, env=None):
            seen['command'] = command
            seen['env'] = env
            stdout.write(b'x' * (self.backup.MINIMUM_DUMP_BYTES + 1))
            return 0

        with mock.patch.dict(os.environ, environment, clear=False), \
                mock.patch.object(self.backup.subprocess, 'call', fake_call):
            self.backup.dump_database(os.devnull if False else self._tmp())
        return seen

    def _tmp(self):
        import tempfile
        handle = tempfile.NamedTemporaryFile(delete=False, suffix='.dump')
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name)
                        and os.remove(handle.name))
        return handle.name

    def test_the_host_is_named_instead_of_a_local_socket(self):
        seen = self._command_for({'DB_HOST': 'mysql', 'DB_PORT': '3306',
                                  'DB_USER': 'someone', 'DB_PASSWORD': 'p'})
        command = seen['command']
        self.assertIn('--host', command)
        self.assertEqual('mysql', command[command.index('--host') + 1])
        self.assertEqual('3306', command[command.index('--port') + 1])
        self.assertEqual('someone', command[command.index('--user') + 1])
        # The database name stays last, as mysqldump expects.
        self.assertEqual(self.backup.MYSQL_DB_NAME, command[-1])

    def test_the_password_never_appears_on_the_command_line(self):
        # ps shows the argv of every process to every user on the machine.
        seen = self._command_for({'DB_HOST': 'mysql', 'DB_USER': 'someone',
                                  'DB_PASSWORD': 'notonthecommandline'})
        self.assertNotIn('notonthecommandline', ' '.join(seen['command']))
        self.assertEqual('notonthecommandline', seen['env']['MYSQL_PWD'])

    def test_the_dump_is_consistent_while_the_site_writes(self):
        seen = self._command_for({'DB_HOST': 'mysql'})
        self.assertIn('--single-transaction', seen['command'])

    def test_a_failed_dump_is_still_refused(self):
        # Control: the guard that made this bug visible must survive the fix.
        def failing_call(command, stdout=None, env=None):
            return 2

        with mock.patch.object(self.backup.subprocess, 'call', failing_call):
            with self.assertRaises(RuntimeError):
                self.backup.dump_database(self._tmp())

    def test_a_short_dump_is_still_refused(self):
        # Second control: a connection that works but writes an error message.
        def tiny_call(command, stdout=None, env=None):
            stdout.write(b'ERROR 1045: access denied\n')
            return 0

        with mock.patch.object(self.backup.subprocess, 'call', tiny_call):
            with self.assertRaises(RuntimeError):
                self.backup.dump_database(self._tmp())
