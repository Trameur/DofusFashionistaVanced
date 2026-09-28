# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Dofus 2 row the client lists as landing on the cast, but dealt by a sub-spell on a trigger, is not counted on the cast."""
import contextlib
import io
import json
import os

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

HAND = 13244
CRYOTHERAPY = 25875
ARDENT_THISTLES = 13517
EXPLODING_ARROW = 13085
TYRANNICAL_ARROW = 13082

# {spell id: {row: token}} the Dofus 2 turn holds back
HELD = {
    HAND: {1: 'telefrag_ends'},
    ARDENT_THISTLES: {1: 'mp_removal'},
    EXPLODING_ARROW: {2: 'around_the_target_at_turn_end'},
    TYRANNICAL_ARROW: {2: 'pushback', 3: 'attracted_or_pushed'},
}

# {spell id: {row: when}} the Dofus 2 turn counts apart, as landing later
LATE = {
    CRYOTHERAPY: {1: 'later_turn', 2: 'later_turn'},
}

# Ankama's words for the trigger of each held row, lower case
SAYS = {
    HAND: {'en': 'upon leaving the {spell,24510,1::telefrag} state',
           'fr': "en sortie d'état {spell,24510,1::téléfrag}",
           'es': 'al salir del estado {spell,24510,1::telefrag}',
           'pt': 'na saída do estado {spell,24510,1::telefrag}',
           'de': 'am ende des zustands „{spell,24510,1::telefrag}“'},
    CRYOTHERAPY: {'en': 'if the target loses the state',
                  'fr': "si la cible perd l'état",
                  'es': 'si el objetivo pierde el estado',
                  'pt': 'se o alvo perder o estado',
                  'de': 'wenn der zustand des ziels aufgehoben wird'},
    ARDENT_THISTLES: {'en': 'hit by an attempted mp removal',
                      'fr': 'subit une tentative de retrait de pm',
                      'es': 'sufre un intento de retirada de pm',
                      'pt': 'sofrer uma tentativa de retirada de pm',
                      'de': 'wenn versucht wird, dem ziel bp zu entziehen'},
    EXPLODING_ARROW: {'en': "at the end of the target's turn",
                      'fr': 'à la fin du tour de la cible',
                      'es': 'al final del turno del objetivo',
                      'pt': 'no fim do turno do alvo',
                      'de': 'am ende der runde des ziels'},
    TYRANNICAL_ARROW: {'en': 'if it is attracted or pushed',
                       'fr': 'si elle est attirée ou poussée',
                       'es': 'si este es atraído o empujado',
                       'pt': 'se ele for atraído ou empurrado',
                       'de': 'wenn das ziel herangezogen oder geschubst wird'},
}

# Ankama's words placing Exploding Arrow's burst around the target
AROUND_IT = {'en': 'around the target', 'fr': "autour d'elle", 'es': 'alrededor de este',
             'pt': 'ao redor dele', 'de': 'umkreis'}

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLASS_FILE = os.path.join(REPO, 'itemscraper', 'transformed_class_spells_dofus2.json')


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_dofus2(test):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version('dofus2')


def _spell(spell_id):
    return next(spell for spells in get_damage_spells_for_version('dofus2').values()
                for spell in spells if spell.spell_id == spell_id)


def _text(spell_id, language):
    for entries in get_spell_reference('dofus2').values():
        for entry in entries:
            if entry.get('id') == spell_id:
                text = (entry.get('description') or {}).get(language) or ''
                return ' '.join(text.replace('’', "'").lower().split())
    return ''


def _top_cast(spell, crit=False):
    from chardata.spell_combo import Castable
    return Castable(spell, len(spell.level_req) - 1, crit)


def _row(ranges, triggers, mask='A'):
    return {'element': 'FIRE', 'steals': False, 'heals': False, 'ranges': ranges,
            'triggers': triggers, 'situation': '%s|' % mask}


def _probe(triggers):
    return {'ankama_id': 900001, 'name_en': 'Probe', 'breed_ids': [1],
            'level_requirements': [1], 'levels': [],
            'damage_templates': {'normal': [_row(['10-12'], 'I', 'a,A'),
                                            _row(['5-6'], triggers)],
                                 'critical': []}}


class AnkamaSaysEachRowWaitsTests(SimpleTestCase):

    def test_each_card_names_what_the_row_waits_for_in_five_languages(self):
        for spell_id, words in SAYS.items():
            for language in LANGUAGES:
                with self.subTest(spell=spell_id, language=language):
                    self.assertIn(words[language], _text(spell_id, language))

    def test_exploding_arrow_says_its_burst_is_around_the_target(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertIn(AROUND_IT[language], _text(EXPLODING_ARROW, language))


class EachSpellCarriesWhatItsRowsWaitForTests(SimpleTestCase):

    def test_each_held_row_is_held_back_on_its_trigger(self):
        for spell_id, held in HELD.items():
            with self.subTest(spell=spell_id):
                spell = _spell(spell_id)
                self.assertEqual(held, spell.conditional)
                self.assertFalse(spell.delayed)

    def test_the_burst_of_cryotherapy_lands_on_a_later_turn(self):
        for spell_id, late in LATE.items():
            with self.subTest(spell=spell_id):
                spell = _spell(spell_id)
                self.assertEqual(late, spell.delayed)
                self.assertIsNone(getattr(spell, 'delayed_crit', None))
                self.assertFalse(spell.conditional)


class TheTurnCountsOnlyWhatTheCastLandsTests(SimpleTestCase):

    def test_a_held_row_is_left_out_of_the_cast(self):
        _in_dofus2(self)
        for spell_id, held in HELD.items():
            spell = _spell(spell_id)
            for crit in (False, True):
                cast = _top_cast(spell, crit)
                if not cast.effects:
                    continue
                with self.subTest(spell=spell_id, crit=crit):
                    waiting = cast.waiting_crit if crit else cast.waiting_plain
                    self.assertEqual(sorted(held.values()),
                                     sorted(token for _effect, token in waiting))
                    held_rows = {id(cast.effects[index]) for index in held}
                    self.assertFalse(held_rows & {id(effect) for effect in cast.hits})
                    self.assertTrue(cast.hits)

    def test_the_burst_is_scored_apart_from_the_cast(self):
        _in_dofus2(self)
        cast = _top_cast(_spell(CRYOTHERAPY))
        burst = cast.effects[2]
        self.assertIn(burst, cast.hits)
        self.assertEqual('later_turn', cast.late_by_effect.get(id(burst)))
        self.assertNotIn(id(cast.effects[0]), cast.late_by_effect)


class TheGeneratorReadsEveryTriggerTests(SimpleTestCase):

    def test_a_push_or_a_pull_holds_the_row_back(self):
        generator = _generator()
        for triggers in ('P|MA', 'MA|P'):
            with self.subTest(triggers=triggers):
                self.assertEqual((None, 'attracted_or_pushed'),
                                 generator._trigger_tokens(triggers))
                entry = generator.convert_spell(_probe(triggers))
                self.assertEqual({1: 'attracted_or_pushed'}, entry.conditional)
                self.assertIsNone(entry.trigger_problem)

    def test_a_trigger_no_token_reads_stops_the_run(self):
        generator = _generator()
        entry = generator.convert_spell(_probe('ZZ'))
        self.assertIsNone(entry.conditional)
        self.assertIn('ZZ', entry.trigger_problem or '')
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'ZZ'):
                generator.build_spell_map({'Iop': {'breed_id': 1}}, [_probe('ZZ')])

    def test_a_listed_late_row_must_exist(self):
        generator = _generator()
        self.addCleanup(setattr, generator, 'DELAYED_ROWS', generator.DELAYED_ROWS)
        generator.DELAYED_ROWS = {900001: {5: generator.LATER_TURN}}
        with self.assertRaisesRegex(RuntimeError, 'no row 5'):
            generator.convert_spell(_probe('I'))

    def test_a_listed_late_row_must_be_one_the_client_marks_on_cast(self):
        generator = _generator()
        self.addCleanup(setattr, generator, 'DELAYED_ROWS', generator.DELAYED_ROWS)
        generator.DELAYED_ROWS = {900001: {1: generator.LATER_TURN}}
        self.assertEqual({1: generator.LATER_TURN},
                         generator.convert_spell(_probe('I')).delayed)
        for triggers in ('TE', 'PD', 'P|MA'):
            with self.subTest(triggers=triggers):
                with self.assertRaisesRegex(RuntimeError, 'row 1 of spell 900001 waits'):
                    generator.convert_spell(_probe(triggers))
        critical = _probe('I')
        critical['damage_templates']['critical'] = [_row(['12-14'], 'I', 'a,A'),
                                                    _row(['6-7'], 'TE')]
        with self.assertRaisesRegex(RuntimeError, 'waits on TE'):
            generator.convert_spell(critical)

    def test_only_dofus2_lists_these_rows(self):
        generator = _generator()
        dofus2 = generator.CONDITIONAL_ROWS_BY_VERSION['dofus2']
        for spell_id, held in HELD.items():
            listed = {row: token for row, token in held.items()
                      if token not in ('pushback', 'attracted_or_pushed')}
            with self.subTest(spell=spell_id):
                self.assertEqual(listed, dofus2.get(spell_id, {}))
        self.assertEqual(LATE, generator.DELAYED_ROWS_BY_VERSION['dofus2'])
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertEqual({}, generator.DELAYED_ROWS_BY_VERSION[version])

    def test_the_client_still_marks_the_listed_rows_on_cast(self):
        if not os.path.exists(CLASS_FILE):
            self.skipTest('transformed_class_spells_dofus2.json is not tracked; '
                          'run itemscraper/get_spells.py')
        with open(CLASS_FILE, encoding='utf-8') as handle:
            classes = json.load(handle)
        rows = {spell['ankama_id']: spell['damage_templates']['normal']
                for payload in classes.values()
                for spell in payload.get('spells') or []
                if spell.get('ankama_id') in SAYS}
        self.assertEqual(set(SAYS), set(rows))
        listed = dict(LATE)
        listed.update({HAND: HELD[HAND], ARDENT_THISTLES: HELD[ARDENT_THISTLES],
                       EXPLODING_ARROW: HELD[EXPLODING_ARROW]})
        for spell_id, marked in listed.items():
            for index in marked:
                with self.subTest(spell=spell_id, row=index):
                    self.assertEqual('I', rows[spell_id][index]['triggers'])
        self.assertEqual('P|MA', rows[TYRANNICAL_ARROW][3]['triggers'])


class TheNewRulesAreWrittenInFiveLanguagesTests(SimpleTestCase):

    def test_each_label_reads_differently_in_every_language(self):
        from chardata.spells_view import _CONDITIONAL_LABELS
        for token in ('telefrag_ends', 'attracted_or_pushed'):
            rendered = {}
            for language in LANGUAGES:
                with translation.override(language):
                    rendered[language] = str(_CONDITIONAL_LABELS[token])
            with self.subTest(rule=token):
                self.assertEqual(5, len(set(rendered.values())),
                                 'a language fell back to English: %s' % rendered)
