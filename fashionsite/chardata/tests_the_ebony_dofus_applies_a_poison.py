# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le Dofus Ebene applique UN poison, pas cinq coups.

Le client range l'effet de ce Dofus comme un sort: cinq lignes de degats et un
cout en PA. La fiche de l'objet, elle, dit ce qui se passe vraiment. Lue le 12
septembre 2026 dans notre catalogue, en anglais sur Dofus 3:

    <<Triggering both effects during the turn allows the next attack to apply
    a 16 poison in its element for 2 turns (stackable 2 times).>>

Trois choses que la page disait faux, sur Dofus 3 comme sur Dofus 2:

- les cinq lignes elementaires etaient lues comme simultanees, soit **80
  annonces la ou le jeu en met 16**. Le poison tombe dans SON element, celui
  de l'attaque qui l'applique: ce sont cinq faces, pas une somme;
- **1 PA** etait affiche pour un effet que le joueur ne lance jamais: il est
  applique par sa prochaine attaque;
- le nombre de cumuls affiche sur Dofus 3 etait **5**, celui du bonus de 2%
  de dommages, alors que le POISON se cumule 2 fois.

Rien ne disait non plus a quelle condition il tombe. Il la dit maintenant,
dans les cinq langues.

Le meme defaut avait deja ete corrige une fois, pour le Bluff de Retro
(<<Coup dans un element au hasard>>): deux lignes lues comme deux coups la ou
le jeu n'en tire qu'un.
"""

from django.test import SimpleTestCase

VERSIONS_CONCERNEES = ('dofus3', 'beta', 'dofus2')

#: La phrase de la fiche de l'objet sur laquelle repose tout ce module, par
#: version, en anglais. Un test la relit dans le catalogue: si Ankama la
#: reecrit, la question se repose au lieu de rester repondue par habitude.
CE_QUE_L_OBJET_DIT = {
    # <<Triggering both effects during the turn allows the next attack to
    # apply a 16 poison in its element for 2 turns (stackable 2 times)>>, les
    # deux effets etant l'attaque en melee et l'attaque a distance.
    'dofus3': ('poison in its element', 'stackable 2 times',
               'close combat', 'from range'),
    'beta': ('poison in its element', 'stackable 2 times',
             'close combat', 'from range'),
    # Dofus 2 le dit autrement et avec un trait d'union: <<Inflicting ranged
    # damage and close-combat damage during one's turn triggers the Ebony
    # Dofus's power: the next attack during the same turn applies a poison>>.
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
        """Chaque version est un jeu different, et l'ecrit avec ses mots: la
        table ci-dessus cite ceux de chacune plutot qu'un seul jeu de mots
        qui ne tiendrait que sur l'une d'elles."""
        dofus3 = _texte_de_l_objet('dofus3').lower()
        dofus2 = _texte_de_l_objet('dofus2').lower()
        self.assertIn('close combat', dofus3)
        self.assertNotIn('close combat', dofus2)
        self.assertIn('close-combat damage', dofus2)


class OnePoisonLandsAndNotFiveTests(SimpleTestCase):

    def test_the_element_rows_are_alternatives(self):
        """La fonction qui decide <<une seule tombe>> doit les reconnaitre."""
        from chardata.spell_combo import _element_alternatives
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                effets = sort.get_effects_digest().non_crit_dams[-1]
                groupes = _element_alternatives(sort.aggregates, effets)
                self.assertIsNotNone(groupes, 'lues comme une somme')
                self.assertEqual(5, len(groupes))
                for groupe in groupes:
                    self.assertEqual(1, len(groupe))

    def test_the_turn_reads_sixteen_and_not_eighty(self):
        """Le nombre lui-meme, par le chemin que le site emprunte.

        Les cinq lignes valent 16 chacune et leur somme fait 80: c'est ce que
        la page annoncait. Lues comme des faces, une seule tombe et le compte
        est 16.
        """
        from chardata.spell_combo import _element_alternatives
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                lignes = sort.get_effects_digest().non_crit_dams[-1]
                self.assertEqual(80, sum(ligne.max_dam for ligne in lignes),
                                 'la somme des lignes ne change pas')
                groupes = _element_alternatives(sort.aggregates, lignes)
                self.assertIsNotNone(groupes, 'encore lues comme une somme')
                tombent = [max(lignes[index].max_dam for index in groupe)
                           for groupe in groupes]
                self.assertEqual([16] * 5, tombent)
                self.assertEqual(16, max(tombent), 'une seule tombe')

    def test_nobody_is_charged_ap_for_it(self):
        """Le joueur ne le lance pas: sa prochaine attaque l'applique."""
        for version in VERSIONS_CONCERNEES:
            with self.subTest(version=version):
                sort = _sort_partage(version)
                self.assertIsNone(sort.casting)
                self.assertIsNone(sort.ap_cost())

    def test_the_poison_stacks_twice_on_the_three_versions(self):
        """Le 5 de Dofus 3 etait celui du bonus de 2% de dommages, un autre
        effet du meme Dofus."""
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
        """Un poison ne frappe pas au moment ou il est pose."""
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

    def test_the_other_rows_carry_no_second_label(self):
        """Une etiquette par groupe ferait lire cinq poisons au lieu d'un."""
        carte = self._carte('en')
        self.assertEqual(['', '', '', ''],
                         [groupe[0] for groupe in carte['aggregates'][1:]])
