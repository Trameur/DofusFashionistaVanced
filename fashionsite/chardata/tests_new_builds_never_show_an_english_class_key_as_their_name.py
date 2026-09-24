# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Quick start and import both go through create_build; neither should
leave the raw English class key where the reader's language expects a
localized name."""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import translation

from chardata.build_name import display_name
from chardata.coaching_view import create_build
from chardata.models import Char


class NewBuildNameNeverCarriesTheEnglishClassKeyTests(TestCase):

    def _request(self, name):
        user = User.objects.create_user(name, '%s@test.local' % name, 'pw-42-solid')
        request = RequestFactory().post('/')
        request.user = user
        return request

    def test_quick_start_never_stores_the_class_key_as_char_name(self):
        char = create_build(self._request('quick'), 'Rogue', 200, {'agi'}, 'dofus3')
        self.assertEqual('', char.char_name)

    def test_quick_start_name_is_localized_for_a_french_reader(self):
        with translation.override('fr'):
            char = create_build(self._request('quickfr'), 'Rogue', 200,
                                {'agi'}, 'dofus3')
        self.assertIn('Roublard', char.name)
        self.assertNotIn('Rogue', char.name)

    def test_an_import_never_stores_the_class_key_as_char_name(self):
        char = create_build(self._request('import'), 'Masqueraider', 200,
                            set(), 'dofus3', name='Zobal build')
        self.assertEqual('', char.char_name)
        self.assertEqual('Zobal build', char.name)

    def test_a_build_with_no_char_name_falls_back_to_class_and_level(self):
        char = Char(name='NoName', char_name='', char_class='Rogue', level=200)
        with translation.override('fr'):
            self.assertEqual('Roublard 200', display_name(char))
