# -*- coding: utf-8 -*-
"""requirements_aws.txt must install what the Docker image runs, plus only what Apache needs."""
import os
import re
import unittest

from chardata.tests_the_backup_can_reach_s3 import REPO

PIN = re.compile(r'^([A-Za-z0-9._-]+)==([^\s#;]+)', re.M)
AWS_ONLY = {'mod-wsgi'}


def read_pins(name):
    path = os.path.join(REPO, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as handle:
        return {re.sub(r'[-_.]+', '-', package).lower(): version
                for package, version in PIN.findall(handle.read())}


class TheAwsRequirementsFollowTheDockerPins(unittest.TestCase):

    def setUp(self):
        self.docker = read_pins('requirements-docker.txt')
        self.aws = read_pins('requirements_aws.txt')
        if self.docker is None or self.aws is None:
            self.skipTest('a requirements file is not in this checkout')

    def test_every_docker_pin_is_in_the_aws_file_at_the_same_version(self):
        self.assertGreater(len(self.docker), 30)
        differences = {package: (version, self.aws.get(package))
                       for package, version in self.docker.items()
                       if self.aws.get(package) != version}
        self.assertEqual({}, differences)

    def test_the_aws_file_adds_only_the_apache_module(self):
        self.assertEqual(AWS_ONLY, set(self.aws) - set(self.docker))
