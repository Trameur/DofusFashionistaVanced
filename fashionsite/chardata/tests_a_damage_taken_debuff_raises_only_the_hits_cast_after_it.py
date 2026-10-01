# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell raising the damage its target takes raises, in the best turn, only the hits cast after it."""
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

from chardata import default_elements
from chardata.management.commands import store_default_elements as generator
from chardata.spell_combo import (best_turn, castable_spells, crit_chance,
                                  damage_taken_by_cast, damage_taken_for_version)
from chardata.spell_variants import variant_of
from chardata.spells_view import _localized_spell_name, _taken_notes
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import set_current_game_version

LEVEL = 200
AP = 12
VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

PIERCING_SHOT = 32471
REPRISAL = 32472
VENDETTA = 32473
VOLCANO = 13718
JUMP = 13107
MASSACRE = 13112
SNAKE_BITE = 31112
VENISON = 13786
DECIMATION = 12731
CUT_THROAT = 12935
HOT_IRON = 23756
TOUCH_JUMP = 8113
VULNERABILITY = 7037
MUMMIFICATION = 7983

# {version: {(class, spell id): (percent, stack cap, ends on the next hit)}} at level 200
EXPECTED = {
    'dofus3': {('Cra', PIERCING_SHOT): (115, 1, True), ('Cra', REPRISAL): (110, 1, False),
               ('Huppermage', VOLCANO): (104, 1, False), ('Iop', JUMP): (115, 1, False),
               ('Iop', MASSACRE): (115, 1, False), ('Osamodas', SNAKE_BITE): (104, 1, False),
               ('Ouginak', VENISON): (107, 1, False), ('Sacrier', DECIMATION): (103, 2, False),
               ('Sram', CUT_THROAT): (110, 1, False),
               ('Forgelance', HOT_IRON): (107, 1, False)},
    'beta': {('Cra', PIERCING_SHOT): (115, 1, True),
             ('Huppermage', VOLCANO): (104, 1, False), ('Iop', JUMP): (115, 1, False),
             ('Iop', MASSACRE): (115, 1, False), ('Osamodas', SNAKE_BITE): (104, 1, False),
             ('Ouginak', VENISON): (107, 1, False), ('Sacrier', DECIMATION): (103, 2, False),
             ('Sram', CUT_THROAT): (110, 1, False),
             ('Forgelance', HOT_IRON): (107, 1, False)},
    'dofus2': {('Iop', MASSACRE): (115, 1, False), ('Iop', JUMP): (110, 1, False),
               ('Ouginak', VENISON): (107, 1, False), ('Sacrier', DECIMATION): (103, 2, False)},
    'touch': {('Iop', TOUCH_JUMP): (110, 1, False), ('Pandawa', VULNERABILITY): (115, 2, False)},
    'retro': {},
}
# {(class, spell id): percent on a critical hit} at level 200, where it differs
EXPECTED_CRITICAL = {'touch': {('Iop', TOUCH_JUMP): 115, ('Pandawa', VULNERABILITY): 117}}


def _in(test, version):
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _stats(version, char_class, element='str'):
    gear = default_elements.default_elements_table(version)['gear'][str(LEVEL)]
    return generator.reference_stats(version, char_class, element, gear, AP, LEVEL)


def _castables(version, char_class):
    return castable_spells(char_class, LEVEL, version)


def _by_id(spells, spell_id):
    return next(spell for spell in spells if spell.spell_id == spell_id)


def _one_row_hits(spell):
    return all(len([row for row in alternative if row.min_dam or row.max_dam]) == 1
               for alternative in spell.plain_alternatives + spell.crit_alternatives)


def _probes(version, spells, debuff, stats):
    """The class's plain one-hit spells besides debuff, best alone first."""
    found = [spell for spell in spells
             if spell is not debuff and spell.hits and not spell.buffs and spell.taken is None
             and not spell.late_by_effect and _one_row_hits(spell)
             and (variant_of(version, spell.spell_id) is None
                  or variant_of(version, spell.spell_id) != variant_of(version, debuff.spell_id))]
    return sorted(found, key=lambda spell: -_alone(version, stats, spell))


def _alone(version, stats, spell):
    return best_turn(stats, [spell], spell.cost, game_version=version, caster_level=LEVEL)[0]


class EveryDebuffIsReadTests(SimpleTestCase):

    def test_each_version_attaches_these_debuffs_and_no_other(self):
        for version in VERSIONS:
            _in(self, version)
            found = {}
            for char_class in filter_classes_for_version(CHARACTER_CLASSES, version):
                for spell in _castables(version, char_class):
                    if spell.taken is not None:
                        found[(char_class, spell.spell_id)] = (
                            spell.taken.percent, spell.taken.stacks, spell.taken.ends_on_hit)
            with self.subTest(version=version):
                self.assertEqual(EXPECTED[version], found)

    def test_only_touch_puts_another_percent_on_a_critical_hit(self):
        for version in VERSIONS:
            _in(self, version)
            found = {}
            for char_class in filter_classes_for_version(CHARACTER_CLASSES, version):
                for spell in _castables(version, char_class):
                    if spell.taken is not None and spell.taken.critical != spell.taken.percent:
                        found[(char_class, spell.spell_id)] = spell.taken.critical
            with self.subTest(version=version):
                self.assertEqual(EXPECTED_CRITICAL.get(version, {}), found)

    def test_mummification_lowers_what_its_caster_takes_and_is_not_read(self):
        _in(self, 'touch')
        mummification = _by_id(_castables('touch', 'Xelor'), MUMMIFICATION)
        self.assertIsNone(mummification.taken)
        self.assertNotIn(MUMMIFICATION, [entry['spell_id'] for entries
                                         in damage_taken_for_version('touch').values()
                                         for entry in entries])


class APlacedDebuffWaitsWithItsHitTests(SimpleTestCase):

    def test_vendetta_puts_its_debuff_on_a_trap_whose_hit_the_turn_leaves_out(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        _in(self, 'beta')
        entry = next(entry for entry in damage_taken_for_version('beta')['Cra']
                     if entry['spell_id'] == VENDETTA)
        self.assertEqual(['trap'], entry['placed'])
        vendetta = next(spell for spell in get_damage_spells_for_version('beta')['Cra']
                        if spell.spell_id == VENDETTA)
        self.assertEqual({'trap'}, set(vendetta.conditional.values()))
        self.assertNotIn(VENDETTA, [spell.spell_id for spell in _castables('beta', 'Cra')])

    def test_a_debuff_on_any_placed_thing_attaches_nothing(self):
        from chardata.spell_combo import _damage_taken_at
        for when in ('trap', 'glyph', 'aura', 'bomb', 'state', 'turn_begin', 'turn_end'):
            with self.subTest(when=when):
                entry = {'levels': [200], 'percent': [110], 'stacks': [1], 'placed': [when]}
                self.assertIsNone(_damage_taken_at(entry, [200], 0))
                entry['placed'] = [None]
                self.assertEqual(110, _damage_taken_at(entry, [200], 0).percent)


class TheDebuffRaisesTheNextHitsTests(SimpleTestCase):

    def _then_a_hit(self, version, char_class, spell_id, factor):
        _in(self, version)
        stats = _stats(version, char_class)
        spells = _castables(version, char_class)
        debuff = _by_id(spells, spell_id)
        probe = _probes(version, spells, debuff, stats)[0]
        total, order = best_turn(stats, [debuff, probe], debuff.cost + probe.cost,
                                 game_version=version, caster_level=LEVEL)
        self.assertEqual([debuff.name, probe.name], [name for name, _damage in order])
        own = _alone(version, stats, debuff) if debuff.hits else 0.0
        self.assertAlmostEqual(own + _alone(version, stats, probe) * factor, total, places=6)
        return stats, spells, debuff, probe

    def test_an_iop_hit_cast_before_jump_is_not_raised(self):
        stats, spells, debuff, probe = self._then_a_hit('beta', 'Iop', JUMP, 1.15)
        self.assertEqual([[], []], damage_taken_by_cast(
            spells, [(probe.name, 0.0), (debuff.name, 0.0)]))
        self.assertEqual([[], [(debuff, 1)]], damage_taken_by_cast(
            spells, [(debuff.name, 0.0), (probe.name, 0.0)]))

    def test_reprisal_then_a_cra_hit_deals_ten_percent_more_on_dofus3(self):
        self._then_a_hit('dofus3', 'Cra', REPRISAL, 1.10)

    def test_piercing_shot_raises_the_next_hit_only(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                stats, spells, debuff, _probe = self._then_a_hit(version, 'Cra', PIERCING_SHOT,
                                                                 1.15)
                twice = next(spell for spell in _probes(version, spells, debuff, stats)
                             if not spell.limit or spell.limit >= 2)
                total, order = best_turn(stats, [debuff, twice], debuff.cost + 2 * twice.cost,
                                         game_version=version, caster_level=LEVEL)
                self.assertEqual([debuff.name, twice.name, twice.name],
                                 [name for name, _damage in order])
                alone = _alone(version, stats, twice)
                self.assertAlmostEqual(alone * 1.15 + alone, total, places=6)
                self.assertEqual([[], [(debuff, 1)], []], damage_taken_by_cast(spells, order))

    def test_cut_throat_raises_the_next_cast_and_not_its_own_hit(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                _in(self, version)
                stats = _stats(version, 'Sram', 'int')
                debuff = _by_id(_castables(version, 'Sram'), CUT_THROAT)
                total, _order = best_turn(stats, [debuff], 2 * debuff.cost,
                                          game_version=version, caster_level=LEVEL)
                alone = _alone(version, stats, debuff)
                self.assertAlmostEqual(alone + alone * 1.10, total, places=6)

    def test_decimation_stacks_twice_on_the_hit_after_both(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            with self.subTest(version=version):
                _in(self, version)
                stats = _stats(version, 'Sacrier')
                spells = _castables(version, 'Sacrier')
                debuff = _by_id(spells, DECIMATION)
                probe = _probes(version, spells, debuff, stats)[0]
                total, order = best_turn(stats, [debuff, probe], 2 * debuff.cost + probe.cost,
                                         game_version=version, caster_level=LEVEL)
                self.assertEqual([debuff.name, debuff.name, probe.name],
                                 [name for name, _damage in order])
                own = _alone(version, stats, debuff)
                self.assertAlmostEqual(own + own * 1.03 + _alone(version, stats, probe) * 1.03 ** 2,
                                       total, places=6)

    def test_jump_then_an_iop_hit(self):
        for version, factor in (('dofus3', 1.15), ('beta', 1.15), ('dofus2', 1.10)):
            with self.subTest(version=version):
                self._then_a_hit(version, 'Iop', JUMP, factor)

    def test_massacre_then_an_iop_hit_and_with_jump_both_apply(self):
        for version, jump in (('dofus3', 1.15), ('beta', 1.15), ('dofus2', 1.10)):
            with self.subTest(version=version):
                stats, spells, massacre, probe = self._then_a_hit(version, 'Iop', MASSACRE, 1.15)
                leap = _by_id(spells, JUMP)
                total, _order = best_turn(stats, [massacre, leap, probe],
                                          massacre.cost + leap.cost + probe.cost,
                                          game_version=version, caster_level=LEVEL)
                self.assertAlmostEqual(_alone(version, stats, probe) * 1.15 * jump, total,
                                       places=6)

    def test_volcano_then_a_huppermage_hit(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self._then_a_hit(version, 'Huppermage', VOLCANO, 1.04)

    def test_snake_bite_then_an_osamodas_hit_leaves_its_poison_as_it_was(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self._then_a_hit(version, 'Osamodas', SNAKE_BITE, 1.04)

    def test_venison_then_an_ouginak_hit(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            with self.subTest(version=version):
                self._then_a_hit(version, 'Ouginak', VENISON, 1.07)

    def test_hot_iron_then_a_forgelance_hit_and_not_its_own_hit(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                _stats, _spells, debuff, _probe = self._then_a_hit(version, 'Forgelance',
                                                                   HOT_IRON, 1.07)
                self.assertTrue(debuff.hits)


class TouchWeighsTheCriticalPercentAtTheCritOddsTests(SimpleTestCase):

    def _pair(self, char_class, spell_id, crit=False):
        _in(self, 'touch')
        stats = _stats('touch', char_class)
        spells = castable_spells(char_class, LEVEL, 'touch', crit=crit)
        debuff = _by_id(spells, spell_id)
        probe = next(spell for spell in _probes('touch', _castables('touch', char_class),
                                                debuff, stats)
                     if spell.limit == 1 or spell.cost > debuff.cost)
        probe = _by_id(spells, probe.spell_id)
        return stats, debuff, probe

    def _then_a_hit(self, char_class, spell_id, normal, critical):
        stats, debuff, probe = self._pair(char_class, spell_id)
        total, order = best_turn(stats, [debuff, probe], debuff.cost + probe.cost,
                                 game_version='touch', caster_level=LEVEL)
        self.assertEqual([debuff.name, probe.name], [name for name, _damage in order])
        odds = crit_chance(debuff.crit_rate, stats, 'touch')
        self.assertGreater(odds, 0)
        self.assertAlmostEqual(_alone('touch', stats, probe)
                               * ((1 - odds) * normal + odds * critical), total, places=6)

    def test_vulnerability_then_a_pandawa_hit(self):
        self._then_a_hit('Pandawa', VULNERABILITY, 1.15, 1.17)

    def test_jump_then_an_iop_hit(self):
        self._then_a_hit('Iop', TOUCH_JUMP, 1.10, 1.15)

    def test_a_critical_turn_takes_the_critical_percent(self):
        stats, debuff, probe = self._pair('Pandawa', VULNERABILITY, crit=True)
        total, _order = best_turn(stats, [debuff, probe], debuff.cost + probe.cost, crit=True,
                                  game_version='touch', caster_level=LEVEL)
        alone = best_turn(stats, [probe], probe.cost, crit=True, game_version='touch',
                          caster_level=LEVEL)[0]
        self.assertAlmostEqual(alone * 1.17, total, places=6)

    def test_a_rank_sharing_its_required_level_reads_its_own_percent(self):
        _in(self, 'touch')
        found = {}
        for level in (50, 200):
            taken = _by_id(castable_spells('Pandawa', level, 'touch'), VULNERABILITY).taken
            found[level] = (taken.percent, taken.critical)
        self.assertEqual({50: (112, 114), 200: (115, 117)}, found)

    def test_the_cast_says_both_percents_and_the_hit_names_the_spell(self):
        _in(self, 'touch')
        stats = _stats('touch', 'Pandawa')
        debuff = _by_id(_castables('touch', 'Pandawa'), VULNERABILITY)
        self.assertEqual(['Dommages subis x115%', 'Dommages subis x117% (Coup critique)'],
                         _taken_notes(debuff, [], 'fr', 'touch', stats))
        self.assertEqual(['x115% damage sustained', 'x117% damage sustained (Critical hit)'],
                         _taken_notes(debuff, [], 'en', 'touch', stats))
        self.assertEqual('Salto', _localized_spell_name('Bond', 'es', 'touch', TOUCH_JUMP))

    def test_the_hit_says_the_percent_the_turn_multiplied_it_by(self):
        stats, debuff, probe = self._pair('Pandawa', VULNERABILITY)
        total, _order = best_turn(stats, [debuff, probe], debuff.cost + probe.cost,
                                  game_version='touch', caster_level=LEVEL)
        applied = '%.1f' % (100 * total / _alone('touch', stats, probe))
        self.assertNotIn(applied, ('115.0', '117.0'))
        self.assertEqual(['x%s%% damage sustained (Vulnerability)' % applied],
                         _taken_notes(probe, [(debuff, 1)], 'en', 'touch', stats))
        self.assertEqual(['Daños sufridos x%s%% (Vulnerabilidad)' % applied.replace('.', ',')],
                         _taken_notes(probe, [(debuff, 1)], 'es', 'touch', stats))


class AClassWithoutADebuffTurnsAsBeforeTests(SimpleTestCase):

    def test_every_class_without_one_keeps_its_turn_to_the_last_decimal(self):
        for version in VERSIONS:
            _in(self, version)
            with_debuff = {char_class for char_class, _spell_id in EXPECTED[version]}
            for char_class in filter_classes_for_version(CHARACTER_CLASSES, version):
                if char_class in with_debuff:
                    continue
                with self.subTest(version=version, char_class=char_class):
                    stats = _stats(version, char_class)
                    now = best_turn(stats, _castables(version, char_class), AP,
                                    game_version=version, caster_level=LEVEL)
                    with mock.patch('chardata.spell_combo.damage_taken_for_version',
                                    return_value={}):
                        before = best_turn(stats, _castables(version, char_class), AP,
                                           game_version=version, caster_level=LEVEL)
                    self.assertEqual(before, now)

    def test_the_same_switch_changes_a_class_with_one(self):
        _in(self, 'beta')
        stats = _stats('beta', 'Iop', 'agi')
        now = best_turn(stats, _castables('beta', 'Iop'), AP, game_version='beta',
                        caster_level=LEVEL)
        with mock.patch('chardata.spell_combo.damage_taken_for_version', return_value={}):
            before = best_turn(stats, _castables('beta', 'Iop'), AP, game_version='beta',
                               caster_level=LEVEL)
        self.assertGreater(now[0], before[0])


class ThePanelNamesTheDebuffTests(SimpleTestCase):

    def test_the_debuff_cast_and_the_hit_it_raises_say_it_in_ankama_words(self):
        _in(self, 'dofus3')
        spells = _castables('dofus3', 'Cra')
        reprisal = _by_id(spells, REPRISAL)
        self.assertEqual(['Dommages subis x110%'], _taken_notes(reprisal, [], 'fr', 'dofus3', {}))
        probe = next(spell for spell in spells if spell.hits and spell.taken is None)
        self.assertEqual(['x110% damage sustained (Reprisal)'],
                         _taken_notes(probe, [(reprisal, 1)], 'en', 'dofus3', {}))

    def test_spanish_and_portuguese_get_their_own_line_and_spell_name(self):
        _in(self, 'beta')
        spells = _castables('beta', 'Sacrier')
        decimation = _by_id(spells, DECIMATION)
        probe = next(spell for spell in spells if spell.hits and spell.taken is None)
        self.assertEqual(['Daños sufridos x103% (Aniquilamiento)'],
                         _taken_notes(probe, [(decimation, 1)], 'es', 'beta', {}))
        self.assertEqual(['Danos sofridos x103% (Dizimação)'],
                         _taken_notes(probe, [(decimation, 1)], 'pt', 'beta', {}))

    def test_two_stacks_show_the_multiplier_they_make(self):
        _in(self, 'beta')
        decimation = _by_id(_castables('beta', 'Sacrier'), DECIMATION)
        self.assertEqual(['Erlittener Schaden x103%', 'Erlittener Schaden x106% (Dezimierung)'],
                         _taken_notes(decimation, [(decimation, 2)], 'de', 'beta', {}))


class TheSpellsPageCarriesTheNotesTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_user('auteur', 'a@x.test', 'pw'))

    def _sacrier_at_the_reference_stats(self):
        from chardata.models import Char
        from chardata.solution import get_solution
        from fashionistapulp.structure import get_structure
        _in(self, 'dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(item for item in structure.types[LEVEL][type_name]
                        if not item.removed and item.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {'text': '\n'.join(names), 'confirm': '1',
                                           'char_class': 'Sacrier', 'level': str(LEVEL)})
        char = Char.objects.order_by('-id').first()
        solution = get_solution(char)
        patcher = mock.patch.object(type(solution), 'get_stats_total',
                                    return_value=_stats('dofus3', 'Sacrier'))
        patcher.start()
        self.addCleanup(patcher.stop)
        return char, solution

    def test_the_page_and_its_refresh_show_every_note_the_turn_carries(self):
        from chardata.spells_view import _best_combo
        char, solution = self._sacrier_at_the_reference_stats()
        for language in ('en', 'es'):
            with self.subTest(language=language):
                with override(language):
                    combo = _best_combo(char, solution, 'dofus3')
                notes = [note for cast in combo['casts'] for note in cast['taken_notes']]
                self.assertTrue(any(note.endswith(')') for note in notes), notes)
                page = self.client.get('/spells/%d/' % char.pk,
                                       HTTP_ACCEPT_LANGUAGE=language).content.decode('utf-8')
                refreshed = self.client.post('/best_combo/%d/' % char.pk, {'buff_state': '{}'},
                                             HTTP_ACCEPT_LANGUAGE=language).json()
                self.assertEqual([cast['taken_notes'] for cast in combo['casts']],
                                 [cast['taken_notes']
                                  for cast in refreshed['best_combo']['casts']])
                for note in notes:
                    self.assertIn('>%s</div>' % note, page)
