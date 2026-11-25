# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The target line, its picker, its search and the encyclopedia link exist for the builds of a version with targets only, in every language."""
import json
import pickle
import re
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import translation

from chardata import spells_view, targets
from chardata.models import Char
from chardata.targets import _monster_index
from fashionistapulp.modelresult import ModelResultMinimal

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
PAGE_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
DEFAULT_LINE = 'Target: none (raw damage)'
TEMPLATE = Path(__file__).parent / 'templates' / 'chardata' / 'spells.html'


def _make_build(owner, version, name='picker'):
    base = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
            'Chance': 0, 'Agility': 0}
    minimal = ModelResultMinimal(
        {},
        {'options': {'ap_exo': False, 'mp_exo': False},
         'origin': 'generated', 'char_level': 200,
         'base_stats_by_attr': base, 'locked_equips': {}},
        {'vit': 0, 'wis': 0, 'str': 0, 'int': 0, 'cha': 0, 'agi': 0})
    return Char.objects.create(
        name=name, char_name=name, char_class='Iop', char_build='build',
        level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'',
        minimal_solution=pickle.dumps(minimal), owner=owner,
        link_shared=False, game_version=version)


def _prefix(version):
    return '' if version == 'dofus3' else '/' + version


class TheTargetLineTests(TestCase):

    def _page(self, version, language='en'):
        owner = User.objects.create_user(
            'picker%d' % User.objects.count(), 'pk@test.local', 'pw-42-solid')
        build = _make_build(owner, version)
        self.client.force_login(owner)
        lang = '' if language == 'en' else '/' + language
        page = self.client.get('%s%s/spells/%d/' % (lang, _prefix(version), build.pk))
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8')

    def test_every_version_with_targets_opens_on_raw_damage(self):
        self.assertEqual(set(PAGE_VERSIONS), set(targets.TARGET_VERSIONS))
        for version in PAGE_VERSIONS:
            body = self._page(version)
            with self.subTest(version=version):
                self.assertIn('id="best-combo"', body)
                self.assertIn('data-target-version="%s"' % version, body)
                self.assertRegex(
                    body, r'class="best-combo-target-button"[^>]*>%s<' % re.escape(DEFAULT_LINE))
                self.assertIn('aria-expanded="false"', body)
                self.assertIn('id="best-combo-picker"', body)
                picker = re.search(r'<div[^>]*id="best-combo-picker"[^>]*>', body).group(0)
                self.assertRegex(picker, r'\bhidden\b')

    def test_a_version_without_targets_shows_no_target_line(self):
        for version in ('dofus2', 'touch', 'retro'):
            kept = tuple(key for key in targets.TARGET_VERSIONS if key != version)
            with mock.patch.object(targets, 'TARGET_VERSIONS', kept):
                body = self._page(version)
            with self.subTest(version=version):
                self.assertIn('id="best-combo"', body)
                self.assertIn('data-target-version=""', body)
                for part in ('class="best-combo-target', 'id="best-combo-picker"',
                             'class="best-combo-raw"', 'data-search-url'):
                    self.assertNotIn(part, body)

    def test_the_default_line_and_the_labels_are_translated_in_every_language(self):
        seen = {}
        for language in LANGUAGES:
            with translation.override(language):
                expected = translation.gettext(DEFAULT_LINE)
                headline = translation.gettext(
                    '%(damage)s damage on %(name)s (grade %(grade)s, %(hp)s HP)')
            body = self._page('dofus3', language)
            seen[language] = expected
            with self.subTest(language=language):
                self.assertIn('>%s<' % expected, body)
                self.assertIn('data-label-none="%s"' % expected, body)
                self.assertIn('__damage__', body)
                self.assertNotIn('0,909', body)
                self.assertNotIn('%%', re.search(r'data-hp-share="[^"]*"', body).group(0))
                self.assertIn('%', re.search(r'data-hp-share="[^"]*"', body).group(0))
                self.assertIn(headline.replace('%(damage)s', '__damage__')
                              .replace('%(name)s', '__name__')
                              .replace('%(grade)s', '__grade__')
                              .replace('%(hp)s', '__hp__'), body)
        for language in LANGUAGES[1:]:
            self.assertNotEqual(seen['en'], seen[language])

    def test_the_target_in_the_address_is_read_by_the_page_not_the_server(self):
        first = _monster_index('dofus3')[0][0]
        token = 'm%d.%d' % (first[0], first[2][0][0])
        self._page('dofus3')
        owner = User.objects.latest('pk')
        build = Char.objects.filter(owner=owner).latest('pk')
        with_target = self.client.get('/spells/%d/?target=%s' % (build.pk, token))
        self.assertEqual(200, with_target.status_code)
        self.assertNotIn(token, with_target.content.decode('utf-8'))


class TheTargetScriptKeepsStorageGuardedTests(SimpleTestCase):

    def test_every_storage_access_of_the_picker_sits_in_a_try(self):
        source = TEMPLATE.read_text(encoding='utf-8')
        for name in ('storedTarget', 'rememberTarget', 'urlTarget', 'showTargetInUrl'):
            start = source.index('function %s(' % name)
            body = source[start:source.index('\n    }\n', start)]
            with self.subTest(function=name):
                self.assertRegex(body, r'\{\s*try \{')
                self.assertIn('catch (e)', body)
        for access in re.finditer(r'localStorage\.(get|set|remove)Item', source):
            before = source[:access.start()]
            function = before.rindex('function ')
            with self.subTest(at=source.count('\n', 0, access.start())):
                self.assertIn('try {', source[function:access.start()])


class TheTwoTabsKeepTheirOwnElementsTests(SimpleTestCase):

    def _classes(self, source, start_marker, end_marker):
        start = source.index(start_marker)
        block = source[start:source.index(end_marker, start)]
        return {name for found in re.findall(r'class="([^"]+)"', block) for name in found.split()}

    def test_a_class_both_tabs_carry_is_never_looked_up_across_the_whole_picker(self):
        source = TEMPLATE.read_text(encoding='utf-8')
        monster = 'id="best-combo-tabpanel-monster"'
        character = 'id="best-combo-tabpanel-character"'
        shared = (self._classes(source, monster, character)
                  & self._classes(source, character, '<div class="best-combo-target-summary"'))
        self.assertIn('best-combo-picker-results', shared)
        for name in sorted(shared):
            with self.subTest(css_class=name):
                self.assertNotRegex(source, r"\b(picker|panel)\.find\('\.%s'\)" % re.escape(name))


class TheMonsterSearchViewTests(SimpleTestCase):

    def _get(self, query, version='dofus3', method='get'):
        request = getattr(RequestFactory(), method)('/monster_targets/', {'q': query})
        request.game_version = version
        return spells_view.monster_targets_json(request)

    def test_a_search_answers_json_with_grades_and_may_be_cached(self):
        first = _monster_index('dofus3')[0][0]
        response = self._get(str(first[0]))
        self.assertEqual(200, response.status_code)
        self.assertIn('max-age', response['Cache-Control'])
        self.assertNotIn('private', response['Cache-Control'])
        monsters = json.loads(response.content)['monsters']
        self.assertEqual(first[0], monsters[0]['id'])
        self.assertEqual(['grade', 'hp', 'level', 'target'],
                         sorted(monsters[0]['grades'][0]))
        self.assertTrue(monsters[0]['name'])

    def test_only_a_get_is_answered(self):
        self.assertEqual(405, self._get('blop', method='post').status_code)

    def test_an_empty_query_or_another_version_finds_nothing(self):
        self.assertEqual([], json.loads(self._get('').content)['monsters'])
        for version in ('touchbeta', 'retrobeta'):
            self.assertEqual([], json.loads(self._get('blop', version=version).content)['monsters'])
        first = _monster_index('retro')[0][0]
        self.assertEqual([], json.loads(self._get(str(first[0]), version='retrobeta').content)
                         ['monsters'])
        self.assertTrue(json.loads(self._get(str(first[0]), version='retro').content)['monsters'])

    def test_a_very_long_query_is_cut_not_refused(self):
        self.assertEqual(200, self._get('a' * 5000).status_code)

    def test_the_route_exists_for_every_version_and_the_robots_file_keeps_crawlers_off(self):
        from django.urls import reverse
        self.assertEqual('/monster_targets/', reverse('monster_targets'))
        self.assertEqual('/beta/monster_targets/', reverse('beta:monster_targets'))
        robots = (Path(__file__).parent / 'templates' / 'chardata' / 'robots.txt').read_text(
            encoding='utf-8')
        self.assertIn('Disallow: /monster_targets/', robots)
        self.assertIn('Disallow: /*/monster_targets/', robots)


class TheEncyclopediaLinkTests(TestCase):

    def _grades(self, version):
        monster_id, _names, grades = _monster_index(version)[0][0]
        return monster_id, [grade[0] for grade in grades]

    def _page(self, version):
        monster_id, _grades = self._grades(version)
        page = self.client.get('%s/encyclopedia/monster/%d-x/' % (_prefix(version), monster_id),
                               follow=True)
        self.assertEqual(200, page.status_code)
        return page.content.decode('utf-8')

    def test_a_viewer_with_a_build_gets_one_link_per_grade_to_the_newest_one(self):
        owner = User.objects.create_user('enc1', 'enc1@test.local', 'pw-42-solid')
        older = _make_build(owner, 'dofus3', 'older')
        newer = _make_build(owner, 'dofus3', 'newer')
        Char.objects.filter(pk=older.pk).update(modified_time='2020-01-01T00:00:00Z')
        self.client.force_login(owner)
        monster_id, grades = self._grades('dofus3')
        body = self._page('dofus3')
        links = re.findall(r'class="monster-try-build" href="([^"]+)"', body)
        self.assertEqual(['/spells/%d/?target=m%d.%d' % (newer.pk, monster_id, grade)
                          for grade in grades], links)

    def test_a_touch_retro_or_dofus2_viewer_gets_links_to_a_build_of_that_version(self):
        owner = User.objects.create_user('enc3', 'enc3@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        for version in ('dofus2', 'touch', 'retro'):
            build = _make_build(owner, version, version)
            monster_id, grades = self._grades(version)
            links = re.findall(r'class="monster-try-build" href="([^"]+)"', self._page(version))
            with self.subTest(version=version):
                self.assertEqual(['%s/spells/%d/?target=m%d.%d'
                                  % (_prefix(version), build.pk, monster_id, grade)
                                  for grade in grades], links)

    def test_nothing_is_offered_without_a_build_of_that_version_or_without_a_login(self):
        self.assertNotIn('class="monster-try-build"', self._page('dofus3'))
        owner = User.objects.create_user('enc2', 'enc2@test.local', 'pw-42-solid')
        _make_build(owner, 'dofus3')
        self.client.force_login(owner)
        self.assertNotIn('class="monster-try-build"', self._page('beta'))
        gone = _make_build(owner, 'beta', 'gone')
        Char.objects.filter(pk=gone.pk).update(deleted=True)
        self.assertNotIn('class="monster-try-build"', self._page('beta'))
