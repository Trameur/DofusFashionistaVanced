# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le modele n'est pas relu apres avoir ete rendu au pool.

`fashion()` empruntait un modele, resolvait, le RENDAIT a la file partagee,
puis rappelait `model.get_solved_status()` sur cet objet pour l'ecrire dans la
memoire des solutions. C'est une lecture apres liberation : entre les deux
lignes, un autre appelant peut emprunter ce meme modele, appeler `setup()` et
`run()` dessus, et changer ce que la relecture rend.

**Ca ne peut pas se produire aujourd'hui**, et c'est dit ici pour que personne
ne se rassure a tort : `docker-entrypoint.sh` lance gunicorn avec deux workers
et SANS `--threads`, donc des workers synchrones, une requete a la fois par
processus. Rien ne peut s'intercaler.

Le jour ou quelqu'un ajoute `--threads 4` -- un geste de configuration que
personne ne relierait a ce fichier -- la course s'arme, et la memoire garde
pour une entree le statut calcule pour une AUTRE. Le statut memorise n'est
lu par aucune decision aujourd'hui, ce qui rend la panne silencieuse plutot
qu'absente.

Ce module reproduit la course SANS fil d'execution : le faux modele change de
statut au moment ou il est rendu. Un test qui aurait besoin de vrais threads
serait intermittent, donc inutile comme garde.
"""
from django.test import SimpleTestCase


class _ModeleQuiChangeQuandOnLeRend(object):
    """Un modele dont le statut bascule des qu'il retourne dans la file.

    C'est exactement ce qu'un autre appelant produirait en l'empruntant et en
    resolvant autre chose dessus, mais de facon deterministe.
    """

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
    """Rejoue les deux ordres possibles et rend ce qui atterrit en memoire.

    `lire_apres_liberation=True` est le code d'avant : on rend le modele puis
    on le relit. `False` est celui d'apres : on garde la valeur calculee.
    """
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
        """Le controle positif du module.

        Si le faux modele ne changeait pas de statut, les deux ordres
        rendraient la meme chose et les tests suivants passeraient sur une
        mise en scene qui ne prouve rien.
        """
        avant = _simule(lire_apres_liberation=True)
        apres = _simule(lire_apres_liberation=False)
        self.assertNotEqual(
            avant[0], apres[0],
            'the two orderings give the same status, so this module is not '
            'reproducing anything')
        self.assertEqual('Infeasible', avant[0])
        self.assertEqual('Optimal', apres[0])

    def test_the_code_keeps_the_status_it_computed(self):
        """La vraie garde : la source lit-elle la variable ou l'objet rendu.

        Ce test lit le SOURCE plutot que d'executer une requete, parce que le
        defaut n'est observable a l'execution qu'avec de vrais threads -- et
        un garde intermittent ne garde rien. Ce qu'il attrape est precis : un
        appel a `get_solved_status()` place APRES `return_model`.
        """
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
        """Le controle positif inverse.

        Supprimer l'appel plutot que de le remplacer ferait passer le test
        precedent tout en cassant l'ecriture. Le statut doit toujours partir
        en memoire.
        """
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
