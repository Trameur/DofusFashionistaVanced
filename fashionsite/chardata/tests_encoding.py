# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""User text must survive the full unicode range, 4-byte utf8mb4 included."""

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char


class UnicodeUserTextTests(TestCase):
    def test_project_name_accepts_emoji(self):
        resp = self.client.post('/createproject/', {
            'project': '\U0001F43C 5 pandas',
            'charname': 'Panda',
            'level': '150',
            'class': 'Pandawa',
            'check_str': 'on',
        })
        self.assertIn(resp.status_code, (200, 302),
                      'emoji project name must not 500')
        char = Char.objects.order_by('-id').first()
        self.assertIsNotNone(char)
        self.assertIn('\U0001F43C', char.name)

    def test_turkish_last_name_is_stored(self):
        # The oauth pipeline writes whatever Google sends into auth_user.
        user = User.objects.create_user('turk', 't@test.local', 'pw-42-solid',
                                        first_name='Deniz', last_name='İnal')
        user.refresh_from_db()
        self.assertEqual(user.last_name, 'İnal')

    def test_utf8mb4_migration_is_wired(self):
        from django.db.migrations.loader import MigrationLoader
        loader = MigrationLoader(None, ignore_no_migrations=True)
        self.assertIn(('chardata', '0026_utf8mb4_tables'),
                      loader.disk_migrations)
