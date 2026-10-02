# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import os
import re

from django.db.backends.mysql.base import DatabaseWrapper
from django.test import SimpleTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGE = re.compile(r'^\s*image:\s*mysql:(\d+)\.(\d+)(?:\.\d+)?\s*$', re.MULTILINE)


def _compose_mysql_version():
    with open(os.path.join(ROOT, 'docker-compose.yml'), encoding='utf-8') as handle:
        match = IMAGE.search(handle.read())
    return match and (int(match.group(1)), int(match.group(2)))


def _django_mysql_floor():
    wrapper = DatabaseWrapper({})
    wrapper.__dict__['mysql_is_mariadb'] = False
    return wrapper.features.minimum_database_version[:2]


class TheMysqlImageMeetsTheDjangoFloorTests(SimpleTestCase):

    def test_the_mysql_image_names_a_numbered_version(self):
        self.assertIsNotNone(_compose_mysql_version())

    def test_the_mysql_image_is_not_older_than_the_oldest_mysql_django_accepts(self):
        self.assertGreaterEqual(_compose_mysql_version(), _django_mysql_floor())
