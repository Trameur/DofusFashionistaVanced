# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The gallery badge says a worn piece cannot be worn: a broken piece condition gives it, the build's own minimums never do."""

import json
import pickle
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import translation

from chardata.char_blobs import read_char_blob
from chardata.gallery_visibility import refusal_reason, refusal_sentence
from chardata.min_stats import get_min_stats_digested_by_key
from chardata.models import Char, CharBaseStats
from chardata.shared_builds_view import _get_shared_build_meta, _meta_cache_key
from chardata.solution import get_solution
from chardata.tests_a_piece_its_build_cannot_wear_is_refused_at_every_door import (
    _Build, _minimal)
from chardata.tests_a_touch_build_saved_before_the_seals_still_loads import _OPTIONS
from chardata.version_compat import class_exists_in_version
from chardata.wear_conditions import reasons_not_worn
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, SLOT_NAME_TO_TYPE,
                                              STAT_KEY_TO_NAME, slots_for)
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import (fits_the_class, fits_the_level,
                                       get_structure, level_to_wear,
                                       set_current_game_version)
from fashionistapulp.wearer import Wearer

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
SLOTS = ('hat', 'cloak', 'amulet', 'belt', 'boots', 'ring1', 'weapon', 'shield',
         'emblem1')
CONDITION_FIELDS = ('unusable', 'classes', 'sexes', 'names', 'max_level',
                    'spell_conditions', 'own_not_worn_with', 'not_worn_with',
                    'min_stats_to_equip', 'max_stats_to_equip', 'or_conditions')
OR_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch')
AP_MP_OR_VERSIONS = ('dofus3', 'beta', 'dofus2')
BADGE = 'Conditions not met'
SENTENCE_END = 'Open it to see which ones.'
_RED_SLOTS = re.compile(r'itemViolates\s*=\s*(\{[^}]*\})')


def _has(item, field):
    value = getattr(item, field, None)
    return value is not None if field == 'max_level' else bool(value)


def _wearable_slot(version, item):
    structure = get_structure(version)
    kind = structure.get_type_name_by_id(item.type)
    return next((slot for slot in SLOTS if slot in slots_for(version)
                 and SLOT_NAME_TO_TYPE[slot] == kind), None)


def _pieces(version, field=None, ok=()):
    """(piece, slot) of the pieces asking for the condition `field` and nothing else but `ok`."""
    found = []
    for item in sorted(get_structure(version).items_dict.values(),
                       key=lambda item: item.id):
        slot = _wearable_slot(version, item)
        if (slot is None or item.removed or item.set is not None
                or any((item.weird_conditions or {}).values())):
            continue
        others = [other for other in CONDITION_FIELDS
                  if other != field and _has(item, other)]
        if set(others) - set(ok):
            continue
        if field is not None and not _has(item, field):
            continue
        found.append((len(others), item, slot))
    return [(item, slot) for _extras, item, slot in sorted(
        found, key=lambda row: (row[0], row[1].id))]


def _the_piece(version, field=None, ok=()):
    pieces = _pieces(version, field, ok)
    if field is None:
        pieces = sorted(pieces, key=lambda pair: -level_to_wear(pair[0]))
    if not pieces:
        raise AssertionError('no %s piece asks for only %s' % (version, field))
    return pieces[0]


def _gender_for(piece):
    return piece.sexes[0] if getattr(piece, 'sexes', ()) else 0


def _another_class(version, classes):
    return next(name for name in CHARACTER_CLASSES
                if name not in classes and class_exists_in_version(name, version))


def _or_piece(version, keys, is_max):
    """(piece, slot, {stat key: limit}) of a piece asking only for one-stat OR branches on `keys`."""
    structure = get_structure(version)
    for piece, slot in _pieces(version, 'or_conditions'):
        branches = [[(structure.get_stat_by_id(stat_id).key, gate_is_max, value)
                     for stat_id, gate_is_max, value in branch]
                    for branch in piece.or_conditions]
        if (all(len(branch) == 1 and branch[0][1] == is_max for branch in branches)
                and {branch[0][0] for branch in branches} == set(keys)):
            return piece, slot, {branch[0][0]: branch[0][2] for branch in branches}
    raise AssertionError('no %s piece asks only for %s OR branches on %s'
                         % (version, 'max' if is_max else 'min', keys))


def _clean_minimal(version, char_class, level):
    """A stored build wearing, in each slot, the first piece that asks for nothing."""
    minimal = _minimal(version, char_class, level)
    structure = get_structure(version)
    taken = set()
    for slot in slots_for(version):
        minimal.item_per_slot[slot] = None
        for item in structure.types[level][SLOT_NAME_TO_TYPE[slot]]:
            if (item.id not in taken and fits_the_level(item, level)
                    and not item.removed and item.set is None
                    and not any(_has(item, field) for field in CONDITION_FIELDS)
                    and not any((item.weird_conditions or {}).values())):
                taken.add(item.id)
                minimal.item_per_slot[slot] = item.id
                break
    return minimal


class _Badge(_Build):

    made = 0

    def _make(self, version, wearing=None, slot=None, char_class='Iop', level=200,
              gender=0, char_name='', minimums=None, origin='generated', bare=False):
        set_current_game_version(version)
        type(self).made += 1
        number = type(self).made
        owner = User.objects.create_user('badge-%d' % number, 'badge@test.local',
                                         'pw-42-solid')
        self.client.force_login(owner)
        minimal = _clean_minimal(version, char_class, level)
        minimal.input['origin'] = origin
        if bare:
            minimal.item_per_slot = {name: None for name in minimal.item_per_slot}
        if wearing is not None:
            minimal.item_per_slot[slot] = wearing.id
        return Char.objects.create(
            name='Badge %d' % number, char_name=char_name, char_class=char_class,
            char_build='', level=level, gender=gender,
            minimum_stats=pickle.dumps(dict(minimums or {})),
            minimum_crits=pickle.dumps({}), stats_weight=pickle.dumps({}),
            options=pickle.dumps(dict(_OPTIONS)), inclusions=b'', exclusions=b'',
            owner=owner, link_shared=True, game_version=version,
            minimal_solution=pickle.dumps(minimal))

    def _prefix(self, char):
        return '' if char.game_version == 'dofus3' else '/' + char.game_version

    def _with_totals(self, char, totals):
        """Store base stats so the build totals come to `totals`, {stat key: value}."""
        set_current_game_version(char.game_version)
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution')
        base = minimal.input.setdefault('base_stats_by_attr', {})
        for key in totals:
            base[STAT_KEY_TO_NAME[key]] = 0
        char.minimal_solution = pickle.dumps(minimal)
        gear = get_solution(char).get_stats_total()
        for key, wanted in totals.items():
            base[STAT_KEY_TO_NAME[key]] = wanted - gear[key]
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        reached = get_solution(char).get_stats_total()
        self.assertEqual(totals, {key: reached[key] for key in totals})

    def _with_spent(self, char, key, wanted):
        """Spend points so the total of a main stat comes to `wanted`."""
        set_current_game_version(char.game_version)
        name = STAT_KEY_TO_NAME[key]
        CharBaseStats.objects.filter(char=char, stat=name).delete()
        have = get_solution(char).get_stats_total()[key]
        CharBaseStats.objects.create(char=char, stat=name, scrolled_value=0,
                                     total_value=wanted - have)
        self.assertEqual(wanted, get_solution(char).get_stats_total()[key])

    def _meta(self, char):
        cache.clear()
        with translation.override('en'):
            return _get_shared_build_meta(char)

    def _red_slots_on_the_page(self, char):
        page = self.client.get('%s/solution/%d/' % (self._prefix(char), char.id),
                               follow=True)
        self.assertEqual(200, page.status_code)
        found = _RED_SLOTS.search(page.content.decode('utf-8'))
        self.assertIsNotNone(found, 'the page does not carry its red slots')
        return {slot for slot, red in json.loads(found.group(1)).items() if red}

    def _red_slots(self, char):
        set_current_game_version(char.game_version)
        solution = get_solution(char)
        return {item.slot for item in solution.item_list
                if item.item_added and solution.get_violations_on_item(item)}

    def _card(self, char, hide_invalid):
        query = '?hide_invalid=1' if hide_invalid else ''
        page = self.client.get('%s/sharedbuilds/%s' % (self._prefix(char), query))
        self.assertEqual(200, page.status_code)
        for card in page.content.decode('utf-8').split('<div class="build-card">')[1:]:
            if char.name in card:
                return card
        return None

    def _flags_only(self, char, slot):
        meta = self._meta(char)
        self.assertEqual({slot}, self._red_slots(char))
        self.assertTrue(meta['has_condition_issues'])
        self.assertTrue(meta['is_invalid'])
        self.assertEqual('conditions', refusal_reason(char))

    def _flags_nothing(self, char):
        meta = self._meta(char)
        self.assertEqual(set(), self._red_slots(char))
        self.assertFalse(meta['has_condition_issues'])
        self.assertFalse(meta['is_invalid'])
        self.assertIsNone(refusal_reason(char))


class TheBuildsOwnMinimumsNeverGiveTheBadgeTests(_Badge):

    MINIMUMS = {'AP': 12, 'MP': 6, 'Range': 6, 'Vitality': 5000}

    def test_a_build_missing_only_its_own_minimums_has_no_badge_and_is_not_hidden(self):
        for version in ('dofus3', 'dofus2'):
            for origin in ('generated', 'dofusbook'):
                with self.subTest(version=version, origin=origin):
                    char = self._make(version, minimums=self.MINIMUMS, origin=origin)
                    solution = get_solution(char)
                    self.assertTrue(solution._get_min_violations(
                        get_min_stats_digested_by_key(char)))
                    self._flags_nothing(char)
                    cache.clear()
                    card = self._card(char, hide_invalid=True)
                    self.assertIsNotNone(card, 'the gallery hides a build that only misses its minimums')
                    self.assertNotIn(BADGE, card)

    def test_a_build_missing_its_minimums_has_no_refusal_reason_in_any_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                char = self._make(version, minimums=self.MINIMUMS)
                self.assertIsNone(refusal_reason(char))
                self.assertFalse(self._meta(char)['has_condition_issues'])

    def test_a_build_whose_gear_cannot_be_read_is_not_said_to_break_its_conditions(self):
        char = self._make('dofus3')
        with mock.patch('chardata.shared_builds_view.get_solution',
                        side_effect=ValueError('unreadable')):
            meta = self._meta(char)
            reason = refusal_reason(char)
        self.assertTrue(meta['cannot_render'])
        self.assertFalse(meta['has_condition_issues'])
        self.assertNotEqual(reason, 'conditions')


class ABrokenPieceConditionStillGivesTheBadgeTests(_Badge):

    def _the_stat_condition_piece(self, version):
        pieces = [(piece, slot) for piece, slot in _pieces(version, 'min_stats_to_equip')
                  if level_to_wear(piece) <= 200]
        self.assertTrue(pieces, version)
        return max(pieces, key=lambda pair: max(
            value for _stat, value in pair[0].min_stats_to_equip))

    def test_a_piece_whose_stat_condition_is_broken_gives_the_badge_and_is_hidden(self):
        for version in ('dofus3', 'dofus2'):
            with self.subTest(version=version):
                piece, slot = self._the_stat_condition_piece(version)
                char = self._make(version, piece, slot, bare=True)
                self._flags_only(char, slot)
                cache.clear()
                self.assertIsNone(self._card(char, hide_invalid=True))
                cache.clear()
                self.assertIn(BADGE, self._card(char, hide_invalid=False))

    def test_the_page_marks_the_piece_with_the_broken_stat_condition_red(self):
        piece, slot = self._the_stat_condition_piece('dofus3')
        self.assertEqual({slot}, self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, bare=True)))

    def test_the_sentence_says_some_pieces_cannot_be_worn(self):
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with self.subTest(language=language), translation.override(language):
                sentence = refusal_sentence('conditions')
                self.assertNotIn('own conditions', sentence)
                self.assertGreater(len(sentence), 40)
                if language != 'en':
                    with translation.override('en'):
                        self.assertNotEqual(refusal_sentence('conditions'), sentence)
        with translation.override('en'):
            sentence = refusal_sentence('conditions')
        self.assertIn('some pieces cannot be worn', sentence)
        self.assertTrue(sentence.endswith(SENTENCE_END))


class ThePageAndTheGalleryAgreeOnWhatTheWearerCannotWearTests(_Badge):

    def test_a_level_too_low_marks_the_slot_red_at_a_low_level_and_at_the_cap(self):
        for version in VERSIONS:
            piece, slot = _the_piece(version)
            needed = level_to_wear(piece)
            self.assertGreater(needed, 100, version)
            for level in (5, needed - 1):
                with self.subTest(version=version, level=level):
                    self.assertFalse(fits_the_level(piece, level))
                    self._flags_only(self._make(version, piece, slot, level=level), slot)
            with self.subTest(version=version, level=needed):
                self._flags_nothing(self._make(version, piece, slot, level=needed))

    def test_a_level_too_low_marks_the_slot_red_on_the_page(self):
        piece, slot = _the_piece('dofus3')
        self.assertEqual({slot}, self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, level=5)))
        self.assertEqual(set(), self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, level=level_to_wear(piece))))

    def test_the_page_says_in_red_which_level_the_piece_needs(self):
        piece, slot = _the_piece('dofus3')
        line = 'Be level %d or higher' % piece.level

        def page_of(level):
            char = self._make('dofus3', piece, slot, level=level)
            with translation.override('en'):
                page = self.client.get('/solution/%d/' % char.id, follow=True)
            self.assertEqual(200, page.status_code)
            return page.content.decode('utf-8')

        self.assertIn(line, page_of(5))
        self.assertNotIn(line, page_of(level_to_wear(piece)))

    def test_a_spell_rank_needing_a_higher_level_than_the_piece_marks_the_slot_red(self):
        pieces = [(piece, slot) for piece, slot in _pieces('touch', 'spell_conditions', ('classes',))
                  if level_to_wear(piece) > (piece.level or 0)]
        self.assertTrue(pieces, 'no touch piece has a spell rank above its level')
        piece, slot = pieces[0]
        needed = level_to_wear(piece)
        for level in (needed - 1, 5):
            with self.subTest(level=level):
                self._flags_only(self._make('touch', piece, slot, piece.classes[0], level), slot)
        with self.subTest(level=needed):
            self._flags_nothing(self._make('touch', piece, slot, piece.classes[0], needed))

    def test_a_character_past_the_max_level_of_a_piece_marks_the_slot_red(self):
        for version in VERSIONS:
            piece, slot = _the_piece(version, 'max_level')
            highest = piece.max_level
            for level in (highest + 1, 200):
                with self.subTest(version=version, level=level):
                    self._flags_only(self._make(version, piece, slot, level=level), slot)
            with self.subTest(version=version, level=highest):
                self._flags_nothing(self._make(version, piece, slot, level=highest))

    def test_a_character_past_the_max_level_marks_the_slot_red_on_the_page(self):
        piece, slot = _the_piece('dofus3', 'max_level')
        self.assertEqual({slot}, self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, level=piece.max_level + 1)))
        self.assertEqual(set(), self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, level=piece.max_level)))

    def test_a_piece_of_another_class_marks_the_slot_red_at_a_low_level_and_at_the_cap(self):
        for version in VERSIONS:
            piece, slot = _the_piece(version, 'classes', ('sexes',))
            wrong = _another_class(version, piece.classes)
            right = piece.classes[0]
            needed = max(level_to_wear(piece), 1)
            self.assertTrue(class_exists_in_version(right, version), version)
            for level in sorted({needed, 200}):
                with self.subTest(version=version, level=level):
                    self.assertFalse(fits_the_class(piece, wrong))
                    self._flags_only(self._make(
                        version, piece, slot, wrong, level, _gender_for(piece)), slot)
                    self._flags_nothing(self._make(
                        version, piece, slot, right, level, _gender_for(piece)))

    def test_a_piece_of_another_class_marks_the_slot_red_on_the_page(self):
        piece, slot = _the_piece('dofus3', 'classes', ('sexes',))
        self.assertEqual({slot}, self._red_slots_on_the_page(self._make(
            'dofus3', piece, slot, _another_class('dofus3', piece.classes),
            gender=_gender_for(piece))))
        self.assertEqual(set(), self._red_slots_on_the_page(self._make(
            'dofus3', piece, slot, piece.classes[0], gender=_gender_for(piece))))

    def test_a_piece_for_the_other_sex_marks_the_slot_red_at_a_low_level_and_at_the_cap(self):
        for version in VERSIONS:
            piece, slot = _the_piece(version, 'sexes')
            right = piece.sexes[0]
            for level in sorted({max(level_to_wear(piece), 1), 200}):
                with self.subTest(version=version, level=level):
                    self._flags_only(self._make(
                        version, piece, slot, level=level, gender=1 - right), slot)
                    self._flags_nothing(self._make(
                        version, piece, slot, level=level, gender=right))

    def test_a_piece_for_the_other_sex_marks_the_slot_red_on_the_page(self):
        piece, slot = _the_piece('dofus3', 'sexes')
        self.assertEqual({slot}, self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, gender=1 - piece.sexes[0])))
        self.assertEqual(set(), self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, gender=piece.sexes[0])))

    def test_a_piece_for_another_name_marks_the_slot_red_at_a_low_level_and_at_the_cap(self):
        for version in VERSIONS:
            piece, slot = _the_piece(version, 'names')
            wanted = piece.names[0]
            for level in sorted({max(level_to_wear(piece), 1), 200}):
                for wrong in ('', wanted[:-1]):
                    with self.subTest(version=version, level=level, name=wrong):
                        self._flags_only(self._make(
                            version, piece, slot, level=level, char_name=wrong), slot)
                with self.subTest(version=version, level=level, name=wanted.upper()):
                    self._flags_nothing(self._make(
                        version, piece, slot, level=level, char_name=wanted.upper()))

    def test_a_piece_for_another_name_marks_the_slot_red_on_the_page(self):
        piece, slot = _the_piece('dofus3', 'names')
        self.assertEqual({slot}, self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, char_name='Nobody')))
        self.assertEqual(set(), self._red_slots_on_the_page(
            self._make('dofus3', piece, slot, char_name=piece.names[0])))

    def test_an_unequippable_piece_marks_the_slot_red_in_every_version(self):
        for version in VERSIONS:
            piece, slot = _the_piece(version, 'unusable')
            with self.subTest(version=version):
                self._flags_only(self._make(
                    version, piece, slot, level=max(level_to_wear(piece), 1)), slot)

    def test_a_piece_worn_beside_the_one_it_excludes_marks_a_slot_red(self):
        structure = get_structure('dofus2')
        piece = next(piece for piece in structure.items_dict.values()
                     if getattr(piece, 'own_not_worn_with', ()) and not piece.removed)
        other = structure.get_item_by_id(piece.own_not_worn_with[0])
        kind = structure.get_type_name_by_id(piece.type)
        slots = [slot for slot in slots_for('dofus2') if SLOT_NAME_TO_TYPE[slot] == kind]
        self.assertGreaterEqual(len(slots), 2)
        alone = self._make('dofus2', piece, slots[0], level=max(level_to_wear(piece), 1))
        self.assertEqual(set(), self._red_slots(alone))
        minimal = read_char_blob(alone.minimal_solution, None, 'minimal_solution')
        minimal.item_per_slot[slots[1]] = other.id
        alone.minimal_solution = pickle.dumps(minimal)
        alone.save()
        self.assertIn(slots[0], self._red_slots(alone))


class TheReasonIsTheItemPagesWordingTests(_Badge):

    def test_each_reason_reads_like_the_item_pages_line_in_every_language(self):
        cases = []
        for field, wearer in (('classes', lambda piece, version: Wearer(
                char_class=_another_class(version, piece.classes))),
                              ('sexes', lambda piece, version: Wearer(
                                  gender=1 - piece.sexes[0])),
                              ('names', lambda piece, version: Wearer(char_name='Nobody')),
                              ('max_level', lambda piece, version: Wearer(
                                  level=piece.max_level + 1))):
            piece, _slot = _the_piece('dofus2', field, ('sexes',))
            cases.append((field, piece, wearer(piece, 'dofus2')))
        piece, _slot = _the_piece('dofus2')
        cases.append(('level', piece, Wearer(level=5)))
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                for field, piece, wearer in cases:
                    with self.subTest(language=language, field=field):
                        expected = reasons_not_worn(
                            'dofus2', piece, char_class=wearer.char_class,
                            level=wearer.level, gender=wearer.gender,
                            char_name=wearer.char_name)
                        self.assertTrue(expected)
                        self.assertEqual(
                            expected, [text for _kind, text in wearer.reasons(piece)])

    def test_the_reasons_of_a_piece_are_the_violations_the_page_and_the_gallery_share(self):
        piece, slot = _the_piece('dofus3', 'sexes')
        char = self._make('dofus3', piece, slot, gender=1 - piece.sexes[0])
        set_current_game_version('dofus3')
        solution = get_solution(char)
        worn = next(item for item in solution.item_list if item.slot == slot)
        violations = solution.get_violations_on_item(worn)
        self.assertEqual(['wear_sex'], [violation.condition_type for violation in violations])
        self.assertTrue(violations[0].is_red)
        self.assertTrue(violations[0].cant_equip)
        self.assertEqual(worn.localized_name, violations[0].item_name)


class AnUnknownWearerFlagsNothingTests(_Badge):

    def test_a_wearer_with_nothing_known_flags_no_piece(self):
        for version in VERSIONS:
            for field in ('classes', 'sexes', 'names', 'max_level'):
                piece, _slot = _the_piece(version, field, ('sexes',))
                with self.subTest(version=version, field=field):
                    self.assertEqual([], Wearer().reasons(piece))
            piece, _slot = _the_piece(version)
            with self.subTest(version=version, field='level'):
                self.assertEqual([], Wearer().reasons(piece))

    def test_a_build_without_a_known_level_flags_no_piece_for_its_level(self):
        piece, slot = _the_piece('dofus3')
        char = self._make('dofus3', piece, slot, level=200)
        Char.objects.filter(pk=char.pk).update(level=0)
        char.refresh_from_db()
        self.assertIsNone(Wearer.of(char).level)
        self._flags_nothing(char)

    def test_a_stored_build_without_the_newer_fields_neither_crashes_nor_flags(self):
        piece, slot = _the_piece('dofus3')
        char = self._make('dofus3', piece, slot, level=200)
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution')
        for key in ('char_class', 'origin'):
            minimal.input.pop(key, None)
        for field in ('stats', 'exo_assumed', 'exo_option_tops_owned', 'proven'):
            minimal.__dict__.pop(field, None)
        minimal.stats = {}
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        self._flags_nothing(char)

    def test_a_result_built_without_a_wearer_checks_no_wearer_condition(self):
        piece, slot = _the_piece('dofus3')
        char = self._make('dofus3', piece, slot, level=5)
        set_current_game_version('dofus3')
        result = model_result_from_minimal(read_char_blob(char.minimal_solution, None, 'minimal_solution'))
        self.assertIsNone(result.wearer)
        self.assertEqual([], [item.slot for item in result.item_list
                              if item.item_added and result.get_violations_on_item(item)])
        result.wearer = Wearer.of(char)
        self.assertEqual([slot], [item.slot for item in result.item_list
                                  if item.item_added and result.get_violations_on_item(item)])


class APieceWithOrConditionsIsRedWhenNoBranchHoldsTests(_Badge):

    def _levels(self, piece):
        return sorted({max(level_to_wear(piece), 1), 200})

    def _ap_mp_build(self, version, piece, slot, level, ap, mp):
        char = self._make(version, piece, slot, level=level, bare=True)
        self._with_totals(char, {'ap': ap, 'mp': mp})
        return char

    def test_a_piece_asking_for_few_ap_or_few_mp_is_red_when_both_are_exceeded(self):
        for version in AP_MP_OR_VERSIONS:
            piece, slot, limit = _or_piece(version, ('ap', 'mp'), True)
            for level in self._levels(piece):
                with self.subTest(version=version, level=level):
                    self._flags_only(self._ap_mp_build(
                        version, piece, slot, level,
                        limit['ap'] + 1, limit['mp'] + 1), slot)

    def test_a_piece_asking_for_few_ap_or_few_mp_is_not_red_when_one_of_them_holds(self):
        for version in AP_MP_OR_VERSIONS:
            piece, slot, limit = _or_piece(version, ('ap', 'mp'), True)
            for level in self._levels(piece):
                for ap, mp in ((limit['ap'], limit['mp'] + 1),
                               (limit['ap'] + 1, limit['mp']),
                               (limit['ap'], limit['mp'])):
                    with self.subTest(version=version, level=level, ap=ap, mp=mp):
                        self._flags_nothing(self._ap_mp_build(
                            version, piece, slot, level, ap, mp))

    def test_twelve_ap_and_six_mp_mark_the_slot_red_on_the_page_and_eleven_ap_does_not(self):
        piece, slot, limit = _or_piece('dofus3', ('ap', 'mp'), True)
        self.assertEqual({'ap': 11, 'mp': 5}, limit)
        self.assertEqual({slot}, self._red_slots_on_the_page(
            self._ap_mp_build('dofus3', piece, slot, 200, 12, 6)))
        self.assertEqual(set(), self._red_slots_on_the_page(
            self._ap_mp_build('dofus3', piece, slot, 200, 11, 6)))
        self.assertEqual(set(), self._red_slots_on_the_page(
            self._ap_mp_build('dofus3', piece, slot, 200, 12, 5)))

    def test_twelve_ap_and_six_mp_hide_the_build_from_the_gallery_and_eleven_ap_does_not(self):
        piece, slot, _limit = _or_piece('dofus3', ('ap', 'mp'), True)
        too_many = self._ap_mp_build('dofus3', piece, slot, 200, 12, 6)
        cache.clear()
        self.assertIsNone(self._card(too_many, hide_invalid=True))
        cache.clear()
        self.assertIn(BADGE, self._card(too_many, hide_invalid=False))
        within = self._ap_mp_build('dofus3', piece, slot, 200, 11, 6)
        cache.clear()
        card = self._card(within, hide_invalid=True)
        self.assertIsNotNone(card)
        self.assertNotIn(BADGE, card)

    def test_a_piece_asking_for_one_stat_or_another_is_red_until_one_of_them_is_reached(self):
        for version in OR_VERSIONS:
            piece, slot, limit = _or_piece(version, _min_stat_keys(version), False)
            key = sorted(limit)[0]
            for level in self._levels(piece):
                with self.subTest(version=version, level=level):
                    char = self._make(version, piece, slot, level=level, bare=True)
                    self._flags_only(char, slot)
                    self._with_spent(char, key, limit[key] - 1)
                    self._flags_only(char, slot)
                    self._with_spent(char, key, limit[key])
                    self._flags_nothing(char)

    def test_the_reason_lists_the_branches_with_the_wording_of_the_item_page(self):
        piece, slot, _limit = _or_piece('dofus3', ('ap', 'mp'), True)
        char = self._ap_mp_build('dofus3', piece, slot, 200, 12, 6)
        expected = {'en': 'AP < 12 or MP < 6', 'fr': 'PA < 12 ou PM < 6',
                    'es': 'PA < 12 o PM < 6', 'pt': 'PA < 12 ou PM < 6',
                    'de': 'AP < 12 oder BP < 6'}
        for language, text in expected.items():
            with self.subTest(language=language), translation.override(language):
                solution = get_solution(char)
                worn = next(item for item in solution.item_list if item.slot == slot)
                violations = solution.get_violations_on_item(worn)
                self.assertEqual(['or'], [v.condition_type for v in violations])
                self.assertEqual(text, violations[0].stat_name)
                self.assertTrue(violations[0].is_red)

    def test_a_worn_piece_from_a_stored_result_without_or_conditions_flags_nothing(self):
        piece, slot, limit = _or_piece('dofus3', ('ap', 'mp'), True)
        char = self._ap_mp_build('dofus3', piece, slot, 200,
                                 limit['ap'] + 1, limit['mp'] + 1)
        solution = get_solution(char)
        worn = next(item for item in solution.item_list if item.slot == slot)
        self.assertTrue(solution.get_violations_on_item(worn))
        del worn.or_conditions
        self.assertEqual([], solution.get_violations_on_item(worn))


def _min_stat_keys(version):
    """The stats of the first plain piece whose OR branches each ask for a minimum."""
    structure = get_structure(version)
    for piece, _slot in _pieces(version, 'or_conditions'):
        gates = [gate for branch in piece.or_conditions for gate in branch]
        if all(not is_max for _stat, is_max, _value in gates) and all(
                len(branch) == 1 for branch in piece.or_conditions):
            return tuple(structure.get_stat_by_id(stat_id).key
                         for stat_id, _is_max, _value in gates)
    raise AssertionError('no %s piece asks only for minimum OR branches' % version)


class ASwitchOfSexReachesTheGalleryWithoutWaitingTests(_Badge):

    def _one_sex_build(self):
        piece, slot = _the_piece('dofus3', 'sexes')
        return piece, slot, self._make('dofus3', piece, slot, gender=piece.sexes[0])

    def _switch_to(self, char, gender):
        answer = self.client.post('/setchargender/%d/' % char.id,
                                  {'gender': str(gender)})
        self.assertEqual(200, answer.status_code)
        char.refresh_from_db()
        self.assertEqual(gender, char.gender)

    def test_the_meta_cache_key_follows_the_sex_of_the_character(self):
        _piece, _slot, char = self._one_sex_build()
        before = _meta_cache_key(char.pk, char.modified_time, char.game_version,
                                 char.gender)
        self.assertNotEqual(before, _meta_cache_key(
            char.pk, char.modified_time, char.game_version, 1 - char.gender))

    def test_the_badge_and_the_refusal_follow_a_switch_of_sex_without_a_cache_clear(self):
        piece, slot, char = self._one_sex_build()
        with translation.override('en'):
            self.assertFalse(_get_shared_build_meta(char)['has_condition_issues'])
            self.assertIsNone(refusal_reason(char))
            self._switch_to(char, 1 - piece.sexes[0])
            self.assertTrue(_get_shared_build_meta(char)['has_condition_issues'])
            self.assertEqual('conditions', refusal_reason(char))
            self._switch_to(char, piece.sexes[0])
            self.assertFalse(_get_shared_build_meta(char)['has_condition_issues'])
            self.assertIsNone(refusal_reason(char))

    def test_the_hide_invalid_filter_follows_a_switch_of_sex_without_a_cache_clear(self):
        piece, slot, char = self._one_sex_build()
        self.assertIsNotNone(self._card(char, hide_invalid=True))
        self._switch_to(char, 1 - piece.sexes[0])
        self.assertIsNone(self._card(char, hide_invalid=True))
        self._switch_to(char, piece.sexes[0])
        self.assertIsNotNone(self._card(char, hide_invalid=True))
