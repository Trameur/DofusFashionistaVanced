# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The model is not read after it is returned to the pool."""
from django.test import SimpleTestCase


class _ModeleQuiChangeQuandOnLeRend(object):

    STATUT_A_MOI = 'Optimal'
    STATUT_DE_L_AUTRE = 'Infeasible'

    def __init__(self):
        self.rendu = False
        self.structure = type('S', (), {'game_version': 'dofus3'})()

    def setup(self, _entree):
        pass

    def run(self, _iterations):
        pass

    def get_solved_status(self):
        return self.STATUT_DE_L_AUTRE if self.rendu else self.STATUT_A_MOI

    def get_stats(self):
        return {'vit': 1}

    def get_result_minimal(self):
        return 'resultat'


def _simule(lire_apres_liberation):
    modele = _ModeleQuiChangeQuandOnLeRend()
    modele.setup(None)
    modele.run(2)
    statut = modele.get_solved_status()
    stats = modele.get_stats()
    resultat = modele.get_result_minimal()
    modele.rendu = True                      # return_model(model)
    if lire_apres_liberation:
        return (modele.get_solved_status(), stats, resultat)
    return (statut, stats, resultat)


class TheModelIsNotReadAfterItIsReturnedTests(SimpleTestCase):

    def test_the_simulation_actually_reproduces_the_race(self):
        avant = _simule(lire_apres_liberation=True)
        apres = _simule(lire_apres_liberation=False)
        self.assertNotEqual(
            avant[0], apres[0],
            'the two orderings give the same status, so this module is not '
            'reproducing anything')
        self.assertEqual('Infeasible', avant[0])
        self.assertEqual('Optimal', apres[0])

    def test_the_code_keeps_the_status_it_computed(self):
        import inspect
        import re

        from chardata import fashion_action

        source = inspect.getsource(fashion_action.fashion)
        lignes = source.split('\n')
        rendus = [i for i, l in enumerate(lignes) if 'return_model(' in l]
        self.assertTrue(
            rendus,
            'return_model no longer appears in fashion(); this guard has lost '
            'its subject and must be rewritten, not deleted')
        premier_rendu = rendus[0]
        apres = [(i, l) for i, l in enumerate(lignes)
                 if i > premier_rendu and 'get_solved_status()' in l
                 and not l.strip().startswith('#')]
        self.assertFalse(
            apres,
            'the model is read after being returned to the shared pool, at '
            'line(s) %s of fashion(): a concurrent borrower would change what '
            'this reads' % [i - premier_rendu for i, _l in apres])

    def test_the_memory_still_receives_a_status(self):
        import inspect
        import re

        from chardata import fashion_action

        source = inspect.getsource(fashion_action.fashion)
        m = re.search(r'MEMORY\.put\(\s*model_input\s*,\s*\(([^)]*)\)', source)
        self.assertIsNotNone(m, 'MEMORY.put no longer stores a tuple')
        premier = m.group(1).split(',')[0].strip()
        self.assertEqual(
            'solved_status', premier,
            'the first field written to the solution memory is %r, which is '
            'neither the computed variable nor a recognised replacement'
            % premier)
