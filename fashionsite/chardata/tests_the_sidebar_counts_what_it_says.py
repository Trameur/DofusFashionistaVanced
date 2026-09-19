# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The sidebar counter counts what it says."""

import os

from django.test import SimpleTestCase, TestCase


def _gabarit():
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', 'sidebar-stats.html')
    with open(chemin, encoding='utf-8') as f:
        return f.read()


class TheCounterCountsAnswersNotRunsTests(TestCase):

    def test_a_request_served_from_memory_still_counts(self):
        import pickle
        from django.db.models import Sum
        from chardata.models import SolutionCounter, SolutionMemory
        from chardata.solution_memory import DatabaseSolutionMemory

        CLE = 424242424242

        class Demande(object):
            def cache_key(self):
                return CLE

        memoire = DatabaseSolutionMemory()
        demande = Demande()
        # Already cached for this request
        SolutionMemory.objects.create(input_hash=CLE,
                                      input=pickle.dumps('x'),
                                      stored=pickle.dumps(('reponse',)))
        avant = (SolutionCounter.objects.aggregate(t=Sum('get_count'))['t']
                 or 0)
        rendu = memoire.get(demande)
        apres = SolutionCounter.objects.aggregate(t=Sum('get_count'))['t']
        self.assertEqual(('reponse',), rendu, 'the memory did not answer')
        self.assertEqual(avant + 1, apres,
                         'a request answered from memory did not count, so '
                         'the sidebar label may now be the wrong one')


class TheLabelSaysAnswersTests(SimpleTestCase):

    def test_the_sidebar_no_longer_claims_solver_runs(self):
        corps = _gabarit()
        self.assertNotIn('{% trans "solver runs" %}', corps)
        self.assertNotIn('solver run{% plural %}', corps)
        self.assertIn('solver answer{% plural %}solver answers', corps)

    def test_the_label_is_translated_in_the_four_other_languages(self):
        from django.utils.translation import ngettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for nombre, attendu in ((1, 'solver answer'),
                                        (2, 'solver answers')):
                    if ngettext('solver answer', 'solver answers',
                                nombre) == attendu:
                        muettes.append((langue, nombre))
        self.assertEqual([], muettes)

    def test_no_translation_says_generated_on_its_own(self):
        from django.utils.translation import ngettext, override
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for nombre in (1, 2):
                    rendu = ngettext('solver answer', 'solver answers',
                                     nombre).lower()
                    self.assertNotIn('gener', rendu, (langue, nombre, rendu))
                    self.assertNotIn('generier', rendu,
                                     (langue, nombre, rendu))
