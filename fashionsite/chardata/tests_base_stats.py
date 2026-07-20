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

"""Characteristic point cost curve, per game version.

User report (2026-07-10): on Dofus 3 the first 100 invested points cost 200
instead of 100. Root cause: the engine applied the RETRO rule (scrolled
points consume the cheap cost tiers) to every version, and characters carry
scrolled=100 by default. Since Dofus 2.48 (October 2018) scrolls are tracked
separately and never push the cost curve; only Retro (1.29) and Touch (2.x
fork frozen before 2.48) keep the old rule.

Separate module from tests.py so it can evolve without touching the shared
test file (the worktree is shared with a second session).
"""

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
        # Touch adopted the post-2.48 separate tracking despite its 2.x
        # origin: a live Touch character (int scrolled 51, 305 invested)
        # was charged the flat 925, not the pushed 1078; the site's -153
        # mismatch (2026-07-20 player report) pinned the rule down.
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
        # Iop 200, str build, scrolled 100 everywhere (the default seed):
        # 995 points must fill the 1/2/3 tiers (300 str for 600 points) and
        # push into 4:1, landing at 398. The old retro-rule behavior started
        # at the 2:1 tier and stopped at 323.
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
