# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A posted name never exceeds the column that stores it; Char.save() cuts it to the field's length."""
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
        exact = 'A' * self._limite('name')
        self._enregistre(exact, 'Bob')
        self.assertEqual(exact, self.char.name)
        self.assertEqual('Bob', self.char.char_name)

    def test_the_limit_is_read_from_the_model(self):
        import ast
        import inspect
        import textwrap

        # Char.save is a method, so indented: dedent keeps it parseable where cleandoc would not
        source = textwrap.dedent(inspect.getsource(Char.save))
        self.assertIn('_meta.get_field', source,
                      'the limit is no longer read from the model')
        # The docstring may cite the length; only the code must not carry it
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
