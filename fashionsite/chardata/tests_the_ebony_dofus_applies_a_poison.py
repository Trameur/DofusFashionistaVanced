# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Ebony Dofus applies one poison in the attack's element, not five hits."""

from django.test import SimpleTestCase

VERSIONS_CONCERNEES = ('dofus3', 'beta', 'dofus2')

# The item card wording this module rests on, per version
CE_QUE_L_OBJET_DIT = {
    'dofus3': ('poison in its element', 'stackable 2 times',
               'close combat', 'from range'),
    'beta': ('poison in its element', 'stackable 2 times',
             'close combat', 'from range'),
    # Dofus 2 words it differently, with a hyphen
    'dofus2': ('applies a poison', 'stacked 2 times',
               'close-combat damage', 'ranged damage'),
}


def _sort_partage(version, nom='Ebony Dofus'):
    from fashionistapulp import (dofus_constants, dofus_constants_beta,
                                 dofus_constants_dofus2)
    par_version = {'dofus3': dofus_constants,
                   'beta': dofus_constants_beta,
                   'dofus2': dofus_constants_dofus2}
    return next(spell for spell in par_version[version].DAMAGE_SPELLS['default']
                if spell.name == nom)


def _texte_de_l_objet(version, langue='en'):
    from fashionistapulp.structure import (get_structure,
                                           set_current_game_version)
    set_current_game_version(version)
    structure = get_structure(version)
    objet = next(item
                 for niveau in structure.types
                 for items in structure.types[niveau].values()
                 for item in items
                 if structure.get_item_name_in_language(item, 'en')
                 == 'Ebony Dofus')
    return ' '.join(objet.localized_extras.get(langue) or [])


class TheItemStillSaysWhatThisRestsOnTests(SimpleTestCase):

    def test_the_sentence_is_still_there(self):
        for version, phrases in CE_QUE_L_OBJET_DIT.items():
            with self.subTest(version=version):
                texte = _texte_de_l_objet(version).lower()
                for phrase in phrases:
                    self.assertIn(phrase, texte)

    def test_the_two_clients_word_it_differently(self):
        dofus3 = _texte_de_l_objet('dofus3').lower()
        dofus2 = _texte_de_l_objet('dofus2').lower()
        self.assertIn('close combat', dofus3)
        self.assertNotIn('close combat', dofus2)
        self.assertIn('close-combat damage', dofus2)


class OnePoisonLandsAndNotFiveTests(SimpleTestCase):

    def test_the_element_rows_are_alternatives(self):
        """_element_alternatives reads the five rows as one of five."""
        from chardata.spell_combo import _element_alternatives
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                effets = sort.get_effects_digest().non_crit_dams[-1]
                groupes = _element_alternatives(sort.aggregates, effets)
                self.assertIsNotNone(groupes, 'read as a sum')
                self.assertEqual(5, len(groupes))
                for groupe in groupes:
                    self.assertEqual(1, len(groupe))

    def test_the_turn_reads_sixteen_and_not_eighty(self):
        """Five rows of 16 are faces, not a sum of 80."""
        from chardata.spell_combo import _element_alternatives
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                lignes = sort.get_effects_digest().non_crit_dams[-1]
                self.assertEqual(80, sum(ligne.max_dam for ligne in lignes),
                                 'the sum of the rows does not change')
                groupes = _element_alternatives(sort.aggregates, lignes)
                self.assertIsNotNone(groupes, 'still read as a sum')
                tombent = [max(lignes[index].max_dam for index in groupe)
                           for groupe in groupes]
                self.assertEqual([16] * 5, tombent)
                self.assertEqual(16, max(tombent), 'une seule tombe')

    def test_nobody_is_charged_ap_for_it(self):
        """Nobody casts it, the next attack applies it."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                self.assertIsNone(sort.casting)
                self.assertIsNone(sort.ap_cost())

    def test_the_poison_stacks_twice_on_the_three_versions(self):
        """The 5 stacks on Dofus 3 belong to the 2% damage bonus, not the poison."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                self.assertEqual(2, _sort_partage(version).stacks)

    def test_every_row_says_what_it_waits_for(self):
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                attendu = {index: 'melee_and_ranged' for index in range(5)}
                self.assertEqual(attendu, sort.conditional)

    def test_it_still_lands_at_the_start_of_a_turn(self):
        """A poison hits at turn start, not when applied."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                self.assertEqual({'turn_begin'}, set(sort.delayed.values()))


class TheCardSaysItInTheReaderLanguageTests(SimpleTestCase):

    LANGUES = ('en', 'fr', 'es', 'pt', 'de')

    def _carte(self, langue, version='dofus3'):
        from django.utils.translation import override
        from chardata.spells_view import _create_spell_web_digest
        with override(langue):
            return _create_spell_web_digest(_sort_partage(version), version)

    def test_the_label_and_the_condition_answer_in_five_languages(self):
        anglais = self._carte('en')
        for langue in self.LANGUES:
            with self.subTest(langue=langue):
                carte = self._carte(langue)
                etiquette = carte['aggregates'][0][0]
                condition = carte['conditional']['0']
                self.assertTrue(etiquette)
                self.assertTrue(condition)
                if langue != 'en':
                    self.assertNotEqual(anglais['aggregates'][0][0], etiquette)
                    self.assertNotEqual(anglais['conditional']['0'], condition)

    def test_the_french_reader_reads_a_poison(self):
        carte = self._carte('fr')
        self.assertIn('Poison', carte['aggregates'][0][0])
        self.assertIn('mêlée', carte['conditional']['0'])

    def test_the_five_faces_are_one_poison_and_not_five(self):
        """One group carries the five rows."""
        carte = self._carte('en')
        groupes = carte['aggregates']
        self.assertEqual(1, len(groupes), groupes)
        etiquette, lignes, forme = groupes[0]
        self.assertTrue(etiquette)
        self.assertEqual(5, len(lignes), lignes)
        self.assertEqual('one', forme)
