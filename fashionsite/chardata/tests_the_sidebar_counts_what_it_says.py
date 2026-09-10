# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le compteur de la barre laterale dit ce qu'il compte.

Le lot A bis avait remplace <<stuffs generes>> par <<solver runs>>. Mesure du
10 septembre 2026 sur le code: le nombre est la somme des `get_count` de
SolutionCounter, et `DatabaseSolutionMemory.get` l'incremente AVANT de
regarder la memoire. Une demande servie depuis la memoire, sans faire tourner
le solveur, compte donc autant qu'un calcul. <<solver runs>> disait plus que
le chiffre, et le disait sur chaque page, sous 442 243 en production.

Une reponse servie de memoire reste une reponse du solveur, calculee une
premiere fois pour la meme demande: <<reponses du solveur>> est vrai dans
les deux cas, et le nombre garde son histoire cumulee depuis 2016.
"""

import os

from django.test import SimpleTestCase, TestCase


def _gabarit():
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', 'sidebar-stats.html')
    with open(chemin, encoding='utf-8') as f:
        return f.read()


class TheCounterCountsAnswersNotRunsTests(TestCase):
    """La mesure qui justifie le libelle, gardee comme un test: si un jour
    le compteur ne bouge plus sur une reponse de memoire, le libelle
    <<reponses>> devient a son tour trop large et ce test le dira."""

    def test_a_request_served_from_memory_still_counts(self):
        import pickle
        from django.db.models import Sum
        from chardata.models import SolutionCounter, SolutionMemory
        from chardata.solution_memory import DatabaseSolutionMemory

        # La cle est un entier en base, comme ce que cache_key() rend pour
        # une vraie demande.
        CLE = 424242424242

        class Demande(object):
            def cache_key(self):
                return CLE

        memoire = DatabaseSolutionMemory()
        demande = Demande()
        # Une reponse deja en memoire pour cette demande.
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
        self.assertNotIn('"solver runs"', corps)
        self.assertIn('"solver answers"', corps)

    def test_the_label_is_translated_in_the_four_other_languages(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                if gettext('solver answers') == 'solver answers':
                    muettes.append(langue)
        self.assertEqual([], muettes)

    def test_no_translation_says_generated_on_its_own(self):
        """La derive que le lot A bis avait trouvee: l'anglais propre et la
        traduction qui dit <<genere>> toute seule."""
        from django.utils.translation import gettext, override
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                rendu = gettext('solver answers').lower()
                self.assertNotIn('gener', rendu, (langue, rendu))
                self.assertNotIn('generier', rendu, (langue, rendu))
