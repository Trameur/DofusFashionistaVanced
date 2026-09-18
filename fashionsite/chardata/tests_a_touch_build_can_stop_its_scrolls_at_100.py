# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch build at level 200 can be scrolled to 0, 100 or 150.

Thibaud, 2026-09-18: "dans un build dofus touch, il me semblait qu'on
proposait parcho 0, 100 ou 150, je vois juste les options parcho 0 ou max".
Touch's three scroll tiers past 100 carry a level 200 condition
(max_scroll_for_version), and a player may stop at 100 all the same. The
wizard and the base characteristics page offered only none or the maximum.

The same day the wizard's "fully scroll" was found reading the cap without the
character's level, so a level 150 Touch build was scrolled to 150, which the
game refuses below level 200.
"""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.models import CharBaseStats
from fashionistapulp.structure import set_current_game_version


class ATouchBuildCanStopItsScrollsAt100Tests(TestCase):

    def _char(self, version='touch', level=200):
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        owner, _ = User.objects.get_or_create(
            username='scroller', defaults={'email': 'sc@test.local'})
        request = RequestFactory().post('/')
        request.user = owner
        char = create_build(request, 'Iop', level, {'str'}, version)
        self.client.force_login(owner)
        return char

    def _prefix(self, char):
        return '' if char.game_version == 'dofus3' else '/' + char.game_version

    def _scrolls(self, char):
        return {row.stat: (row.total_value, row.scrolled_value)
                for row in CharBaseStats.objects.filter(char=char)}

    def test_the_wizard_offers_100_on_touch_at_level_200(self):
        char = self._char()
        page = self.client.get('%s/wizard/%d/' % (self._prefix(char), char.id))
        self.assertContains(page, 'value="hundred"')
        self.assertContains(page, 'Fully scroll my character (150)')

    def test_where_the_cap_is_100_there_is_no_second_choice(self):
        for version, level in (('touch', 150), ('dofus3', 200)):
            with self.subTest(version=version, level=level):
                char = self._char(version, level)
                page = self.client.get('%s/wizard/%d/'
                                       % (self._prefix(char), char.id))
                self.assertNotContains(page, 'value="hundred"')
                setup = self.client.get('%s/setup/%d/'
                                        % (self._prefix(char), char.id))
                self.assertNotContains(setup, 'id="button-scroll-100"')

    def test_retro_offers_100_beside_its_101(self):
        """Retro's cap is a hundred of scrolls plus one point of food."""
        char = self._char('retro', 200)
        page = self.client.get('/retro/wizard/%d/' % char.id)
        self.assertContains(page, 'value="hundred"')
        self.assertContains(page, 'Fully scroll my character (101)')

    def test_the_base_characteristics_page_has_a_100_button(self):
        char = self._char()
        page = self.client.get('/touch/setup/%d/' % char.id)
        self.assertContains(page, 'id="button-scroll-100"')

    def test_choosing_100_scrolls_every_characteristic_to_100(self):
        from chardata.wizard_view import _get_third_scroll_option, _scroll_char_to
        char = self._char()
        row = CharBaseStats.objects.get(char=char, stat='Strength')
        row.total_value, row.scrolled_value = 250, 150
        row.save()
        _scroll_char_to(char, 100)
        scrolls = self._scrolls(char)
        self.assertEqual({100}, {scrolled for _total, scrolled in scrolls.values()})
        self.assertEqual((200, 100), scrolls['Strength'])
        self.assertEqual('hundred', _get_third_scroll_option(char))

    def test_the_wizard_post_takes_the_choice(self):
        char = self._char()
        self.client.post('/touch/wizardpost/%d/' % char.id,
                         {'scrolling': 'hundred'})
        self.assertEqual({100}, {scrolled for _total, scrolled
                                 in self._scrolls(char).values()})

    def test_fully_scrolling_below_level_200_stops_at_100(self):
        from chardata.wizard_view import _full_scroll_char
        char = self._char('touch', 150)
        _full_scroll_char(char)
        self.assertEqual({100}, {scrolled for _total, scrolled
                                 in self._scrolls(char).values()})
