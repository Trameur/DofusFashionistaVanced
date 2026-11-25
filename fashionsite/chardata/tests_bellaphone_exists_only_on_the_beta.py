# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Bellaphone, the Dofus 3.8 class, is offered on the Beta and on each version once its game files carry it, and plays there with its own spells."""
from unittest import skipIf

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.spell_reference import get_spell_reference

TOUCH_VERSIONS = ('touch', 'touchbeta')
LIVE_HAS_IT = 'Bellaphone' in get_spell_reference('dofus3')
OTHER_VERSIONS = (() if LIVE_HAS_IT else ('dofus3',)) + ('dofus2', 'retro') + tuple(
    version for version in ('touch',) if 'Bellaphone' not in get_spell_reference(version))
PYROLYSIS = 33311
GAME_NAMES = {'fr': 'Bellaphone', 'en': 'Bellaphone', 'es': 'Bel\u00edade',
              'pt': 'Bel\u00e9fone', 'de': 'Bellaphon'}


class BellaphoneIsListedOnTheBetaAloneTests(SimpleTestCase):

    def test_the_beta_lists_it(self):
        from chardata.version_compat import class_exists_in_version, filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        self.assertIn('Bellaphone', filter_classes_for_version(CHARACTER_CLASSES, 'beta'))
        self.assertTrue(class_exists_in_version('Bellaphone', 'beta'))

    def test_no_other_version_lists_it(self):
        from chardata.version_compat import class_exists_in_version, filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        for version in OTHER_VERSIONS:
            with self.subTest(version=version):
                self.assertNotIn('Bellaphone', filter_classes_for_version(CHARACTER_CLASSES, version))
                self.assertFalse(class_exists_in_version('Bellaphone', version))

    def test_touch_lists_it_exactly_when_its_spell_reference_has_it(self):
        from chardata.version_compat import class_exists_in_version
        for version in TOUCH_VERSIONS:
            with self.subTest(version=version):
                self.assertEqual('Bellaphone' in get_spell_reference(version),
                                 class_exists_in_version('Bellaphone', version))

    def test_the_beta_keeps_every_class_dofus3_has(self):
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        live = set(filter_classes_for_version(CHARACTER_CLASSES, 'dofus3'))
        beta = set(filter_classes_for_version(CHARACTER_CLASSES, 'beta'))
        self.assertEqual(set() if LIVE_HAS_IT else {'Bellaphone'}, beta - live)
        self.assertEqual(set(), live - beta)

    def test_dofus3_lists_it_once_its_spell_reference_does(self):
        from chardata.version_compat import class_exists_in_version
        self.assertEqual(LIVE_HAS_IT, class_exists_in_version('Bellaphone', 'dofus3'))

    def test_the_game_breed_is_21(self):
        from chardata.character_look import CLASS_TO_BREED
        self.assertEqual(21, CLASS_TO_BREED['Bellaphone'])
        self.assertEqual(1, list(CLASS_TO_BREED.values()).count(21))

    def test_the_beta_constants_list_it_too(self):
        from fashionistapulp import dofus_constants_beta
        self.assertIn('Bellaphone', dofus_constants_beta.CHARACTER_CLASSES)

    def test_the_quick_start_offers_it_on_the_beta_with_its_own_figure(self):
        from chardata.home_view import quick_start_classes
        beta = {entry['key']: entry for entry in quick_start_classes('beta')}
        self.assertIn('Bellaphone', beta)
        self.assertIn('designs/wizard/Bellaphone/myWizardBellaphone1.png', beta['Bellaphone']['figure'])
        for version in OTHER_VERSIONS:
            with self.subTest(version=version):
                self.assertNotIn('Bellaphone', [e['key'] for e in quick_start_classes(version)])


class BellaphoneIsNamedInFiveLanguagesTests(SimpleTestCase):

    def test_each_language_uses_the_name_the_game_gives(self):
        from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
        for language, name in GAME_NAMES.items():
            with self.subTest(language=language), translation.override(language):
                self.assertEqual(name, str(LOCALIZED_CHARACTER_CLASSES['Bellaphone']))

    def test_the_five_catalogues_carry_the_entry(self):
        import os
        import re
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locale')
        for language, name in GAME_NAMES.items():
            path = os.path.join(root, language, 'LC_MESSAGES', 'django.po')
            with self.subTest(language=language):
                with open(path, encoding='utf-8') as handle:
                    text = handle.read()
                found = re.search(r'msgid "Bellaphone"\r?\nmsgstr "([^"]*)"', text)
                self.assertIsNotNone(found)
                self.assertEqual('' if language == 'en' else name, found.group(1))


class BellaphonePlaysOnTheBetaTests(TestCase):

    def test_the_beta_awaits_the_data_of_no_class(self):
        from chardata.presets import version_class
        from chardata.setup_preview import panel_context
        from chardata.version_compat import CLASSES_AWAITING_DATA, classes_with_data
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        self.assertEqual(set(), set(CLASSES_AWAITING_DATA.get('beta', ())))
        self.assertIn('Bellaphone', classes_with_data(CHARACTER_CLASSES, 'beta'))
        self.assertIn(version_class('Nobody', 'beta'), classes_with_data(CHARACTER_CLASSES, 'beta'))
        self.assertTrue(panel_context('beta')['sections'])

    def test_the_setup_preview_answers_for_it(self):
        from chardata.setup_preview import DEFAULT_PLAY_MODE, DEFAULT_PRIORITY, preview_state
        state = preview_state('beta', 'Bellaphone', 200, frozenset(), DEFAULT_PRIORITY,
                              DEFAULT_PLAY_MODE, False)
        self.assertIn('weights', state)

    def test_the_class_profile_carries_the_reach_its_best_turn_reads(self):
        from chardata.class_reach import reach_shares
        from chardata.smart_build import RACE_TO_BUILD_PROFILE, param_for_build
        self.assertIn('Bellaphone', RACE_TO_BUILD_PROFILE)
        for param, measured in reach_shares('beta', 'Bellaphone').items():
            with self.subTest(param=param):
                self.assertEqual(measured, param_for_build('Bellaphone', set(), param,
                                                           game_version='beta'))

    def test_the_class_profile_carries_the_vitality_weight_its_hp_shares_read(self):
        from chardata.class_reach import vit_importance
        from chardata.smart_build import param_for_build
        self.assertEqual(vit_importance('beta', 'Bellaphone'),
                         param_for_build('Bellaphone', set(), 'vit_importance', game_version='beta'))

    def test_the_bellaphone_casts_its_damage_spells_on_the_beta(self):
        from chardata.management.commands.store_default_elements import (
            TOP_LEVEL, element_turns, gear_line)
        from chardata.spell_buffs import get_damage_spells_for_version
        own = {spell.name for spell in get_damage_spells_for_version('beta')['Bellaphone']}
        turns = element_turns('beta', 'Bellaphone', gear_line('beta'), TOP_LEVEL)
        for element, (turn, orders) in turns.items():
            with self.subTest(element=element):
                self.assertGreater(turn, 0)
                cast = {name for order in orders.values() for name, _damage in order}
                self.assertTrue(cast)
                self.assertEqual(set(), cast - own)

    def test_the_beta_default_element_table_lists_it_at_every_level(self):
        from chardata.management.commands.store_default_elements import LEVELS, stored_table
        table = stored_table('beta')['classes']['Bellaphone']
        self.assertEqual({str(level) for level in LEVELS}, set(table))
        for level, entry in table.items():
            with self.subTest(level=level):
                self.assertEqual(max(entry['turns'].values()), entry['turns'][entry['element']])

    def test_a_player_can_write_its_name_in_any_language(self):
        from chardata.nl_parser import _CLASS_ALIAS_INDEX, _normalize
        for name in GAME_NAMES.values():
            with self.subTest(name=name):
                self.assertEqual('Bellaphone', _CLASS_ALIAS_INDEX[_normalize(name)])

    def test_a_build_read_from_a_breed_id_finds_it(self):
        from chardata.fashionista_build import _class_of
        self.assertEqual('Bellaphone', _class_of(21))
        self.assertEqual('Bellaphone', _class_of('bellaphone'))

    @skipIf(LIVE_HAS_IT, 'dofus3 has the class')
    def test_a_dofus3_page_does_not_offer_it_as_the_class_of_a_build(self):
        from chardata.presets import version_class
        self.assertNotEqual('Bellaphone', version_class('Bellaphone', 'dofus3'))


def _select_options(html):
    import re
    block = re.search(r'<select[^>]*id="select-char-class".*?</select>', html, re.S).group(0)
    return re.findall(r'<option value="([^"]*)"', block)


class TheSetupClassSelectFollowsTheVersionTests(TestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        self.addCleanup(set_current_game_version, 'dofus3')

    def options(self, version, language):
        from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
        html, _page = setup_page(self.client, version, language)
        return _select_options(html)

    def test_no_language_leaks_a_class_the_version_lacks(self):
        from chardata.version_compat import CLASSES_NOT_IN_VERSION
        for version in OTHER_VERSIONS:
            for language in GAME_NAMES:
                with self.subTest(version=version, language=language):
                    options = self.options(version, language)
                    for absent in CLASSES_NOT_IN_VERSION.get(version, ()):
                        self.assertNotIn(absent, options)

    def test_forgelance_stays_out_of_dofus2_touch_and_retro(self):
        for version in ('dofus2', 'touch', 'retro'):
            for language in GAME_NAMES:
                with self.subTest(version=version, language=language):
                    self.assertNotIn('Forgelance', self.options(version, language))

    def test_the_beta_offers_it_in_every_language(self):
        for language in GAME_NAMES:
            with self.subTest(language=language):
                options = self.options('beta', language)
                self.assertIn('Bellaphone', options)
                self.assertIn('Forgelance', options)

    def test_the_select_starts_with_an_empty_option(self):
        for version in OTHER_VERSIONS + ('beta',):
            with self.subTest(version=version):
                self.assertEqual('', self.options(version, 'en')[0])


class TheSmartBuildReadsOnlyTheClassesOfItsVersionTests(TestCase):

    @skipIf(LIVE_HAS_IT, 'dofus3 has the class')
    def test_dofus3_does_not_read_it(self):
        from chardata.nl_parser import parse_build_request
        parsed = parse_build_request('bellaphone 200 terre pvm', 'dofus3')
        self.assertIsNone(parsed['char_class'])
        self.assertFalse(parsed['matched_class'])

    def test_the_beta_keeps_it(self):
        from chardata.nl_parser import parse_build_request
        parsed = parse_build_request('bellaphone 200 terre pvm', 'beta')
        self.assertEqual('Bellaphone', parsed['char_class'])
        self.assertTrue(parsed['matched_class'])

    @skipIf(LIVE_HAS_IT, 'dofus3 has the class')
    def test_a_posted_phrase_on_dofus3_asks_for_the_class(self):
        from chardata.models import Char
        before = Char.objects.count()
        response = self.client.post('/smartbuild/', {'q': 'bellaphone 200 terre pvm', 'confirm': '1'},
                                    HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, response.status_code)
        self.assertEqual(before, Char.objects.count())
        self.assertContains(response, 'Tell us which class')


class TheBetaReadsTheBellaphoneBookTests(SimpleTestCase):

    def book(self):
        from chardata.spell_reference import get_spell_reference
        return get_spell_reference('beta')['Bellaphone']

    def test_the_beta_spell_reference_names_every_bellaphone_spell_in_five_languages(self):
        for entry in self.book():
            for language in GAME_NAMES:
                with self.subTest(spell=entry['id'], language=language):
                    name = (entry.get('name') or {}).get(language) or ''
                    description = (entry.get('description') or {}).get(language) or ''
                    self.assertTrue(name.strip())
                    self.assertTrue(description.strip())
                    self.assertNotIn('[!]', name + description)

    def test_no_spell_of_another_class_lands_in_the_bellaphone_book(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        from chardata.spell_reference import get_spell_reference
        own = {entry['id'] for entry in self.book()}
        damage = get_damage_spells_for_version('beta')
        own_damage = {spell.spell_id for spell in damage['Bellaphone']}
        self.assertTrue(own_damage)
        self.assertEqual(set(), own_damage - own)
        for char_class, entries in get_spell_reference('beta').items():
            if char_class == 'Bellaphone':
                continue
            with self.subTest(char_class=char_class):
                self.assertEqual(set(), own & {entry['id'] for entry in entries or []})
                self.assertEqual(set(), own_damage & {spell.spell_id
                                                      for spell in damage.get(char_class) or []})

    def test_every_bellaphone_damage_spell_has_its_icon(self):
        import os
        from chardata.spell_buffs import get_damage_spells_for_version
        from chardata.spells_view import _spell_icon_name
        directory = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'static', 'chardata', 'spells', 'beta')
        for spell in get_damage_spells_for_version('beta')['Bellaphone']:
            with self.subTest(spell=spell.name):
                name = _spell_icon_name(spell.name, spell.spell_id, 'beta')
                self.assertTrue(os.path.isfile(os.path.join(directory, '%s.png' % name)))

    def test_a_spell_branching_on_the_bellaura_size_lands_one_row_per_cast(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        branching = [spell for spell in get_damage_spells_for_version('beta')['Bellaphone']
                     if spell.spell_id == PYROLYSIS]
        self.assertEqual(1, len(branching))
        rows = len(branching[0].effects.non_crit_ranges)
        self.assertGreater(rows, 1)
        self.assertEqual([[row] for row in range(rows)],
                         sorted(list(indexes) for _label, indexes in branching[0].aggregates))


def _bellaphone_groups():
    from chardata.spell_reference import get_spell_reference
    from chardata.spell_variants import get_variant_by_spell_id
    own = {entry['id'] for entry in get_spell_reference('beta')['Bellaphone']}
    groups = {}
    for spell_id, variant in get_variant_by_spell_id('beta').items():
        groups.setdefault(variant, set()).add(int(spell_id))
    return own, {variant: faces for variant, faces in groups.items() if faces & own}


def _bellaphone_spell(spell_id):
    from chardata.spell_buffs import get_damage_spells_for_version
    return next(spell for spell in get_damage_spells_for_version('beta')['Bellaphone']
                if spell.spell_id == spell_id)


class TheBellaphoneArmsOneFaceOfEachGroupTests(SimpleTestCase):

    def test_every_book_spell_sits_in_a_variant_group(self):
        from chardata.spell_variants import variant_of
        own, _groups = _bellaphone_groups()
        for spell_id in own:
            with self.subTest(spell=spell_id):
                self.assertIsNotNone(variant_of('beta', spell_id))

    def test_every_face_of_its_groups_is_in_its_book(self):
        own, groups = _bellaphone_groups()
        for variant, faces in groups.items():
            with self.subTest(variant=variant):
                self.assertEqual(set(), faces - own)

    def test_the_lineage_group_is_damage_spells_in_its_reference(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        _own, groups = _bellaphone_groups()
        lineage = [faces for faces in groups.values() if len(faces) > 2]
        self.assertEqual(1, len(lineage))
        damage = {spell.spell_id for spell in get_damage_spells_for_version('beta')['Bellaphone']}
        self.assertEqual(set(), lineage[0] - damage)

    def test_the_best_turn_casts_one_lineage_spell_at_most(self):
        from chardata.management.commands.store_default_elements import (
            TOP_LEVEL, element_turns, gear_line)
        _own, groups = _bellaphone_groups()
        lineage = next(faces for faces in groups.values() if len(faces) > 2)
        names = {_bellaphone_spell(spell_id).name for spell_id in lineage}
        turns = element_turns('beta', 'Bellaphone', gear_line('beta'), TOP_LEVEL)
        for element, (_turn, orders) in turns.items():
            for ap, order in orders.items():
                with self.subTest(element=element, ap=ap):
                    self.assertLessEqual(len({name for name, _damage in order} & names), 1)


class ABellauraSizeBranchIsNamedByItsCounterTests(SimpleTestCase):

    def labels(self):
        return [label for label, _indexes in _bellaphone_spell(PYROLYSIS).aggregates]

    def test_each_row_is_one_group_gated_on_one_counter(self):
        import re
        from chardata.spells_view import _COUNTER_LABEL
        counters = {_COUNTER_LABEL.match(label).group(1) for label in self.labels()}
        self.assertEqual(1, len(counters))
        rows = len(_bellaphone_spell(PYROLYSIS).effects.non_crit_ranges)
        self.assertEqual(list(range(rows)), sorted(
            index for _label, indexes in _bellaphone_spell(PYROLYSIS).aggregates
            for index in indexes))
        self.assertTrue(all(re.match(r'^Counter \d+[=<>]\d+$', label) for label in self.labels()))

    def test_the_counter_carries_its_game_name_in_five_languages(self):
        from chardata.spell_reference import state_name
        from chardata.spells_view import _COUNTER_LABEL, _localized_aggregate_label
        label = self.labels()[0]
        counter = _COUNTER_LABEL.match(label).group(1)
        for language in GAME_NAMES:
            with self.subTest(language=language), translation.override(language):
                name = state_name('beta', 'Ct' + counter, language)
                self.assertTrue(name)
                self.assertTrue(_localized_aggregate_label(label, 'beta').startswith(name))

    def test_the_turn_scores_the_group_listed_first(self):
        from chardata.management.commands.store_default_elements import TOP_LEVEL
        from chardata.spell_combo import castable_spells
        spell = next(spell for spell in castable_spells('Bellaphone', TOP_LEVEL, 'beta')
                     if spell.spell_id == PYROLYSIS)
        self.assertEqual(self.labels()[0], spell.scored_group)
