# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A share of the caster's HP counts the build's HP alone; a life the build cannot know shows unnumbered."""
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase
from django.utils.translation import override

from chardata import default_elements
from chardata.management.commands import store_default_elements as generator
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (HpShare, best_turn, castable_spells, damage_taken_for_version,
                                  hp_share_hits_for_version)
from chardata.spells_view import _create_spell_web_digest, _hp_share_lines
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES, NEUTRAL
from fashionistapulp.structure import set_current_game_version

LEVEL = 200
AP = 12
HP = 3000
VERSIONS = ('dofus3', 'beta', 'dofus2')
RAISED = ('str', 'pow', 'dam', 'neutdam', 'perspedam', 'cridam')

TRANSFUSION = 12738
RETRIBUTION = 12741
PUNISHMENT = 12760
MASQUERADE = 13404
REPRISAL = 32472

SACRIER = {TRANSFUSION, RETRIBUTION, PUNISHMENT}
EXPECTED = {
    'dofus3': {'Cra': {REPRISAL}, 'Masqueraider': {MASQUERADE}, 'Sacrier': SACRIER},
    'beta': {'Cra': {REPRISAL}, 'Masqueraider': {MASQUERADE}, 'Sacrier': SACRIER},
    'dofus2': {'Masqueraider': {MASQUERADE}, 'Sacrier': SACRIER},
}
# {version: {spell id: (class, percent of the caster's HP at level 200)}}
COUNTED = {
    'dofus3': {TRANSFUSION: ('Sacrier', 10), PUNISHMENT: ('Sacrier', 15),
               MASQUERADE: ('Masqueraider', 25)},
    'beta': {TRANSFUSION: ('Sacrier', 10), PUNISHMENT: ('Sacrier', 15),
             MASQUERADE: ('Masqueraider', 25)},
    'dofus2': {TRANSFUSION: ('Sacrier', 10), PUNISHMENT: ('Sacrier', 20),
               MASQUERADE: ('Masqueraider', 25)},
}

DOFUS3_TEXTS = {
    'Fire damage: #1{{~1~2 to }}#2% of the caster\'s <sprite name="PV"> HP': 'caster_hp',
    'Neutral damage: #1{{~1~2 to }}#2% of the caster\'s <sprite name="erosion"> missing HP':
        'caster_missing_hp',
    'Neutral damage: #1{{~1~2 to }}#2% <sprite name="erosion"> of the middle of the '
    'caster\'s HP': 'caster_middle_hp',
    'Neutral damage: #1{{~1~2 to }}#2% of the target\'s <sprite name="PV"> HP': 'target_hp',
    'Earth damage: #1{{~1~2 to }}#2% of the target\'s <sprite name="erosion"> eroded HP':
        'target_eroded_hp',
    'Earth damage: #1{{~1~2 to }}#2% of the caster\'s <sprite name="erosion"> eroded HP':
        'caster_eroded_hp',
    'Damage: #1{{~1~2 to }}#2% of final damage suffered': None,
    '#1{{~1~2 to }}#2 Earth damage (% remaining <sprite name="PM">MP)': None,
}
DOFUS2_TEXTS = {
    "#1{~1~2 to }#2% of attacker's HP (Fire damage)": 'caster_hp',
    "#1{~1~2 to }#2% of attacker's missing HP (Neutral damage)": 'caster_missing_hp',
    "#1{~1~2 to }#2% of the target's eroded HP inflicted as Earth damage": 'target_eroded_hp',
    "#1{~1~2 to }#2% of the caster's eroded HP inflicted as Earth damage": 'caster_eroded_hp',
}
CASTER_HP_TEXT = {'en': "Neutral damage: #1{{~1~2 to }}#2% of the caster's HP",
                  'fr': 'Dommages Neutre : #1{{~1~2 à }}#2% PV du lanceur'}
MISSING_HP_TEXT = {'en': "Neutral damage: #1{{~1~2 to }}#2% of the caster's missing HP"}
FIRE_TEXT = {'en': '#1{{~1~2 to }}#2 Fire damage'}


def _in(test, version):
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _stats(version, char_class, hp, element='str'):
    gear = default_elements.default_elements_table(version)['gear'][str(LEVEL)]
    stats = generator.reference_stats(version, char_class, element, gear, AP, LEVEL)
    stats['hp'] = hp
    return stats


def _castable(version, char_class, spell_id):
    return next(spell for spell in castable_spells(char_class, LEVEL, version)
                if spell.spell_id == spell_id)


def _alone(version, spell, stats):
    return best_turn(stats, [spell], spell.cost, game_version=version, caster_level=LEVEL)[0]


def _table_spell(version, char_class, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)[char_class]
                if spell.spell_id == spell_id)


def _scraper(name):
    from chardata.tests import itemscraper_module
    return itemscraper_module(name)


def _effect(text, mask='A', minimum=25, maximum=0, element=0, uid=1, delay=0, triggers='I',
            effect_id=89, flags=79):
    return {'effect_uid': uid, 'effect_id': effect_id, 'order': uid, 'target_mask': mask,
            'triggers': triggers, 'dice': {'min': minimum, 'max': maximum},
            'effect_trigger_duration': 0, 'duration': 0, 'delay': delay, 'random': 0,
            'flags': flags, 'effect_element': element, 'value': 0, 'zone': None,
            'effect_metadata': {'category': 2, 'description': dict(text)}}


def _casting(effect_id, spell_id, mask='A', triggers='I', delay=0, uid=9):
    """A row casting or placing spell_id at grade 1."""
    return {'effect_uid': uid, 'effect_id': effect_id, 'order': uid, 'target_mask': mask,
            'triggers': triggers, 'dice': {'min': spell_id, 'max': 1},
            'effect_trigger_duration': 0, 'duration': 0, 'delay': delay, 'random': 0,
            'flags': 8, 'effect_element': 0, 'value': 0, 'zone': None,
            'effect_metadata': {'category': 0, 'description': {'en': '#1'}}}


def _spell(effects, critical_effects=None, spell_id=50):
    level = {'grade': 1, 'ap_cost': 3, 'max_cast_per_turn': 1, 'critical_hit_probability': 0,
             'max_stack': 1, 'effects': effects,
             'critical_effects': critical_effects if critical_effects is not None else []}
    return {'ankama_id': spell_id, 'name_en': 'Spell %d' % spell_id,
            'level_requirements': [200], 'levels': [level]}


class TheClientTextNamesWhoseLifeTests(SimpleTestCase):

    def test_each_client_text_gives_its_share_or_none(self):
        hp_share_of = _scraper('get_spells').hp_share_of
        for version, texts in (('dofus3', DOFUS3_TEXTS), ('dofus2', DOFUS2_TEXTS)):
            for text, kind in texts.items():
                with self.subTest(version=version, text=text):
                    self.assertEqual(kind, hp_share_of(
                        {'category': 2, 'description': {'en': text}}))

    def test_672_reads_the_middle_of_the_casters_hp_where_the_2_73_text_reads_like_89(self):
        hp_share_of = _scraper('get_spells').hp_share_of
        dofus2 = {'category': 2,
                  'description': {'en': "#1{~1~2 to }#2% of attacker's HP (Neutral damage)"}}
        self.assertEqual('caster_middle_hp', hp_share_of(dofus2, 672))
        self.assertEqual('caster_hp', hp_share_of(dofus2, 89))
        self.assertEqual('caster_missing_hp', hp_share_of(
            {'category': 2, 'description': dict(MISSING_HP_TEXT)}, 672))

    def test_an_effect_id_reads_one_share_in_every_pinned_client(self):
        import fashionista_version as ours
        from fashionistapulp.fashionista_config import get_fashionista_path
        reader = _scraper('get_spells')
        kinds = {}
        read = 0
        for tag in (ours.FASHIONISTA_VERSION, ours.FASHIONISTA_BETA_VERSION,
                    ours.FASHIONISTA_DOFUS2_VERSION):
            directory = Path(get_fashionista_path()) / 'itemscraper' / 'raw' / tag
            if not (directory / 'effects.json').exists():
                continue
            read += 1
            texts = reader._load_translations(directory, ('en',))['en']
            for effect_id, effect in reader._load_datacenter_table(
                    directory / 'effects.json').items():
                metadata = {'category': effect.get('category'),
                            'description': {'en': texts.get(str(effect.get('descriptionId')))}}
                kind = reader.hp_share_of(metadata, int(effect_id))
                if kind:
                    kinds.setdefault(int(effect_id), set()).add(kind)
                if int(effect_id) == 672 and tag != ours.FASHIONISTA_DOFUS2_VERSION:
                    with self.subTest(tag=tag):
                        self.assertEqual('caster_middle_hp', reader.hp_share_of(metadata))
        if not read:
            self.skipTest('no client archive on this machine')
        self.assertEqual({}, {effect_id: found for effect_id, found in kinds.items()
                              if len(found) > 1})
        self.assertEqual({'caster_middle_hp'}, kinds.get(672))

    def test_a_text_outside_the_damage_category_is_no_share(self):
        self.assertIsNone(_scraper('get_spells').hp_share_of(
            {'category': 1, 'description': dict(CASTER_HP_TEXT)}))

    def test_the_scaled_rows_leave_the_share_out(self):
        reader = _scraper('get_spells')
        transformer = object.__new__(reader.SpellTransformer)
        fire = _effect(FIRE_TEXT, minimum=30, maximum=34, element=2, uid=2)
        rows = transformer._collect_damage_rows(
            [{'effects': [_effect(CASTER_HP_TEXT), fire], 'critical_effects': []}], False)
        self.assertEqual(1, len(rows))
        self.assertEqual('FIRE', rows[0]['element'])


class TheGeneratorReadsTheShareTests(SimpleTestCase):

    def test_a_gate_on_the_casters_life_is_read_with_the_percent_and_text(self):
        entry = _scraper('generate_damage_spells').hp_share_entry(_spell([
            _effect(CASTER_HP_TEXT, mask='A,*v50', uid=1),
            _effect(MISSING_HP_TEXT, mask='A,*V50', uid=2)]))
        self.assertIsNone(entry['critical'])
        self.assertEqual(
            [('caster_hp', 'NEUTRAL', ['caster_at_least', 50], ['25']),
             ('caster_missing_hp', 'NEUTRAL', ['caster_below', 50], ['25'])],
            [(row['of'], row['element'], row['gate'], row['percent'])
             for row in entry['normal']])
        self.assertEqual({'en': "Neutral damage: 25% of the caster's HP",
                          'fr': 'Dommages Neutre : 25% PV du lanceur'},
                         entry['normal'][0]['text'][0])

    def test_a_share_on_allies_only_is_not_read(self):
        self.assertIsNone(_scraper('generate_damage_spells').hp_share_entry(
            _spell([_effect(CASTER_HP_TEXT, mask='a')])))

    def test_a_share_landing_later_stops_the_generator(self):
        generate = _scraper('generate_damage_spells')
        for effect in (_effect(CASTER_HP_TEXT, delay=1), _effect(CASTER_HP_TEXT, triggers='DR')):
            with self.subTest(effect=effect['triggers']):
                with self.assertRaises(RuntimeError):
                    generate.hp_share_entry(_spell([effect]))

    def test_a_gate_no_rule_reads_stops_the_generator(self):
        with self.assertRaises(RuntimeError):
            _scraper('generate_damage_spells').hp_share_entry(
                _spell([_effect(CASTER_HP_TEXT, mask='A,*E3360')]))


class TheGeneratorReadsTheShareASpellCastsTests(SimpleTestCase):

    def test_tooltip_rows_matching_the_share_the_cast_spell_deals_are_read(self):
        child = _spell([_effect(CASTER_HP_TEXT, mask='g,A,*v50', flags=15)], spell_id=60)
        parent = _spell([_effect(CASTER_HP_TEXT, mask='g,A,*v50', flags=31),
                         _casting(1160, 60, mask='g,A')])
        entry = _scraper('generate_damage_spells').hp_share_entry(parent, {60: child})
        self.assertEqual([('caster_hp', ['caster_at_least', 50], ['25'])],
                         [(row['of'], row['gate'], row['percent']) for row in entry['normal']])

    def test_tooltip_rows_the_cast_spells_do_not_deal_stop_the_generator(self):
        generate = _scraper('generate_damage_spells')
        parent = _spell([_effect(CASTER_HP_TEXT, flags=31), _casting(1160, 60)])
        for lookup in ({}, {60: _spell([_effect(CASTER_HP_TEXT, minimum=30, flags=15)],
                                       spell_id=60)}):
            with self.subTest(cast=sorted(lookup)):
                with self.assertRaises(RuntimeError):
                    generate.hp_share_entry(parent, lookup)

    def test_a_share_in_a_trap_glyph_or_bomb_stops_the_generator(self):
        generate = _scraper('generate_damage_spells')
        lookup = {60: _spell([_effect(CASTER_HP_TEXT)], spell_id=60)}
        for placing, target in ((400, 60), (401, 60), (1008, 900)):
            with self.subTest(effect_id=placing):
                with mock.patch.object(generate, 'BOMB_SPELLS', {900: 60}):
                    with self.assertRaises(RuntimeError):
                        generate.hp_share_entry(_spell([_casting(placing, target)]), lookup)

    def test_a_share_in_a_spell_cast_later_or_behind_a_gate_stops_the_generator(self):
        generate = _scraper('generate_damage_spells')
        lookup = {60: _spell([_effect(CASTER_HP_TEXT)], spell_id=60)}
        for cast in (_casting(792, 60, triggers='DR'), _casting(1160, 60, delay=1),
                     _casting(2960, 60, mask='A,*E3360')):
            with self.subTest(effect_id=cast['effect_id']):
                with self.assertRaises(RuntimeError):
                    generate.hp_share_entry(_spell([cast]), lookup)

    def test_a_placed_or_cast_spell_without_a_share_leaves_the_spell_without_one(self):
        generate = _scraper('generate_damage_spells')
        lookup = {60: _spell([_effect(FIRE_TEXT, minimum=30, maximum=34, element=2)],
                             spell_id=60)}
        for placing in (400, 1160):
            with self.subTest(effect_id=placing):
                self.assertIsNone(generate.hp_share_entry(
                    _spell([_casting(placing, 60)]), lookup))


class EachVersionListsTheseSpellsTests(SimpleTestCase):

    def test_each_version_lists_these_spells_and_no_other(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(EXPECTED[version], {
                    char_class: set(by_id)
                    for char_class, by_id in hp_share_hits_for_version(version).items()})

    def test_retro_and_touch_list_none(self):
        for version in ('retro', 'touch'):
            with self.subTest(version=version):
                self.assertEqual({}, hp_share_hits_for_version(version))

    def test_their_scaled_rows_keep_no_neutral_share(self):
        for version in VERSIONS:
            _in(self, version)
            for char_class, spell_ids in EXPECTED[version].items():
                for spell_id in spell_ids:
                    with self.subTest(version=version, spell_id=spell_id):
                        spell = _table_spell(version, char_class, spell_id)
                        self.assertNotIn(NEUTRAL, spell.effects.elements)

    def test_retribution_keeps_its_hit_in_the_best_element(self):
        for version in VERSIONS:
            _in(self, version)
            with self.subTest(version=version):
                spell = _table_spell(version, 'Sacrier', RETRIBUTION)
                self.assertEqual(4, len(spell.effects.elements))
                self.assertEqual('Hit in best element', spell.aggregates[0][0])


class TheTurnCountsTheBuildsHpTests(SimpleTestCase):

    def test_transfusion_punishment_and_masquerade_deal_their_share_of_the_builds_hp(self):
        for version in VERSIONS:
            _in(self, version)
            for spell_id, (char_class, percent) in COUNTED[version].items():
                with self.subTest(version=version, spell_id=spell_id):
                    spell = _castable(version, char_class, spell_id)
                    self.assertEqual(0.0, _alone(version, spell, _stats(version, char_class, 0)))
                    self.assertEqual(HP * percent // 100,
                                     _alone(version, spell, _stats(version, char_class, HP)))
                    self.assertEqual(2 * HP * percent // 100, _alone(
                        version, spell, _stats(version, char_class, 2 * HP)))

    def test_characteristics_power_and_damage_never_raise_the_share(self):
        for version in VERSIONS:
            _in(self, version)
            for spell_id, (char_class, percent) in COUNTED[version].items():
                with self.subTest(version=version, spell_id=spell_id):
                    spell = _castable(version, char_class, spell_id)
                    stats = _stats(version, char_class, HP)
                    for key in RAISED:
                        stats[key] = (stats.get(key) or 0) + 500
                    self.assertEqual(HP * percent // 100, _alone(version, spell, stats))

    def test_masquerade_counts_the_face_of_a_caster_at_full_hp_only(self):
        for version in VERSIONS:
            _in(self, version)
            with self.subTest(version=version):
                spell = _castable(version, 'Masqueraider', MASQUERADE)
                self.assertEqual([[HpShare]], [[type(row) for row in alternative]
                                               for alternative in spell.plain_alternatives])

    def test_retribution_leaves_the_turn_where_the_hp_puts_it(self):
        for version in VERSIONS:
            _in(self, version)
            with self.subTest(version=version):
                spell = _castable(version, 'Sacrier', RETRIBUTION)
                self.assertFalse([row for alternative in spell.plain_alternatives
                                  + spell.crit_alternatives for row in alternative
                                  if isinstance(row, HpShare)])
                self.assertEqual(_alone(version, spell, _stats(version, 'Sacrier', 0)),
                                 _alone(version, spell, _stats(version, 'Sacrier', HP)))

    def test_reprisal_without_its_damage_taken_leaves_the_turn(self):
        for version in ('dofus3', 'beta'):
            _in(self, version)
            with self.subTest(version=version):
                self.assertEqual({'target_eroded_hp'}, {
                    row['of'] for row in hp_share_hits_for_version(version)['Cra'][REPRISAL]
                    ['normal']})
                self.assertEqual([], _table_spell(version, 'Cra', REPRISAL).effects.elements)
                self.assertNotIn(REPRISAL, [entry['spell_id'] for entry
                                            in damage_taken_for_version(version)['Cra']])
                self.assertNotIn(REPRISAL, [spell.spell_id for spell
                                            in castable_spells('Cra', LEVEL, version)])


class AClassWithoutThemTests(SimpleTestCase):

    def test_no_other_class_casts_a_share_of_hp(self):
        for version in VERSIONS:
            _in(self, version)
            for char_class in filter_classes_for_version(CHARACTER_CLASSES, version):
                if char_class in EXPECTED[version]:
                    continue
                with self.subTest(version=version, char_class=char_class):
                    self.assertFalse([
                        spell.name for spell in castable_spells(char_class, LEVEL, version)
                        if spell.hp_share or any(
                            isinstance(row, HpShare)
                            for alternative in spell.plain_alternatives
                            + spell.crit_alternatives for row in alternative)])

    def test_the_hp_never_moves_the_turn_of_an_iop(self):
        for version in VERSIONS:
            _in(self, version)
            with self.subTest(version=version):
                spells = castable_spells('Iop', LEVEL, version)
                turns = [best_turn(_stats(version, 'Iop', hp), spells, AP,
                                   game_version=version, caster_level=LEVEL)
                         for hp in (0, HP)]
                self.assertEqual(turns[0], turns[1])


class TheSpellPageShowsAnkamasLineTests(SimpleTestCase):

    def test_transfusion_shows_its_line_and_its_share_in_french(self):
        _in(self, 'dofus3')
        entry = hp_share_hits_for_version('dofus3')['Sacrier'][TRANSFUSION]
        with override('fr'):
            digest = _create_spell_web_digest(_table_spell('dofus3', 'Sacrier', TRANSFUSION),
                                              'dofus3', LEVEL, hp_share=entry)
        self.assertEqual([{'text': 'Dommages Neutre : 10% PV du lanceur', 'element': NEUTRAL,
                           'percent': [10, 10], 'counted': True, 'gated': False}],
                         digest['hp_share']['normal'][2])
        self.assertIsNone(digest['hp_share']['critical'])

    def test_masquerade_shows_both_faces_and_counts_the_full_hp_one(self):
        _in(self, 'dofus3')
        entry = hp_share_hits_for_version('dofus3')['Masqueraider'][MASQUERADE]
        with override('en'):
            digest = _create_spell_web_digest(
                _table_spell('dofus3', 'Masqueraider', MASQUERADE), 'dofus3', LEVEL,
                hp_share=entry)
        self.assertEqual(
            [("Neutral damage: 25% of the caster's HP", True, True),
             ("Neutral damage: 25% of the caster's missing HP", False, True)],
            [(line['text'], line['counted'], line['gated'])
             for line in digest['hp_share']['normal'][0]])

    def test_the_turn_panel_counts_one_line_and_names_the_other(self):
        cases = (('dofus3', 'Sacrier', TRANSFUSION, 'de',
                  (['Neutralschaden: 10 % der LP des Zaubernden'], [])),
                 ('dofus3', 'Masqueraider', MASQUERADE, 'en',
                  (["Neutral damage: 25% of the caster's HP"], [])),
                 ('dofus2', 'Sacrier', RETRIBUTION, 'en',
                  ([], ["35% of the caster's eroded HP inflicted as Neutral damage"])),
                 ('dofus3', 'Sacrier', RETRIBUTION, 'es',
                  ([], ['Daños neutrales: 35% PdV erosionados del lanzador'])))
        for version, char_class, spell_id, language, expected in cases:
            _in(self, version)
            with self.subTest(version=version, spell_id=spell_id):
                self.assertEqual(expected, _hp_share_lines(
                    _castable(version, char_class, spell_id), language))
