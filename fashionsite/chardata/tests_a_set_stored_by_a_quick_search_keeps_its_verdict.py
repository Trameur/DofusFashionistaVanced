# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A set stored by the retired quick search keeps its verdict on every page, and offers no way to continue it."""
import pickle
from types import SimpleNamespace

from django.test import RequestFactory, TestCase

from chardata.solution import get_solution
from chardata.solution_view import _build_og_description, _build_share_text
from chardata.tests_a_search_stopped_on_time_can_go_on import BUTTON, PROVEN, _FlowMixin, _outcome

QUICK = ('Quick search: the solver stopped as soon as it knew this set is within %s%% of the best '
         'on your criteria. A better set may exist, so this is not a proof.')
OG_QUICK = 'Within %s%% of the best, not a proof.'


class AStoredQuickSetKeepsItsVerdictTests(_FlowMixin, TestCase):

    def stored_quick_set(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1030.0))
        minimal = self.minimal(char)
        minimal.proven = False
        minimal.tolerance = 0.03
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        return char

    def test_the_page_says_quick_search_with_how_far_and_never_proven(self):
        page = self.page(self.stored_quick_set())
        self.assertIn(QUICK % '3', page)
        self.assertNotIn('Best set found in', page)
        self.assertNotIn(PROVEN, page)

    def test_the_share_text_says_quick_search(self):
        char = self.stored_quick_set()
        request = RequestFactory().get('/')
        request.game_version = self.version
        text = _build_share_text(request, char, get_solution(char))
        self.assertIn(QUICK % '3', text)
        self.assertNotIn(PROVEN, text)

    def test_the_link_preview_says_how_far_and_not_a_proof(self):
        description = _build_og_description(
            SimpleNamespace(char_class='Cra', level=200, game_version='dofus3'),
            SimpleNamespace(items={}), False, '3')
        self.assertEqual('Cra lvl 200, Dofus 3. ' + OG_QUICK % '3', description)

    def test_a_set_whose_search_key_does_not_match_offers_no_continuation(self):
        char = self.stored_quick_set()
        minimal = self.minimal(char)
        minimal.search = dict(minimal.search or {}, key='another key')
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        self.assertNotIn(BUTTON, self.page(char))
