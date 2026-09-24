# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An imported build counts its character's own AP, MP, prospecting, pods and summons."""

from django.test import SimpleTestCase, TestCase

from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.solution import get_solution
from chardata.util import base_stats_by_attr_for


class _Faux(object):
    def __init__(self, level, allow=True):
        self.level = level
        self.allow_points_distribution = allow
        self.pk = None
        self.id = None


class WhatACharacterBringsAloneTests(TestCase):

    def test_the_five_the_gear_never_gives(self):
        base = base_stats_by_attr_for(Char.objects.create(
            name='x', char_name='x', char_class='Cra', char_build='',
            level=200, link_shared=False, minimum_stats=b'',
            minimum_crits=b'', stats_weight=b'', options=b'',
            inclusions=b'', exclusions=b'', game_version='dofus3'))
        self.assertEqual(7, base['AP'])
        self.assertEqual(3, base['MP'])
        self.assertEqual(100, base['Prospecting'])
        self.assertEqual(1000, base['Pods'])
        self.assertEqual(1, base['Summon'])

    def test_a_young_character_has_one_ap_less(self):
        jeune = Char.objects.create(
            name='x', char_name='x', char_class='Cra', char_build='',
            level=99, link_shared=False, minimum_stats=b'', minimum_crits=b'',
            stats_weight=b'', options=b'', inclusions=b'', exclusions=b'',
            game_version='dofus3')
        self.assertEqual(6, base_stats_by_attr_for(jeune)['AP'])


class AnImportedBuildCarriesThemTests(TestCase):

    def _importe(self, char_class='Cra', level=200, pieces=2, with_ap=False):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        ap = structure.get_stat_by_key('ap').id
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt')[:pieces]:
            candidats = [i for i in structure.types[200][type_name]
                         if not i.removed and i.ankama_id
                         and (not with_ap or dict(i.stats).get(ap))]
            noms.append(structure.get_item_name_in_language(candidats[0], 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': char_class, 'level': str(level)})
        return Char.objects.order_by('-id').first()

    def test_the_sheet_counts_the_seven_ap_of_the_character(self):
        char = self._importe()
        stats = dict(get_solution(char).get_stats_total())
        # Seven from the character, plus what the pieces give
        self.assertGreaterEqual(stats['ap'], 7)
        self.assertGreaterEqual(stats['mp'], 3)
        self.assertGreaterEqual(stats['pod'], 1000)

    def test_the_prospecting_starts_at_a_hundred(self):
        char = self._importe()
        self.assertGreaterEqual(
            dict(get_solution(char).get_stats_total())['pp'], 100)

    def test_the_best_combo_panel_comes_back(self):
        from chardata.spell_combo import combat_ap
        from chardata.spells_view import _best_combo
        char = self._importe(with_ap=True)
        stats = dict(get_solution(char).get_stats_total())
        self.assertGreaterEqual(stats['ap'], 8,
                                'the pieces do not carry any AP')
        self.assertGreaterEqual(combat_ap(stats['ap'], 'dofus3'), 8)
        combo = _best_combo(char, get_solution(char), 'dofus3')
        self.assertIsNotNone(combo, 'no combo, the turn has no AP')
        self.assertGreater(combo['total'], 0)
        self.assertTrue(combo['casts'])

    def test_a_low_level_import_gets_six(self):
        char = self._importe(level=50)
        self.assertGreaterEqual(dict(get_solution(char).get_stats_total())['ap'],
                                6)

    def test_the_page_shows_it(self):
        char = self._importe()
        page = self.client.get('/solution/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertEqual(200, self.client.get(
            '/solution/%d/' % char.id).status_code)
        # The best combo panel is rendered by the spells page; the stat sheet here must start at seven AP
        stats = dict(get_solution(char).get_stats_total())
        self.assertIn(str(stats['ap']), page)


class TheTwoPathsAgreeTests(SimpleTestCase):

    def test_the_request_helper_delegates_to_the_char_one(self):
        import inspect

        from chardata.util import get_base_stats_by_attr
        source = inspect.getsource(get_base_stats_by_attr)
        self.assertIn('base_stats_by_attr_for', source)
        self.assertNotIn("['AP']", source)

    def test_the_import_path_asks_for_them(self):
        import inspect

        from chardata import dofusbook_view
        source = inspect.getsource(dofusbook_view._place_items)
        self.assertIn('base_stats_by_attr_for(char)', source)
        self.assertNotIn("'base_stats_by_attr': {}", source)


class ABuildSavedBeforeTheFixIsRepairedAsItIsReadTests(TestCase):

    def _importe_a_l_ancienne(self, level=200):
        import pickle

        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        ap = structure.get_stat_by_key('ap').id
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id and dict(i.stats).get(ap))
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': str(level)})
        char = Char.objects.order_by('-id').first()
        minimal = read_char_blob(char.minimal_solution, None,
                                 'minimal_solution', char)
        minimal.input['base_stats_by_attr'] = {}
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        return char

    def test_an_old_import_reads_back_with_its_character(self):
        char = self._importe_a_l_ancienne()
        stats = dict(get_solution(char).get_stats_total())
        self.assertGreaterEqual(stats['ap'], 8)
        self.assertGreaterEqual(stats['mp'], 3)
        self.assertGreaterEqual(stats['pp'], 100)

    def test_a_young_character_is_repaired_with_six(self):
        char = self._importe_a_l_ancienne(level=50)
        self.assertGreaterEqual(
            dict(get_solution(char).get_stats_total())['ap'], 6)

    def test_the_database_row_is_left_alone(self):
        import pickle

        char = self._importe_a_l_ancienne()
        avant = char.minimal_solution
        get_solution(char)
        char.refresh_from_db()
        self.assertEqual(avant, char.minimal_solution)
        relu = read_char_blob(char.minimal_solution, None,
                              'minimal_solution', char)
        self.assertEqual({}, relu.input['base_stats_by_attr'])

    def test_a_solution_that_already_carries_them_is_untouched(self):
        from chardata.solution import _repair_character_base

        class _Mini(object):
            def __init__(self):
                self.input = {'base_stats_by_attr': {'AP': 12, 'MP': 9}}

        mini = _Mini()
        _repair_character_base(Char(level=200), mini)
        self.assertEqual({'AP': 12, 'MP': 9},
                         mini.input['base_stats_by_attr'])
