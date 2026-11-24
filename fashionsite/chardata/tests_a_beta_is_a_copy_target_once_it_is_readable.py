# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build offers a copy to the beta of its game once that beta is readable, by itself and never before, and the copy is a new build."""
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.models import Char, CharBaseStats
from chardata.version_copy import copy_targets
from fashionistapulp import game_versions
from fashionistapulp.game_versions import GAME_VERSIONS, family_members, is_beta, main_of
from fashionistapulp.modelresult import ModelResultMinimal
from fashionsite import urls


def _betas():
    return [key for key, version in GAME_VERSIONS.items() if version.dofus and is_beta(key)]


def _readable(key):
    return mock.patch.object(GAME_VERSIONS[key], 'experimental', False)


def _hidden(key):
    return mock.patch.object(GAME_VERSIONS[key], 'experimental', True)


def _routed(key):
    return GAME_VERSIONS[key].prefix == '' or GAME_VERSIONS[key].prefix + '/' in [
        str(pattern.pattern) for pattern in urls.urlpatterns]


def _prefix(key):
    return '/' + GAME_VERSIONS[key].prefix if GAME_VERSIONS[key].prefix else ''


def _keys(version):
    return [target['key'] for target in copy_targets(version)]


class TheOfferFollowsTheFamilyOfTheRegistryTests(SimpleTestCase):

    def test_a_hidden_beta_is_offered_from_nowhere(self):
        for beta in _betas():
            with _hidden(beta):
                for key in family_members(main_of(beta)):
                    self.assertNotIn(beta, _keys(key), (beta, key))

    def test_a_readable_beta_is_offered_from_its_main_version_and_offers_it_back(self):
        for beta in _betas():
            main = main_of(beta)
            with _readable(beta):
                self.assertIn(beta, _keys(main), beta)
                self.assertIn(main, _keys(beta), beta)
                self.assertEqual({'key': beta, 'name': GAME_VERSIONS[beta].game_name},
                                 [target for target in copy_targets(main) if target['key'] == beta][0])

    def test_a_beta_is_never_offered_to_another_game(self):
        for beta in _betas():
            with _readable(beta):
                for key, version in GAME_VERSIONS.items():
                    if version.dofus and not version.experimental and main_of(key) != main_of(beta):
                        self.assertNotIn(beta, _keys(key), (beta, key))

    def test_a_game_without_a_readable_beta_offers_no_copy(self):
        for key, version in GAME_VERSIONS.items():
            if version.dofus and not is_beta(key) and not version.experimental:
                if all(GAME_VERSIONS[other].experimental or main_of(other) != key
                       for other in _betas()):
                    self.assertEqual([], _keys(key), key)


def _a_build(owner, version):
    input_ = {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    char = Char.objects.create(
        name='Original', char_name='original', char_class='Iop', char_build='build', level=200,
        minimum_stats=pickle.dumps({'Vitality': 100}), minimum_crits=b'',
        stats_weight=pickle.dumps({'Vitality': 1.0}), options=pickle.dumps({}),
        inclusions=pickle.dumps({}), exclusions=pickle.dumps([]),
        minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
        owner=owner, link_shared=True, auto_publish=True, view_count=12, game_version=version)
    CharBaseStats.objects.create(char=char, stat='Vitality', total_value=120, scrolled_value=100)
    return char


def _row(char):
    return (Char.objects.filter(pk=char.pk).values().get(),
            sorted(CharBaseStats.objects.filter(char=char).values_list('stat', 'total_value', 'scrolled_value')))


class TheCopyToTheBetaIsANewBuildTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('author', 'a@x.test', 'pw-42-solid')
        self.reader = User.objects.create_user('reader', 'r@x.test', 'pw-42-solid')

    def test_a_copy_to_each_beta_and_back_makes_a_new_build_and_leaves_the_original_alone(self):
        for beta in _betas():
            main = main_of(beta)
            for source, target in ((main, beta), (beta, main)):
                if not (_routed(source) and _routed(target)):
                    continue
                with self.subTest(source=source, target=target), _readable(beta):
                    original = _a_build(self.owner, source)
                    before = _row(original)
                    others = set(Char.objects.exclude(pk=original.pk).values_list('pk', flat=True))
                    self.client.force_login(self.owner)
                    response = self.client.post('%s/copytoversion/%d/' % (_prefix(source), original.pk), {'version': target})
                    self.assertEqual(302, response.status_code)
                    self.assertEqual(before, _row(original))
                    made = Char.objects.exclude(pk__in=others | {original.pk})
                    self.assertEqual(1, made.count())
                    copy = made.get()
                    self.assertEqual(target, copy.game_version)
                    self.assertEqual(self.owner, copy.owner)
                    self.assertEqual(0, copy.view_count)

    def test_a_reader_copy_belongs_to_the_reader(self):
        for beta in _betas():
            if not (_routed(main_of(beta)) and _routed(beta)):
                continue
            with self.subTest(beta=beta), _readable(beta):
                original = _a_build(self.owner, main_of(beta))
                before = _row(original)
                self.client.force_login(self.reader)
                from chardata.encoded_char_id import encode_char_id
                self.client.post('%s/copysharedtoversion/%s/' % (_prefix(main_of(beta)), encode_char_id(original.pk)),
                                 {'version': beta})
                self.assertEqual(before, _row(original))
                self.assertEqual(self.reader, Char.objects.get(game_version=beta, owner=self.reader).owner)

    def test_a_copy_to_a_hidden_beta_is_refused(self):
        for beta in _betas():
            with self.subTest(beta=beta), _hidden(beta):
                original = _a_build(self.owner, main_of(beta))
                self.client.force_login(self.owner)
                response = self.client.post('%s/copytoversion/%d/' % (_prefix(main_of(beta)), original.pk),
                                            {'version': beta})
                self.assertEqual(404, response.status_code)
                self.assertFalse(Char.objects.filter(game_version=beta).exists())
