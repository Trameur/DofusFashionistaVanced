# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An item text says the number its effect carries and the count form that number calls for."""

import json
import os
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRAPERS = os.path.join(_REPO, 'itemscraper')
_LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

_MENALT = 32116
_ORDER_OF_THUNDER = 31859
_PUSHBACK_DAMAGE = 414
_CASTS_PER_TURN = 290
_CAP_RICOTT = 8632

_PUSHBACK_TEMPLATES = {
    'en': '#1{{~1~2 to }}#2 Pushback Damage{{~p}}{{~z}}',
    'fr': '#1{{~1~2 à }}#2 Dommage{{~ps}}{{~zs}} Poussée',
    'es': '#1{{~1~2 a }}#2 de daño{{~p}}{{~z}} de empuje',
    'pt': '#1{{~1~2 a }}#2 de dano{{~ps}}{{~zs}} de empurrão',
    'de': '#1{{~1~2 bis }}#2 Schubsschaden{{~ps}}{{~zs}}',
}
_CAST_TEMPLATES = {
    'en': '#1: +#3 cast{{~ps}} per turn',
    'fr': '#1 : +#3 lancer{{~ps}} par tour',
    'es': '#1: +#3 lanzamiento{{~ps}} por turno',
    'pt': '#1: +#3 lançamento{{~ps}} por turno',
    'de': '#1: +#3 Zauber{{~p}} pro Runde',
}

_BETA_MENALT_TEXTS = {
    'en': '{{spell,31859,1::Order of Thunder}}:\n'
          '• The bearer gains 8 Pushback Damage for 2 turns for each MP they use.\n'
          '• At the end of each turn, the bearer gives 1 MP to all allies in their line of sight '
          'for 1 turn (stackable 1 time).',
    'fr': '{{spell,31859,1::Ordre du Tonnerre}} :\n'
          "• Le porteur gagne 6 Dommages Poussée pendant 2 tours pour chaque PM qu'il utilise.\n"
          '• À chaque fin de tour, le porteur donne 1 PM pendant 1 tour à tous les alliés dans '
          'sa ligne de vue (cumulable 1 fois).',
    'es': '{{spell,31859,1::Orden del Trueno}}:\n'
          '• El portador gana 8 de daños de empuje durante 2 turnos por cada PM que use.\n'
          '• Al final de cada turno, el portador da 1 PM durante 1 turno a todos los aliados en '
          'su línea de visión (acumulable 1 vez).',
    'pt': '{{spell,31859,1::Ordem do Trovão}}:\n'
          '• O portador ganha 8 de danos de empurrão durante 2 turnos para cada PM que ele utilizar.\n'
          '• No fim de cada turno, o portador concede 1 PM durante 1 turno a todos os aliados em '
          'sua linha de visão (acumula até 1 vez).',
    'de': '{{spell,31859,1::Orden des Donners}}:\n'
          '• Der Träger erhält 2 Runden lang für jeden von ihm verwendeten BP 8 Schubsschaden.\n'
          '• Am Ende jeder Runde gewährt der Träger allen Verbündeten in seiner Sichtlinie 1 Runde '
          'lang 1 BP und 40 Schubsschaden (1-mal kumulierbar).',
}

_ONE_CAST = {
    'en': ('Poisoned Wind: +1 casts per turn', 'Poisoned Wind: +1 cast per turn'),
    'fr': ('Vent Empoisonné : +1 lancers par tour', 'Vent Empoisonné : +1 lancer par tour'),
    'es': ('Viento Envenenado: +1 lanzamientos por turno', 'Viento Envenenado: +1 lanzamiento por turno'),
    'pt': ('Vento Envenenado: +1 lançamentos por turno', 'Vento Envenenado: +1 lançamento por turno'),
    'de': ('Giftiger Windstrom: +1 Zauber pro Runde', 'Giftiger Windstrom: +1 Zauber pro Runde'),
}
_TWO_CASTS = {
    'en': 'Hemlock: +2 casts per turn',
    'fr': 'Cigüe : +2 lancers par tour',
    'es': 'Cicuta: +2 lanzamientos por turno',
    'pt': 'Cicuta: +2 lançamentos por turno',
    'de': 'Schierling: +2 Zauber pro Runde',
}


def _table(records):
    """A datacenter table as the Dofus 3 dump writes it, records shared by reference."""
    refs, keys, values = [], [], []
    for key, record in records.items():
        refs.append({'rid': len(refs) + 1, 'data': record})
        keys.append(key)
        values.append({'rid': len(refs)})
    return {'references': {'RefIds': refs},
            'objectsById': {'m_keys': {'Array': keys}, 'm_values': {'Array': values}}}


def _spell_levels(effect_key):
    effect = {'rid': 1000}
    table = _table({70001: {'id': 70001, 'effects': {'Array': [effect]}}})
    table['references']['RefIds'].append({'rid': 1000, 'data': {
        effect_key: _PUSHBACK_DAMAGE, 'diceNum': 6, 'diceSide': 0, 'value': 0}})
    return table


def _effect(formatted, low, type_name):
    return {'int_minimum': low, 'int_maximum': 0, 'ignore_int_min': low == 0,
            'ignore_int_max': True, 'formatted': formatted,
            'type': {'name': type_name, 'id': 0, 'is_meta': False, 'is_active': False}}


def _equipment(language):
    return {'items': [
        {'ankama_id': _MENALT, 'name': 'Menalt', 'level': 200, 'type': {'name': 'Dofus', 'id': 23},
         'effects': [_effect(_BETA_MENALT_TEXTS[language], 0, '-special spell-')]},
        {'ankama_id': _CAP_RICOTT, 'name': 'Cap Ricott', 'level': 40, 'type': {'name': 'Hat', 'id': 27},
         'effects': [_effect(_ONE_CAST[language][0], 13529, ': + cast per turn'),
                     _effect(_TWO_CASTS[language], 13577, ': + cast per turn')]},
    ]}


def _write(path, data):
    with open(path, 'w', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False)


def _transform(effect_key='effectId', with_spells=True, spells_cut_short=False):
    """{(ankama id, language): special text} from get_equipments2.py run on the witness files."""
    with tempfile.TemporaryDirectory() as directory:
        work, raw = os.path.join(directory, 'work'), os.path.join(directory, 'raw')
        os.makedirs(work)
        os.makedirs(raw)
        for language in _LANGUAGES:
            _write(os.path.join(work, 'all_equipment_%s.json' % language), _equipment(language))
            _write(os.path.join(raw, '%s.json' % language), {'entries': {
                '9001': _PUSHBACK_TEMPLATES[language], '9002': _CAST_TEMPLATES[language]}})
        _write(os.path.join(raw, 'items.json'), {'references': {'RefIds': []}})
        _write(os.path.join(raw, 'breeds.json'), [])
        _write(os.path.join(raw, 'effects.json'), _table({
            _PUSHBACK_DAMAGE: {'id': _PUSHBACK_DAMAGE, 'descriptionId': 9001},
            _CASTS_PER_TURN: {'id': _CASTS_PER_TURN, 'descriptionId': 9002}}))
        if with_spells:
            _write(os.path.join(raw, 'spells.json'), _table({_ORDER_OF_THUNDER: {
                'id': _ORDER_OF_THUNDER, 'spellLevels': {'Array': [70001]}}}))
            _write(os.path.join(raw, 'spell_levels.json'), _spell_levels(effect_key))
        if spells_cut_short:
            with open(os.path.join(raw, 'spells.json'), 'r+', encoding='utf-8') as cut:
                cut.truncate(len(cut.read()) // 2)
        done = subprocess.run(
            [sys.executable, 'get_equipments2.py', '--work-dir', work, '--raw-dir', raw,
             '--game-version', 'beta'],
            cwd=_SCRAPERS, capture_output=True, text=True, encoding='utf-8', timeout=300,
            env=dict({key: value for key, value in os.environ.items() if key != 'PYTHONPATH'},
                     PYTHONIOENCODING='utf-8'))
        if done.returncode:
            raise AssertionError(done.stdout + done.stderr)
        with open(os.path.join(work, 'transformed_equipment.json'), encoding='utf-8') as source:
            rows = json.load(source)
    return {(row['ankama_id'], language): row.get('special_spell_%s' % language)
            for row in rows for language in _LANGUAGES}, done.stdout


class AnItemTextNumberFollowsItsEffectTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.texts, cls.output = _transform()

    def _line(self, ankama_id, language, index):
        return self.texts[ankama_id, language].split('\n')[index]

    def test_an_item_text_number_follows_its_effect(self):
        for language, words in (('en', 'gains 6 Pushback Damage'), ('es', 'gana 6 de daños de empuje'),
                                ('pt', 'ganha 6 de danos de empurrão'), ('de', 'BP 6 Schubsschaden.')):
            with self.subTest(language=language):
                self.assertIn(words, self._line(_MENALT, language, 1))
                self.assertNotIn(' 8 ', self._line(_MENALT, language, 1))

    def test_the_language_that_already_agrees_is_left_as_written(self):
        self.assertEqual(_BETA_MENALT_TEXTS['fr'], self.texts[_MENALT, 'fr'])

    def test_a_number_no_effect_of_the_spell_carries_is_left_as_written(self):
        for language in _LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(_BETA_MENALT_TEXTS[language].split('\n')[2],
                                 self._line(_MENALT, language, 2))

    def test_the_rebuilt_number_is_reported(self):
        self.assertEqual(4, self.output.count('Number rebuilt from its effect in %d' % _MENALT))

    def test_one_cast_is_singular(self):
        for language, (_written, singular) in _ONE_CAST.items():
            with self.subTest(language=language):
                self.assertEqual(singular, self._line(_CAP_RICOTT, language, 0))

    def test_two_casts_stay_plural(self):
        for language, plural in _TWO_CASTS.items():
            with self.subTest(language=language):
                self.assertEqual(plural, self._line(_CAP_RICOTT, language, 1))


class TheLiveEffectKeyIsReadTooTests(SimpleTestCase):

    def test_a_level_effect_under_action_id_backs_the_number(self):
        texts, _ = _transform(effect_key='actionId')
        self.assertIn('gains 6 Pushback Damage', texts[_MENALT, 'en'])


class WithoutTheSpellFilesTheTextStaysTests(SimpleTestCase):

    def test_the_text_stays_and_the_missing_files_are_named(self):
        texts, output = _transform(with_spells=False)
        self.assertEqual(_BETA_MENALT_TEXTS['en'], texts[_MENALT, 'en'])
        self.assertIn('spells.json, spell_levels.json', output)


class AnUnreadableSpellFileLeavesTheTextTests(SimpleTestCase):

    def test_the_text_stays_and_the_unreadable_file_is_named(self):
        texts, output = _transform(spells_cut_short=True)
        self.assertEqual(_BETA_MENALT_TEXTS['en'], texts[_MENALT, 'en'])
        self.assertIn('missing or unreadable', output)
        self.assertIn('spells.json (', output)


class OnlyALineThatNamesTheEffectAsOftenAsTheReferenceIsRebuiltTests(SimpleTestCase):

    def test_a_line_that_names_the_effect_more_often_than_the_reference_is_left_as_written(self):
        module = itemscraper_module('item_effect_texts')
        texts = module.EffectTexts(
            {language: {_PUSHBACK_DAMAGE: template}
             for language, template in _PUSHBACK_TEMPLATES.items()},
            {_ORDER_OF_THUNDER: {_PUSHBACK_DAMAGE: {6}}})
        written = dict(_BETA_MENALT_TEXTS)
        written['de'] = written['de'].replace('BP 8 Schubsschaden.',
                                              'BP 8 Schubsschaden, bis zu 16 Schubsschaden.')
        rebuilt = texts.rebuild_numbers(written)
        self.assertIn('gains 6 Pushback Damage', rebuilt['en'])
        self.assertEqual(written['de'], rebuilt['de'])
