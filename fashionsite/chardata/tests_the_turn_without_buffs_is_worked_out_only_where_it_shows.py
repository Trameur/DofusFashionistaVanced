# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The turn without its buffs costs a second search: only the spells page, which prints it, asks for it."""
from unittest import mock

from django.test import TestCase

import chardata.spell_combo as spell_combo
import chardata.spells_view as spells_view


class _ACraBuild(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_user('author', 'a@x.test', 'pw'))

    def _char(self):
        from chardata.models import Char
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {'text': '\n'.join(names), 'confirm': '1',
                                           'char_class': 'Cra', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _searches(self, action):
        """(best_turn searches, turns without buffs worked out) while action runs."""
        from django.core.cache import cache
        cache.clear()
        with mock.patch.object(spell_combo, 'best_turn',
                               wraps=spell_combo.best_turn) as searched, \
                mock.patch.object(spells_view, '_without_buffs_note',
                                  wraps=spells_view._without_buffs_note) as noted:
            action()
        return searched.call_count, noted.call_count


class ThePagesThatPrintItTests(_ACraBuild):

    def test_the_spells_page_works_it_out(self):
        char = self._char()
        searched, noted = self._searches(lambda: self.client.get('/spells/%d/' % char.id))
        self.assertGreater(searched, 0)
        self.assertEqual(1, noted)

    def test_the_spells_page_refresh_works_it_out(self):
        char = self._char()
        searched, noted = self._searches(lambda: self.client.get('/best_combo/%d/' % char.id))
        self.assertGreater(searched, 0)
        self.assertEqual(1, noted)


class ThePagesThatDoNotTests(_ACraBuild):

    def test_the_build_page_does_not(self):
        char = self._char()
        searched, noted = self._searches(lambda: self.client.get('/solution/%d/' % char.id))
        self.assertGreater(searched, 0, 'the build page no longer reads a best turn')
        self.assertEqual(0, noted)

    def test_the_comparison_does_not(self):
        first, second = self._char(), self._char()
        searched, noted = self._searches(lambda: self.client.get(
            '/compare_sets/%d/%d' % (first.id, second.id)))
        self.assertGreater(searched, 0, 'the comparison no longer reads a best turn')
        self.assertEqual(0, noted)

    def test_the_guarded_solve_does_not(self):
        from chardata.presets import _panel_turn
        from chardata.solution import get_solution
        char = self._char()
        solution = get_solution(char)
        searched, noted = self._searches(lambda: self.assertTrue(_panel_turn(char, solution)))
        self.assertGreater(searched, 0)
        self.assertEqual(0, noted)

    def test_the_spell_modifier_gain_does_not(self):
        from chardata.solution import get_solution
        from chardata.spell_modifier_values import true_gain
        char = self._char()
        solution = get_solution(char)
        searched, noted = self._searches(lambda: true_gain(char, solution, 'dofus3', set()))
        self.assertGreater(searched, 0)
        self.assertEqual(0, noted)
