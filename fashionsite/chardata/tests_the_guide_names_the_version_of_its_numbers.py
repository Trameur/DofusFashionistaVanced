# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The how-it-works guide names the version its numbers come from."""

import math

from django.test import SimpleTestCase

AFFIRME = {'dofus3': 37, 'beta': 37, 'dofus2': 36, 'touch': 36, 'retro': 28}


def _espace(version):
    from fashionistapulp.structure import get_structure
    structure = get_structure(version)
    niveau = max(structure.types)
    par_type = {nom: len([item for item in structure.types[niveau][nom]
                          if not item.removed])
                for nom in structure.types[niveau]}
    combinaisons = 1
    for nom in ('Weapon', 'Shield', 'Hat', 'Cloak', 'Amulet', 'Belt',
                'Boots', 'Pet'):
        combinaisons *= par_type[nom]
    combinaisons *= math.comb(par_type['Ring'], 2)
    combinaisons *= math.comb(par_type['Dofus'], 6)
    return par_type, combinaisons


def _paragraphes():
    from chardata.guides_content import GUIDES
    guide = GUIDES['how-it-works']['i18n']
    return {langue: texte['body'] for langue, texte in guide.items()}


class EveryNumberTheGuideCitesIsTrueForItsVersionTests(SimpleTestCase):

    def test_each_version_really_passes_the_power_the_guide_gives_it(self):
        for version, exposant in AFFIRME.items():
            _par_type, combinaisons = _espace(version)
            self.assertGreater(
                combinaisons, 10 ** exposant,
                '%s: the guide says more than 10^%d and the catalogue gives '
                '%.1e' % (version, exposant, combinaisons))

    def test_the_guide_does_not_undersell_either(self):
        for version, exposant in AFFIRME.items():
            _par_type, combinaisons = _espace(version)
            self.assertLess(combinaisons, 10 ** (exposant + 2),
                            '%s is past 10^%d, the guide undersells it'
                            % (version, exposant + 2))

    def test_only_dofus_3_is_promised_a_hundred_candidates_per_slot(self):
        par_type, _c = _espace('dofus3')
        self.assertGreater(min(par_type.values()), 100)
        par_type, _c = _espace('retro')
        self.assertLess(min(par_type.values()), 100,
                        'Retro now has a hundred candidates everywhere; the '
                        'guide could promise it there too')


class TheParagraphNamesItsVersionInEveryLanguageTests(SimpleTestCase):

    def test_dofus_3_is_named_next_to_its_number(self):
        for langue, corps in _paragraphes().items():
            self.assertIn('Dofus 3', corps, langue)
            self.assertIn('37', corps, langue)

    def test_the_other_versions_get_their_own_numbers(self):
        for langue, corps in _paragraphes().items():
            for exposant in ('36', '28'):
                self.assertIn(exposant, corps, (langue, exposant))
            self.assertIn('Touch', corps, langue)
            self.assertIn('Dofus 2', corps, langue)

    def test_the_hundred_candidates_promise_is_scoped_to_dofus_3(self):
        marqueurs = {
            'en': ('On Dofus 3', 'well over a hundred'),
            'fr': ('Sur Dofus 3', "plus d'une centaine"),
            'es': ('En Dofus 3', 'más de cien'),
            'pt': ('No Dofus 3', 'mais de cem'),
            'de': ('Auf Dofus 3', 'über hundert'),
        }
        for langue, corps in _paragraphes().items():
            nomme, promet = marqueurs[langue]
            self.assertLess(corps.index(nomme), corps.index(promet), langue)
