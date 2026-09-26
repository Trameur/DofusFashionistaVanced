# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The spell modifiers of worn items reach the best turn, each version from its own data."""

import json
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import gettext, override

from chardata.spell_combo import (best_turn, cast_limit, castable_spells,
                                  conditional_extras, crit_chance,
                                  delayed_damage, retro_critical_x)
from chardata.spell_modifiers import (SpellModifier, spell_modifier_table,
                                      worn_spell_modifiers)
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY

VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')
REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

HONOH_RING = 8714
BAUDRIER_POPEE = 27553
LUPINE_BELT = 8654
HARRE_RING = 8717
BLORD_WEAPONS = (8992, 8993)
WEAPON_SPELLS = {364, 366, 367, 369}

ARROW_OF_JUDGEMENT = 32460
FULMINATING_ARROW = 32450
EXPLOSIVE_ARROW = 32445
JORMUN = 23268
HAND = 13244
DOFUS2_DESTRUCTIVE_BOLTS = 13061
RETRO_HARASSING_ARROW = 173
RETRO_EXPLOSIVE_ARROW = 179
RETRO_IOP_SWORD = 160
ANTRIN_BOOTS = 8663
ROBBIE_HOOD = 8636
SLOW_DOWN_ARROW = 32439
TYRANNICAL_ARROW = 32448
NOA = 23735
RENOWN = 23319
EXPIATION_ARROW = 32438
TARG_BELT = 8660
RETRO_ROULETTE = 101
BLABER_RING = 8715
RETRO_CONTRECOUP = 111
RETRO_GLOWING_ARMOUR = 1
GIRDLE_BELT = 8661
RETRO_SOOTHING_BRAMBLE = 192
CAP_RICOTT = 8632

# The French words each version's own template uses for what a kind does
KIND_WORDS = {
    'ap_cost': r'\bPA\b',
    'per_turn': r'par tour',
    'per_target': r'par cible',
    'cooldown': r'relance',
    'cooldown_set': r'relance',
    'critical': r'Critique|CC',
    'damage': r'[Dd]ommages(?! de base)',
    'base_damage': r'dégâts de base',
    'heals': r'[Ss]oins',
    'max_range': r'[Pp]ortée|PO',
    'min_range': r'[Pp]ortée',
    'modifiable_range': r'[Pp]ortée',
    'straight_line': r'en ligne',
    'line_of_sight': r'ligne de vue',
    'occupied_cell': r'case occupée',
}


def _stats(**values):
    stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
    stats.update(values)
    return stats


class _Piece(object):

    def __init__(self, ankama_id, name=None, added=True):
        self.item_added = added
        self.ankama_id = ankama_id
        self.ankama_type = 'equipment'
        self.name = self.localized_name = name or str(ankama_id)


class _Solution(object):

    def __init__(self, stats, pieces=()):
        self.items = {'Ring': list(pieces), 'Weapon': []}
        self._stats = stats

    def get_stats_total(self):
        return dict(self._stats)


class _Char(object):

    def __init__(self, char_class, level=200):
        self.char_class = char_class
        self.level = level


def _worn(game_version, *ankama_ids):
    solution = _Solution({}, [_Piece(ankama_id) for ankama_id in ankama_ids])
    return worn_spell_modifiers(solution, game_version)


def _only(char_class, game_version, spell_ids, modifiers=None):
    return [spell for spell in castable_spells(char_class, 200, game_version,
                                               modifiers=modifiers)
            if spell.spell_id in spell_ids]


def _entry(game_version, char_class, spell_id):
    from chardata.spell_reference import get_spell_reference
    return next(entry for entry in get_spell_reference(game_version)[char_class]
                if entry.get('id') == spell_id)


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('store_spell_modifiers')


class EachVersionReadsItsOwnModifiersTests(SimpleTestCase):

    def test_an_archived_version_names_its_archive_and_retro_touch_name_none(self):
        import fashionista_version
        expected = {'dofus3': fashionista_version.FASHIONISTA_VERSION,
                    'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
                    'dofus2': fashionista_version.FASHIONISTA_DOFUS2_VERSION}
        for version in VERSIONS:
            with self.subTest(version=version):
                table = spell_modifier_table(version)
                self.assertEqual(version, table.get('game_version'))
                self.assertEqual(expected.get(version), table.get('data_version'))

    def test_the_label_is_the_tag_the_pipeline_passed(self):
        generator = _generator()
        self.assertEqual('9.9.9.9', generator.table(
            'dofus3', {}, {}, set(), '9.9.9.9')['data_version'])
        self.assertNotIn('data_version', generator.table(
            'retro', {}, {}, set(), '9.9.9.9'))

    def test_the_stored_file_is_what_the_generator_writes(self):
        generator = _generator()
        collected = {}
        for version in VERSIONS:
            try:
                collected[version] = generator.collect(version)
            except FileNotFoundError as missing:
                self.skipTest('%s is gitignored and not fetched here'
                              % missing.filename)
        for version, (rows, templates, misses) in collected.items():
            with self.subTest(version=version):
                payload = generator.table(
                    version, rows, templates,
                    generator.items_the_site_holds(version))
                self.assertEqual(spell_modifier_table(version),
                                 json.loads(json.dumps(payload)))
                self.assertFalse(any((misses or {}).values()), misses)

    def test_each_kind_is_what_the_versions_own_template_says(self):
        for version in VERSIONS:
            for effect_id, entry in spell_modifier_table(version)['effects'].items():
                with self.subTest(version=version, effect=effect_id):
                    self.assertIn(entry['kind'], KIND_WORDS)
                    self.assertRegex(entry['text'], KIND_WORDS[entry['kind']])
                    if entry['sign'] < 0:
                        self.assertRegex(entry['text'], r'-#3|Réduit|Diminue')
                    if entry['sign'] > 0:
                        self.assertRegex(entry['text'], r'\+#3|Augmente')

    def test_the_rows_name_spells_of_the_version_but_the_weapon_ones(self):
        from chardata.spell_reference import get_spell_reference
        for version in VERSIONS:
            known = {entry['id']
                     for entries in get_spell_reference(version).values()
                     for entry in entries if entry.get('id') is not None}
            named = {row[0]
                     for rows in spell_modifier_table(version)['items'].values()
                     for row in rows}
            with self.subTest(version=version):
                expected = (WEAPON_SPELLS if version in ('retro', 'touch')
                            else set())
                self.assertEqual(expected, named - known)

    def test_every_class_item_carries_its_rows_in_each_version(self):
        counts = {'dofus3': (95, 760), 'beta': (95, 760),
                  'dofus2': (95, 760), 'retro': (63, 257), 'touch': (2, 8)}
        for version, (items, rows) in counts.items():
            table = spell_modifier_table(version)['items']
            with self.subTest(version=version):
                self.assertEqual(items, len(table))
                self.assertEqual(rows, sum(len(row) for row in table.values()))

    def test_retro_files_a_spell_bonus_under_the_stat_it_adds(self):
        path = os.path.join(REPO, 'itemscraper', 'retro_raw', 'effects_fr.json')
        if not os.path.exists(path):
            self.skipTest('retro_raw is gitignored; run '
                          'itemscraper/download_retro_langs.py')
        with open(path, encoding='utf-8') as handle:
            effects = json.load(handle)['E']
        self.assertEqual(effects['115']['c'], effects['287']['c'])
        self.assertEqual(effects['112']['c'], effects['283']['c'])

    def test_touch_imports_no_class_item_with_a_modifier(self):
        self.assertEqual({str(ankama_id) for ankama_id in BLORD_WEAPONS},
                         set(spell_modifier_table('touch')['items']))


class AClassItemGivesTheExtraCastTests(SimpleTestCase):

    def _casts(self, spells, ap, version, **stats):
        _total, order = best_turn(_stats(**stats), spells, ap,
                                  game_version=version, caster_level=200)
        return [name for name, _damage in order]

    def test_honoh_ring_fits_two_four_ap_arrows_in_six_ap(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                keys = {ARROW_OF_JUDGEMENT, FULMINATING_ARROW}
                bare = _only('Cra', version, keys)
                worn = _only('Cra', version, keys, _worn(version, HONOH_RING))
                self.assertEqual([4, 4], sorted(s.cost for s in bare))
                self.assertEqual([3, 3], sorted(s.cost for s in worn))
                self.assertEqual(1, len(self._casts(bare, 6, version, str=1000)))
                self.assertEqual(2, len(self._casts(worn, 6, version, str=1000)))

    def test_baudrier_popee_casts_jormun_twice(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                bare = _only('Forgelance', version, {JORMUN})
                worn = _only('Forgelance', version, {JORMUN},
                             _worn(version, BAUDRIER_POPEE))
                self.assertEqual((1, 2), (bare[0].limit, worn[0].limit))
                self.assertEqual(['Jormun'],
                                 self._casts(bare, 6, version, cha=1000))
                self.assertEqual(['Jormun', 'Jormun'],
                                 self._casts(worn, 6, version, cha=1000))

    def test_dofus2_honoh_ring_casts_destructive_bolts_twice(self):
        bare = _only('Cra', 'dofus2', {DOFUS2_DESTRUCTIVE_BOLTS})
        worn = _only('Cra', 'dofus2', {DOFUS2_DESTRUCTIVE_BOLTS},
                     _worn('dofus2', HONOH_RING))
        self.assertEqual((4, 3), (bare[0].cost, worn[0].cost))
        self.assertEqual(1, len(self._casts(bare, 6, 'dofus2', str=1000)))
        self.assertEqual(2, len(self._casts(worn, 6, 'dofus2', str=1000)))

    def test_retro_honoh_ring_casts_the_harassing_arrow_twice(self):
        bare = _only('Cra', 'retro', {RETRO_HARASSING_ARROW})
        worn = _only('Cra', 'retro', {RETRO_HARASSING_ARROW},
                     _worn('retro', HONOH_RING))
        self.assertEqual((3, 2), (bare[0].cost, worn[0].cost))
        self.assertEqual(1, len(self._casts(bare, 4, 'retro', agi=1000)))
        self.assertEqual(2, len(self._casts(worn, 4, 'retro', agi=1000)))

    def test_touch_weapons_change_no_class_spell(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        modifiers = _worn('touch', *BLORD_WEAPONS)
        self.assertEqual(WEAPON_SPELLS, set(modifiers))
        for char_class in get_damage_spells_for_version('touch'):
            if char_class == 'default':
                continue
            with self.subTest(char_class=char_class):
                self.assertEqual(
                    [(s.name, s.cost, s.limit)
                     for s in castable_spells(char_class, 200, 'touch')],
                    [(s.name, s.cost, s.limit)
                     for s in castable_spells(char_class, 200, 'touch',
                                              modifiers=modifiers)])

    def test_a_turn_limit_under_a_target_limit_stays_one_cast(self):
        worn = _only('Xelor', 'dofus3', {HAND}, _worn('dofus3', LUPINE_BELT))
        self.assertEqual((4, 1, 1),
                         (worn[0].per_turn, worn[0].per_target, worn[0].limit))

    def test_the_critical_bonus_follows_each_versions_rule(self):
        stats = _stats(ch=10)
        worn = _only('Cra', 'dofus3', {EXPLOSIVE_ARROW},
                     _worn('dofus3', HONOH_RING))[0]
        own = dict(stats, ch=stats['ch'] + worn.bonus_stats['ch'])
        self.assertEqual((20 + 30 + 10) / 100.0,
                         crit_chance(worn.crit_rate, own, 'dofus3'))
        retro = _only('Cra', 'retro', {RETRO_EXPLOSIVE_ARROW},
                      _worn('retro', HONOH_RING))[0]
        self.assertEqual({'ch': 30}, retro.bonus_stats)
        own = dict(stats, ch=stats['ch'] + 30)
        self.assertEqual(1.0 / retro_critical_x(retro.crit_rate, 40, 0),
                         crit_chance(retro.crit_rate, own, 'retro'))


class ADamageBonusReachesOnlyItsSpellTests(SimpleTestCase):

    def test_retro_spell_damage_adds_to_the_hit_of_that_spell(self):
        bare = _only('Iop', 'retro', {RETRO_IOP_SWORD})
        worn = _only('Iop', 'retro', {RETRO_IOP_SWORD},
                     _worn('retro', ANTRIN_BOOTS))
        self.assertEqual({'dam': 30}, worn[0].bonus_stats)
        before, _order = best_turn(_stats(), bare, 4, game_version='retro')
        after, _order = best_turn(_stats(), worn, 4, game_version='retro')
        self.assertAlmostEqual(30.0, after - before)

    def test_base_damage_raises_copies_of_the_rows(self):
        bare = _only('Cra', 'dofus3', {SLOW_DOWN_ARROW})[0]
        worn = _only('Cra', 'dofus3', {SLOW_DOWN_ARROW},
                     _worn('dofus3', ROBBIE_HOOD))[0]
        rows = [(r.min_dam, r.max_dam) for r in bare.plain_alternatives[0]]
        self.assertEqual([(low + 6, high + 6) for low, high in rows],
                         [(r.min_dam, r.max_dam)
                          for r in worn.plain_alternatives[0]])
        self.assertEqual(rows, [(r.min_dam, r.max_dam)
                                for r in _only('Cra', 'dofus3',
                                               {SLOW_DOWN_ARROW})[0]
                                .plain_alternatives[0]])


class TheLateAndWaitingRowsGetTheItemOnceTests(SimpleTestCase):

    def _tyrannical(self, *modifiers):
        worn = {TYRANNICAL_ARROW: list(modifiers)} if modifiers else None
        return _only('Cra', 'dofus3', {TYRANNICAL_ARROW}, worn)[0]

    def _late(self, spell):
        return delayed_damage(_stats(), [spell], [(spell.name, 0)],
                              game_version='dofus3')[spell.name]

    def test_base_damage_raises_each_late_row_once(self):
        bare = self._tyrannical()
        worn = self._tyrannical(SpellModifier('base_damage', 10, 'Test'))
        late = worn.delayed_plain + worn.delayed_crit
        self.assertEqual(15, bare.crit_rate)
        self.assertEqual([(20, 22), (24, 26)],
                         [(row.min_dam, row.max_dam)
                          for row, _when in bare.delayed_plain + bare.delayed_crit])
        self.assertEqual([(30, 32), (34, 36)],
                         [(row.min_dam, row.max_dam) for row, _when in late])
        self.assertLessEqual({id(row) for row, _when in late},
                             set(worn.late_by_effect))
        self.assertAlmostEqual(21 * 0.85 + 25 * 0.15, self._late(bare))
        self.assertAlmostEqual(31 * 0.85 + 35 * 0.15, self._late(worn))

    def test_a_damage_bonus_reaches_the_late_rows(self):
        worn = self._tyrannical(SpellModifier('damage', 30, 'Test'))
        self.assertAlmostEqual(51 * 0.85 + 55 * 0.15, self._late(worn))

    def test_a_damage_bonus_reaches_a_row_waiting_on_a_push(self):
        pusher = next(spell for spell in castable_spells('Forgelance', 200,
                                                         'dofus3')
                      if spell.pushes and spell.spell_id != NOA)

        def waiting(modifiers):
            noa = _only('Forgelance', 'dofus3', {NOA}, modifiers)[0]
            return sum(dealt for name, trigger, dealt in conditional_extras(
                _stats(), [pusher, noa], [(pusher.name, 0), (noa.name, 0)],
                game_version='dofus3')
                if name == noa.name and trigger == 'pushback')

        self.assertAlmostEqual((26 + 29) / 2.0, waiting(None))
        self.assertAlmostEqual((26 + 30 + 29 + 30) / 2.0, waiting(
            {NOA: [SpellModifier('damage', 30, 'Test')]}))


class ACooldownTakenToZeroLiftsTheOneCastLimitTests(SimpleTestCase):

    def test_a_cooldown_of_zero_leaves_the_turn_and_target_limits(self):
        self.assertEqual(1, cast_limit(None, None, 1))
        self.assertIsNone(cast_limit(None, None, 0))
        self.assertEqual(2, cast_limit(2, 3, 0))

    def test_a_worn_reduction_to_zero_lifts_the_limit_of_the_cast(self):
        bare = _only('Ecaflip', 'retro', {RETRO_CONTRECOUP})[0]
        worn = _only('Ecaflip', 'retro', {RETRO_CONTRECOUP}, {
            RETRO_CONTRECOUP: [SpellModifier('cooldown', -bare.cooldown,
                                             'Test')]})[0]
        self.assertEqual((None, None, 1), (bare.per_turn, bare.per_target,
                                           bare.limit))
        self.assertEqual((0, None), (worn.cooldown, worn.limit))

    def test_the_blaber_ring_leaves_roulettes_last_rank_no_cooldown(self):
        from chardata.spells_view import _reference_digest
        entry = _entry('retro', 'Ecaflip', RETRO_ROULETTE)
        with override('en'):
            digest = _reference_digest(
                entry, _worn('retro', BLABER_RING)[RETRO_ROULETTE])
        self.assertEqual([5, 4, 3, 2, 1, 0], digest['cooldown'])
        self.assertEqual([6, 5, 4, 3, 2, 1], entry['cooldown'])


class EachVersionReadsItsOwnRowForTheSameItemTests(SimpleTestCase):

    def test_the_sash_adds_a_cast_of_renown_on_beta_only(self):
        from chardata.spells_view import _reference_digest
        for version, kinds, per_turn in (('dofus3', ['cooldown'], [1]),
                                         ('beta', ['per_turn'], [2])):
            with self.subTest(version=version):
                entry = _entry(version, 'Forgelance', RENOWN)
                modifiers = _worn(version, BAUDRIER_POPEE)[RENOWN]
                with override('en'):
                    digest = _reference_digest(entry, modifiers)
                self.assertEqual(kinds, [m.kind for m in modifiers])
                self.assertEqual([1], entry['per_turn'])
                self.assertEqual(per_turn, digest['per_turn'])
                self.assertIsNone(digest.get('cooldown'))


class TheReferenceLineShowsWhatTheItemChangesTests(SimpleTestCase):

    def test_ranks_of_unequal_lengths_each_keep_their_own_length(self):
        from chardata.spells_view import _modified_ranks
        digest = {'ap': [4, 4, 3], 'per_turn': [2], 'per_target': None,
                  'cooldown': [3, 2]}
        modifiers = [SpellModifier('ap_cost', -1, 'Test'),
                     SpellModifier('per_turn', 1, 'Test'),
                     SpellModifier('cooldown', -1, 'Test')]
        self.assertEqual({'ap': [3, 3, 2], 'per_turn': [3], 'cooldown': [2, 1]},
                         _modified_ranks(digest, modifiers))

    def test_the_targ_belt_brings_the_arrow_of_expiation_closer(self):
        from chardata.spells_view import _item_notes, _reference_digest
        entry = _entry('dofus3', 'Cra', EXPIATION_ARROW)
        modifiers = _worn('dofus3', TARG_BELT)[EXPIATION_ARROW]
        with override('en'):
            digest = _reference_digest(entry, modifiers)
            notes = _item_notes(modifiers, 'dofus3')
        self.assertEqual([[6, 10], [6, 12]], entry['range'])
        self.assertEqual([[1, 10], [1, 12]], digest['range'])
        self.assertEqual(['%d: -5 Minimum range' % TARG_BELT], notes)

    def test_the_honoh_ring_lengthens_the_range_of_the_arrows_it_names(self):
        from chardata.spells_view import _reference_digest
        worn = _worn('dofus3', HONOH_RING)
        lengthened = {spell_id: sum(m.amount for m in modifiers
                                    if m.kind == 'max_range')
                      for spell_id, modifiers in worn.items()}
        self.assertEqual({32443: 3, 32459: 2, 32457: 3},
                         {k: v for k, v in lengthened.items() if v})
        for spell_id, amount in lengthened.items():
            entry = _entry('dofus3', 'Cra', spell_id)
            with self.subTest(spell=spell_id), override('en'):
                self.assertEqual(
                    [[low, high + amount] for low, high in entry['range']],
                    _reference_digest(entry, worn[spell_id])['range'])

    def test_a_spell_with_no_damage_table_counts_the_items_critical(self):
        from chardata.spells_view import _create_reference_web_digest
        entry = _entry('retro', 'Feca', RETRO_GLOWING_ARMOUR)
        modifiers = _worn('retro', GIRDLE_BELT)[RETRO_GLOWING_ARMOUR]
        with override('en'):
            digest = _create_reference_web_digest(entry, 'retro', 200,
                                                  modifiers)
        self.assertEqual({'ch': 30}, digest['item_stats'])
        self.assertEqual(['%d: +30 crit' % GIRDLE_BELT], digest['item_notes'])

    def test_the_cap_ricott_adds_its_heals_to_soothing_bramble(self):
        from chardata.spells_view import _create_reference_web_digest
        entry = _entry('retro', 'Sadida', RETRO_SOOTHING_BRAMBLE)
        modifiers = _worn('retro', CAP_RICOTT)[RETRO_SOOTHING_BRAMBLE]
        with override('en'):
            digest = _create_reference_web_digest(entry, 'retro', 200,
                                                  modifiers)
        self.assertEqual({'heals': 100}, digest['item_stats'])
        self.assertEqual(['%d: +100 Heals' % CAP_RICOTT], digest['item_notes'])


class AnItemNotWornChangesNothingTests(SimpleTestCase):

    def _shape(self, spells):
        return [(s.name, s.cost, s.limit, s.crit_rate, s.bonus_stats)
                for s in spells]

    def test_no_worn_modifier_leaves_every_spell_as_the_data_states(self):
        for version in ('dofus3', 'beta', 'dofus2', 'retro'):
            with self.subTest(version=version):
                self.assertEqual({}, worn_spell_modifiers(_Solution({}), version))
                self.assertEqual(
                    self._shape(castable_spells('Cra', 200, version)),
                    self._shape(castable_spells('Cra', 200, version,
                                                modifiers={})))

    def test_a_piece_left_out_of_the_set_changes_nothing(self):
        solution = _Solution({}, [_Piece(HONOH_RING, added=False)])
        self.assertEqual({}, worn_spell_modifiers(solution, 'dofus3'))

    def test_another_classs_item_changes_no_spell_of_this_class(self):
        for version in ('dofus3', 'dofus2', 'retro'):
            with self.subTest(version=version):
                modifiers = _worn(version, HARRE_RING)
                self.assertTrue(modifiers)
                self.assertEqual(
                    self._shape(castable_spells('Cra', 200, version)),
                    self._shape(castable_spells('Cra', 200, version,
                                                modifiers=modifiers)))


class ThePanelMatchesAHandCalculationTests(SimpleTestCase):

    def _combo(self, pieces):
        from chardata.spells_view import _best_combo
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        solution = _Solution(_stats(str=1000, ap=3), pieces)
        with override('en'):
            return _best_combo(_Char('Cra'), solution, 'dofus3')

    def test_the_ring_puts_the_arrow_of_judgement_in_three_ap(self):
        combo = self._combo([_Piece(HONOH_RING, 'Honoh Ring')])
        plain = (36 * 1100 // 100 + 40 * 1100 // 100) / 2.0 \
            + (25 * 1100 // 100 + 27 * 1100 // 100) / 2.0
        critical = (43 * 1100 // 100 + 48 * 1100 // 100) / 2.0 \
            + (30 * 1100 // 100 + 32 * 1100 // 100) / 2.0
        by_hand = 0.8 * plain + 0.2 * critical
        self.assertEqual(731.5, by_hand)
        self.assertEqual(1, len(combo['casts']))
        cast = combo['casts'][0]
        self.assertEqual('Arrow of Judgement', cast['name'])
        self.assertEqual(3, cast['ap'])
        self.assertEqual(int(round(by_hand)), cast['damage'])
        self.assertEqual(int(round(by_hand)), combo['total'])
        self.assertEqual(3, combo['ap_used'])
        with override('en'):
            self.assertEqual([gettext('%(item)s: %(changes)s') % {
                'item': 'Honoh Ring', 'changes': '-1 AP'}], cast['item_notes'])

    def test_without_the_ring_three_ap_cast_eye_for_eye(self):
        combo = self._combo([])
        plain = (27 * 1100 // 100 + 30 * 1100 // 100) / 2.0
        critical = (32 * 1100 // 100 + 36 * 1100 // 100) / 2.0
        by_hand = 0.85 * plain + 0.15 * critical
        self.assertEqual(['Eye for Eye'], [c['name'] for c in combo['casts']])
        self.assertEqual(int(round(by_hand)), combo['total'])
        self.assertEqual([], combo['casts'][0]['item_notes'])


class TheSpellsPageShowsTheItemTests(TestCase):

    DIGESTS = re.compile(r'var spellDigests = (.*?);\s*\n', re.S)

    def setUp(self):
        from django.contrib.auth.models import User
        self.author = User.objects.create_user('author', 'a@x.test', 'pw')
        self.client.force_login(self.author)

    def _build(self, with_ring):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        if with_ring:
            names.append('Honoh Ring')
        self.client.post('/import/text/', {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _digest(self, page, canonical):
        digests = json.loads(self.DIGESTS.search(page).group(1))
        return next(d for d in digests if d.get('canonical') == canonical)

    def test_the_spell_table_shows_the_cost_and_names_the_ring(self):
        char = self._build(with_ring=True)
        with override('en'):
            page = self.client.get('/spells/%d/' % char.id,
                                   follow=True).content.decode('utf-8')
        judgement = self._digest(page, 'Arrow of Judgement')
        self.assertEqual({3}, set(judgement['reference']['ap']))
        self.assertEqual(['Honoh Ring: -1 AP'], judgement['item_notes'])
        explosive = self._digest(page, 'Explosive Arrow')
        self.assertEqual({'ch': 30}, explosive['item_stats'])

    def test_without_the_ring_the_table_keeps_the_game_cost(self):
        char = self._build(with_ring=False)
        with override('en'):
            page = self.client.get('/spells/%d/' % char.id,
                                   follow=True).content.decode('utf-8')
        judgement = self._digest(page, 'Arrow of Judgement')
        self.assertEqual({4}, set(judgement['reference']['ap']))
        self.assertEqual([], judgement['item_notes'])

    def test_the_build_page_shows_the_turn_of_the_spells_panel(self):
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        char = self._build(with_ring=True)
        response = self.client.get('/solution/%d/' % char.id, follow=True)
        combo = _best_combo(char, get_solution(char), 'dofus3')
        self.assertEqual(combo['total'], response.context['best_turn'])
