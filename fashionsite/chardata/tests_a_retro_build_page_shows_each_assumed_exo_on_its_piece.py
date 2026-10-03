# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Retro build asking two AP exos marks the two pieces that carry them and counts both in the AP total."""
import json
import pickle
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.models import Char
from chardata.options import set_options
from chardata.solution import get_solution
from chardata.solution_result import stat_sources
from fashionistapulp.structure import set_current_game_version

_MARK = '>Exo AP<'
_TITLE = 'Exo to forge: the optimizer counts one AP exo on this piece.'


class TheRetroBuildPageMarksEachAssumedExoTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('exomarks', 'exomarks@test.local', 'pw-1234')
        self.client.force_login(self.owner)

    def _solved(self, version, options):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', 200, {'str'}, version)
        set_options(char, options)
        self.client.get('%s/fashion/%d/' % (self._prefix(version), char.id))
        char = Char.objects.get(id=char.id)
        self.assertTrue(char.minimal_solution)
        return char

    @staticmethod
    def _prefix(version):
        return '' if version == 'dofus3' else '/%s' % version

    def _page(self, char):
        response = self.client.get('%s/solution/%d/' % (self._prefix(char.game_version), char.id))
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    @staticmethod
    def _exo_points(page):
        found = re.search(r'EXO_POINTS\s*=\s*(null|\{[^}]*\})', page)
        return json.loads(found.group(1))

    def test_two_ap_exos_mark_two_pieces_and_add_two_ap(self):
        char = self._solved('retro', {'ap_exo': 2, 'mp_exo': 0, 'range_exo': 0})
        self.assertEqual({'ap': 2, 'mp': 0, 'range': 0},
                         pickle.loads(char.minimal_solution).exo_assumed)
        page = self._page(char)
        self.assertEqual(2, page.count(_MARK))
        self.assertEqual(2, page.count(_TITLE))
        self.assertEqual({'ap': 2, 'mp': 0, 'range': 0}, self._exo_points(page))
        set_current_game_version('retro')
        result = get_solution(char)
        worn = [item for item in result.item_list if item.item_added]
        pieces = sum(item.stats.get('ap', 0) for item in worn)
        sets = sum(item_set.get_bonus().get('ap', 0) for item_set in result.sets)
        self.assertEqual(pieces + sets + 2, result.get_stats_gear()['ap'])
        exo_lines = [line for line in stat_sources(result)['ap'] if line['kind'] == 'exo']
        self.assertEqual(2, sum(line['value'] for line in exo_lines))
        self.assertTrue(all(line['label'].endswith(', exo') for line in exo_lines))

    def test_a_solution_saved_before_the_count_places_the_option_count(self):
        char = self._solved('retro', {'ap_exo': 2, 'mp_exo': 0, 'range_exo': 0})
        minimal = pickle.loads(char.minimal_solution)
        del minimal.exo_assumed
        self.assertIsNone(minimal.exo_assumed)
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        page = self._page(char)
        self.assertEqual(2, page.count(_MARK))
        self.assertEqual(2, self._exo_points(page)['ap'])

    def test_dofus3_shows_no_assumed_exo(self):
        char = self._solved('dofus3', {'ap_exo': True, 'mp_exo': True})
        page = self._page(char)
        self.assertNotIn(_MARK, page)
        self.assertIsNone(self._exo_points(page))
        set_current_game_version('dofus3')
        self.assertIn('Exotic bonus', [line['label'] for line
                                       in stat_sources(get_solution(char))['ap']])
