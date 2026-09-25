# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hit whose rows split on the target (shield points, HP) lands one face; the turn counts the plain one."""
import copy
import json
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version

PIERCING_ARROW = 32429
ABOLITION_ARROW = 32453
LETHAL_ATTACK = 12917
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
VERSIONS = ('dofus3', 'beta')

_REFERENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'spell_reference')

_STATS = {'agi': 800, 'str': 0, 'int': 0, 'cha': 0, 'pow': 0, 'dam': 0,
          'cridam': 35, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 97, 'neutdam': 0, 'ch': 3, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}

_STRENGTH_STATS = dict(_STATS, agi=0, airdam=0, str=1100, pow=80, dam=30,
                       earthdam=70, cridam=35, ch=35, ap=11)

_DOFUS2_HP_FACES = [('Target with 25% of its HP or more', [0]),
                    ('Target with less than 25% of its HP', [1])]

_SHIELD_LABELS = {'Target with shield points', 'Target without shield points'}
_HP_LABEL = re.compile(r'^Target with (?:less than )?(\d+)% of its HP(?: or more)?$')

# The condition in the spell's own text, one word per language
_SHIELD_WORD = {'en': 'shield', 'fr': 'bouclier', 'es': 'escudo',
                'pt': 'escudo', 'de': 'schild'}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _spell(char_class, spell_id, version='dofus3'):
    return next(spell for spell in get_damage_spells_for_version(version)[char_class]
                if spell.spell_id == spell_id)


def _convert(*rows):
    spell = {'ankama_id': 1, 'name_en': 'Probe', 'level_requirements': [1],
             'damage_templates': {'normal': [
                 {'element': 'AIR', 'ranges': [ranges], 'situation': situation}
                 for situation, ranges in rows]}}
    return _generator().convert_spell(spell)


def _convert_states(*rows):
    spell = {'ankama_id': 1, 'name_en': 'Probe', 'level_requirements': [1],
             'damage_templates': {'normal': [
                 {'element': 'EARTH', 'ranges': [ranges], 'state_group': state,
                  'situation': situation}
                 for state, situation, ranges in rows]}}
    return _generator().convert_spell(spell)


def _castable(char_class, spell_id, version='dofus3'):
    from chardata.spell_combo import castable_spells
    from fashionistapulp.structure import set_current_game_version
    set_current_game_version(version)
    try:
        return next(castable for castable in castable_spells(char_class, 200, version)
                    if castable.spell_id == spell_id)
    finally:
        set_current_game_version('dofus3')


def _ranges(rows):
    return [(row.min_dam, row.max_dam) for row in rows]


def _prefix(version):
    return '' if version == 'dofus3' else version + '/'


class TheGeneratorSplitsAHitOnItsTargetTests(SimpleTestCase):

    def test_a_shield_pair_is_two_faces_with_the_plain_one_first(self):
        entry = _convert(('A,PB|76,3,0', '44-48'), ('A,pb|76,3,0', '38-42'))
        self.assertEqual([('Target without shield points', [1]),
                          ('Target with shield points', [0])],
                         entry.aggregates)

    def test_the_hp_threshold_is_the_number_the_mask_carries(self):
        entry = _convert(('a,A,v25|80,1,0', '43-48'), ('a,A,V25|80,1,0', '54-60'))
        self.assertEqual([('Target with 25% of its HP or more', [0]),
                          ('Target with less than 25% of its HP', [1])],
                         entry.aggregates)

    def test_rows_in_different_zones_are_not_faces_of_one_hit(self):
        entry = _convert(('A,pb|76,3,0', '38-42'), ('A,PB|80,1,0', '44-48'))
        self.assertFalse(entry.aggregates)

    def test_a_row_without_the_condition_leaves_the_spell_alone(self):
        entry = _convert(('A,pb|76,3,0', '38-42'), ('A|76,3,0', '44-48'))
        self.assertFalse(entry.aggregates)

    def test_one_face_alone_is_no_choice(self):
        self.assertFalse(_convert(('A,PB|76,3,0', '44-48')).aggregates)
        self.assertFalse(_convert(('a,A,V50|80,1,0', '54-60'),
                                  ('a,A,V50|80,1,0', '54-60')).aggregates)

    def test_two_thresholds_are_not_one_split(self):
        entry = _convert(('a,A,v25|80,1,0', '43-48'), ('a,A,V50|80,1,0', '54-60'))
        self.assertFalse(entry.aggregates)

    def test_states_landing_the_same_hit_split_it_into_two_faces(self):
        entry = _convert_states(
            ('e7120,e7121', 'a,A,pb,*e7120,*e7121|80,1,0', '9-11'),
            ('E7120', 'a,A,pb,*E7120|88,1,0', '9-11'),
            ('E7121', 'a,A,pb,*E7121|67,2,0', '9-11'),
            ('e7120,e7121', 'a,A,PB,*e7120,*e7121|80,1,0', '18-22'),
            ('E7120', 'a,A,PB,*E7120|88,1,0', '18-22'),
            ('E7121', 'a,A,PB,*E7121|67,2,0', '18-22'))
        self.assertEqual([('Target without shield points', [0]),
                          ('Target with shield points', [3])],
                         entry.aggregates)

    def test_inside_states_the_plain_face_still_comes_first(self):
        entry = _convert_states(
            ('e7120', 'a,A,PB,*e7120|80,1,0', '18-22'),
            ('e7120', 'a,A,pb,*e7120|80,1,0', '9-11'),
            ('E7120', 'a,A,PB,*E7120|88,1,0', '18-22'),
            ('E7120', 'a,A,pb,*E7120|88,1,0', '9-11'))
        self.assertEqual([('Target without shield points', [1]),
                          ('Target with shield points', [0])],
                         entry.aggregates)

    def test_states_without_the_condition_stay_one_group(self):
        entry = _convert_states(
            ('e7120', 'a,A,*e7120|80,1,0', '9-11'),
            ('e7120', 'a,A,*e7120|80,1,0', '18-22'),
            ('E7120', 'a,A,*E7120|88,1,0', '9-11'),
            ('E7120', 'a,A,*E7120|88,1,0', '18-22'))
        self.assertEqual([('', [0, 1])], entry.aggregates)

    def test_states_collapsing_to_two_groups_keep_both_unsplit(self):
        entry = _convert_states(
            ('e7120,e7121', 'a,A,pb,*e7120,*e7121|80,1,0', '9-11'),
            ('E7120', 'a,A,pb,*E7120|88,1,0', '9-11'),
            ('E7121', 'a,A,pb,*E7121|67,2,0', '12-14'),
            ('e7120,e7121', 'a,A,PB,*e7120,*e7121|80,1,0', '18-22'),
            ('E7120', 'a,A,PB,*E7120|88,1,0', '18-22'),
            ('E7121', 'a,A,PB,*E7121|67,2,0', '23-27'))
        self.assertEqual([('', [0, 3]), ('', [2, 5])], entry.aggregates)

    def test_groups_past_the_damage_rows_come_back_after_the_two_faces(self):
        rows = [{'element': 'EARTH', 'ranges': ['9-11'], 'situation': 'a,A,pb|80,1,0'},
                {'element': 'EARTH', 'ranges': ['18-22'], 'situation': 'a,A,PB|80,1,0'}]
        split = _generator()._split_the_one_state_on_its_target(
            rows, [('', [0, 1]), ('', [len(rows)])])
        self.assertEqual([('Target without shield points', [0]),
                          ('Target with shield points', [1]),
                          ('', [2])], split)

    def test_every_version_the_generator_accepts_has_its_own_table(self):
        generator = _generator()
        self.assertEqual(set(generator.CONDITIONAL_ROWS_BY_VERSION),
                         set(generator.TARGET_CONDITIONS_BY_VERSION))

    def test_the_dofus2_table_splits_on_hp_and_not_on_shield_points(self):
        from unittest import mock
        generator = _generator()
        with mock.patch.object(generator, 'TARGET_CONDITIONS',
                               generator.TARGET_CONDITIONS_BY_VERSION['dofus2']):
            hp = _convert(('a,A,v25|', '43-48'), ('a,A,V25|', '54-60'))
            shield = _convert(('A,PB|76,3,0', '44-48'), ('A,pb|76,3,0', '38-42'))
        self.assertEqual(_DOFUS2_HP_FACES, hp.aggregates)
        self.assertFalse(shield.aggregates)


class TheTablesCarryTheFacesTests(SimpleTestCase):

    def test_piercing_arrow_splits_on_shield_points(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell('Cra', PIERCING_ARROW, version)
                self.assertEqual([('Target without shield points', [0]),
                                  ('Target with shield points', [1])],
                                 spell.aggregates)
                top = spell.get_effects_digest().non_crit_dams[-1]
                self.assertEqual([(38, 42), (44, 48)], _ranges(top))

    def test_abolition_arrow_splits_on_shield_points_inside_its_states(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell('Cra', ABOLITION_ARROW, version)
                self.assertEqual([('Target without shield points', [0]),
                                  ('Target with shield points', [3])],
                                 spell.aggregates)
                top = spell.get_effects_digest().non_crit_dams[-1]
                self.assertEqual([(9, 11), (18, 22)], _ranges([top[0], top[3]]))

    def test_lethal_attack_splits_on_half_the_targets_hp(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell('Sram', LETHAL_ATTACK, version)
                self.assertEqual([('Target with 50% of its HP or more', [0]),
                                  ('Target with less than 50% of its HP', [1])],
                                 spell.aggregates)
                top = spell.get_effects_digest().non_crit_dams[-1]
                self.assertEqual([(43, 48), (54, 60)], _ranges(top))

    def test_dofus2_lethal_attack_splits_on_a_quarter_of_the_targets_hp(self):
        spell = _spell('Sram', LETHAL_ATTACK, 'dofus2')
        self.assertEqual(_DOFUS2_HP_FACES, spell.aggregates)
        top = spell.get_effects_digest().non_crit_dams[-1]
        self.assertEqual([(43, 48), (54, 60)], _ranges(top))


class EachSplitIsOneTheSpellTextStatesTests(SimpleTestCase):
    """A split stays only while Ankama's description, in five languages, names its condition."""

    def test_the_text_names_the_shield_or_the_hp_threshold(self):
        for version, least in (('dofus3', 2), ('beta', 2), ('dofus2', 1)):
            with open(os.path.join(_REFERENCE_DIR, '%s.json' % version),
                      encoding='utf-8') as handle:
                reference = json.load(handle)
            texts = {entry['id']: entry.get('description') or {}
                     for entries in reference.values() for entry in entries}
            checked = 0
            for char_class, spells in get_damage_spells_for_version(version).items():
                for spell in spells:
                    labels = [label for label, _indices in spell.aggregates or []
                              if label in _SHIELD_LABELS or _HP_LABEL.match(label)]
                    if not labels:
                        continue
                    checked += 1
                    description = texts.get(spell.spell_id) or {}
                    for language in LANGUAGES:
                        text = (description.get(language) or '').lower()
                        for label in labels:
                            with self.subTest(version=version, spell=spell.name,
                                              language=language, label=label):
                                match = _HP_LABEL.match(label)
                                if match:
                                    self.assertRegex(text, r'\b%s\s?%%' % match.group(1))
                                else:
                                    self.assertIn(_SHIELD_WORD[language], text)
            with self.subTest(version=version):
                self.assertGreaterEqual(checked, least)


class TheTurnCountsThePlainFaceTests(SimpleTestCase):

    def test_piercing_arrow_lands_its_hit_without_shield_points(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                castable = _castable('Cra', PIERCING_ARROW, version)
                self.assertEqual([(38, 42)], _ranges(castable.hits))
                self.assertEqual([[(46, 50)]], [_ranges(alternative) for alternative
                                                in castable.crit_alternatives])
                self.assertEqual('Target without shield points',
                                 castable.scored_group)

    def test_lethal_attack_lands_its_hit_above_half_hp(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                castable = _castable('Sram', LETHAL_ATTACK, version)
                self.assertEqual([(43, 48)], _ranges(castable.hits))
                self.assertEqual([[(52, 58)]], [_ranges(alternative) for alternative
                                                in castable.crit_alternatives])
                self.assertEqual('Target with 50% of its HP or more',
                                 castable.scored_group)

    def test_dofus2_lethal_attack_lands_its_hit_above_a_quarter_hp(self):
        castable = _castable('Sram', LETHAL_ATTACK, 'dofus2')
        self.assertEqual([(43, 48)], _ranges(castable.hits))
        self.assertEqual([[(52, 58)]], [_ranges(alternative) for alternative
                                        in castable.crit_alternatives])
        self.assertEqual('Target with 25% of its HP or more',
                         castable.scored_group)

    def test_one_dofus2_lethal_attack_is_worth_the_plain_face_and_no_more(self):
        from chardata.spell_combo import _average, best_turn, crit_chance
        from fashionistapulp.dofus_constants import calculate_damage

        def face(rows, critical):
            return _average(calculate_damage([copy.copy(row) for row in rows],
                                              _STRENGTH_STATS, critical, True))

        castable = _castable('Sram', LETHAL_ATTACK, 'dofus2')
        total, order = best_turn(_STRENGTH_STATS, [castable], castable.cost,
                                 game_version='dofus2')
        self.assertEqual(['Lethal Attack'], [name for name, _damage in order])
        odds = crit_chance(castable.crit_rate, _STRENGTH_STATS, 'dofus2')
        expected = (face(castable.plain_alternatives[0], False) * (1 - odds)
                    + face(castable.crit_alternatives[0], True) * odds)
        self.assertAlmostEqual(expected, total, places=6)
        both = face(castable.spell.get_effects_digest().non_crit_dams[-1], False)
        self.assertLess(total, both)

    def test_each_dofus2_lethal_attack_cast_is_worth_the_plain_face(self):
        from chardata.spell_combo import _average, best_turn, crit_chance
        from fashionistapulp.dofus_constants import calculate_damage

        def face(rows, critical):
            return _average(calculate_damage([copy.copy(row) for row in rows],
                                              _STRENGTH_STATS, critical, True))

        castable = _castable('Sram', LETHAL_ATTACK, 'dofus2')
        self.assertEqual(2, castable.limit)
        total, order = best_turn(_STRENGTH_STATS, [castable],
                                 castable.limit * castable.cost,
                                 game_version='dofus2')
        self.assertEqual(['Lethal Attack'] * castable.limit,
                         [name for name, _damage in order])
        odds = crit_chance(castable.crit_rate, _STRENGTH_STATS, 'dofus2')
        one = (face(castable.plain_alternatives[0], False) * (1 - odds)
               + face(castable.crit_alternatives[0], True) * odds)
        self.assertAlmostEqual(castable.limit * one, total, places=6)
        both = face(castable.spell.get_effects_digest().non_crit_dams[-1], False)
        self.assertLess(total, castable.limit * both)

    def test_abolition_arrow_lands_its_hit_without_shield_points(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                castable = _castable('Cra', ABOLITION_ARROW, version)
                self.assertEqual([(9, 11)], _ranges(castable.hits))
                self.assertEqual([[(12, 14)]], [_ranges(alternative) for alternative
                                                in castable.crit_alternatives])
                self.assertEqual('Target without shield points',
                                 castable.scored_group)

    def test_each_abolition_arrow_cast_is_worth_the_plain_face(self):
        from chardata.spell_combo import _average, best_turn, crit_chance
        from fashionistapulp.dofus_constants import calculate_damage

        def face(rows, critical):
            return _average(calculate_damage([copy.copy(row) for row in rows],
                                              _STATS, critical, True))

        for version in VERSIONS:
            with self.subTest(version=version):
                castable = _castable('Cra', ABOLITION_ARROW, version)
                self.assertEqual(3, castable.limit)
                total, order = best_turn(_STATS, [castable], 3 * castable.cost,
                                         game_version=version)
                self.assertEqual(['Abolition Arrow'] * 3,
                                 [name for name, _damage in order])
                odds = crit_chance(castable.crit_rate, _STATS, version)
                one = (face(castable.plain_alternatives[0], False) * (1 - odds)
                       + face(castable.crit_alternatives[0], True) * odds)
                self.assertAlmostEqual(3 * one, total, places=6)
                top = castable.spell.get_effects_digest().non_crit_dams[-1]
                both = face([top[0], top[3]], False)
                self.assertLess(total, 3 * both)

    def test_one_cast_is_worth_the_plain_face_and_no_more(self):
        from chardata.spell_combo import _average, best_turn, crit_chance
        from fashionistapulp.dofus_constants import calculate_damage
        castable = _castable('Cra', PIERCING_ARROW)
        total, order = best_turn(_STATS, [castable], castable.cost,
                                 game_version='dofus3')
        self.assertEqual(['Piercing Arrow'], [name for name, _damage in order])
        odds = crit_chance(castable.crit_rate, _STATS, 'dofus3')

        def face(rows, critical):
            return _average(calculate_damage([copy.copy(row) for row in rows],
                                              _STATS, critical, True))

        expected = (face(castable.plain_alternatives[0], False) * (1 - odds)
                    + face(castable.crit_alternatives[0], True) * odds)
        self.assertAlmostEqual(expected, total, places=6)
        both = face(castable.spell.get_effects_digest().non_crit_dams[-1], False)
        self.assertLess(total, both)

    def test_the_panel_note_names_the_face_it_counted(self):
        from chardata.spells_view import _cast_note
        castable = _castable('Cra', PIERCING_ARROW)
        with translation.override('fr'):
            self.assertEqual('compté sur Cible sans bouclier',
                             _cast_note(castable, castable.name, {}, 586))

    def test_the_dofus2_panel_note_names_the_quarter_hp_face(self):
        from chardata.spells_view import _cast_note
        castable = _castable('Sram', LETHAL_ATTACK, 'dofus2')
        with translation.override('fr'):
            self.assertEqual('compté sur Cible à 25% de sa vie ou plus',
                             _cast_note(castable, castable.name, {}, 768,
                                        'dofus2'))


class TheFacesSpeakEveryLanguageTests(SimpleTestCase):

    EXPECTED = {
        'en': ('Target with shield points', 'Target without shield points',
               'Target with less than 50% of its HP',
               'Target with 50% of its HP or more'),
        'fr': ('Cible avec bouclier', 'Cible sans bouclier',
               'Cible à moins de 50% de sa vie', 'Cible à 50% de sa vie ou plus'),
        'es': ('Objetivo con escudo', 'Objetivo sin escudo',
               'Objetivo con menos del 50% de su vida',
               'Objetivo con el 50% de su vida o más'),
        'pt': ('Alvo com escudo', 'Alvo sem escudo',
               'Alvo com menos de 50% da vida', 'Alvo com 50% da vida ou mais'),
        'de': ('Ziel mit Schild', 'Ziel ohne Schild',
               'Ziel mit weniger als 50 % seiner Lebenspunkte',
               'Ziel mit 50 % seiner Lebenspunkte oder mehr'),
    }

    def test_each_label_reads_natively_in_five_languages(self):
        from chardata.spells_view import _localized_aggregate_label
        labels = self.EXPECTED['en']
        for language, wanted in self.EXPECTED.items():
            with translation.override(language):
                shown = tuple(_localized_aggregate_label(label, 'dofus3')
                              for label in labels)
            with self.subTest(language=language):
                self.assertEqual(wanted, shown)

    def test_every_label_the_generator_writes_is_read_by_the_site(self):
        from chardata.spells_view import _localized_aggregate_label
        for table in _generator().TARGET_CONDITIONS_BY_VERSION.values():
            for pattern, meets, fails in table:
                for label in (meets.format('50'), fails.format('50')):
                    with self.subTest(label=label):
                        with translation.override('fr'):
                            shown = _localized_aggregate_label(label, 'dofus3')
                        self.assertNotEqual(label, shown)
                        self.assertNotIn('%%', shown)
                        self.assertLessEqual(shown.count('%'), 1)


class TheSpellsPageLabelsTheFacesTests(TestCase):

    def _build(self, version='dofus3', char_class='Cra'):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        from chardata.models import Char
        set_current_game_version(version)
        try:
            structure = get_structure(version)
            names = []
            for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
                item = next(i for i in structure.types[200][type_name]
                            if not i.removed and i.ankama_id)
                names.append(structure.get_item_name_in_language(item, 'en'))
        finally:
            set_current_game_version('dofus3')
        self.client.post('/%simport/text/' % _prefix(version), {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _aggregates(self, char, name, language, version='dofus3'):
        page = self.client.get('/%sspells/%d/' % (_prefix(version), char.id),
                               HTTP_ACCEPT_LANGUAGE=language, follow=True)
        self.assertEqual(200, page.status_code)
        found = re.search(r'var spellDigests = (.*);',
                          page.content.decode('utf-8'))
        self.assertTrue(found, 'the page carries no spell digests')
        digests = {digest.get('canonical'): digest
                   for digest in json.loads(found.group(1))}
        return digests[name]['aggregates']

    def test_the_cra_page_names_both_faces_of_abolition_arrow(self):
        for version in VERSIONS:
            char = self._build(version)
            self.assertEqual(version, char.game_version or 'dofus3')
            for language, wanted in (
                    ('en', [['Target without shield points', [0]],
                            ['Target with shield points', [3]]]),
                    ('fr', [['Cible sans bouclier', [0]],
                            ['Cible avec bouclier', [3]]])):
                with self.subTest(version=version, language=language):
                    self.assertEqual(wanted, self._aggregates(
                        char, 'Abolition Arrow', language, version))

    def test_the_dofus2_sram_page_names_both_faces_of_lethal_attack(self):
        char = self._build('dofus2', 'Sram')
        self.assertEqual(('dofus2', 'Sram'), (char.game_version, char.char_class))
        for language, wanted in (
                ('en', [['Target with 25% of its HP or more', [0]],
                        ['Target with less than 25% of its HP', [1]]]),
                ('fr', [['Cible à 25% de sa vie ou plus', [0]],
                        ['Cible à moins de 25% de sa vie', [1]]]),
                ('es', [['Objetivo con el 25% de su vida o más', [0]],
                        ['Objetivo con menos del 25% de su vida', [1]]]),
                ('pt', [['Alvo com 25% da vida ou mais', [0]],
                        ['Alvo com menos de 25% da vida', [1]]]),
                ('de', [['Ziel mit 25 % seiner Lebenspunkte oder mehr', [0]],
                        ['Ziel mit weniger als 25 % seiner Lebenspunkte', [1]]])):
            with self.subTest(language=language):
                self.assertEqual(wanted, self._aggregates(
                    char, 'Lethal Attack', language, 'dofus2'))

    def test_the_cra_page_names_both_faces_of_piercing_arrow(self):
        char = self._build()
        for language, wanted in (
                ('en', [['Target without shield points', [0]],
                        ['Target with shield points', [1]]]),
                ('fr', [['Cible sans bouclier', [0]],
                        ['Cible avec bouclier', [1]]])):
            with self.subTest(language=language):
                page = self.client.get('/spells/%d/' % char.id,
                                       HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(200, page.status_code)
                found = re.search(r'var spellDigests = (.*);',
                                  page.content.decode('utf-8'))
                self.assertTrue(found, 'the page carries no spell digests')
                digests = {digest.get('canonical'): digest
                           for digest in json.loads(found.group(1))}
                self.assertEqual(wanted, digests['Piercing Arrow']['aggregates'])
