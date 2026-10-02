# -*- coding: utf-8 -*-
"""On an Amazon Linux 2023 host, python3 is 3.9 and Django 6.0 needs 3.12: every EC2 job must name its Python."""
import importlib.util
import os
import re
import types
import unittest
from unittest import mock

from chardata.tests_the_backup_can_reach_s3 import REPO

CRON_FILES = ('cronjobs_for_user.txt', 'cronjobs_for_root.txt')
COMMAND = re.compile(r';\s*(\S+)\s+(\S+\.py)\b')
THIRD_PARTY = re.compile(r'^\s*(import|from)\s+(django|boto3|s3_fashionista|pymysql)\b', re.M)


def cron_commands():
    commands = []
    for name in CRON_FILES:
        path = os.path.join(REPO, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                if line.strip() and not line.lstrip().startswith('#'):
                    commands.append((name, line.strip()))
    return commands


def load_root_configuration():
    path = os.path.join(REPO, 'configure_fashionista_root.py')
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location('configure_fashionista_root_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheCronJobsNameTheirPython(unittest.TestCase):

    def setUp(self):
        self.commands = cron_commands()
        if not self.commands:
            self.skipTest('no cron file in this checkout')

    def test_every_job_runs_an_existing_script_through_an_interpreter(self):
        self.assertEqual(3, len(self.commands))
        for name, line in self.commands:
            with self.subTest(cron=name, line=line):
                match = COMMAND.search(line)
                self.assertIsNotNone(match)
                self.assertRegex(match.group(1), r'^python3(\.\d+)?$')
                self.assertTrue(os.path.exists(os.path.join(REPO, match.group(2))))

    def test_the_jobs_that_import_the_site_packages_run_on_python_3_12_or_later(self):
        checked = 0
        for name, line in self.commands:
            interpreter, script = COMMAND.search(line).groups()
            with open(os.path.join(REPO, script), encoding='utf-8') as handle:
                if not THIRD_PARTY.search(handle.read()):
                    continue
            checked += 1
            with self.subTest(cron=name, script=script):
                minor = re.fullmatch(r'python3\.(\d+)', interpreter)
                self.assertIsNotNone(minor, interpreter)
                self.assertGreaterEqual(int(minor.group(1)), 12)
        self.assertEqual(2, checked)


class TheRootConfigurationInstallsTheAwsRequirements(unittest.TestCase):

    def setUp(self):
        self.module = load_root_configuration()
        if self.module is None:
            self.skipTest('configure_fashionista_root.py is not in this checkout')

    def _install_on(self, version_info):
        fake_sys = types.SimpleNamespace(version_info=version_info,
                                         executable='/usr/bin/python%d.%d' % version_info[:2])
        with mock.patch.object(self.module, 'sys', fake_sys), \
                mock.patch.object(self.module, 'call') as call, \
                mock.patch('builtins.print'):
            self.module._install_linux_python_packages(self.module.REQUIREMENTS_FILES['yum'])
        return call

    def test_amazon_linux_installs_the_aws_requirements_with_the_python_that_runs_the_script(self):
        call = self._install_on((3, 14, 0))
        call.assert_called_once()
        command = call.call_args[0][0]
        self.assertEqual(['/usr/bin/python3.14', '-m', 'pip', 'install', '-r'], command[:5])
        self.assertEqual(os.path.normcase(os.path.join(REPO, 'requirements_aws.txt')),
                         os.path.normcase(command[5]))
        self.assertTrue(os.path.exists(command[5]))

    def test_the_python_amazon_linux_calls_python3_installs_nothing(self):
        self.assertFalse(self._install_on((3, 9, 16)).called)

    def test_amazon_linux_installs_the_python_it_then_needs(self):
        packages = self.module.PACKAGES_TO_INSTALL['yum']
        for package in ('python3.14', 'python3.14-devel', 'python3.14-pip', 'httpd-devel', 'gcc'):
            self.assertIn(package, packages)
