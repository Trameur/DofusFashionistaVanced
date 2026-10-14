# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A translated count says the number it counts, and a build is not called a set."""

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext, ngettext

CHARGES = {
    'fr': ('Chargée 3 fois', 'Chargée 12 fois'),
    'es': ('Cargada 3 veces', 'Cargada 12 veces'),
    'pt': ('Carregado 3 vezes', 'Carregado 12 vezes'),
    'de': ('Dreimal aufgeladen', 'Zwölfmal aufgeladen'),
}

SHARED_BUILDS = {
    'es': ('Builds Compartidos', 'build compartido', 'builds compartidos'),
    'pt': ('Builds Compartilhados', 'build compartilhado', 'builds compartilhados'),
    'de': ('Geteilte Builds', 'geteilter Build', 'geteilte Builds'),
}


class ATranslatedCountSaysItsOwnNumberTests(SimpleTestCase):

    def test_each_charge_count_names_its_own_number(self):
        for language, (three, twelve) in CHARGES.items():
            with self.subTest(language=language), translation.override(language):
                self.assertEqual(three, gettext('Charged 3 times'))
                self.assertEqual(twelve, gettext('Charged 12 times'))


class ABuildIsNotCalledASetWhenItIsSharedTests(SimpleTestCase):

    def test_the_gallery_title_and_the_found_count_name_a_build(self):
        for language, (title, one, many) in SHARED_BUILDS.items():
            with self.subTest(language=language), translation.override(language):
                self.assertEqual(title, gettext('Shared Builds'))
                found_one = ngettext('Found %(counter)s shared build',
                                     'Found %(counter)s shared builds', 1)
                found_many = ngettext('Found %(counter)s shared build',
                                      'Found %(counter)s shared builds', 5)
                self.assertIn(one, found_one)
                self.assertIn(many, found_many)
