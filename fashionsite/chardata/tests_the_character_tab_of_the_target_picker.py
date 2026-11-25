# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The picker's Character tab: its list, its payload on a build target on every version, the compare page's picker, and no list for an anonymous viewer."""
import json
import pickle
import re
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata import targets
from chardata.models import Char
from chardata.targets import BUILD_TOKEN, TARGET_VERSIONS
from fashionistapulp.modelresult import ModelResultMinimal

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
HERE = Path(__file__).parent
HIDDEN = r'(?<![\w-])hidden(?![\w-])'
SPELLS_TEMPLATE = HERE / 'templates' / 'chardata' / 'spells.html'
COMPARE_SCRIPT = HERE / 'static' / 'chardata' / 'compare_target.js'
NEW_STRINGS = ('Character', 'Your builds', 'Paste a build link', 'Use this link',
               'Their best turn on you', 'This is not a build link.',
               'Percent resistances above the cap count as the cap.')


def _prefix(version):
    return '' if version == 'dofus3' else '/' + version


def _make_build(owner, version, name, char_class='Iop', level=200):
    base = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
            'Chance': 0, 'Agility': 0}
    minimal = ModelResultMinimal(
        {},
        {'options': {'ap_exo': False, 'mp_exo': False},
         'origin': 'generated', 'char_level': level,
         'base_stats_by_attr': base, 'locked_equips': {}},
        {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0})
    return Char.objects.create(
        name=name, char_name=name, char_class=char_class, char_build='build',
        level=level, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'',
        minimal_solution=pickle.dumps(minimal), owner=owner,
        link_shared=False, game_version=version)


class TheCharacterListTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('lister', 'l@x.test', 'pw-42-solid')
        self.other = User.objects.create_user('someone', 's@x.test', 'pw-42-solid')

    def _list(self, version='dofus3'):
        response = self.client.get('%s/build_targets/' % _prefix(version))
        self.assertEqual(200, response.status_code)
        return json.loads(response.content)['builds']

    def test_the_list_holds_the_viewers_own_builds_of_this_version_only(self):
        mine = _make_build(self.owner, 'dofus3', 'Mine')
        _make_build(self.owner, 'dofus2', 'Elsewhere')
        gone = _make_build(self.owner, 'dofus3', 'Gone')
        Char.objects.filter(pk=gone.pk).update(deleted=True)
        _make_build(self.other, 'dofus3', 'Not-mine')
        self.client.force_login(self.owner)
        found = self._list()
        self.assertEqual(['b%d' % mine.pk], [entry['target'] for entry in found])
        self.assertEqual(['class', 'level', 'name', 'target'], sorted(found[0]))
        self.assertEqual(['Elsewhere'], [entry['name'] for entry in self._list('dofus2')])

    def test_a_build_without_a_solution_is_not_listed(self):
        Char.objects.create(
            name='Unsolved', char_name='Unsolved', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'', options=b'',
            inclusions=b'', exclusions=b'', owner=self.owner, link_shared=False,
            game_version='dofus3')
        solved = _make_build(self.owner, 'dofus3', 'Solved')
        self.client.force_login(self.owner)
        self.assertEqual(['b%d' % solved.pk], [entry['target'] for entry in self._list()])

    def test_a_build_without_a_real_name_shows_its_class_and_level(self):
        _make_build(self.owner, 'dofus3', 'NoName', char_class='Cra', level=150)
        self.client.force_login(self.owner)
        entry = self._list()[0]
        self.assertEqual(150, entry['level'])
        self.assertNotEqual('NoName', entry['name'])
        self.assertIn('150', entry['name'])
        self.assertTrue(entry['class'])

    def test_an_anonymous_viewer_gets_no_character_list(self):
        response = self.client.get('/build_targets/')
        self.assertEqual({'builds': []}, json.loads(response.content))
        session = self.client.session
        session['anon_char_ids'] = {'1': 1}
        session.save()
        self.assertEqual({'builds': []}, json.loads(self.client.get('/build_targets/').content))

    def test_the_list_is_never_cached(self):
        self.client.force_login(self.owner)
        header = self.client.get('/build_targets/')['Cache-Control']
        self.assertIn('no-cache', header)
        self.assertIn('private', header)


class TheCharacterTabOnThePageTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('tabber', 't@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)

    def _tag(self, body, marker):
        return re.search(r'<div[^>]*%s[^>]*>' % re.escape(marker), body).group(0)

    def _page(self, version, language='en'):
        build = _make_build(self.owner, version, 'Page-%s' % version)
        lang = '' if language == 'en' else '/' + language
        page = self.client.get('%s%s/spells/%d/' % (lang, _prefix(version), build.pk))
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8')

    def test_every_version_with_targets_carries_the_tab_the_list_url_and_their_turn_block(self):
        for version in TARGET_VERSIONS:
            body = self._page(version)
            with self.subTest(version=version):
                self.assertIn('id="best-combo-tab-character"', body)
                self.assertIn('id="best-combo-tabpanel-character"', body)
                self.assertIn('data-builds-url="%s/build_targets/"' % _prefix(version), body)
                self.assertRegex(self._tag(body, 'best-combo-their-turn'), HIDDEN)
                self.assertRegex(self._tag(body, 'id="best-combo-tabpanel-character"'), HIDDEN)

    def test_a_version_without_targets_carries_none_of_it(self):
        kept = tuple(key for key in TARGET_VERSIONS if key != 'retro')
        with mock.patch.object(targets, 'TARGET_VERSIONS', kept):
            body = self._page('retro')
        for part in ('id="best-combo-tab-character"', 'class="best-combo-their-turn"',
                     'data-builds-url'):
            self.assertNotIn(part, body)

    def test_the_new_strings_reach_the_page_in_every_language(self):
        seen = {}
        for language in LANGUAGES:
            body = self._page('dofus3', language)
            with translation.override(language):
                expected = {text: translation.gettext(text) for text in NEW_STRINGS}
            seen[language] = expected
            with self.subTest(language=language):
                for text in ('Character', 'Your builds', 'Paste a build link', 'Use this link',
                             'Their best turn on you'):
                    self.assertIn('>%s<' % expected[text], body)
                self.assertIn('data-link-error="%s"' % expected['This is not a build link.'],
                              body)
                self.assertIn(expected['Percent resistances above the cap count as the cap.'],
                              body)
                self.assertNotIn('%%', re.search(r'data-their-hp-share="[^"]*"', body).group(0))
        for language in LANGUAGES[1:]:
            for text in NEW_STRINGS:
                with self.subTest(language=language, text=text):
                    self.assertNotEqual(seen['en'][text], seen[language][text])

    def test_the_total_of_their_turn_is_one_translated_sentence_in_every_language(self):
        for language in LANGUAGES:
            body = self._page('dofus3', language)
            with translation.override(language):
                expected = translation.gettext('%(name)s: %(total)s damage') % {
                    'name': '__name__', 'total': '__total__'}
            with self.subTest(language=language):
                self.assertIn('data-their-total="%s"' % expected, body)
        self.assertIn('__name__ : __total__', self._page('dofus3', 'fr'))

    def test_an_anonymous_viewer_is_told_to_sign_in_not_that_he_has_no_build(self):
        build = _make_build(self.owner, 'dofus3', 'Shared-one')
        Char.objects.filter(pk=build.pk).update(link_shared=True)
        self.client.logout()
        from chardata.encoded_char_id import encode_char_id
        page = self.client.get('/spells_linked/Shared-one/%s/' % encode_char_id(build.pk))
        body = page.content.decode('utf-8')
        self.assertEqual(200, page.status_code)
        self.assertIn('data-no-build="Sign in to list your builds, or paste a build link."', body)
        self.client.force_login(self.owner)
        logged = self._page('dofus3')
        self.assertIn('data-no-build="No build of yours for this version."', logged)


class ACharacterTargetPayloadTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('duelist', 'd@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)

    def _post(self, version, page, target):
        return self.client.post('%s/best_combo/%d/' % (_prefix(version), page.pk),
                                {'target': target, 'pushback': 'false'})

    def test_every_version_answers_with_the_build_its_counted_resistances_and_their_turn(self):
        for version in TARGET_VERSIONS:
            mine = _make_build(self.owner, version, 'Mine-%s' % version, 'Iop')
            theirs = _make_build(self.owner, version, 'Theirs-%s' % version, 'Cra', 150)
            response = self._post(version, mine, 'b%d' % theirs.pk)
            with self.subTest(version=version):
                self.assertEqual(200, response.status_code)
                data = json.loads(response.content)
                self.assertNotIn('target_refused', data)
                info = data['best_combo']['target']
                self.assertEqual('build', info['kind'])
                self.assertEqual('Theirs-%s' % version, info['name'])
                self.assertEqual('b%d' % theirs.pk, info['token'])
                self.assertEqual(150, info['level'])
                self.assertTrue(info['class'])
                self.assertEqual(5, len(info['resistances']))
                for line in info['resistances']:
                    self.assertIn('counted', line)
                    self.assertIn('percent', line)
                their = data['their_turn']
                self.assertEqual('Theirs-%s' % version, their['name'])
                self.assertEqual({'name', 'total', 'raw_total', 'later_total', 'hp_share',
                                  'casts', 'not_counted'}, set(their))
                for cast in their['casts']:
                    self.assertEqual({'name', 'image_url', 'ap', 'damage', 'running'},
                                     set(cast))
                self.assertIn('stages', data['best_combo'])
                self.assertTrue(data['best_combo']['not_counted'])

    def test_a_monster_target_carries_no_their_turn_and_no_build_fields(self):
        mine = _make_build(self.owner, 'dofus3', 'Mine-monster')
        monster_id, _names, grades = targets._monster_index('dofus3')[0][0]
        data = json.loads(self._post('dofus3', mine, 'm%d.%d' % (monster_id, grades[0][0])).content)
        self.assertNotIn('their_turn', data)
        self.assertNotIn('kind', data['best_combo']['target'])
        self.assertEqual(monster_id, data['best_combo']['target']['monster_id'])

    def test_a_build_of_another_player_that_is_not_shared_is_refused_like_a_missing_one(self):
        mine = _make_build(self.owner, 'dofus3', 'Mine-refused')
        stranger = User.objects.create_user('stranger2', 's2@x.test', 'pw-42-solid')
        hidden = _make_build(stranger, 'dofus3', 'Hidden-name')
        missing = Char.objects.order_by('-pk').first().pk + 500
        bodies = [self._post('dofus3', mine, 'b%d' % char_id).content.decode('utf-8')
                  for char_id in (hidden.pk, missing)]
        self.assertEqual(bodies[0], bodies[1])
        self.assertNotIn('Hidden-name', bodies[0])
        self.assertEqual('build', json.loads(bodies[0])['target_refused'])
        self.assertNotIn('their_turn', json.loads(bodies[0]))


class TheCompareTargetPickerTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('comparer', 'c@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)

    def _compare(self, version, query=''):
        first = _make_build(self.owner, version, 'First-%s' % version)
        second = _make_build(self.owner, version, 'Second-%s' % version, 'Cra')
        third = _make_build(self.owner, version, 'Third-%s' % version, 'Sram', 120)
        self.ids = (first.pk, second.pk)
        url = '%s/compare_sets/%d/%d/' % (_prefix(version), first.pk, second.pk)
        return self.client.get(url + query), third

    def test_one_picker_serves_both_sets_and_names_the_target(self):
        for version in TARGET_VERSIONS:
            plain, third = self._compare(version)
            with self.subTest(version=version):
                self.assertEqual(200, plain.status_code)
                body = plain.content.decode('utf-8')
                self.assertEqual(1, body.count('id="compare-target"'))
                self.assertIn('data-builds-url="%s/build_targets/"' % _prefix(version), body)
                self.assertIn('>Target: none (raw damage)<', body)
                self.assertNotIn('class="compare-target-clear"', body)
                self.assertNotIn('name="target"', body)
                on_build = self.client.get('%s/compare_sets/%d/%d/?target=b%d' % (
                    _prefix(version), self.ids[0], self.ids[1], third.pk))
                text = on_build.content.decode('utf-8')
                self.assertEqual('Third-%s' % version, on_build.context['best_turn_target']['name'])
                self.assertIn('>Target: Third-%s<' % version, text)
                self.assertIn('class="compare-target-clear"', text)
                self.assertIn('<b>Best turn (Third-%s)</b>' % version, text)
                self.assertEqual(2, len(on_build.context['best_turn_by_char']))

    def test_the_target_survives_the_spell_preview_forms(self):
        plain, third = self._compare('dofus3')
        text = self.client.get('/compare_sets/%d/%d/?target=b%d' % (
            self.ids[0], self.ids[1], third.pk)).content.decode('utf-8')
        forms = re.findall(r'<form method="get"[^>]*>.*?</form>', text, re.S)
        for form in forms:
            self.assertRegex(form, r'<input[^>]*name="target"[^>]*value="b%d"' % third.pk)

    def test_a_target_that_cannot_be_opened_shows_the_picker_on_none_and_nothing_of_it(self):
        stranger = User.objects.create_user('stranger3', 's3@x.test', 'pw-42-solid')
        hidden = _make_build(stranger, 'dofus3', 'Veiled-name')
        plain, _third = self._compare('dofus3')
        refused = self.client.get('/compare_sets/%d/%d/?target=b%d' % (
            self.ids[0], self.ids[1], hidden.pk))
        text = refused.content.decode('utf-8')
        self.assertEqual(200, refused.status_code)
        self.assertNotIn('Veiled-name', text)
        self.assertIn('>Target: none (raw damage)<', text)
        self.assertIn('<b>Best turn</b>', text)

    def test_a_version_without_targets_has_no_picker(self):
        kept = tuple(key for key in TARGET_VERSIONS if key != 'retro')
        with mock.patch.object(targets, 'TARGET_VERSIONS', kept):
            plain, _third = self._compare('retro')
        text = plain.content.decode('utf-8')
        self.assertNotIn('id="compare-target"', text)
        self.assertNotIn('compare_target.js', text)


class TheScriptsAcceptWhatTheServerAcceptsTests(SimpleTestCase):

    def test_both_scripts_read_the_build_tokens_the_server_reads(self):
        build_part = BUILD_TOKEN.pattern[1:-1]
        for path in (SPELLS_TEMPLATE, COMPARE_SCRIPT):
            source = path.read_text(encoding='utf-8')
            with self.subTest(script=path.name):
                self.assertIn('|' + build_part + ')', source)

    def test_the_compare_script_keeps_the_page_when_it_changes_the_target(self):
        source = COMPARE_SCRIPT.read_text(encoding='utf-8')
        self.assertIn('new URL(window.location.href)', source)
        self.assertIn("searchParams.set('target'", source)
        self.assertIn("searchParams.delete('target')", source)
        self.assertNotIn('localStorage', source)
