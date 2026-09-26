# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hit with a row on enemies and a row on allies: the turn counts the enemy's row."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

MODERN = ('dofus3', 'beta', 'dofus2')
SHOT_PELLETS = 14411
EXTRACTION = 13433
TOUCH_TRANSFUSION_ARROW = 5813

ON_ALLIES = {'en': 'on allies', 'fr': 'sur les alliés', 'es': 'en los aliados',
             'pt': 'nos aliados', 'de': 'bei verbündeten'}
ALLIED_BEACONS = {'en': 'allied beacons', 'fr': 'balises alliées',
                  'es': 'balizas aliadas', 'pt': 'balizas aliadas'}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _touch_reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _row(situation, element='FIRE', ranges='30-34', **extra):
    row = {'element': element, 'ranges': [ranges], 'situation': situation,
           'triggers': 'I'}
    row.update(extra)
    return row


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _descriptions(version):
    return {entry.get('id'): entry.get('description') or {}
            for entries in get_spell_reference(version).values()
            for entry in entries if entry.get('id') is not None}


def _castable(char_class, spell_id, version):
    from chardata.spell_combo import castable_spells
    from fashionistapulp.structure import set_current_game_version
    set_current_game_version(version)
    try:
        return next(castable for castable in castable_spells(char_class, 200,
                                                             version)
                    if castable.spell_id == spell_id)
    finally:
        set_current_game_version('dofus3')


class TheGeneratorHoldsBackTheRowOnAlliesTests(SimpleTestCase):

    def test_a_row_on_allies_beside_its_enemy_twin_waits(self):
        for ally in ('a', 'g'):
            with self.subTest(mask=ally):
                rows = [_row('A|88,1,0'), _row('%s|88,1,0' % ally, ranges='15-17')]
                self.assertEqual({1: 'on_ally'},
                                 _generator()._rows_only_on_allies(rows, []))

    def test_rows_that_differ_by_more_than_their_target_stay(self):
        cases = {
            'state': [_row('A|80,1,0'), _row('a,e256|80,1,0')],
            'zone': [_row('A|80,1,0'), _row('a|67,2,1')],
            'element': [_row('A|80,1,0'), _row('a|80,1,0', element='WATER')],
            'steal': [_row('A|80,1,0', steals=True), _row('a|80,1,0')],
            'heal': [_row('A|80,1,0'), _row('a|80,1,0', heals=True)],
            'enemies and allies': [_row('A|80,1,0'), _row('a,A|80,1,0')],
            'caster': [_row('A|80,1,0'), _row('C|80,1,0')],
            'no enemy row': [_row('a|80,1,0')],
        }
        for case, rows in cases.items():
            with self.subTest(case=case):
                self.assertEqual({}, _generator()._rows_only_on_allies(rows, []))

    def test_crit_rows_in_another_order_leave_the_index_alone(self):
        normal = [_row('A|88,1,0'), _row('g|88,1,0')]
        crit = [_row('g|88,1,0'), _row('A|88,1,0')]
        self.assertEqual({}, _generator()._rows_only_on_allies(normal, crit))

    def test_a_converted_spell_carries_the_row_as_waiting(self):
        spell = {'ankama_id': 1, 'name_en': 'Probe', 'level_requirements': [1],
                 'damage_templates': {'normal': [
                     _row('A|88,1,0', steals=True),
                     _row('g|88,1,0', ranges='15-17', steals=True)]}}
        entry = _generator().convert_spell(spell)
        self.assertEqual({1: 'on_ally'}, entry.conditional)


class TheShippedSpellsCountTheEnemyRowTests(SimpleTestCase):

    def test_the_row_on_allies_is_half_the_enemy_row_and_waits(self):
        for version in MODERN:
            for spell_id in (SHOT_PELLETS, EXTRACTION):
                with self.subTest(version=version, spell=spell_id):
                    spell = _spell(version, spell_id)
                    self.assertEqual({1: 'on_ally'}, spell.conditional)
                    digest = spell.get_effects_digest()
                    for ranks in (digest.non_crit_dams, digest.crit_dams):
                        for rank in ranks:
                            enemy, ally = rank[0], rank[1]
                            self.assertEqual(
                                (enemy.min_dam, enemy.max_dam),
                                (ally.min_dam * 2, ally.max_dam * 2))

    def test_every_row_held_on_allies_is_in_ankamas_text(self):
        for version in MODERN:
            texts = _descriptions(version)
            held = {spell.spell_id
                    for spells in get_damage_spells_for_version(version).values()
                    for spell in spells
                    if 'on_ally' in (spell.conditional or {}).values()}
            with self.subTest(version=version):
                self.assertGreaterEqual(len(held), 2)
            for spell_id in held:
                for language, words in ON_ALLIES.items():
                    with self.subTest(version=version, spell=spell_id,
                                      language=language):
                        self.assertIn(words, (texts[spell_id].get(language)
                                              or '').lower())

    def test_the_turn_scores_the_enemy_row_and_leaves_the_other(self):
        for version in MODERN:
            with self.subTest(version=version):
                castable = _castable('Rogue', SHOT_PELLETS, version)
                self.assertEqual([castable.effects[0]], castable.hits)
                self.assertEqual([(castable.effects[1], 'on_ally')],
                                 castable.waiting_plain)


def _touch_line(effect_id, low, high, mask):
    return {'effectId': effect_id, 'diceNum': low, 'diceSide': high,
            'targetMask': mask, 'rawZone': 'P', 'triggers': 'I'}


class TouchKeepsTheLineTheEnemyTakesTests(SimpleTestCase):

    def _rows(self, *effects, on_ally=None):
        return _touch_reader().collect_damage(
            [_touch_line(*effect) for effect in effects], on_ally=on_ally)

    def test_a_line_on_an_allied_beacon_gives_way_to_the_enemy_line(self):
        self.assertEqual({'earth': (24, 26, None)},
                         self._rows((92, 24, 26, 'A'), (92, 48, 52, 'a,F4033')))

    def test_the_line_on_an_allied_beacon_is_handed_back_apart(self):
        on_ally = {}
        self.assertEqual({'earth': (24, 26, None)},
                         self._rows((92, 24, 26, 'A'), (92, 48, 52, 'a,F4033'),
                                    on_ally=on_ally))
        self.assertEqual({'earth': (48, 52, None)}, on_ally)

    def test_a_line_on_allies_alone_is_still_read(self):
        on_ally = {}
        self.assertEqual({'earth': (48, 52, None)},
                         self._rows((92, 48, 52, 'a,F4033'), on_ally=on_ally))
        self.assertEqual({}, on_ally)

    def test_a_line_on_allies_in_another_element_is_still_read(self):
        self.assertEqual({'earth': (24, 26, None), 'fire': (48, 52, None)},
                         self._rows((92, 24, 26, 'A'), (94, 48, 52, 'a')))

    def test_a_decoded_spell_carries_the_line_on_allies_as_waiting(self):
        levels = {'1': {'effects': [_touch_line(92, 24, 26, 'A'),
                                    _touch_line(92, 48, 52, 'a,F4033')],
                        'criticalEffect': [_touch_line(92, 26, 28, 'A'),
                                           _touch_line(92, 52, 56, 'a,F4033')],
                        'minPlayerLevel': 1}}
        decoded = _touch_reader().decode_spell(
            {'id': 1, 'nameId': 'Probe', 'spellLevels': [1]}, levels)
        self.assertEqual(['earth', 'earth'], decoded['elements'])
        self.assertEqual([['24-26'], ['48-52']], decoded['non_crit_ranges'])
        self.assertEqual([['26-28'], ['52-56']], decoded['crit_ranges'])
        self.assertEqual({1: 'on_ally'}, decoded['conditional'])

    def test_a_line_on_allies_beside_a_best_element_hit_stops_the_run(self):
        reader = _touch_reader()
        levels = {'1': {'effects': [
            _touch_line(92, 24, 26, 'A'), _touch_line(92, 48, 52, 'a'),
            _touch_line(reader.BEST_ELEMENT_EFFECT, 10, 12, 'A'),
            _touch_line(94, 10, 12, 'A')], 'minPlayerLevel': 1}}
        with self.assertRaises(SystemExit):
            reader.decode_spell({'id': 1, 'nameId': 'Probe', 'spellLevels': [1]},
                                levels)

    def test_transfusion_arrow_shows_what_an_enemy_takes(self):
        spell = _spell('touch', TOUCH_TRANSFUSION_ARROW)
        digest = spell.get_effects_digest()
        self.assertEqual([(11, 13), (13, 15), (15, 17), (17, 19), (20, 22),
                          (24, 26)],
                         [(rank[0].min_dam, rank[0].max_dam)
                          for rank in digest.non_crit_dams])
        castable = _castable('Cra', TOUCH_TRANSFUSION_ARROW, 'touch')
        self.assertEqual([(24, 26)],
                         [(row.min_dam, row.max_dam) for row in castable.hits])

    def test_transfusion_arrows_beacon_line_waits_on_an_ally(self):
        spell = _spell('touch', TOUCH_TRANSFUSION_ARROW)
        self.assertEqual({1: 'on_ally'}, spell.conditional)
        digest = spell.get_effects_digest()
        for ranks in (digest.non_crit_dams, digest.crit_dams):
            for rank in ranks:
                enemy, beacon = rank[0], rank[1]
                self.assertEqual(enemy.element, beacon.element)
                self.assertGreater(beacon.max_dam, enemy.max_dam)
        castable = _castable('Cra', TOUCH_TRANSFUSION_ARROW, 'touch')
        self.assertEqual([((48, 52), 'on_ally')],
                         [((row.min_dam, row.max_dam), trigger)
                          for row, trigger in castable.waiting_plain])

    def test_every_touch_line_held_on_allies_is_in_ankamas_text(self):
        texts = _descriptions('touch')
        held = {spell.spell_id
                for spells in get_damage_spells_for_version('touch').values()
                for spell in spells
                if 'on_ally' in (spell.conditional or {}).values()}
        self.assertIn(TOUCH_TRANSFUSION_ARROW, held)
        for spell_id in held:
            for language in ('en', 'fr'):
                with self.subTest(spell=spell_id, language=language):
                    self.assertIn('alli', (texts[spell_id].get(language)
                                           or '').lower())

    def test_transfusion_arrows_text_names_allied_beacons(self):
        description = _descriptions('touch')[TOUCH_TRANSFUSION_ARROW]
        for language, words in ALLIED_BEACONS.items():
            with self.subTest(language=language):
                self.assertIn(words, description[language].lower())
