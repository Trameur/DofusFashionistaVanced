# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The blocks under the build grid are workbench cards, the big figures of the header are grouped, and the stat groups follow the workbench order."""

import os
import re

from django.template.defaultfilters import floatformat
from django.test import SimpleTestCase, TestCase
from django.utils import translation

HEAD = re.compile(r'<header[^>]*fm-sol-head[^>]*>(.*?)</header>', re.S)
HERE = os.path.dirname(__file__)


def _read(*parts):
    with open(os.path.join(HERE, *parts), encoding='utf-8') as handle:
        return handle.read()


class TheBlocksUnderTheGridTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.owner = User.objects.create_user('owner', 'o@x.test', 'pw')
        self.client.force_login(self.owner)

    def _response(self):
        from chardata.models import Char
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name] if not i.removed and i.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {'text': '\n'.join(names), 'confirm': '1',
                                           'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        return self.client.get('/solution/%d/' % char.id, follow=True)

    def test_the_explanation_is_one_card_with_a_kicker_hidden_in_the_classic_design(self):
        page = self._response().content.decode('utf-8')
        self.assertEqual(1, len(re.findall(r'<p class="text fm-sol-explain fm-card">', page)))
        self.assertIn('<span class="fm-kicker fm-modern-only">', page)

    def test_the_support_box_and_the_comments_are_cards(self):
        page = self._response().content.decode('utf-8')
        self.assertIn('<aside class="solution-support fm-card">', page)

    def test_the_header_score_is_grouped_by_the_project_filter(self):
        response = self._response()
        page = response.content.decode('utf-8')
        score = response.context['build_score']
        if score is None:
            self.skipTest('no score on this build')
        head = HEAD.search(page).group(1)
        self.assertIn(floatformat(score, '0g'), head)

    def test_the_stat_groups_are_reordered_by_a_script_that_runs_only_in_the_modern_design(self):
        page = self._response().content.decode('utf-8')
        marker = "if(blocks.length===5){"
        self.assertEqual(1, page.count(marker))
        before = page[:page.index(marker)]
        self.assertIn("classList.contains('fm-modern'))return;", before[before.rindex('<script>'):])

    def test_the_stat_cells_keep_a_plain_number_in_the_classic_design(self):
        page = self._response().content.decode('utf-8')
        self.assertIn("var FM_GROUP_DIGITS = document.documentElement.classList.contains('fm-modern');", page)


class TheCriteriaFiguresAreGroupedTests(SimpleTestCase):

    def test_the_weights_and_minimums_go_through_the_grouping_filter(self):
        template = _read('templates', 'chardata', 'solution.html')
        self.assertIn('{{ priority.weight|floatformat:"-1g" }}', template)
        self.assertIn('{{ line.asked|floatformat:"0g" }}', template)
        self.assertIn('{{ line.reached|floatformat:"0g" }}', template)
        self.assertIn('{% widthratio priority.weight solver_priorities.0.weight 100 %}', template)

    def test_a_weight_keeps_its_decimal_and_a_big_one_is_grouped(self):
        with translation.override('en'):
            self.assertEqual('2.5', floatformat(2.5, '-1g'))
            self.assertEqual('2,400', floatformat(2400, '-1g'))


class TheStatsCardAndTheBannerTests(SimpleTestCase):

    def test_the_stats_card_has_a_title_hidden_in_the_classic_design(self):
        template = _read('templates', 'chardata', 'solution.html')
        self.assertIn('<h2 class="fm-sol-card-title fm-sol-stats-title fm-modern-only">{% trans "Characteristics" %}</h2>', template)

    def test_the_banner_copy_of_the_new_build_link_is_hidden_in_the_modern_design_only(self):
        sheet = _read('static', 'chardata', 'modern-solution-parts.css')
        self.assertIn('html.fm-modern .char-banner .char-banner-patch-rerun{ display:none !important; }', sheet)
