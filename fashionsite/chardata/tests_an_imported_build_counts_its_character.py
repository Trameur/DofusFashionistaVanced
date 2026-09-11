# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un build importe compte le personnage, pas seulement son stuff.

Mesure du 11 septembre 2026 sur la page de solution d'un Cra de niveau 200
importe: <<PA 2+1>>, <<PM 1+1>>, <<Prospection 92>>. Un personnage de ce
niveau a sept PA, trois PM, cent de prospection, mille pods et une invocation
de son propre chef. Le site le sait depuis toujours
(`util.base_stats_by_attr_for`) et c'est ce que le chemin du solveur lui
donne; le chemin de l'import partait avec un dictionnaire vide.

Deux consequences, toutes deux visibles:

- la feuille du build montrait sept PA de moins que la verite;
- le panneau <<meilleur combo de ce tour>> disparaissait, parce qu'un tour a
  deux PA n'a rien a lancer et que le calcul rend alors None.

Les six caracteristiques, elles, n'etaient pas concernees: elles sont
rafraichies a chaque lecture par `ModelResultMinimal.update_base_stats`. Ce
sont les cinq autres qui manquaient, parce que rien d'autre ne les ecrit.
"""

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
        """La regle du site, inchangee: sept PA a partir du niveau 100."""
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
        """Un build importe, et au besoin avec des pieces qui portent des PA.

        `with_ap` n'est pas un detail: `spell_combo.combat_ap` lit
        `total_ap or BASE_AP`, donc un stuff qui ne donne AUCUN PA retombait
        sur six et masquait le defaut. Il ne mordait que quand les pieces en
        donnaient un peu, ce qui est le cas de tout vrai build, et c'est
        exactement pourquoi il a vecu si longtemps.
        """
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
        # Sept du personnage, plus ce que les pieces donnent.
        self.assertGreaterEqual(stats['ap'], 7)
        self.assertGreaterEqual(stats['mp'], 3)
        self.assertGreaterEqual(stats['pod'], 1000)

    def test_the_prospecting_starts_at_a_hundred(self):
        char = self._importe()
        self.assertGreaterEqual(
            dict(get_solution(char).get_stats_total())['pp'], 100)

    def test_the_best_combo_panel_comes_back(self):
        """La consequence que le lecteur voyait: avec deux PA le calcul rend
        None et la page n'affiche rien du tout."""
        from chardata.spell_combo import combat_ap
        from chardata.spells_view import _best_combo
        char = self._importe(with_ap=True)
        stats = dict(get_solution(char).get_stats_total())
        self.assertGreaterEqual(stats['ap'], 8,
                                'les pieces ne portent pas de PA')
        self.assertGreaterEqual(combat_ap(stats['ap'], 'dofus3'), 8)
        combo = _best_combo(char, get_solution(char), 'dofus3')
        self.assertIsNotNone(combo, 'aucun combo, le tour n a pas ses PA')
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
        # Le panneau du meilleur combo est rendu par la page des sorts, mais
        # la feuille de stats est ici: elle doit porter un nombre de PA qui
        # commence au moins a sept.
        stats = dict(get_solution(char).get_stats_total())
        self.assertIn(str(stats['ap']), page)


class TheTwoPathsAgreeTests(SimpleTestCase):
    """Une seule source pour ce que le personnage porte: si le chemin du
    solveur et celui de l'import s'en donnaient deux, ils divergeraient a la
    premiere correction."""

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
    """Les builds deja importes ne sont pas reecrits: ils sont repares a la
    lecture. Rien ne touche la base ([[no-retrofit-user-builds]]), et les
    cinq valeurs ne dependent que du niveau, donc la reparation ne coute
    aucune requete."""

    def _importe_a_l_ancienne(self, level=200):
        """Un build importe puis remis dans l'etat d'avant le correctif."""
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
        """La reparation vit en memoire: la ligne stockee ne bouge pas."""
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
        """Un build passe par le solveur porte ses cinq valeurs: la
        reparation ne doit pas ecraser ce qui est deja la."""
        from chardata.solution import _repair_character_base

        class _Mini(object):
            def __init__(self):
                self.input = {'base_stats_by_attr': {'AP': 12, 'MP': 9}}

        mini = _Mini()
        _repair_character_base(Char(level=200), mini)
        self.assertEqual({'AP': 12, 'MP': 9},
                         mini.input['base_stats_by_attr'])
