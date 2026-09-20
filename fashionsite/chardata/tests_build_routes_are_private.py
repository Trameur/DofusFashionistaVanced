# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No build route answers anyone but the owner; the routes come from check_pages.BUILD_PATHS."""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.management.commands.check_pages import BUILD_PATHS
from chardata.models import Char

# What the site serves a stranger when the build is shared; tested on an unshared build, so these refuse too
_PARTAGEABLES = ('/solution/%s/', '/spells/%s/')


class NoBuildRouteAnswersAStrangerTests(TestCase):

    def setUp(self):
        self.proprio = User.objects.create_user(
            username='proprio', email='p@test.local', password='pw-42-solid')
        self.inconnu = User.objects.create_user(
            username='inconnu', email='i@test.local', password='pw-42-solid')
        self.char = Char.objects.create(
            name='projet prive', char_name='perso', char_class='Iop',
            char_build='build', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=b'', options=b'', inclusions=b'',
            exclusions=b'', owner=self.proprio, game_version='dofus3',
            link_shared=False, deleted=False, minimal_solution=b'')

    def _codes_pour(self, client):
        out = []
        for route in BUILD_PATHS:
            chemin = route % self.char.id
            try:
                code = client.get(chemin).status_code
            except Exception as erreur:            # noqa: BLE001
                # An unhandled exception is worse than a 200: the route never considered the case
                code = '%s: %s' % (type(erreur).__name__, str(erreur)[:60])
            out.append((chemin, code))
        return out

    def test_the_route_list_is_not_empty(self):
        self.assertGreaterEqual(
            len(BUILD_PATHS), 20,
            'only %d build routes to walk; this module would be guarding '
            'almost nothing' % len(BUILD_PATHS))

    def test_an_anonymous_stranger_gets_no_page(self):
        codes = self._codes_pour(self.client)
        servies = [(c, k) for c, k in codes if k == 200]
        self.assertFalse(
            servies,
            'these serve an unowned build to an anonymous visitor: %s'
            % servies[:6])

    def test_a_logged_in_stranger_gets_no_page(self):
        self.client.force_login(self.inconnu)
        codes = self._codes_pour(self.client)
        servies = [(c, k) for c, k in codes if k == 200]
        self.assertFalse(
            servies,
            'these serve an unowned build to any logged-in account: %s'
            % servies[:6])

    def test_the_owner_is_not_locked_out(self):
        self.client.force_login(self.proprio)
        codes = self._codes_pour(self.client)
        ouvertes = [c for c, k in codes if k == 200]
        self.assertGreaterEqual(
            len(ouvertes), 3,
            'the owner gets 200 on only %d of the %d build routes, so the two '
            'tests above may be passing on a site that is simply broken: %s'
            % (len(ouvertes), len(BUILD_PATHS), codes[:8]))

    def test_no_build_route_raises_on_a_stranger(self):
        codes = self._codes_pour(self.client)
        casses = [(c, k) for c, k in codes if not isinstance(k, int)]
        self.assertFalse(casses, 'these raise for a stranger: %s' % casses[:4])
