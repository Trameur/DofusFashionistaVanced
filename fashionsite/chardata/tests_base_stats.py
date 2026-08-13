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

"""Base stats page: cost curve per game version, and the save round trip."""

import unittest

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from fashionistapulp.dofus_constants import (DEFAULT_SOFT_CAPS,
                                             scrolls_push_cost_curve,
                                             tier_widths_after_scroll)


def _pulp_solver_available():
    try:
        import pulp
        return pulp.PULP_CBC_CMD(msg=False).available()
    except Exception:
        return False


class ScrollCostCurveTests(TestCase):
    def test_only_retro_pushes_the_curve(self):
        for version, expected in (('dofus3', False), ('beta', False),
                                  ('dofus2', False), ('touch', False),
                                  ('retro', True)):
            self.assertEqual(scrolls_push_cost_curve(version), expected, version)

    def test_tier_widths_stay_full_when_scroll_is_ignored(self):
        # The modern path passes scrolled=0: the first 100 points cost 1:1.
        self.assertEqual(tier_widths_after_scroll(DEFAULT_SOFT_CAPS['str'], 0),
                         [0, 100, 100, 100, None, 0])

    def test_base_stats_page_flags_the_curve_per_version(self):
        owner = User.objects.create_user('curve', 'cv@test.local', 'pw-42-solid')
        req = RequestFactory().post('/')
        req.user = owner
        from chardata.coaching_view import create_build

        cases = (('dofus3', '', 'scrollsPushCurve = false'),
                 ('retro', '/retro', 'scrollsPushCurve = true'),
                 ('touch', '/touch', 'scrollsPushCurve = false'))
        self.client.force_login(owner)
        for version, prefix, needle in cases:
            with self.subTest(version=version):
                char = create_build(req, 'Iop', 100, {'str'}, version)
                resp = self.client.get('%s/setup/%d/' % (prefix, char.pk))
                self.assertEqual(resp.status_code, 200)
                self.assertIn(needle, resp.content.decode('utf-8'))

    @unittest.skipUnless(_pulp_solver_available(), 'no pulp solver available')
    def test_dofus3_distribution_ignores_scrolls_on_the_cost_curve(self):
        # Iop 200 str with the default scrolled 100: the 995 points must fill
        # the 1:1, 2:1 and 3:1 tiers and reach into 4:1.
        from chardata.coaching_view import create_build
        from chardata.solution import get_solution
        from chardata.util import get_stats

        owner = User.objects.create_user('curve2', 'cv2@test.local', 'pw-42-solid')
        req = RequestFactory().post('/')
        req.user = owner
        char = create_build(req, 'Iop', 200, {'str'}, 'dofus3')
        self.assertTrue(char.allow_points_distribution)
        self.client.force_login(owner)
        resp = self.client.get('/fashion/%d/' % char.pk)
        self.assertIn(resp.status_code, (200, 302))
        char.refresh_from_db()
        self.assertIsNotNone(get_solution(char))
        strength = get_stats(char)['Strength']
        self.assertGreaterEqual(
            strength, 390,
            'distribution still pays the scrolled tiers: %d str' % strength)


class ChooseStatsCheckboxTests(TestCase):
    """A save from the page keeps the "Distribute the points for me" box as
    the user left it, in both directions."""

    def _char(self, owner):
        from chardata.coaching_view import create_build
        req = RequestFactory().post('/')
        req.user = owner
        return create_build(req, 'Iop', 100, {'str'}, 'dofus3')

    def _save_payload(self, with_checkbox):
        payload = {}
        for abr in ('vit', 'wis', 'str', 'int', 'cha', 'agi'):
            payload['scrolled_%s' % abr] = '0'
            payload['points_%s' % abr] = '0'
        if with_checkbox:
            # The exact value a real browser posts for this form.
            payload['choose_stats'] = 'choose_stats'
        return payload

    def test_checkbox_survives_a_real_browser_save(self):
        owner = User.objects.create_user('cbx', 'cbx@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        char = self._char(owner)

        resp = self.client.post('/save_char/%d/' % char.pk,
                                self._save_payload(with_checkbox=True))
        self.assertEqual(resp.status_code, 200)
        char.refresh_from_db()
        self.assertTrue(char.allow_points_distribution)
        # The page's state engine reuses this response as its reference state.
        self.assertIn('"distrib": true', resp.content.decode('utf-8'))

    def test_unchecking_then_rechecking_round_trips(self):
        owner = User.objects.create_user('cbx2', 'cbx2@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        char = self._char(owner)

        self.client.post('/save_char/%d/' % char.pk,
                         self._save_payload(with_checkbox=False))
        char.refresh_from_db()
        self.assertFalse(char.allow_points_distribution)

        self.client.post('/save_char/%d/' % char.pk,
                         self._save_payload(with_checkbox=True))
        char.refresh_from_db()
        self.assertTrue(char.allow_points_distribution)


class BaseStatsBoundsTests(TestCase):
    """A stat typed out of range is saved clamped, and the save still goes
    through."""

    def _char(self, owner):
        from chardata.coaching_view import create_build
        req = RequestFactory().post('/')
        req.user = owner
        return create_build(req, 'Iop', 100, {'str'}, 'dofus3')

    def _payload(self, **overrides):
        payload = {}
        for abr in ('vit', 'wis', 'str', 'int', 'cha', 'agi'):
            payload['scrolled_%s' % abr] = '0'
            payload['points_%s' % abr] = '0'
        payload.update(overrides)
        return payload

    def _saved(self, char, stat):
        from chardata.models import CharBaseStats
        return CharBaseStats.objects.get(char=char, stat=stat)

    def test_a_stat_far_above_the_ceiling_is_saved_clamped(self):
        from chardata.base_stats_view import MAX_TOTAL_VALUE
        owner = User.objects.create_user('bnd', 'bnd@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        char = self._char(owner)

        resp = self.client.post('/save_char/%d/' % char.pk,
                                self._payload(points_cha='04000', scrolled_cha='100'))
        self.assertEqual(resp.status_code, 200)
        chance = self._saved(char, 'Chance')
        self.assertEqual(chance.total_value, MAX_TOTAL_VALUE)
        self.assertEqual(chance.scrolled_value, 100)

    def test_a_negative_stat_is_saved_at_zero(self):
        owner = User.objects.create_user('bnd2', 'bnd2@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        char = self._char(owner)

        resp = self.client.post('/save_char/%d/' % char.pk,
                                self._payload(points_str='-500'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._saved(char, 'Strength').total_value, 0)

    def test_scrolls_above_the_version_cap_come_back_to_it(self):
        from fashionistapulp.dofus_constants import max_scroll_for_version
        owner = User.objects.create_user('bnd3', 'bnd3@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        char = self._char(owner)

        resp = self.client.post('/save_char/%d/' % char.pk,
                                self._payload(scrolled_agi='9999'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._saved(char, 'Agility').scrolled_value,
                         max_scroll_for_version('dofus3'))
