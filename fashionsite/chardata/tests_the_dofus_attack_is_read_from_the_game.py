# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'attaque du Dofus Ebene est lue dans le jeu, non ecrite a la main.

Les sorts que porte un OBJET et non une classe etaient apparies au client par
leur nom anglais. Le client de Dofus 3 a rebaptise l'attaque du Dofus Ebene en
<<Ebony Black>> (<<Noir Ebene>> en francais, type <<[!] Dofus Ebene>>, lu le
11 septembre 2026 dans transformed_spells.json): l'appariement a echoue, le
repli sur les valeurs ecrites a la main a pris le relais **sans un mot**, et
le site a servi pendant ce temps quatre elements a 14-16, sans cout en PA et
sans dire que le coup part au debut du tour.

Ce que le client de Dofus 3 dit vraiment, pour l'identifiant 18645: cinq
elements (Eau, Feu, Air, Terre et Neutre) a 16 chacun, 1 PA, et chaque ligne
declenchee en debut de tour. Il l'ecrit en neuf paliers gagnant un element
chacun, mais ce sont des etats de CHARGE et non des rangs que le joueur
choisit: lus comme des rangs ils dessinent un triangle de zeros et la page
montrerait un objet qui forcit quand le lecteur monte en niveau. On garde donc
l'attaque chargee, exactement la forme sous laquelle le client de Dofus 2
livre deja le meme sort, avec ses propres nombres a lui (14-16).

Le sort est desormais apparie par son IDENTIFIANT, qui ne se renomme pas. La
porte de niveau, elle, reste celle de l'OBJET: Ankama ecrit le sort comme
atteignable au niveau 1, ce qui est vrai du sort et faux du joueur, puisqu'il
faut porter le Dofus. Un test ci-dessous relit ce niveau dans le catalogue.
"""

from django.test import SimpleTestCase

VERSIONS_CONCERNEES = ('dofus3', 'beta', 'dofus2')

#: Les deux seuls sorts partages dont les valeurs viennent de nous. Le client
#: porte bien leurs identifiants (24006 et 3506) mais AUCUNE ligne de degats,
#: verifie le 11 septembre 2026 dans les trois fichiers de sorts.
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
        """Un repli silencieux se voit ici: il perd l'identifiant."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual(18645, sort.spell_id)

    def test_every_other_shared_spell_carries_one_too(self):
        """La garde generale: si le client rebaptise un autre sort d'objet,
        l'appariement retombe sur les valeurs ecrites a la main et perd
        l'identifiant. Cette liste est donc la liste des sorts dont nous
        assumons les valeurs, et elle ne doit pas s'allonger toute seule."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sans_id = {nom for nom, sort in _sorts_partages(version).items()
                           if not sort.spell_id}
                self.assertEqual(ECRITS_A_LA_MAIN, sans_id)

    def test_it_costs_one_ap_and_lands_at_the_start_of_the_turn(self):
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual([1] * len(sort.level_req),
                                 sort.casting.get('ap'))
                self.assertTrue(sort.delayed)
                self.assertEqual({'turn_begin'}, set(sort.delayed.values()))

    def test_the_neutral_element_was_missing_and_is_back(self):
        """Les valeurs ecrites a la main n'en portaient que quatre."""
        from fashionistapulp.dofus_constants import NEUTRAL
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual(5, len(sort.effects.elements))
                self.assertIn(NEUTRAL, sort.effects.elements)

    def test_the_charge_states_are_not_shown_as_spell_ranks(self):
        """Un seul palier, celui de l'attaque chargee, sur les trois
        versions. Sans cela la page promet un sort qui forcit avec le niveau,
        et le garde `test_no_spell_counts_a_row_it_replaced` tombe sur le
        triangle de zeros que les paliers dessinent."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                self.assertEqual(1, len(sort.level_req))
                for ligne in sort.effects.non_crit_ranges:
                    self.assertEqual(1, len(ligne))
                    self.assertTrue(ligne[0].max_dam, 'un element a zero')

    def test_each_element_is_a_flat_sixteen(self):
        """Dofus 3 donne 16, Dofus 2 donne 14-16: deux jeux, deux nombres,
        et c'est bien pour cela qu'on ne recopie pas l'un sur l'autre. Le
        14-16 servi par Dofus 3 venait de ce recopiage."""
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                sort = _sorts_partages(version)['Ebony Dofus']
                dernier = [(ligne[-1].min_dam, ligne[-1].max_dam)
                           for ligne in sort.effects.non_crit_ranges]
                self.assertEqual([(16, 16)] * 5, dernier)


class TheGateIsTheDofusNotTheSpellTests(SimpleTestCase):

    def test_the_level_is_the_one_the_catalogue_gives_the_item(self):
        """Le 180 n'est pas une croyance: il est relu dans le catalogue de
        chaque version, a cote de l'objet qui donne le sort."""
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
    """Une exclusion est ecrite sur une phrase d'Ankama, et chaque client
    ecrit la sienne. Le meme numero ne designe meme pas toujours le meme sort:
    25802 porte <<Mot Alchimique>> sur Dofus 3 et seulement <<Mot d'Amitie>>
    sur Dofus 2, ou l'exclure retirerait les lignes d'un autre sort."""

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
        """Le bloc de Dofus 2 ne se regenerait plus du tout, donc l'exclusion
        ecrite pour Dofus 3 n'y avait jamais ete appliquee: le sort y portait
        encore quatre lignes de caracteristique a 60/120/200, soit 800 points
        pour un lancer ou le jeu en donne 200."""
        from fashionistapulp.dofus_constants_dofus2 import DAMAGE_SPELLS
        drain = next(spell for spell in DAMAGE_SPELLS['Huppermage']
                     if spell.spell_id == 13672)
        caracteristiques = [element for element in drain.effects.elements
                            if isinstance(element, str)
                            and element.startswith('buff_')]
        self.assertEqual([], caracteristiques)


class TheReaderGetsTheNameInTheirLanguageTests(SimpleTestCase):
    """Le meme renommage cachait un second defaut: la carte des noms du client
    est indexee par le nom ANGLAIS DU SORT, devenu <<Ebony Black>>. Notre
    etiquette, elle, est celle du Dofus qui donne l'attaque, et n'y etait donc
    plus. Tous les lecteurs lisaient <<Ebony Dofus>>, en francais compris."""

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
        """La table n'est pas une croyance: elle est relue a cote de l'objet.
        Si le catalogue rebaptise le Dofus, ce test le dit."""
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
        """Notre table n'est qu'un secours: elle ne sert que si la carte du
        client ne connait pas l'etiquette."""
        from chardata.spell_localization import get_localized_spell_name
        self.assertEqual('Mantiscroc',
                         get_localized_spell_name('Mantiscroc', 'fr'))
        self.assertEqual('Manticolmillo',
                         get_localized_spell_name('Mantiscroc', 'es'))
