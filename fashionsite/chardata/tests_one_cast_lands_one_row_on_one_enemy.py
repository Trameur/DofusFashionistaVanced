# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One cast on one enemy: the payout, ring and throw rows it does not take stay out of the turn."""
from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

MODERN = ('dofus3', 'beta', 'dofus2')

NOA = 23735
PILFER = 13823
FATE_OF_ECAFLIP = 12859
HARD_CASH = 13353
PLACER_MINING = 13363
COLLAPSE = 13352
FIREDAMP_EXPLOSION = 13368
VOODOO_CURSE = 13576
SENTENCE = 13147
THROWS = {12811: 'Stretcher', 12793: 'Pandilongation', 12788: 'Propulsion',
          12808: 'Brandy', 12823: 'Waterfall'}

DOFUS2_HELD_BACK = {
    NOA: 'pushback',
    PILFER: 'pushback',
    FATE_OF_ECAFLIP: 'critical_hit',
    HARD_CASH: 'ap_removal',
    PLACER_MINING: 'mp_removal',
    COLLAPSE: 'range_removal',
    FIREDAMP_EXPLOSION: 'healed',
    VOODOO_CURSE: 'doll_dies',
    SENTENCE: 'around_the_target_at_turn_end',
}

MODERN_HELD_BACK = {
    FIREDAMP_EXPLOSION: 'healed',
    VOODOO_CURSE: 'doll_dies',
    SENTENCE: 'around_the_target_at_turn_end',
}

# Enutrof spells whose state pays out a smaller row of the cast's element
ENUTROF_PAYOUTS = (HARD_CASH, PLACER_MINING, COLLAPSE, FIREDAMP_EXPLOSION)

SAYS = {
    'pushback': {'en': 'pushback damage', 'fr': 'dommages de pouss',
                 'es': 'daños de empuje', 'pt': 'danos de empurr',
                 'de': 'schubsschaden'},
    'critical_hit': {'en': 'lands a critical hit',
                     'fr': 'effectue un coup critique',
                     'es': 'golpe crítico', 'pt': 'golpe crítico',
                     'de': 'kritischen treffer landet'},
    'ap_removal': {'en': 'attempted ap reduction',
                   'fr': 'tentative de retrait de pa',
                   'es': 'intento de retirada de pa',
                   'pt': 'tentativa de retirada de pa',
                   'de': 'ap zu entziehen'},
    'mp_removal': {'en': 'attempted mp reduction',
                   'fr': 'tentative de retrait de pm',
                   'es': 'intento de retirada de pm',
                   'pt': 'tentativa de retirada de pm',
                   'de': 'bp zu entziehen'},
    'range_removal': {'en': 'range reduction', 'fr': 'retrait de portée',
                      'es': 'retirada de alcance', 'pt': 'retirada de alcance',
                      'de': 'reichweite entzogen'},
    'healed': {'en': 'if it is healed', 'fr': 'si elle est soignée',
               'es': 'si este recibe curas', 'pt': 'se ele for curado',
               'de': 'wenn es geheilt wird'},
    'doll_dies': {'en': "when one of the caster's dolls dies",
                  'fr': "à la mort d'une poupée du lanceur",
                  'es': 'con la muerte de una muñeca del lanzador',
                  'pt': 'quando uma boneca do lançador morre',
                  'de': 'wenn ein püppchen des zaubernden stirbt'},
    'around_the_target_at_turn_end': {'en': 'around the target',
                                      'fr': "autour d'elle",
                                      'es': 'alrededor de este',
                                      'pt': 'ao redor dele',
                                      'de': 'ende der runde des ziels'},
}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _descriptions(version):
    return {entry.get('id'): entry.get('description') or {}
            for entries in get_spell_reference(version).values()
            for entry in entries if entry.get('id') is not None}


def _top_cast(spell):
    from chardata.spell_combo import Castable
    return Castable(spell, len(spell.level_req) - 1, False)


def _row(situation, ranges='18-20', element='EARTH', heals=False):
    return {'element': element, 'ranges': [ranges], 'situation': situation,
            'triggers': 'I', 'heals': heals, 'steals': False}


class ARowThatWaitsIsNotTurnDamageTests(SimpleTestCase):

    def test_dofus2_holds_back_the_row_its_text_says_waits(self):
        _in_version(self, 'dofus2')
        for spell_id, trigger in DOFUS2_HELD_BACK.items():
            with self.subTest(spell=spell_id):
                self.assertEqual({1: trigger}, _spell('dofus2', spell_id).conditional)

    def test_the_modern_versions_hold_back_the_same_rows(self):
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            for spell_id, trigger in MODERN_HELD_BACK.items():
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual({1: trigger},
                                     _spell(version, spell_id).conditional)

    def test_the_turn_scores_the_cast_row_and_leaves_the_other(self):
        for version in MODERN:
            _in_version(self, version)
            held = DOFUS2_HELD_BACK if version == 'dofus2' else MODERN_HELD_BACK
            for spell_id, trigger in held.items():
                with self.subTest(version=version, spell=spell_id):
                    cast = _top_cast(_spell(version, spell_id))
                    self.assertEqual([cast.effects[0]], cast.hits)
                    self.assertEqual([(cast.effects[1], trigger)],
                                     cast.waiting_plain)

    def test_ankamas_text_states_each_rule_in_five_languages(self):
        for version in MODERN:
            texts = _descriptions(version)
            held = DOFUS2_HELD_BACK if version == 'dofus2' else MODERN_HELD_BACK
            for spell_id, trigger in held.items():
                for language, words in SAYS[trigger].items():
                    with self.subTest(version=version, spell=spell_id,
                                      language=language):
                        self.assertIn(words, (texts[spell_id].get(language)
                                              or '').lower())

    def test_each_enutrof_payout_is_the_smaller_second_row(self):
        for version in MODERN:
            _in_version(self, version)
            for spell_id in ENUTROF_PAYOUTS:
                digest = _spell(version, spell_id).get_effects_digest()
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    for rank in ranks:
                        with self.subTest(version=version, spell=spell_id):
                            cast, payout = rank
                            self.assertEqual(cast.element, payout.element)
                            self.assertLess(payout.max_dam, cast.min_dam)


class SentenceSparesItsOwnTargetTests(SimpleTestCase):

    def test_the_client_timing_stays_on_the_row(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertEqual({1: 'turn_end'}, _spell(version, SENTENCE).delayed)

    def test_the_best_turn_does_not_count_it_as_late_damage(self):
        from chardata.spell_combo import best_turn, castable_spells, delayed_damage
        from fashionistapulp.structure import get_structure
        for version in MODERN:
            _in_version(self, version)
            stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
            stats.update({'int': 400, 'pow': 100})
            spells = [spell for spell in castable_spells('Iop', 200, version)
                      if spell.spell_id == SENTENCE]
            with self.subTest(version=version):
                self.assertEqual(1, len(spells))
                total, order = best_turn(stats, spells, 12, game_version=version)
                self.assertGreater(total, 0)
                self.assertEqual({}, delayed_damage(stats, spells, order,
                                                    game_version=version))


class APandawaThrowLandsOneRowTests(SimpleTestCase):

    def test_the_carried_row_and_its_area_twins_are_one_hit(self):
        rows = [_row('g,K|80,1,0', heals=True), _row('g|108,1,63', heals=True),
                _row('A,K|80,1,0'), _row('A|108,1,63')]
        self.assertEqual([('', [0]), ('', [2])],
                         _generator()._build_thrown_hit_aggregates(rows, rows, 4))

    def test_every_area_zone_is_a_face_of_the_same_hit(self):
        rows = [_row('A,K|'), _row('A|'), _row('A|')]
        self.assertEqual([('', [0]), ('', [3])],
                         _generator()._build_thrown_hit_aggregates(rows, [], 4))

    def test_rows_that_are_not_all_twins_are_left_alone(self):
        cases = {
            'no carried row': [_row('A|80,1,0'), _row('A|88,1,0')],
            'carried row alone': [_row('A,K|80,1,0'), _row('A|88,1,0', '9-11')],
            'other element': [_row('A,K|80,1,0'), _row('A|88,1,0'),
                              _row('A|84,1,0', element='FIRE')],
            'two carried rows': [_row('A,K|80,1,0'), _row('A,K|81,1,0'),
                                 _row('A|88,1,0')],
        }
        for case, rows in cases.items():
            with self.subTest(case=case):
                self.assertIsNone(
                    _generator()._build_thrown_hit_aggregates(rows, [], len(rows)))

    def test_crit_rows_that_differ_leave_the_throw_alone(self):
        rows = [_row('A,K|80,1,0'), _row('A|88,1,0')]
        crit = [_row('A,K|80,1,0', '21-24'), _row('A|88,1,0', '22-25')]
        self.assertIsNone(_generator()._build_thrown_hit_aggregates(rows, crit, 2))

    def test_a_converted_throw_keeps_its_heal_and_its_hit(self):
        rows = [_row('g,K|80,1,0', heals=True), _row('g|88,1,0', heals=True),
                _row('A,K|80,1,0'), _row('A|88,1,0')]
        spell = {'ankama_id': 1, 'name_en': 'Probe', 'level_requirements': [1],
                 'damage_templates': {'normal': rows, 'critical': rows}}
        entry = _generator().convert_spell(spell)
        self.assertEqual([('', [0]), ('', [2])], entry.aggregates)

    def test_each_shipped_throw_scores_one_hit_on_an_enemy(self):
        for version in MODERN:
            _in_version(self, version)
            for spell_id, name in THROWS.items():
                with self.subTest(version=version, spell=name):
                    cast = _top_cast(_spell(version, spell_id))
                    self.assertEqual(1, len(cast.hits))
                    self.assertFalse(cast.hits[0].heals)

    def test_the_table_shows_one_line_per_hit(self):
        from chardata.spells_view import _create_spell_web_digest
        for version in MODERN:
            _in_version(self, version)
            for spell_id, name in THROWS.items():
                with self.subTest(version=version, spell=name):
                    spell = _spell(version, spell_id)
                    digest = _create_spell_web_digest(spell, version)
                    heals = any(effect.heals for effect in
                                spell.get_effects_digest().non_crit_dams[0])
                    self.assertEqual(2 if heals else 1, len(digest['aggregates']))
                    self.assertIsNone(digest['always_land'])


class TheNewRulesAreWrittenInFiveLanguagesTests(SimpleTestCase):

    def test_each_label_reads_differently_in_every_language(self):
        from chardata.spells_view import _CONDITIONAL_LABELS
        for trigger in ('doll_dies', 'around_the_target_at_turn_end'):
            rendered = {}
            for language in ('en', 'fr', 'es', 'pt', 'de'):
                with translation.override(language):
                    rendered[language] = str(_CONDITIONAL_LABELS[trigger])
            with self.subTest(rule=trigger):
                self.assertEqual(5, len(set(rendered.values())),
                                 'a language fell back to English: %s' % rendered)
