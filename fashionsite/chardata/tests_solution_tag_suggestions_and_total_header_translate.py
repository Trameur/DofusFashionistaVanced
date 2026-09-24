# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solution page tag suggestions and the Total header are translated."""

import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

SUGGEST_LINK = re.compile(
    r'<a[^>]*class="build-tag-suggest"[^>]*>([^<]*)</a>')
TOTAL_CELL = re.compile(
    r'<td[^>]*class="solution-stat-summary-value-header '
    r'solution-stat-summary-value-cell"[^>]*>([^<]*)</td>')


class SolutionTagSuggestionsAndTotalHeaderTranslateTests(TestCase):

    def _owned_build(self, langue):
        from chardata.coaching_view import create_build
        owner = User.objects.create_user(
            'tag-suggest-%s' % langue, '%s@test.local' % langue, 'pw-42')
        request = RequestFactory().post('/')
        request.user = owner
        char = create_build(request, 'Iop', 200, {'str'}, 'dofus3')
        self.client.force_login(owner)
        return char

    def test_the_group_suggestion_is_translated(self):
        temoins = {'fr': 'Groupe', 'es': 'Grupo', 'pt': 'Grupo', 'de': 'Gruppe'}
        for langue, mot in temoins.items():
            char = self._owned_build(langue)
            page = self.client.get(
                '/%s/solution/%d/' % (langue, char.id),
                follow=True).content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(mot, SUGGEST_LINK.findall(page))

    def test_the_total_header_is_translated(self):
        temoins = {'fr': 'Total', 'es': 'Total', 'pt': 'Total', 'de': 'Gesamt'}
        for langue, mot in temoins.items():
            char = self._owned_build(langue)
            page = self.client.get(
                '/%s/solution/%d/' % (langue, char.id),
                follow=True).content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(mot, TOTAL_CELL.findall(page))
