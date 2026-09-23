# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Retro spell asks the level the game's data gives, one per slot of the class."""

import io
import json
import os

from django.test import SimpleTestCase

# The eighteen spell slots of a Retro class, read from classes_fr.json
ECHELLE = [1, 3, 6, 9, 13, 17, 21, 26, 31, 36, 42, 48, 54, 60, 70, 80, 90, 100]

# The artefact the reader writes beside the module is in the repo
ARTEFACT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'retro',
    'retro_damage_spells.json')


def _sorts():
    from fashionistapulp.dofus_constants_retro_spells import (
        RETRO_DAMAGE_SPELLS)
    return [(classe, sort)
            for classe, sorts in RETRO_DAMAGE_SPELLS.items()
            for sort in sorts]


class TheLevelsComeFromTheGameTests(SimpleTestCase):

    def test_the_spells_do_not_all_ask_the_same_level(self):
        formes = {tuple(sort.level_req) for _classe, sort in _sorts()}
        self.assertEqual(18, len(formes), sorted(formes))

    def test_the_base_levels_are_the_ladder_the_game_uses(self):
        bases = {sort.level_req[0] for _classe, sort in _sorts()}
        self.assertEqual(set(ECHELLE), bases)

    def test_the_starting_spells_match_their_class(self):
        expected = {
            'Cra': {161, 164, 169}, 'Ecaflip': {102}, 'Eniripsa': {125},
            'Enutrof': {43, 51}, 'Feca': {3, 17}, 'Iop': {141, 143},
            'Osamodas': {21}, 'Pandawa': {687, 692}, 'Sacrier': {432},
            'Sadida': {183}, 'Sram': {61, 65}, 'Xelor': {83},
        }
        actual = {}
        for char_class, spell in _sorts():
            if spell.level_req[0] == 1:
                actual.setdefault(char_class, set()).add(spell.spell_id)
        self.assertEqual(expected, actual)

    def test_the_last_rank_asks_a_hundred_levels_above_the_spell(self):
        for classe, sort in _sorts():
            with self.subTest(classe=classe, sort=sort.name):
                req = list(sort.level_req)
                self.assertEqual(6, len(req))
                base = req[0]
                self.assertEqual([base] * 5, req[:5])
                self.assertEqual(base + 100, req[5])

    def test_the_module_says_what_the_scraper_wrote_beside_it(self):
        with io.open(ARTEFACT, encoding='utf-8') as fichier:
            artefact = json.load(fichier)
        expected = {(char_class, spell['id']):
                    (spell['name'], tuple(spell['level_reqs']))
                    for char_class, spells in artefact.items()
                    for spell in spells}
        actual = {(char_class, spell.spell_id):
                  (spell.name, tuple(spell.level_req))
                  for char_class, spell in _sorts()}
        self.assertTrue(expected)
        self.assertEqual(expected, actual)


class ThePanelFollowsTheLevelTests(SimpleTestCase):

    def _castables(self, char_class, level):
        from chardata.spell_combo import castable_spells
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('retro')
        return castable_spells(char_class, level, 'retro')

    def test_a_beginner_is_offered_fewer_spells_than_a_level_two_hundred(self):
        for char_class in ('Cra', 'Iop', 'Xelor'):
            with self.subTest(classe=char_class):
                debutant = len(self._castables(char_class, 1))
                milieu = len(self._castables(char_class, 50))
                complet = len(self._castables(char_class, 200))
                self.assertLess(debutant, milieu)
                self.assertLess(milieu, complet)
                self.assertLessEqual(debutant * 3, complet)

    def test_no_spell_is_read_at_a_rank_the_level_refuses(self):
        from chardata.spell_buffs import _decide_spell_level
        for niveau in (1, 20, 50, 100, 120, 150, 199):
            for char_class in ('Cra', 'Iop', 'Eniripsa'):
                for castable in self._castables(char_class, niveau):
                    spell = castable.spell
                    rang = _decide_spell_level(spell.level_req, niveau)
                    with self.subTest(niveau=niveau, sort=spell.name):
                        self.assertGreaterEqual(niveau,
                                                spell.level_req[rang])
