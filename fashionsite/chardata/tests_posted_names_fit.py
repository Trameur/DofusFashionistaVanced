# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un nom envoye ne peut pas depasser la colonne qui le recoit.

La garde vit dans `Char.save()`, qui coupe `name`, `char_name` et `char_build`
a la longueur de leur champ -- lue sur le modele, pas ecrite en dur. Sa raison
est dans son commentaire : la base de production tourne en
`STRICT_TRANS_TABLES`, donc une valeur trop longue y leve une erreur au lieu
d'etre tronquee, et le lecteur recevrait une 500 pour un nom un peu long.

**Ce module existe parce que j'ai failli poser cette garde une seconde fois.**
En auditant la validation des formulaires, j'ai vu que la vue passe le POST
droit dans un CharField de 50 sans rien couper, j'ai conclu au defaut, et j'ai
ecrit la coupe dans la vue. Elle etait redondante : `Char.save()` le faisait
deja, avec exactement le meme motif `_meta.get_field(...).max_length`.

**C'est la falsification qui l'a dit, pas la relecture.** Le garde restait VERT
avec la coupe retiree de la vue -- et un test qui ne rougit pas quand on enleve
ce qu'il pretend garder ne garde rien. Sans cette etape, un correctif inutile
partait avec un test qui l'accompagnait, et le doublon aurait suggere au lecteur
suivant que la garde du modele n'est pas fiable.

Ce qui reste ici garde donc la VRAIE protection : si quelqu'un retire la
troncature de `Char.save()`, ces trois tests rougissent.

Note de portee : la base de test est SQLite, qui n'applique pas les longueurs de
colonne. Ces tests verifient donc la LONGUEUR ENREGISTREE, vraie sur les deux
moteurs, et non l'absence d'erreur, qui ne se manifesterait qu'en MySQL.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char


class PostedNamesFitTheirColumnTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username='proprio', email='p@test.local', password='pw-42-solid')
        self.client.force_login(self.owner)
        self.char = Char.objects.create(
            name='projet', char_name='perso', char_class='Iop',
            char_build='build', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=b'', options=b'', inclusions=b'',
            exclusions=b'', owner=self.owner, game_version='dofus3',
            link_shared=False, deleted=False, minimal_solution=b'')

    def _limite(self, champ):
        return Char._meta.get_field(champ).max_length

    def _enregistre(self, projet, perso):
        reponse = self.client.post(
            '/saveproject/%d/' % self.char.id,
            {'project': projet, 'charname': perso, 'level': '200',
             'class': 'Iop'})
        self.assertIn(reponse.status_code, (200, 302),
                      'save answered %s' % reponse.status_code)
        self.char.refresh_from_db()

    def test_a_name_longer_than_its_column_is_cut_not_stored_whole(self):
        limite = self._limite('name')
        self._enregistre('P' * (limite + 500), 'C' * (limite + 500))
        self.assertLessEqual(len(self.char.name), limite,
                             'project name stored at %d chars for a column of '
                             '%d' % (len(self.char.name), limite))
        self.assertLessEqual(len(self.char.char_name),
                             self._limite('char_name'))

    def test_a_name_that_fits_is_not_touched(self):
        """Le controle positif de la paire.

        Sans lui, une coupe a zero caractere passerait le test precedent : tout
        serait « plus court que la colonne », et le champ serait vide.
        """
        exact = 'A' * self._limite('name')
        self._enregistre(exact, 'Bob')
        self.assertEqual(exact, self.char.name)
        self.assertEqual('Bob', self.char.char_name)

    def test_the_limit_is_read_from_the_model(self):
        """Ecrire 50 dans `save()` survivrait a un champ passe a 80, en silence.

        Ce test ne verifie pas une valeur mais une PROVENANCE : il echoue si
        quelqu'un remplace la lecture du modele par une constante, meme juste le
        jour ou il l'ecrit.
        """
        import ast
        import inspect

        source = inspect.cleandoc(inspect.getsource(Char.save))
        self.assertIn('_meta.get_field', source,
                      'the limit is no longer read from the model')
        # Le docstring peut citer la longueur en l'expliquant ; seul le CODE ne
        # doit pas la porter. Une premiere version cherchait le chiffre dans la
        # source entiere et accusait sa propre prose.
        arbre = ast.parse(source).body[0]
        corps = [n for n in arbre.body
                 if not (isinstance(n, ast.Expr)
                         and isinstance(n.value, ast.Constant)
                         and isinstance(n.value.value, str))]
        chiffres = [n.value for n in ast.walk(ast.Module(corps, []))
                    if isinstance(n, ast.Constant) and isinstance(n.value, int)]
        self.assertFalse(chiffres,
                         'a hard-coded length would outlive the column it '
                         'describes: %s' % chiffres)
