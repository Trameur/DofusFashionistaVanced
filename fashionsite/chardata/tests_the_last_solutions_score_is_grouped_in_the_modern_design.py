# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The score of a past solution is grouped by thousands in the modern design and left untouched in the classic one."""

import os
import re

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation

HERE = os.path.dirname(__file__)
SCORE_BLOCK = re.compile(r'<div class="solution-history-entry-score">.*?\n                    </div>', re.S)


def _block():
    with open(os.path.join(HERE, 'templates', 'chardata', 'solution.html'), encoding='utf-8') as handle:
        return SCORE_BLOCK.search(handle.read()).group(0)


class TheLastSolutionsScoreTests(SimpleTestCase):

    def _render(self, score, delta):
        template = Template('{% load i18n %}' + _block())
        generation = {'score': score, 'has_score_delta': True, 'score_delta': delta, 'score_delta_class': 'positive',
                      'score_delta_text': '%+d' % delta}
        with translation.override('fr'):
            return template.render(Context({'generation': generation}))

    def test_the_modern_score_is_grouped_and_the_classic_one_is_raw(self):
        html = self._render(225980, 12345)
        modern = re.search(r'<strong class="fm-modern-only">(.*?)</strong>', html).group(1)
        classic = re.search(r'<strong class="fm-classic-only">(.*?)</strong>', html).group(1)
        self.assertEqual('225980', classic)
        self.assertRegex(modern, r'^225\s980$')

    def test_the_modern_delta_is_grouped_with_its_sign(self):
        html = self._render(1, 12345)
        modern = re.search(r'<span class="[^"]*\bfm-modern-only">(.*?) <span>', html).group(1)
        classic = re.search(r'<span class="[^"]*\bfm-classic-only">\s*(.*?) <span>', html).group(1)
        self.assertEqual('+12345', classic)
        self.assertRegex(modern, r'^\+12\s345$')

    def test_a_negative_delta_keeps_its_minus_sign(self):
        html = self._render(1, -4321)
        modern = re.search(r'<span class="[^"]*\bfm-modern-only">(.*?) <span>', html).group(1)
        self.assertRegex(modern, r'^-4\s321$')
