# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch buff with a delay, a hit on a Telefrag and a poison dealt through the caster's summons stay off the turn."""
from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn, castable_spells

VERSIONS = ('touch', 'touchbeta')
PROBE = 4242
CHILD = 4243
GRANDCHILD = 4244
FORTUNE = 42
POISONED_WIND = 4766
TEMPORAL_SHAKE = 7867
TELEFRAG_LABEL = {
    'en': "only each time a Telefrag is generated while the spell's effect lasts",
    'fr': "seulement à chaque fois qu'un Téléfrag est généré tant que l'effet du sort dure",
    'es': "solo cada vez que se genera un telefrag mientras dura el efecto del hechizo",
    'pt': "apenas sempre que um Telefrag for gerado enquanto durar o efeito do feitiço",
    'de': "nur jedes Mal, wenn ein Telefrag erzeugt wird, solange die Wirkung des Zaubers anhält",
}
SUMMON_LABEL = {
    'en': "only through one of the caster's own summons the spell names, then at the start of "
          "the target's turn",
    'fr': "seulement par une des invocations du lanceur que nomme le sort, puis au début du "
          "tour de la cible",
    'es': "solo a través de una de las invocaciones del lanzador que nombra el hechizo, y "
          "después al inicio del turno del objetivo",
    'pt': "apenas por meio de uma das invocações do lançador que o feitiço nomeia, e depois "
          "no início do turno do alvo",
    'de': "nur über eine der eigenen Beschwörungen des Zaubernden, die der Zauber nennt, dann "
          "zu Beginn des Zuges des Ziels",
}

_STATS = {'str': 200, 'int': 200, 'cha': 200, 'agi': 200, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _row(effect_id, low, high, mask='a,A', **extra):
    row = {'effectId': effect_id, 'diceNum': low, 'diceSide': high, 'value': 0, 'targetMask': mask,
           'triggers': 'I', 'delay': 0, 'duration': 0, 'random': 0, 'rawZone': 'P', 'isPreview': False}
    row.update(extra)
    return row


def _level(effects):
    return {'minPlayerLevel': 1, 'apCost': 3, 'maxCastPerTurn': 1, 'maxStack': 0,
            'criticalHitProbability': 0, 'effects': effects, 'criticalEffect': []}


def _decode(effects, children=None):
    """The probe decoded, children being {spell id: effects} of the spells its rows cast."""
    spell = {'id': PROBE, 'nameId': 'Probe', 'descriptionId': 'Occasionne des dommages Terre.',
             'spellLevels': [PROBE * 10]}
    spells = {str(PROBE): spell}
    levels = {str(PROBE * 10): _level(effects)}
    for spell_id, rows in (children or {}).items():
        spells[str(spell_id)] = {'id': spell_id, 'nameId': 'Child', 'spellLevels': [spell_id * 10]}
        levels[str(spell_id * 10)] = _level(rows)
    return _reader().decode_spell(spell, levels, spells)


def _poison_through_a_doll(child_mask='a,F115,F42,P', poison=(26, 28), trigger='TB', more=()):
    """A preview line whose real rows a cast on the caster's own doll reaches."""
    return _decode(
        [_row(97, 26, 28, mask='A', duration=2, isPreview=True),
         _row(1160, CHILD, 1, mask=child_mask)] + list(more),
        {CHILD: [_row(1160, GRANDCHILD, 1, mask='A', duration=2)],
         GRANDCHILD: [_row(97, poison[0], poison[1], triggers=trigger, duration=2)]})


def _spell(version, spell_id):
    return next((spell for spells in get_damage_spells_for_version(version).values()
                 for spell in spells if spell.spell_id == spell_id), None)


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _lone_turn(test, version, spell_id):
    _in_version(test, version)
    spell = _spell(version, spell_id)
    cast = Castable(spell, len(spell.level_req) - 1, False)
    return best_turn(dict(_STATS), [cast], 12, game_version=version, caster_level=200)


class TheTouchReaderLeavesABuffWithADelayOutOfItsTurnTests(SimpleTestCase):

    def test_a_power_row_landing_a_turn_later_is_not_a_buff_of_the_cast(self):
        entry = _decode([_row(97, 10, 14), _row(138, 400, 0, delay=1, duration=1)])
        self.assertEqual(entry['elements'], ['earth'])

    def test_a_power_row_landing_on_the_cast_is_still_a_buff(self):
        entry = _decode([_row(97, 10, 14), _row(138, 400, 0, duration=1)])
        self.assertEqual(entry['elements'], ['earth', 'buff_pow'])

    def test_a_spell_whose_only_buff_waits_a_turn_has_no_entry(self):
        self.assertIsNone(_decode([_row(752, 40, 0, duration=1),
                                   _row(138, 400, 0, delay=1, duration=1)]))

    def test_a_damage_row_with_a_delay_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(97, 10, 14, delay=1)])

    def test_a_buff_with_a_delay_on_a_trigger_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(97, 10, 14), _row(138, 400, 0, delay=1, triggers='TB')])


class TheTouchReaderHoldsAHitOnATelefragApartTests(SimpleTestCase):

    def test_a_lone_preview_row_on_a_telefrag_waits_for_it(self):
        entry = _decode([_row(96, 7, 0, triggers='Y', duration=2, isPreview=True)])
        self.assertEqual(entry['conditional'], {0: 'telefrag_generated'})
        self.assertFalse(entry.get('delayed'))

    def test_a_lone_preview_row_on_an_unread_trigger_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(96, 7, 0, triggers='XYZ', isPreview=True)])


class TheTouchReaderHoldsAPoisonDealtThroughTheCastersSummonsApartTests(SimpleTestCase):

    def test_a_preview_line_paid_through_a_doll_at_turn_begin_waits_for_it(self):
        entry = _poison_through_a_doll()
        self.assertEqual(entry['non_crit_ranges'], [['26-28']])
        self.assertEqual(entry['conditional'], {0: 'own_summon_turn_begin'})
        self.assertFalse(entry.get('delayed'))

    def test_a_preview_line_an_enemy_also_takes_directly_lands_on_the_cast(self):
        entry = _poison_through_a_doll(child_mask='A')
        self.assertFalse(entry.get('conditional'))
        self.assertFalse(entry.get('delayed'))

    def test_a_real_row_of_the_element_beside_the_preview_keeps_the_line_on_the_cast(self):
        entry = _poison_through_a_doll(more=[_row(97, 20, 22, mask='A')])
        self.assertFalse(entry.get('conditional'))

    def test_a_summon_paid_line_unlike_its_preview_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _poison_through_a_doll(poison=(20, 22))

    def test_a_summon_paid_line_on_the_cast_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _poison_through_a_doll(trigger='I')


class TheTouchReaderStopsOnARowThatWaitsOnSomeRanksOnlyTests(SimpleTestCase):

    def _two_ranks(self, first_trigger, second_trigger):
        spell = {'id': PROBE, 'nameId': 'Probe', 'descriptionId': 'Occasionne des dommages Eau.',
                 'spellLevels': [PROBE * 10, PROBE * 10 + 1]}
        levels = {str(PROBE * 10): _level([_row(96, 7, 9, triggers=first_trigger, duration=2)]),
                  str(PROBE * 10 + 1): _level([_row(96, 8, 10, triggers=second_trigger,
                                                    duration=2)])}
        return _reader().decode_spell(spell, levels, {str(PROBE): spell})

    def test_a_hit_that_waits_for_a_telefrag_on_one_rank_and_lands_on_the_next_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            self._two_ranks('Y', 'I')

    def test_a_hit_that_waits_for_a_telefrag_on_every_rank_is_held_apart(self):
        entry = self._two_ranks('Y', 'Y')
        self.assertEqual(entry['conditional'], {0: 'telefrag_generated'})


class TheTouchTablesKeepTheseLinesOffTheTurnTests(SimpleTestCase):

    def test_fortune_gives_the_turn_of_its_cast_no_power(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertIsNone(_spell(version, FORTUNE))
                _in_version(self, version)
                self.assertNotIn(FORTUNE, [cast.spell_id
                                           for cast in castable_spells('Enutrof', 200, version)])

    def test_poisoned_wind_waits_for_a_doll_or_a_tree(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, POISONED_WIND)
                self.assertEqual(spell.conditional, {0: 'own_summon_turn_begin'})
                self.assertFalse(getattr(spell, 'delayed', None))
                self.assertEqual(_lone_turn(self, version, POISONED_WIND), (0.0, []))

    def test_temporal_shake_waits_for_a_telefrag(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, TEMPORAL_SHAKE)
                self.assertEqual(spell.conditional, {0: 'telefrag_generated'})
                self.assertFalse(getattr(spell, 'delayed', None))
                self.assertEqual(_lone_turn(self, version, TEMPORAL_SHAKE), (0.0, []))

    def test_the_spell_cards_name_each_wait_in_each_language(self):
        from chardata import spells_view
        for version in VERSIONS:
            for spell_id, labels in ((POISONED_WIND, SUMMON_LABEL),
                                     (TEMPORAL_SHAKE, TELEFRAG_LABEL)):
                spell = _spell(version, spell_id)
                for language, text in labels.items():
                    with translation.override(language), self.subTest(
                            version=version, spell=spell_id, language=language):
                        digest = spells_view._create_spell_web_digest(spell, version,
                                                                      char_level=200)
                        self.assertEqual(digest['conditional'], {'0': text})
