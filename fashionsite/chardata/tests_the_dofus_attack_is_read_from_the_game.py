# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Ebony Dofus attack is read from the game client, matched by id."""

from django.test import SimpleTestCase

VERSIONS_CONCERNEES = ('dofus3', 'beta', 'dofus2')

#: Shared spells with our own values: the client has their ids, no damage line
ECRITS_A_LA_MAIN = {'Burnt Pie', 'Weapon Skill'}


def _sorts_partages(version):
    from fashionistapulp import (dofus_constants, dofus_constants_beta,
                                 dofus_constants_dofus2)
    par_version = {'dofus3': dofus_constants,
                   'beta': dofus_constants_beta,
                   'dofus2': dofus_constants_dofus2}
    return {spell.name: spell
            for spell in par_version[version].DAMAGE_SPELLS['default']}


class TheEbonyDofusCarriesItsAnkamaIdTests(SimpleTestCase):

    def test_the_spell_is_matched_by_id_on_the_three_versions(self):
        """A fallback to the hand values loses the id."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual(18645, sort.spell_id)

    def test_every_other_shared_spell_carries_one_too(self):
        """The hand-written ones carry the client's id as well."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sans_id = {nom for nom, sort in _sorts_partages(version).items()
                           if not sort.spell_id}
                self.assertEqual(set(), sans_id)

    def test_the_hand_written_ones_keep_their_own_values(self):
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                partages = _sorts_partages(version)
                for nom in ECRITS_A_LA_MAIN:
                    self.assertIsNone(partages[nom].casting, nom)
                    self.assertTrue(partages[nom].spell_id, nom)

    def test_it_lands_at_the_start_of_the_turn(self):
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertTrue(sort.delayed)
                self.assertEqual({'turn_begin'}, set(sort.delayed.values()))

    def test_the_neutral_element_was_missing_and_is_back(self):
        from fashionistapulp.dofus_constants import NEUTRAL
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual(5, len(sort.effects.elements))
                self.assertIn(NEUTRAL, sort.effects.elements)

    def test_the_charge_states_are_not_shown_as_spell_ranks(self):
        """One grade, the charged attack: the charge states are not ranks."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual(1, len(sort.level_req))
                for ligne in sort.effects.non_crit_ranges:
                    self.assertEqual(1, len(ligne))
                    self.assertTrue(ligne[0].max_dam, 'un element a zero')

    def test_each_element_is_a_flat_sixteen(self):
        """Dofus 3 gives 16, Dofus 2 gives 14-16."""
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                dernier = [(ligne[-1].min_dam, ligne[-1].max_dam)
                           for ligne in sort.effects.non_crit_ranges]
                self.assertEqual([(16, 16)] * 5, dernier)


class TheGateIsTheDofusNotTheSpellTests(SimpleTestCase):

    def test_the_level_is_the_one_the_catalogue_gives_the_item(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                set_current_game_version(version)
                structure = get_structure(version)
                objet = next(
                    item
                    for niveau in structure.types
                    for items in structure.types[niveau].values()
                    for item in items
                    if structure.get_item_name_in_language(item, 'en')
                    == 'Ebony Dofus')
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual([objet.level] * len(sort.level_req),
                                 sort.level_req)


class TheExclusionsAreReadPerVersionTests(SimpleTestCase):
    """Each client words its own sentences, and one id can be another spell."""

    def _table(self):
        from chardata.tests import itemscraper_module
        return itemscraper_module('generate_damage_spells'
                                  ).NOT_A_SELF_BUFF_BY_VERSION

    def test_every_version_has_its_own_table(self):
        table = self._table()
        self.assertEqual(set(VERSIONS_CONCERNEES), set(table))

    def test_dofus2_words_the_drain_differently(self):
        table = self._table()
        self.assertEqual("mentaire sur l'ennemi cibl", table['dofus3'][13672])
        self.assertEqual("mentaire de l'ennemi cibl", table['dofus2'][13672])

    def test_dofus2_does_not_carry_the_alchemical_word(self):
        self.assertNotIn(25802, self._table()['dofus2'])
        self.assertIn(25802, self._table()['dofus3'])

    def test_the_drain_no_longer_hands_four_characteristics_on_dofus2(self):
        from fashionistapulp.dofus_constants_dofus2 import DAMAGE_SPELLS
        drain = next(spell for spell in DAMAGE_SPELLS['Huppermage']
                     if spell.spell_id == 13672)
        caracteristiques = [element for element in drain.effects.elements
                            if isinstance(element, str)
                            and element.startswith('buff_')]
        self.assertEqual([], caracteristiques)


class TheReaderGetsTheNameInTheirLanguageTests(SimpleTestCase):
    """The client's name map is keyed by the spell's English name, not the item's."""

    LANGUES = ('en', 'fr', 'es', 'pt', 'de')

    def test_the_five_languages_all_answer(self):
        from chardata.spell_localization import get_localized_spell_name
        noms = {langue: get_localized_spell_name('Ebony Dofus', langue)
                for langue in self.LANGUES}
        self.assertEqual('Dofus \u00c9b\u00e8ne', noms['fr'])
        self.assertEqual('Ebenholz-Dofus', noms['de'])
        for langue, nom in noms.items():
            if langue != 'en':
                self.assertNotEqual('Ebony Dofus', nom, langue)

    def test_those_names_are_the_ones_the_catalogue_gives_the_item(self):
        from chardata.spell_localization import NAMED_AFTER_THEIR_ITEM
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        objet = next(item
                     for niveau in structure.types
                     for items in structure.types[niveau].values()
                     for item in items
                     if structure.get_item_name_in_language(item, 'en')
                     == 'Ebony Dofus')
        attendu = {langue: structure.get_item_name_in_language(objet, langue)
                   for langue in self.LANGUES}
        self.assertEqual(attendu, NAMED_AFTER_THEIR_ITEM['Ebony Dofus'])

    def test_the_client_keeps_the_last_word_if_it_takes_the_name_back(self):
        """Our table is only used when the client's map lacks the label."""
        from chardata.spell_localization import get_localized_spell_name
        self.assertEqual('Mantiscroc',
                         get_localized_spell_name('Mantiscroc', 'fr'))
        self.assertEqual('Manticolmillo',
                         get_localized_spell_name('Mantiscroc', 'es'))
