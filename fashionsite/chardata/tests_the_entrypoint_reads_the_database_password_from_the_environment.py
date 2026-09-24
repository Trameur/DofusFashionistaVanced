# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import os
import re

from django.test import SimpleTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as handle:
        return handle.read()


class TheEntrypointReadsTheDatabasePasswordFromTheEnvironmentTests(SimpleTestCase):

    def test_the_boot_wait_connects_with_the_environment_password(self):
        script = _read('docker-entrypoint.sh')
        self.assertIn("password=os.environ['DB_PASSWORD']", script)
        self.assertIsNone(re.search(r"password\s*=\s*'[^']*'", script))

    def test_compose_takes_every_password_from_the_environment(self):
        compose = _read('docker-compose.yml')
        for line in compose.splitlines():
            if 'PASSWORD' in line:
                with self.subTest(line=line.strip()):
                    self.assertIn('${', line)

    def test_deploy_refuses_to_run_on_the_public_passwords(self):
        deploy = _read('deploy.sh')
        self.assertIn('"$value" = "fashionista"', deploy)
        self.assertIn('"$value" = "root_password"', deploy)
