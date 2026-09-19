# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell name found only inside a longer word names no spell."""

from django.test import SimpleTestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

COUP_DE_POING_DE = ('Nahkampf', 'Verursacht Neutralschaden.')


def _tip(ligne, tooltips):
    from chardata.spell_tips import spell_tip_for
    trouve = spell_tip_for(ligne, tooltips)
    return trouve.spell if trouve else None


class ANameInsideAWordNamesNothingTests(SimpleTestCase):

    def test_the_german_word_for_close_combat_is_not_the_spell(self):
        nom, description = COUP_DE_POING_DE
        tooltips = {nom: description}
        for mot in ('Nahkampfentfernung', 'Nahkampfangriff', 'Nahkampfschaden'):
            with self.subTest(mot=mot):
                ligne = 'fuer jeden Gegner in %s' % mot
                self.assertIsNone(_tip(ligne, tooltips))

    def test_the_spell_standing_alone_is_still_named(self):
        nom, description = COUP_DE_POING_DE
        self.assertEqual(nom, _tip('Erhoeht den Schaden von %s' % nom,
                                   {nom: description}))

    def test_punctuation_still_counts_as_the_end_of_a_word(self):
        tooltips = {'Bond': 'saute'}
        for ligne in ('Bond : -1 de relance', 'Reduit Bond, de 1',
                      '(Bond)', 'Bond'):
            with self.subTest(ligne=ligne):
                self.assertEqual('Bond', _tip(ligne, tooltips))

    def test_the_longest_name_still_wins(self):
        tooltips = {'Bond': 'saute', 'Bond Felin': 'saute plus loin'}
        self.assertEqual('Bond Felin', _tip('Bond Felin : -1 de relance',
                                            tooltips))
        self.assertEqual('Bond', _tip('Bond : -1 de relance', tooltips))

    def test_a_line_naming_no_spell_gets_nothing(self):
        self.assertIsNone(_tip('+40 Fuite', {'Bond': 'saute'}))

    def test_the_retro_belt_names_the_spell_it_lengthens(self):
        tooltips = {'Increase': 'augmente', 'Cut': 'coupe'}
        self.assertEqual('Cut', _tip('Increases the range of Cut by 3',
                                     tooltips))


class TheCatalogueAgreesTests(SimpleTestCase):

    def _objet(self, version, nom_anglais):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version(version)
        structure = get_structure(version)
        return structure, next(
            item
            for niveau in structure.types
            for items in structure.types[niveau].values()
            for item in items
            if not item.removed
            and structure.get_item_name_in_language(item, 'en') == nom_anglais)

    def test_the_emerald_dofus_carries_no_spell_to_explain(self):
        _structure, objet = self._objet('dofus3', 'Emerald Dofus')
        self.assertEqual({}, objet.spell_tooltips)

    def test_its_german_line_would_name_nothing_even_so(self):
        structure, objet = self._objet('dofus3', 'Emerald Dofus')
        lignes = [ligne for ligne in (objet.localized_extras.get('de') or [])
                  if 'Nahkampf' in ligne]
        self.assertTrue(lignes, 'la ligne temoin a change dans le catalogue')
        for ligne in lignes:
            with self.subTest(ligne=ligne[:40]):
                self.assertNotIn('Nahkampf ', ligne,
                                 'le mot y est desormais seul, le test ne '
                                 'garde plus le cas du mot compose')
                self.assertIsNone(_tip(ligne, dict([COUP_DE_POING_DE])))

    def test_no_item_is_explained_in_one_language_only(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        for version in ('dofus3', 'beta', 'dofus2', 'retro', 'touch'):
            with self.subTest(version=version):
                set_current_game_version(version)
                structure = get_structure(version)
                vus = {}
                for niveau in structure.types:
                    for items in structure.types[niveau].values():
                        for item in items:
                            if not item.removed and item.spell_tooltips:
                                vus[item.id] = item
                self.assertTrue(vus, 'aucun objet a infobulle')
                boiteux = sorted(
                    structure.get_item_name_in_language(item, 'en')
                    for item in vus.values()
                    if len(item.spell_tooltips) != len(LANGUES))
                self.assertEqual([], boiteux)

    def test_no_german_line_of_any_item_explains_a_punch_any_more(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        for version in ('dofus3', 'dofus2'):
            with self.subTest(version=version):
                set_current_game_version(version)
                structure = get_structure(version)
                vus = {}
                for niveau in structure.types:
                    for items in structure.types[niveau].values():
                        for item in items:
                            if not item.removed and item.spell_tooltips:
                                vus[item.id] = item
                self.assertTrue(vus, 'aucun objet a infobulle')
                fautifs = []
                for item in vus.values():
                    tooltips = item.spell_tooltips.get('de') or {}
                    if COUP_DE_POING_DE[0] not in tooltips:
                        continue
                    for ligne in (item.localized_extras.get('de') or []):
                        if _tip(ligne, tooltips) == COUP_DE_POING_DE[0]:
                            fautifs.append(
                                structure.get_item_name_in_language(item, 'en'))
                self.assertEqual([], sorted(set(fautifs)))
