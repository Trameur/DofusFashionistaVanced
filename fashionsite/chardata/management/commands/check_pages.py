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

"""Does any public page answer 500, on any version, in any language?

Every 500 this project has had in production was on a public url, and each one
was found by a player or by the error mailbox rather than by us: a GET on a
route that expects a POST, a weapon with no AP cost, a shared build whose
stored solution no longer read back. They are all cheap to find on purpose.

    py fashionsite/manage.py check_pages --settings=fashionsite.settings_test
    py fashionsite/manage.py check_pages --languages fr --only retro

It runs on the test client, so it needs no server, and it walks the same routes
a crawler would, including query strings a crawler invents. Exit code is 1 when
anything answered 500 or raised.
"""
from django.core.management.base import BaseCommand
from django.test import Client

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

# Public routes, without their version prefix.
PATHS = (
    '/', '/encyclopedia/', '/encyclopedia/sets/', '/encyclopedia/monsters/',
    '/guides/', '/forgemagie/', '/sharedbuilds/', '/quickstart/',
    '/about/', '/faq/', '/support/', '/license/', '/privacy/',
)

# What a crawler sends that a form never would.
HOSTILE = (
    '?page=abc', '?page=-1', '?page=99999999', '?page=', '?page[]=1',
    '?type=NoSuchType', '?min_level=abc', '?max_level=-5',
    '?order_by=; DROP TABLE', '?char_class=%00', '?tag=' + 'x' * 300,
    '?hide_invalid=maybe', '?folder=abc', '?top=abc', '?page_size=abc',
)

API = ('/api/v1/shared-builds/', '/api/v1/tier-list/')


class Command(BaseCommand):
    help = 'Walk every public page and report anything that answers 500.'

    def add_arguments(self, parser):
        parser.add_argument('--only', help='one game version')
        parser.add_argument('--languages', default=','.join(LANGUAGES),
                            help='comma separated, default all five')

    def handle(self, *args, **options):
        client = Client()
        versions = [v for v in VERSIONS if not options['only']
                    or v == options['only']]
        languages = [l.strip() for l in options['languages'].split(',') if l.strip()]

        walked = 0
        findings = []

        def visit(path, language):
            nonlocal walked
            walked += 1
            try:
                response = client.get(path, headers={'accept-language': language})
            except Exception as error:                        # noqa: BLE001
                findings.append((path, language, '%s: %s'
                                 % (type(error).__name__, str(error)[:90])))
                return
            if response.status_code >= 500:
                findings.append((path, language, response.status_code))

        for version in versions:
            prefix = '' if version == 'dofus3' else '/' + version
            for language in languages:
                for path in PATHS:
                    visit(prefix + path, language)
            # the query strings only need one language to break a view
            for path in ('/encyclopedia/', '/sharedbuilds/'):
                for query in HOSTILE:
                    visit(prefix + path + query, languages[0])

        for path in API:
            for query in ('', '?page=abc', '?page_size=abc', '?top=abc',
                          '?game_version=nope'):
                visit(path + query, languages[0])

        self.stdout.write('pages walked: %d' % walked)
        if findings:
            self.stdout.write('%d answered 500 or raised:' % len(findings))
            for path, language, what in findings:
                self.stdout.write('   %-46s %-3s %s' % (path[:46], language, what))
            raise SystemExit(1)
        self.stdout.write('no page answered 500')
