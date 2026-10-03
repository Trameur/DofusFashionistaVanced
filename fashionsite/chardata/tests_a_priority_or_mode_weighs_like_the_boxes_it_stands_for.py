# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""At its defaults the advanced section changes nothing; a priority weighs like its boxes, a mode ticks its own."""
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata import presets
from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.smart_build import (ALL_ASPECTS, get_standard_weights, level_minimums,
                                  reapply_weights)
from fashionistapulp.game_versions import GAME_VERSIONS
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
KOLOSSIUM = {'koli_1v1', 'koli_2v2', 'koli_3v3'}
NEW_LABELS = ('No priority', 'Defense', 'General (all content)', 'Solo PvM', 'Kolossium 1v1',
              'Kolossium 2v2', 'Kolossium 3v3', 'Aggression 1v1',
              'Group PvP (prisms, perceptors)', 'Advanced options', 'Priority', 'Safeguard',
              'Changing the priority or the mode in the Options column always restarts the '
              'wizard.',
              'Mode: %(mode)s · Priority: %(priority)s',
              'For monster fights on your own, without the PvP changes.',
              'For 1 vs. 1 PvP: the same as group PvP, with initiative mattering a lot more.',
              'For PvP: AP and MP parry, critical resistance and initiative matter more, and '
              'prospecting not at all.',
              'For PvP: resistances in PvP and initiative matter more, and prospecting not at '
              'all.')


def _path(version, path):
    return path if version == 'dofus3' else '/%s%s' % (version, path)


def _blob(char, field, default):
    return read_char_blob(getattr(char, field), default, field, char)


def _options(char):
    return _blob(char, 'options', {})


def _weights_of(char, aspects):
    return get_standard_weights(Char(char_class=char.char_class, level=char.level,
                                     game_version=char.game_version,
                                     aspects=pickle.dumps(set(aspects))))


class TheRegistryOffersEachVersionItsOwnModesTests(SimpleTestCase):

    def test_every_dofus_version_lists_its_modes_with_the_default_first(self):
        for key, version in GAME_VERSIONS.items():
            if not version.dofus:
                continue
            with self.subTest(version=key):
                modes = [mode for mode, _label in presets.play_modes(key)]
                self.assertEqual(presets.DEFAULT_PLAY_MODE, modes[0])
                self.assertIn('pvm_solo', modes)
                self.assertLessEqual(set(modes), set(presets.PLAY_MODE_BY_KEY))
                self.assertEqual(len(modes), len(set(modes)))

    def test_the_kolossium_formats_follow_each_version(self):
        offered = {version: {mode for mode, _label in presets.play_modes(version)}
                   for version in VERSIONS}
        self.assertEqual(KOLOSSIUM, offered['dofus3'] & KOLOSSIUM)
        self.assertEqual(KOLOSSIUM, offered['dofus2'] & KOLOSSIUM)
        self.assertEqual(KOLOSSIUM, offered['beta'] & KOLOSSIUM)
        self.assertEqual({'koli_1v1', 'koli_3v3'}, offered['touch'] & KOLOSSIUM)
        self.assertEqual(set(), offered['retro'] & KOLOSSIUM)
        self.assertEqual({'general', 'pvm_solo', 'aggression_1v1', 'group_pvp'},
                         offered['retro'])

    def test_every_mode_ticks_only_option_boxes_its_versions_offer(self):
        for version in VERSIONS:
            option_boxes = set(presets.version_presets(version)['option_boxes'])
            for mode, ticked in presets.mode_boxes(version).items():
                with self.subTest(version=version, mode=mode):
                    self.assertLessEqual(set(ticked), option_boxes)
                    self.assertEqual(mode == presets.DEFAULT_PLAY_MODE, not ticked)

    def test_each_option_box_stands_for_a_mode_that_ticks_it(self):
        for version in VERSIONS:
            offered = dict(presets.play_modes(version))
            stands_for = presets.version_presets(version)['box_modes']
            with self.subTest(version=version):
                self.assertEqual(set(presets.version_presets(version)['option_boxes']),
                                 set(stands_for))
                for box, mode in stands_for.items():
                    self.assertIn(mode, offered)
                    self.assertIn(box, presets.PLAY_MODE_BY_KEY[mode].boxes)
                self.assertEqual({'pvp'}, set(presets.PLAY_MODE_BY_KEY[stands_for['pvp']].boxes))

    def test_the_options_column_lists_every_mode_but_the_default_one(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual([key for key, _label in presets.play_modes(version)][1:],
                                 [key for key, _label in presets.option_column_modes(version)])

    def test_a_duel_mode_ticks_both_pvp_boxes_and_a_group_mode_only_group_pvp(self):
        both = {'pvp': True, 'duel': True}
        group = {'pvp': True, 'duel': False}
        self.assertEqual(both, presets.mode_boxes('dofus3')['koli_1v1'])
        self.assertEqual(group, presets.mode_boxes('dofus3')['koli_3v3'])
        self.assertEqual(group, presets.mode_boxes('dofus2')['koli_2v2'])
        self.assertEqual(both, presets.mode_boxes('retro')['aggression_1v1'])
        self.assertEqual(group, presets.mode_boxes('retro')['group_pvp'])
        self.assertEqual({'pvp': False, 'duel': False}, presets.mode_boxes('touch')['pvm_solo'])

    def test_each_priority_stands_for_existing_focus_boxes(self):
        focus = {aspect for column in presets.FOCUS_COLUMNS for aspect in column}
        expected = {'balanced': set(), 'damage': {'glasscannon'}, 'defense': {'vit', 'res'},
                    'heals': {'heal'}}
        self.assertEqual(expected, {priority.key: set(priority.aspects)
                                    for priority in presets.PRIORITIES})
        for priority in presets.PRIORITIES:
            self.assertLessEqual(set(priority.aspects), ALL_ASPECTS & focus)
        self.assertEqual(presets.DEFAULT_PRIORITY, presets.PRIORITIES[0].key)

    def test_the_safeguard_defaults_to_ten_percent_among_its_choices(self):
        self.assertEqual(10, presets.GUARD_DEFAULT_PERCENT)
        self.assertIn(presets.GUARD_DEFAULT_PERCENT, presets.GUARD_PERCENTS)

    def test_every_new_label_is_translated_in_four_languages(self):
        for language in ('fr', 'es', 'pt', 'de'):
            with translation.override(language):
                for label in NEW_LABELS:
                    with self.subTest(language=language, label=label):
                        self.assertNotEqual(label, translation.gettext(label))

    def test_the_damage_and_heals_priorities_have_their_own_wording(self):
        for language in ('fr', 'es', 'pt', 'de'):
            with translation.override(language):
                for key, msgid in (('damage', 'Damage'), ('heals', 'Heals')):
                    with self.subTest(language=language, priority=key):
                        label = str(presets.PRIORITY_BY_KEY[key].label)
                        self.assertEqual(translation.pgettext('Priority', msgid), label)
                        self.assertNotEqual(msgid, label)
        with translation.override('fr'):
            self.assertEqual('Dégâts', str(presets.PRIORITY_BY_KEY['damage'].label))
            self.assertEqual('Dommages', translation.gettext('Damage'))

    def test_the_kolossium_takes_the_name_ankama_gives_it_in_each_language(self):
        names = {'en': 'Kolossium', 'fr': 'Kolizéum', 'es': 'Koliseo', 'pt': 'Koliseu',
                 'de': 'Kolosseum'}
        for language, name in names.items():
            with translation.override(language):
                self.assertEqual('%s 3v3' % name, str(presets.PLAY_MODE_BY_KEY['koli_3v3'].label))


class _SetupMixin(object):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('advanced-setup', 'advanced@test.local',
                                              'pw-advanced-setup-4')
        self.client.force_login(self.owner)

    def create(self, version, char_class, level, aspects, extra=None, button='wizard'):
        set_current_game_version(version)
        data = {'project': 'p', 'charname': '', 'class': char_class, 'level': str(level),
                button: button}
        data.update(('check_%s' % aspect, 'on') for aspect in aspects)
        data.update(extra or {})
        response = self.client.post(_path(version, '/createproject/'), data)
        self.assertEqual(302, response.status_code)
        return Char.objects.order_by('-id').first()

    def save(self, char, aspects, extra=None, reapply=True):
        set_current_game_version(char.game_version)
        data = {'project': 'p', 'charname': '', 'class': char.char_class,
                'level': str(char.level)}
        data.update(('check_%s' % aspect, 'on') for aspect in aspects)
        if reapply:
            data['reapply'] = 'reapply'
        data.update(extra or {})
        response = self.client.post(_path(char.game_version, '/saveproject/%d/' % char.id), data)
        self.assertEqual(200, response.status_code)
        char.refresh_from_db()
        return char, json.loads(response.content.decode('utf-8'))

    def record(self, char):
        return (_blob(char, 'aspects', set()), char.char_build,
                _blob(char, 'stats_weight', {}), _blob(char, 'minimum_stats', {}),
                {key: value for key, value in _options(char).items()
                 if key not in ('dofuses', 'dofusnotforchar')})


class TheClosedSectionChangesNothingTests(_SetupMixin, TestCase):

    def test_the_default_choices_give_the_build_a_form_without_them_gives(self):
        cases = (('dofus3', 'Iop', 200, {'str'}), ('beta', 'Cra', 150, {'agi', 'pvp'}),
                 ('dofus2', 'Eniripsa', 100, {'int', 'heal'}),
                 ('touch', 'Sram', 199, {'agi', 'pvp', 'duel', 'vit'}),
                 ('retro', 'Sacrier', 200, {'omni', 'str', 'int', 'cha', 'agi', 'res'}),
                 ('dofus3', 'Enutrof', 60, {'pp'}))
        defaults = {'priority': presets.DEFAULT_PRIORITY,
                    'play_mode': presets.DEFAULT_PLAY_MODE}
        for version, char_class, level, aspects in cases:
            for button in ('wizard', 'byhand'):
                with self.subTest(version=version, char_class=char_class, button=button):
                    without = self.create(version, char_class, level, aspects, button=button)
                    with_defaults = self.create(version, char_class, level, aspects, defaults,
                                                button=button)
                    self.assertEqual(self.record(without), self.record(with_defaults))
                    self.assertNotIn('priority', _options(with_defaults))
                    self.assertNotIn('play_mode', _options(with_defaults))

    def test_saving_a_build_at_its_defaults_leaves_its_options_untouched(self):
        char = self.create('dofus3', 'Iop', 200, {'str'})
        before = char.options
        char, state = self.save(char, {'str'}, {'priority': 'balanced', 'play_mode': 'general'})
        self.assertEqual(before, char.options)
        self.assertEqual(('balanced', 'general'), (state['priority'], state['play_mode']))

    def test_the_setup_page_folds_the_section_and_starts_at_the_defaults(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                page = self.client.get(_path(version, '/setup/')).content.decode('utf-8')
                details = re.search(r'<details[^>]*advanced-options[^>]*>', page)
                self.assertIsNotNone(details)
                self.assertNotIn(' open', details.group(0))
                radios = re.findall(r'<input[^>]*name="?priority"?[^>]*>', page)
                self.assertEqual([key for key, _label in presets.priorities()],
                                 [re.search(r'value="?(\w+)', tag).group(1) for tag in radios])
                self.assertEqual(['checked' in tag for tag in radios],
                                 [key == presets.DEFAULT_PRIORITY
                                  for key, _label in presets.priorities()])
                self.assertIsNone(re.search(r'<select[^>]*name="?play_mode', page))
                self.assertNotIn('Game mode', page)
                self.assertEqual(presets.mode_boxes(version), json.loads(
                    re.search(r'var modeBoxes = (.*?);', page).group(1)))

    def test_the_options_column_lists_the_modes_of_the_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                page = self.client.get(_path(version, '/setup/'),
                                       HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
                layout = json.loads(re.search(r'var modeLayout = (.*?);\n', page).group(1))
                self.assertEqual([[key, str(label)] for key, label
                                  in presets.option_column_modes(version)], layout)
                hidden = re.search(r'<input[^>]*name="?play_mode"?[^>]*>', page).group(0)
                self.assertRegex(hidden, r'type="?hidden')
                self.assertRegex(hidden, r'value="?general"?')
                tips = re.search(r'var modeToTip = \{(.*?)\n\};', page, re.S).group(1)
                for key, _label in presets.option_column_modes(version):
                    self.assertRegex(tips, r"\n    %s: '[^']+'" % key)

    def test_the_safeguard_starts_at_ten_percent_and_is_sent(self):
        page = self.client.get('/setup/').content.decode('utf-8')
        tag = re.search(r'<select[^>]*guard-percent[^>]*>(.*?)</select>', page, re.S)
        self.assertIsNotNone(tag)
        opening = tag.group(0)[:tag.group(0).index('>') + 1]
        self.assertNotIn('disabled', opening)
        self.assertRegex(opening, r'name="?guard_pct"?[ >]')
        options = re.findall(r'<option([^>]*)>', tag.group(1))
        values = [re.search(r'value="?(\d+)', option).group(1) for option in options]
        self.assertEqual([str(p) for p in presets.GUARD_PERCENTS], values)
        self.assertEqual(['10'], [value for option, value in zip(options, values)
                                  if 'selected' in option])

    def test_a_chosen_safeguard_is_stored_and_read_back(self):
        char = self.create('dofus3', 'Iop', 200, {'str'}, {'priority': 'damage',
                                                          'guard_pct': '20'})
        self.assertEqual(20, _options(char)['guard_pct'])
        char, state = self.save(char, {'str'}, {'priority': 'damage', 'guard_pct': '5'},
                                reapply=False)
        self.assertEqual(5, _options(char)['guard_pct'])
        self.assertEqual(5, state['guard_pct'])
        char, state = self.save(char, {'str'}, {'priority': 'damage', 'guard_pct': '10'},
                                reapply=False)
        self.assertNotIn('guard_pct', _options(char))
        self.assertEqual(10, state['guard_pct'])


class APriorityWeighsLikeItsBoxesTests(_SetupMixin, TestCase):

    def test_each_priority_gives_the_weights_and_minimums_of_its_boxes(self):
        for version in VERSIONS:
            for priority in presets.PRIORITIES[1:]:
                with self.subTest(version=version, priority=priority.key):
                    chosen = self.create(version, 'Eniripsa', 200, {'int'},
                                         {'priority': priority.key})
                    ticked = self.create(version, 'Eniripsa', 200, {'int'} | priority.aspects)
                    self.assertEqual(_blob(ticked, 'stats_weight', {}),
                                     _blob(chosen, 'stats_weight', {}))
                    self.assertEqual(_blob(ticked, 'minimum_stats', {}),
                                     _blob(chosen, 'minimum_stats', {}))
                    self.assertEqual({'int'}, _blob(chosen, 'aspects', set()))
                    self.assertEqual(self.create(version, 'Eniripsa', 200, {'int'}).char_build,
                                     chosen.char_build)
                    self.assertEqual(priority.key, _options(chosen)['priority'])

    def test_a_priority_adds_to_the_focus_boxes_without_counting_against_the_limit(self):
        char = self.create('dofus3', 'Iop', 200, {'str', 'crit', 'pushback'},
                           {'priority': 'defense'})
        self.assertEqual(_weights_of(char, {'str', 'crit', 'pushback', 'vit', 'res'}),
                         _blob(char, 'stats_weight', {}))
        self.assertEqual({'str', 'crit', 'pushback'}, _blob(char, 'aspects', set()))

    def test_an_unknown_priority_reads_as_none(self):
        char = self.create('dofus3', 'Iop', 200, {'str'}, {'priority': 'speed'})
        self.assertNotIn('priority', _options(char))
        self.assertEqual(_weights_of(char, {'str'}), _blob(char, 'stats_weight', {}))

    def test_minimums_stay_those_of_the_level(self):
        char = self.create('touch', 'Osamodas', 150, {'cha', 'summon'},
                           {'priority': 'damage'})
        self.assertEqual(level_minimums(char, {'cha', 'summon'}),
                         _blob(char, 'minimum_stats', {}))


class AModeTicksItsOptionBoxesTests(_SetupMixin, TestCase):

    def test_a_kolossium_mode_sets_the_pvp_boxes_it_stands_for(self):
        group = self.create('dofus3', 'Iop', 200, {'str', 'duel'}, {'play_mode': 'koli_3v3'})
        self.assertEqual({'str', 'pvp'}, _blob(group, 'aspects', set()))
        duel = self.create('dofus2', 'Iop', 200, {'str'}, {'play_mode': 'koli_1v1'})
        self.assertEqual({'str', 'pvp', 'duel'}, _blob(duel, 'aspects', set()))
        self.assertEqual(_weights_of(duel, {'str', 'pvp', 'duel'}),
                         _blob(duel, 'stats_weight', {}))
        self.assertEqual('koli_1v1', _options(duel)['play_mode'])

    def test_the_retro_group_mode_tip_names_what_the_pvp_box_moves_on_retro(self):
        set_current_game_version('retro')
        page = self.client.get('/retro/setup/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertEqual('For PvP: resistances in PvP and initiative matter more, and prospecting '
                         'not at all.', re.search(r"\n    group_pvp: '([^']+)'", page).group(1))
        char = Char(char_class='Iop', level=200, game_version='retro')
        plain, pvp = _weights_of(char, {'str'}), _weights_of(char, {'str', 'pvp'})
        for key in ('apres', 'mpres', 'crires'):
            self.assertEqual(0, pvp[key], key)
        self.assertGreater(pvp['init'], plain['init'])
        self.assertGreater(pvp['pvpearthresper'], plain.get('pvpearthresper', 0))
        self.assertEqual(0, pvp['pp'])

    def test_retro_offers_aggression_and_group_pvp_on_the_same_boxes(self):
        aggression = self.create('retro', 'Iop', 200, {'str'}, {'play_mode': 'aggression_1v1'})
        self.assertEqual({'str', 'pvp', 'duel'}, _blob(aggression, 'aspects', set()))
        group = self.create('retro', 'Iop', 200, {'str', 'duel'}, {'play_mode': 'group_pvp'})
        self.assertEqual({'str', 'pvp'}, _blob(group, 'aspects', set()))

    def test_solo_pvm_clears_the_pvp_boxes_and_general_keeps_them(self):
        solo = self.create('touch', 'Iop', 200, {'str', 'pvp', 'duel'},
                           {'play_mode': 'pvm_solo'})
        self.assertEqual({'str'}, _blob(solo, 'aspects', set()))
        general = self.create('touch', 'Iop', 200, {'str', 'pvp'}, {'play_mode': 'general'})
        self.assertEqual({'str', 'pvp'}, _blob(general, 'aspects', set()))

    def test_a_ticked_mode_weighs_like_the_old_boxes_it_posts(self):
        for version in VERSIONS:
            for box, mode in presets.version_presets(version)['box_modes'].items():
                with self.subTest(version=version, mode=mode):
                    posted = presets.PLAY_MODE_BY_KEY[mode].boxes
                    ticked = self.create(version, 'Iop', 200, {'str'} | posted,
                                         {'play_mode': mode})
                    boxes = self.create(version, 'Iop', 200, {'str'} | posted)
                    self.assertEqual(self.record(boxes)[:4], self.record(ticked)[:4])
                    self.assertEqual(mode, _options(ticked)['play_mode'])

    def test_an_untouched_build_saved_from_the_page_keeps_its_boxes_and_weights(self):
        for aspects in ({'str', 'pvp'}, {'str', 'duel'}, {'str', 'pvp', 'duel'}):
            with self.subTest(aspects=sorted(aspects)):
                char = self.create('dofus3', 'Iop', 200, aspects)
                before = self.record(char)
                char, state = self.save(char, aspects, {'priority': 'balanced',
                                                        'play_mode': 'general'})
                self.assertEqual(before, self.record(char))
                self.assertEqual('general', state['play_mode'])

    def test_a_mode_the_version_does_not_offer_is_the_default_one(self):
        for version, mode in (('retro', 'koli_3v3'), ('touch', 'koli_2v2'),
                              ('beta', 'group_pvp'), ('dofus3', 'group_pvp')):
            with self.subTest(version=version, mode=mode):
                char = self.create(version, 'Iop', 200, {'str', 'duel'}, {'play_mode': mode})
                self.assertEqual({'str', 'duel'}, _blob(char, 'aspects', set()))
                self.assertNotIn('play_mode', _options(char))


class TheChoicesStayWithTheBuildTests(_SetupMixin, TestCase):

    def test_the_edit_page_reads_back_the_stored_choices(self):
        char = self.create('dofus3', 'Iop', 200, {'str'},
                           {'priority': 'heals', 'play_mode': 'koli_3v3'})
        page = self.client.get('/project/%d/' % char.id).content.decode('utf-8')
        state = json.loads(re.search(r'var initialState = (\{.*?\});', page).group(1))
        self.assertEqual(('heals', 'koli_3v3', 'koli_3v3'),
                         (state['priority'], state['play_mode'], state['shown_mode']))
        self.assertTrue(state['char_build_aspects']['pvp'])
        self.assertFalse(state['char_build_aspects']['heal'])

    def test_a_build_ticked_with_the_old_boxes_shows_the_mode_they_stand_for(self):
        for version, aspects, shown in (('dofus3', {'str', 'pvp'}, 'koli_3v3'),
                                        ('dofus3', {'str', 'pvp', 'duel'}, 'koli_1v1'),
                                        ('dofus3', {'str', 'duel'}, 'koli_1v1'),
                                        ('touch', {'str', 'pvp'}, 'koli_3v3'),
                                        ('retro', {'str', 'pvp'}, 'group_pvp'),
                                        ('retro', {'str', 'pvp', 'duel'}, 'aggression_1v1'),
                                        ('beta', {'str'}, 'general')):
            with self.subTest(version=version, aspects=sorted(aspects)):
                char = self.create(version, 'Iop', 200, aspects)
                page = self.client.get(_path(version, '/project/%d/' % char.id))
                state = json.loads(re.search(r'var initialState = (\{.*?\});',
                                             page.content.decode('utf-8')).group(1))
                self.assertEqual(('general', shown), (state['play_mode'], state['shown_mode']))

    def test_a_stored_mode_is_shown_while_its_boxes_match(self):
        shown = presets.shown_play_mode
        self.assertEqual('koli_2v2', shown({'str', 'pvp'}, 'koli_2v2', 'dofus2'))
        self.assertEqual('pvm_solo', shown({'str'}, 'pvm_solo', 'touch'))
        self.assertEqual('koli_1v1', shown({'str', 'pvp', 'duel'}, 'koli_2v2', 'dofus2'))
        self.assertEqual('general', shown({'str'}, 'koli_3v3', 'dofus3'))
        self.assertEqual('group_pvp', shown({'str', 'pvp'}, 'koli_3v3', 'retro'))

    def test_a_form_without_the_fields_keeps_the_stored_choices(self):
        char = self.create('dofus3', 'Iop', 200, {'str'}, {'priority': 'damage'})
        char, state = self.save(char, {'int'})
        self.assertEqual('damage', _options(char)['priority'])
        self.assertEqual(_weights_of(char, {'int', 'glasscannon'}),
                         _blob(char, 'stats_weight', {}))
        self.assertEqual('damage', state['priority'])

    def test_going_back_to_the_defaults_removes_the_keys(self):
        char = self.create('dofus3', 'Iop', 200, {'str'},
                           {'priority': 'defense', 'play_mode': 'koli_1v1'})
        char, _state = self.save(char, {'str', 'pvp', 'duel'},
                                 {'priority': 'balanced', 'play_mode': 'general'})
        self.assertNotIn('priority', _options(char))
        self.assertNotIn('play_mode', _options(char))
        self.assertEqual({'str', 'pvp', 'duel'}, _blob(char, 'aspects', set()))
        self.assertEqual(_weights_of(char, {'str', 'pvp', 'duel'}),
                         _blob(char, 'stats_weight', {}))

    def test_saving_without_the_wizard_keeps_the_weights_and_the_choices(self):
        char = self.create('dofus3', 'Iop', 200, {'str'},
                           {'priority': 'damage', 'play_mode': 'koli_3v3'})
        weights, minimums = char.stats_weight, char.minimum_stats
        char, state = self.save(char, {'str', 'pvp', 'duel'},
                                {'priority': 'defense', 'play_mode': 'koli_1v1'}, reapply=False)
        self.assertEqual((weights, minimums), (char.stats_weight, char.minimum_stats))
        self.assertEqual(('damage', 'koli_3v3'),
                         (_options(char)['priority'], _options(char)['play_mode']))
        self.assertEqual(('damage', 'koli_3v3'), (state['priority'], state['play_mode']))
        self.assertEqual({'str', 'pvp', 'duel'}, _blob(char, 'aspects', set()))

    def test_saving_without_the_wizard_at_the_defaults_stores_no_choice(self):
        char = self.create('dofus3', 'Iop', 200, {'str'})
        before = char.options
        char, _state = self.save(char, {'str', 'pvp'},
                                 {'priority': 'heals', 'play_mode': 'koli_3v3'}, reapply=False)
        self.assertEqual(before, char.options)
        self.assertEqual({'str', 'pvp'}, _blob(char, 'aspects', set()))

    def test_resetting_the_weights_keeps_the_priority(self):
        char = self.create('touch', 'Iop', 200, {'str'}, {'priority': 'damage'})
        char.stats_weight = pickle.dumps({})
        presets.reapply_build_weights(char)
        self.assertEqual(_weights_of(char, {'str', 'glasscannon'}),
                         _blob(char, 'stats_weight', {}))

    def test_resetting_a_build_without_a_priority_is_the_smart_build_reset(self):
        char = self.create('retro', 'Iop', 150, {'str', 'pvp'})
        reference = Char.objects.get(id=char.id)
        reapply_weights(reference)
        char.stats_weight = pickle.dumps({})
        presets.reapply_build_weights(char)
        self.assertEqual(_blob(reference, 'stats_weight', {}), _blob(char, 'stats_weight', {}))

    def test_a_build_without_the_keys_reads_as_the_defaults(self):
        char = Char(game_version='retro', options=pickle.dumps({'ap_exo': True}))
        self.assertEqual((presets.DEFAULT_PRIORITY, presets.DEFAULT_PLAY_MODE),
                         presets.stored_choices(char))
        self.assertIsNone(presets.choices_line(char))


class TheBuildPageNamesTheModeAndPriorityTests(_SetupMixin, TestCase):

    def _solved(self, char):
        input_ = {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated',
                  'char_level': char.level, 'base_stats_by_attr': {}, 'locked_equips': {}}
        minimal = ModelResultMinimal({}, input_, {})
        minimal.proven = True
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        return self.client.get(_path(char.game_version, '/solution/%d/' % char.id),
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')

    def test_a_chosen_mode_and_priority_are_named_under_the_solver_priorities(self):
        char = self.create('dofus2', 'Iop', 200, {'str'},
                           {'priority': 'damage', 'play_mode': 'koli_2v2'}, button='byhand')
        page = self._solved(char)
        self.assertIn('Mode: Kolossium 2v2 · Priority: Damage', page)
        self.assertLess(page.index('Priorities given to the solver:'),
                        page.index('Mode: Kolossium 2v2'))

    def test_the_line_speaks_the_page_language(self):
        char = self.create('retro', 'Iop', 200, {'str'}, {'play_mode': 'group_pvp'},
                           button='byhand')
        self._solved(char)
        page = self.client.get('/fr/retro/solution/%d/' % char.id).content.decode('utf-8')
        self.assertIn('Mode : PvP en groupe (prismes, percepteurs) · Priorité : Aucune priorité',
                      page)

    def test_a_build_at_its_defaults_shows_no_line(self):
        char = self.create('dofus3', 'Iop', 200, {'str'}, button='byhand')
        page = self._solved(char)
        self.assertIn('Why this result?', page)
        self.assertNotIn('solver-setup-choices', page)

    def test_a_save_that_keeps_the_weights_keeps_naming_the_choices_they_came_from(self):
        char = self.create('dofus2', 'Iop', 200, {'str'},
                           {'priority': 'damage', 'play_mode': 'koli_3v3'}, button='byhand')
        char, _state = self.save(char, {'str', 'pvp', 'duel'},
                                 {'priority': 'defense', 'play_mode': 'koli_1v1'}, reapply=False)
        page = self._solved(char)
        self.assertIn('Mode: Kolossium 3v3 · Priority: Damage', page)
        self.assertNotIn('Priority: Defense', page)

    def test_a_priority_saved_without_new_weights_is_not_claimed(self):
        char = self.create('dofus3', 'Iop', 200, {'str'}, button='byhand')
        char, _state = self.save(char, {'str'}, {'priority': 'damage'}, reapply=False)
        page = self._solved(char)
        self.assertIn('Why this result?', page)
        self.assertNotIn('solver-setup-choices', page)


_SYNC_FUNCTIONS = ('showMode', 'shownMode', 'tickModeBoxes', 'chooseMode', 'choicesChanged',
                   'keepRestartForChoices', 'setupChoices')

_JQUERY_STUB = """
var checked = {}, values = {}, shown = {}, handlers = {};
function $(selector) {
    return {
        prop: function(name, value) {
            if (value === undefined) { return !!checked[selector]; }
            checked[selector] = value;
            return this;
        },
        val: function(value) {
            if (value === undefined) { return values[selector]; }
            values[selector] = value;
            return this;
        },
        toggle: function(show) { shown[selector] = show; return this; },
        change: function(handler) {
            (handlers[selector] = handlers[selector] || []).push(handler);
            return this;
        }
    };
}
$.each = function(list, callback) {
    if (Array.isArray(list)) {
        for (var i = 0; i < list.length; i++) { callback(i, list[i]); }
    } else {
        for (var key in list) { callback(key, list[key]); }
    }
};
function fire(selector) {
    (handlers[selector] || []).forEach(function(handler) { handler(); });
}
function click(mode) {
    checked["#mode_" + mode] = !checked["#mode_" + mode];
    fire("#mode_" + mode);
}
function boxes() {
    return [!!checked["#check_pvp"], !!checked["#check_duel"]];
}
function modes() {
    return modeLayout.filter(function(mode) { return checked["#mode_" + mode[0]]; })
                     .map(function(mode) { return mode[0]; });
}
function showChosenOptions() {}
var initialStateStateEngine = null;
var PRIORITY = "input[name='priority']";
var CHOSEN = "input[name='priority']:checked";
"""


class ThePageKeepsTheModeAndTheBoxesInStepUnderNodeTests(_SetupMixin, TestCase):

    def run_page_script(self, version, body, saved=None):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        set_current_game_version(version)
        page = self.client.get(_path(version, '/setup/')).content.decode('utf-8')
        chosen = saved or {'priority': presets.DEFAULT_PRIORITY,
                           'play_mode': presets.DEFAULT_PLAY_MODE,
                           'shown_mode': presets.DEFAULT_PLAY_MODE}
        parts = [_JQUERY_STUB,
                 re.search(r'var modeLayout = .*?;\n', page).group(0),
                 re.search(r'var modeBoxes = .*?;\n', page).group(0),
                 re.search(r'var inertAspects = .*?(?=\nfunction )', page, re.S).group(0),
                 'values[CHOSEN] = %s;' % json.dumps(chosen['priority']),
                 'values["#play-mode"] = %s;' % json.dumps(chosen['play_mode']),
                 'checked["#mode_" + %s] = true;' % json.dumps(chosen['shown_mode'])]
        if saved is not None:
            parts.append('initialStateStateEngine = %s;' % json.dumps(saved))
        for name in _SYNC_FUNCTIONS:
            parts.append(re.search(r'function %s\(.*?\n\}' % name, page, re.S).group(0))
        parts.append('setupChoices();')
        parts.append('console.log(JSON.stringify((function() {%s})()));' % body)
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('\n'.join(parts))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_a_mode_box_ticks_its_option_boxes_and_the_restart_box(self):
        self.assertEqual([[['koli_1v1'], 'koli_1v1', [True, True], True],
                          [['koli_3v3'], 'koli_3v3', [True, False]],
                          [['pvm_solo'], 'pvm_solo', [False, False]],
                          [[], 'general', [False, False]]],
                         self.run_page_script('dofus3', """
            click("koli_1v1");
            var duel = [modes(), values["#play-mode"], boxes(), checked["#reapply-cb"]];
            click("koli_3v3");
            var group = [modes(), values["#play-mode"], boxes()];
            click("pvm_solo");
            var solo = [modes(), values["#play-mode"], boxes()];
            click("pvm_solo");
            return [duel, group, solo, [modes(), values["#play-mode"], boxes()]];"""))

    def test_retro_ticks_the_same_boxes_for_its_own_modes(self):
        self.assertEqual([[True, True], [True, False]], self.run_page_script('retro', """
            click("aggression_1v1");
            var aggression = boxes();
            click("group_pvp");
            return [aggression, boxes()];"""))

    def test_unticking_the_ticked_mode_clears_both_boxes(self):
        for version, mode in (('dofus3', 'koli_1v1'), ('dofus2', 'koli_2v2'),
                              ('retro', 'aggression_1v1'), ('retro', 'group_pvp')):
            with self.subTest(version=version, mode=mode):
                self.assertEqual([[mode], [], 'general', [False, False]],
                                 self.run_page_script(version, """
                    click(%s);
                    var kept = modes();
                    click(%s);
                    return [kept, modes(), values["#play-mode"], boxes()];"""
                                                      % (json.dumps(mode), json.dumps(mode))))

    def test_the_restart_box_stays_ticked_while_a_choice_differs_from_the_saved_one(self):
        saved = {'priority': 'balanced', 'play_mode': 'general', 'shown_mode': 'general'}
        self.assertEqual([[True, True], [False, False]], self.run_page_script('dofus3', """
            values[CHOSEN] = "damage"; fire(PRIORITY);
            checked["#reapply-cb"] = false; fire("#reapply-cb");
            var kept = [checked["#reapply-cb"], shown["#choices-restart-note"]];
            values[CHOSEN] = "balanced"; fire(PRIORITY);
            checked["#reapply-cb"] = false; fire("#reapply-cb");
            return [kept, [checked["#reapply-cb"], shown["#choices-restart-note"]]];""", saved))

    def test_unticking_the_mode_the_old_boxes_stand_for_keeps_the_restart_box(self):
        saved = {'priority': 'balanced', 'play_mode': 'general', 'shown_mode': 'koli_3v3'}
        self.assertEqual(['general', [False, False], True, True],
                         self.run_page_script('dofus3', """
            checked["#check_pvp"] = true;
            click("koli_3v3");
            checked["#reapply-cb"] = false; fire("#reapply-cb");
            return [values["#play-mode"], boxes(), checked["#reapply-cb"],
                    shown["#choices-restart-note"]];""", saved))

    def test_an_untouched_mode_posts_the_stored_one(self):
        saved = {'priority': 'balanced', 'play_mode': 'general', 'shown_mode': 'koli_1v1'}
        self.assertEqual([['koli_1v1'], 'general', False], self.run_page_script('dofus3', """
            keepRestartForChoices();
            return [modes(), values["#play-mode"], !!shown["#choices-restart-note"]];""",
                                                                               saved))

    def test_the_creation_page_forces_nothing(self):
        self.assertEqual([False, False], self.run_page_script('dofus3', """
            values[CHOSEN] = "defense"; fire(PRIORITY);
            checked["#reapply-cb"] = false; fire("#reapply-cb");
            return [checked["#reapply-cb"], shown["#choices-restart-note"]];"""))

    def test_every_box_a_mode_ticks_is_posted_by_the_page(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                set_current_game_version(version)
                page = self.client.get(_path(version, '/setup/')).content.decode('utf-8')
                layout = json.loads(re.search(r'var aspectLayout = (\[.*?\])\s*\.map', page,
                                              re.S).group(1))
                inert = json.loads(re.search(r'var inertAspects = (.*?);', page).group(1))
                posted = set(layout[1]) - set(inert)
                for mode, boxes in presets.mode_boxes(version).items():
                    self.assertLessEqual(set(boxes), posted, mode)

    def test_the_old_boxes_are_posted_hidden_and_the_mode_boxes_are_not_posted(self):
        page = self.client.get('/setup/').content.decode('utf-8')
        column = re.search(r'if \(columnIndex === 1\) \{(.*?)\n            \}', page, re.S)
        self.assertIsNotNone(column)
        self.assertIn("name: 'check_' + aspect", column.group(1))
        self.assertIn('display: none', column.group(1))
        mode_box = re.search(r'function createModeBox\(.*?\n\}', page, re.S).group(0)
        self.assertNotIn('name=', mode_box)

    def test_the_edit_page_hides_the_restart_note_until_a_choice_changes(self):
        char = self.create('dofus3', 'Iop', 200, {'str'}, button='byhand')
        page = self.client.get('/project/%d/' % char.id).content.decode('utf-8')
        note = re.search(r'<div[^>]*id="?choices-restart-note"?[^>]*>([^<]+)</div>', page)
        self.assertIsNotNone(note)
        self.assertIn('display: none', note.group(0))
        self.assertEqual('Changing the priority or the mode in the Options column always '
                         'restarts the wizard.', note.group(1).strip())
