# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build copied between Dofus 3 and Dofus 3 Beta keeps its pieces and names the ones left behind."""
import copy as copying
import pickle
import re
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, CharBaseStats
from fashionistapulp.structure import get_structure, set_current_game_version

LEVEL = 60

TROPHY_CHANGED_ON_THE_BETA = 12640
BETA_ONLY_PIECE = 27228
BETA_ONLY_PIECE_BANNED_BY_DEFAULT = 34569

_PREFIX = {'dofus3': '', 'beta': '/beta'}


def _read_back(blob):
    try:
        return pickle.loads(blob)
    except Exception as error:
        raise AssertionError('a stored column does not read back: %s' % error)


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


def _by_key(structure, item):
    return {structure.get_stat_by_id(stat_id).key: value
            for stat_id, value in item.stats}


def _shared_pieces(level):
    """A hat and a cloak without a set, the same in both versions, by English name."""
    dofus3, beta = get_structure('dofus3'), get_structure('beta')
    names = []
    for type_name in ('Hat', 'Cloak'):
        for item in dofus3.types[level][type_name]:
            other = beta.get_item_by_ankama_id(item.ankama_id)
            name = dofus3.get_item_name_in_language(item, 'en')
            if (not item.removed and item.ankama_id and other is not None
                    and not other.removed and item.name == other.name
                    and item.set is None and other.set is None
                    and _by_key(dofus3, item) == _by_key(beta, other)
                    and dofus3.get_item_by_name(item.name) is item
                    and not getattr(item, 'classes', ())):
                names.append(name)
                break
    assert len(names) == 2, names
    return names


def _name(version, ankama_id):
    structure = get_structure(version)
    return structure.get_item_name_in_language(
        structure.get_item_by_ankama_id(ankama_id), 'en')


def _worn(char):
    from chardata.solution import get_solution
    set_current_game_version(char.game_version)
    try:
        solution = get_solution(char)
        return {item.ankama_id: item for item in solution.item_list
                if getattr(item, 'item_added', False)}, solution
    finally:
        set_current_game_version('dofus3')


class _Renumbered:
    """A catalogue whose every id is shifted, so no id names the same piece as before."""

    def __init__(self, real, shift):
        self._real = real
        self._shift = shift
        self._copies = {}
        self.items_dict = {row.id: row for row in map(
            self._moved, real.items_dict.values())}
        self.dt_items_dict = {row.id: row for row in map(
            self._moved, real.dt_items_dict.values())}

    def _moved(self, item):
        if item is None:
            return None
        if id(item) not in self._copies:
            moved = copying.copy(item)
            moved.id = item.id + self._shift
            self._copies[id(item)] = moved
        return self._copies[id(item)]

    def get_item_by_id(self, item_id):
        if not isinstance(item_id, int):
            return None
        return self._moved(self._real.get_item_by_id(item_id - self._shift))

    def get_item_by_ankama_id(self, ankama_id, dofus_touch=False):
        return self._moved(self._real.get_item_by_ankama_id(ankama_id, dofus_touch))

    def get_item_by_name(self, name, dofus_touch=False):
        return self._moved(self._real.get_item_by_name(name, dofus_touch))

    def __getattr__(self, name):
        return getattr(self._real, name)


def renumbered_beta(shift=1):
    """get_structure with the Beta renumbered and the other versions as they are."""
    from fashionistapulp import structure as real
    shifted = _Renumbered(real.get_structure('beta'), shift)

    def get_structure(game_version=None):
        if game_version == 'beta':
            return shifted
        return real.get_structure(game_version)
    return get_structure


def _row(char):
    stored = Char.objects.get(pk=char.pk)
    fields = {field.name: getattr(stored, field.name)
              for field in Char._meta.concrete_fields}
    fields = {name: bytes(value) if isinstance(value, memoryview) else value
              for name, value in fields.items()}
    fields['base_stats'] = sorted(CharBaseStats.objects.filter(
        char=stored).values_list('stat', 'total_value', 'scrolled_value'))
    return fields


class _Builds(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('owner', 'o@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)

    def _import(self, version, names, client=None):
        client = client or self.client
        before = set(Char.objects.values_list('id', flat=True))
        answer = client.post(_PREFIX[version] + '/import/text/', {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': 'Cra', 'level': str(LEVEL)})
        self.assertEqual(302, answer.status_code)
        made = Char.objects.exclude(id__in=before).get()
        self.assertEqual(version, made.game_version)
        return made

    def _dofus3_build(self):
        char = self._import('dofus3', _shared_pieces(LEVEL)
                            + [_name('dofus3', TROPHY_CHANGED_ON_THE_BETA)])
        CharBaseStats.objects.filter(char=char, stat='Vitality').update(
            total_value=40, scrolled_value=10)
        Char.objects.filter(pk=char.pk).update(link_shared=False, auto_publish=False)
        return Char.objects.get(pk=char.pk)

    def _copy(self, char, version, client=None, shared=False):
        client = client or self.client
        prefix = _PREFIX[char.game_version]
        if shared:
            path = '%s/copysharedtoversion/%s/' % (prefix, encode_char_id(char.id))
        else:
            path = '%s/copytoversion/%d/' % (prefix, char.id)
        return client.post(path, {'version': version})

    def _newest(self, version):
        return Char.objects.filter(game_version=version).order_by('-id').first()


class ACopyLandsOnTheSiblingVersionTests(_Builds):

    def test_the_fixture_is_below_the_level_cap(self):
        char = self._dofus3_build()
        self.assertLess(char.level, 200)
        worn, _solution = _worn(char)
        self.assertEqual(3, len(worn))

    def test_the_copy_wears_the_same_pieces_on_the_beta(self):
        char = self._dofus3_build()
        answer = self._copy(char, 'beta')
        copy = self._newest('beta')
        self.assertIsNotNone(copy)
        self.assertEqual('/beta/loadproject/%d/' % copy.id, answer['Location'])
        self.assertEqual(set(_worn(char)[0]), set(_worn(copy)[0]))
        self.assertEqual(char.name, copy.name)
        self.assertEqual(self.owner, copy.owner)
        self.assertFalse(copy.link_shared)
        self.assertFalse(copy.auto_publish)
        self.assertEqual('', copy.solved_version)
        self.assertIsNone(copy.solved_time)
        self.assertIsNotNone(copy.stuff_time)
        self.assertEqual(
            sorted(CharBaseStats.objects.filter(char=char).values_list(
                'stat', 'total_value', 'scrolled_value')),
            sorted(CharBaseStats.objects.filter(char=copy).values_list(
                'stat', 'total_value', 'scrolled_value')))

    def test_the_copy_gets_the_ban_only_the_beta_could_seed(self):
        from chardata.lock_forbid import get_all_exclusions_ids
        self.assertIsNone(get_structure('dofus3').get_item_by_ankama_id(BETA_ONLY_PIECE_BANNED_BY_DEFAULT))
        char = self._dofus3_build()
        self._copy(char, 'beta')
        copy = self._newest('beta')
        test_item = get_structure('beta').get_item_by_ankama_id(BETA_ONLY_PIECE_BANNED_BY_DEFAULT)
        self.assertIn(test_item.id, get_all_exclusions_ids(copy))
        carried = [get_structure('beta').get_item_by_id(item_id).ankama_id
                   for item_id in get_all_exclusions_ids(copy)]
        before = [get_structure('dofus3').get_item_by_id(item_id).ankama_id
                  for item_id in get_all_exclusions_ids(char)]
        from chardata.lock_forbid import (DEFAULT_EXCLUSION_ANKAMA_IDS,
                                          DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION)
        only_beta = {ankama_id for ankama_id in set(DEFAULT_EXCLUSION_ANKAMA_IDS)
                     | set(DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION['beta'])
                     if get_structure('beta').get_item_by_ankama_id(ankama_id)
                     and not get_structure('dofus3').get_item_by_ankama_id(ankama_id)}
        self.assertIn(BETA_ONLY_PIECE_BANNED_BY_DEFAULT, only_beta)
        self.assertEqual(sorted(set(before) | only_beta), sorted(carried))
        self.assertEqual(len(before) + len(only_beta), len(carried))

    def test_the_source_is_left_exactly_as_it_was(self):
        char = self._dofus3_build()
        before = _row(char)
        self.assertTrue(before['minimal_solution'])
        self.assertEqual(302, self._copy(char, 'beta').status_code)
        self.assertEqual(before, _row(char))

    def test_the_copy_reads_its_numbers_from_the_beta(self):
        before = _by_key(get_structure('dofus3'),
                         get_structure('dofus3').get_item_by_ankama_id(TROPHY_CHANGED_ON_THE_BETA))
        after = _by_key(get_structure('beta'),
                        get_structure('beta').get_item_by_ankama_id(TROPHY_CHANGED_ON_THE_BETA))
        self.assertNotEqual(before, after,
                            'the trophy no longer differs between the versions')
        char = self._dofus3_build()
        self._copy(char, 'beta')
        copy = self._newest('beta')
        source_worn, source_set = _worn(char)
        copy_worn, copy_set = _worn(copy)
        self.assertEqual(before, {key: value for key, value
                                  in source_worn[TROPHY_CHANGED_ON_THE_BETA].stats.items() if value})
        self.assertEqual(after, {key: value for key, value
                                 in copy_worn[TROPHY_CHANGED_ON_THE_BETA].stats.items() if value})
        source_gear, copy_gear = source_set.get_stats_gear(), copy_set.get_stats_gear()
        for key in set(before) | set(after):
            self.assertEqual(after.get(key, 0) - before.get(key, 0),
                             copy_gear[key] - source_gear[key], key)
        stored = _read_back(Char.objects.get(pk=copy.pk).minimal_solution)
        self.assertEqual(30, stored.stats.get('vit'))
        self.assertEqual(10, stored.input['base_stats_by_attr']['Vitality'])

    def test_every_piece_found_is_said_once(self):
        char = self._dofus3_build()
        page = self.client.post('/copytoversion/%d/' % char.id,
                                {'version': 'beta'}, follow=True,
                                HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Copied from Dofus 3. Every piece of the build exists here.')
        again = self.client.get(page.redirect_chain[-1][0],
                                HTTP_ACCEPT_LANGUAGE='en')
        self.assertNotContains(again, 'Copied from Dofus 3.')

    def test_a_piece_the_target_lacks_is_left_out_and_named(self):
        horn = _name('beta', BETA_ONLY_PIECE)
        self.assertIsNone(get_structure('dofus3').get_item_by_ankama_id(BETA_ONLY_PIECE))
        char = self._import('beta', _shared_pieces(LEVEL) + [horn])
        self.assertIn(BETA_ONLY_PIECE, _worn(char)[0])
        page = self.client.post('/beta/copytoversion/%d/' % char.id,
                                {'version': 'dofus3'}, follow=True,
                                HTTP_ACCEPT_LANGUAGE='en')
        copy = self._newest('dofus3')
        worn = _worn(copy)[0]
        self.assertNotIn(BETA_ONLY_PIECE, worn)
        self.assertEqual(2, len(worn))
        body = _text(page.content.decode('utf-8'))
        self.assertIn('Copied from Dofus 3 Beta. These pieces do not exist here and were left out:', body)
        self.assertIn('left out: %s (Dofus)' % horn, body)

    def test_the_report_speaks_the_readers_language(self):
        horn = get_structure('beta').get_item_by_ankama_id(BETA_ONLY_PIECE)
        char = self._import('beta', _shared_pieces(LEVEL) + [_name('beta', BETA_ONLY_PIECE)])
        page = self.client.post('/fr/beta/copytoversion/%d/' % char.id,
                                {'version': 'dofus3'}, follow=True,
                                HTTP_ACCEPT_LANGUAGE='fr')
        name = get_structure('beta').get_item_name_in_language(horn, 'fr')
        self.assertNotEqual(horn.name, name)
        self.assertIn(name, _text(page.content.decode('utf-8')))


class OnlyTheOwnerOrASharedLinkCopiesTests(_Builds):

    def setUp(self):
        super().setUp()
        self.stranger = User.objects.create_user('stranger', 's@x.test', 'pw-42-solid')

    def test_a_strangers_private_build_is_refused(self):
        char = self._dofus3_build()
        self.client.force_login(self.stranger)
        self.assertEqual(403, self._copy(char, 'beta').status_code)
        self.assertEqual(403, self._copy(char, 'beta', shared=True).status_code)
        self.assertFalse(Char.objects.filter(game_version='beta').exists())

    def test_a_shared_build_is_copied_into_the_visitors_builds(self):
        char = self._dofus3_build()
        char.link_shared = True
        char.save()
        self.client.force_login(self.stranger)
        self.assertEqual(302, self._copy(char, 'beta', shared=True).status_code)
        copy = self._newest('beta')
        self.assertEqual(self.stranger, copy.owner)
        self.assertFalse(copy.link_shared)
        self.assertEqual(set(_worn(char)[0]), set(_worn(copy)[0]))

    def test_a_visitors_copy_follows_the_visitors_choice_not_the_authors(self):
        from chardata.create_project_view import wants_to_publish
        from django.test import RequestFactory
        char = self._dofus3_build()
        Char.objects.filter(pk=char.pk).update(link_shared=True, auto_publish=False)
        self.client.force_login(self.stranger)
        self._copy(char, 'beta', shared=True)
        request = RequestFactory().post('/', {'version': 'beta'})
        request.user = self.stranger
        self.assertTrue(wants_to_publish(request))
        self.assertTrue(self._newest('beta').auto_publish)

    def test_a_guests_copy_of_a_published_build_never_publishes_itself(self):
        from chardata.solution import get_solution, set_solution
        char = self._dofus3_build()
        Char.objects.filter(pk=char.pk).update(link_shared=True, auto_publish=True)
        self.client.logout()
        self.assertEqual(302, self._copy(char, 'beta', shared=True).status_code)
        copy = self._newest('beta')
        self.assertIsNone(copy.owner)
        self.assertFalse(copy.auto_publish)
        self.assertFalse(copy.link_shared)
        set_current_game_version('beta')
        try:
            set_solution(copy, get_solution(copy))
        finally:
            set_current_game_version('dofus3')
        self.assertFalse(Char.objects.get(pk=copy.pk).link_shared)
        self.assertTrue(Char.objects.get(pk=char.pk).auto_publish)

    def test_only_a_sibling_is_accepted_and_only_by_post(self):
        char = self._dofus3_build()
        self.assertEqual(404, self._copy(char, 'dofus2').status_code)
        self.assertEqual(404, self._copy(char, 'dofus3').status_code)
        self.assertEqual(405, self.client.get('/copytoversion/%d/' % char.id).status_code)
        self.assertEqual(1, Char.objects.count())

    def test_a_guest_copy_is_remembered_as_the_guests_beta_build(self):
        self.client.logout()
        char = self._dofus3_build()
        self.assertIsNone(char.owner)
        self.assertEqual(302, self._copy(char, 'beta').status_code)
        copy = self._newest('beta')
        self.assertIsNone(copy.owner)
        self.assertEqual(copy.id, self.client.session['char_ids']['beta'])
        self.assertEqual(char.id, self.client.session['char_ids']['dofus3'])
        self.assertEqual(200, self.client.get('/beta/solution/%d/' % copy.id).status_code)

    def test_a_guest_who_holds_a_beta_build_keeps_it(self):
        self.client.logout()
        held = self._import('beta', _shared_pieces(LEVEL))
        char = self._dofus3_build()
        before = dict(self.client.session['char_ids'])
        self.assertEqual(held.id, before['beta'])
        answer = self._copy(char, 'beta')
        self.assertEqual('/beta/loadprojectserror/guest_has_one/', answer['Location'])
        self.assertEqual(before, dict(self.client.session['char_ids']))
        self.assertEqual([held.id], list(Char.objects.filter(
            game_version='beta').values_list('id', flat=True)))
        page = self.client.get(answer['Location'], HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'You already have a build on Dofus 3 Beta')
        self.assertContains(page, held.name)


class TheCapOfTheTargetVersionHoldsTests(_Builds):

    def test_a_full_beta_refuses_the_copy_like_a_duplicate(self):
        char = self._dofus3_build()
        self._import('beta', _shared_pieces(LEVEL))
        with mock.patch('chardata.create_project_view.MAXIMUM_NUMBER_OF_PROJECTS', 1):
            answer = self._copy(char, 'beta')
        self.assertEqual('/beta/loadprojectserror/too_many/', answer['Location'])
        self.assertEqual(1, Char.objects.filter(game_version='beta').count())

    def test_the_source_versions_builds_do_not_count(self):
        char = self._dofus3_build()
        self._import('dofus3', _shared_pieces(LEVEL))
        with mock.patch('chardata.create_project_view.MAXIMUM_NUMBER_OF_PROJECTS', 1):
            answer = self._copy(char, 'beta')
        self.assertEqual(302, answer.status_code)
        self.assertEqual(1, Char.objects.filter(game_version='beta').count())


class TheCopyIsOfferedWhereTheDuplicateIsTests(_Builds):

    def test_the_build_page_and_the_build_list_offer_the_sibling(self):
        char = self._dofus3_build()
        for path in ('/solution/%d/' % char.id, '/loadprojects/'):
            page = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
            self.assertContains(page, 'Copy to Dofus 3 Beta')
        page = self.client.get('/solution/%d/' % char.id).content.decode('utf-8')
        self.assertRegex(page, r'action="?/copytoversion/%d/' % char.id)

    def test_the_beta_offers_dofus3_and_dofus2_offers_nothing(self):
        self._import('beta', _shared_pieces(LEVEL))
        page = self.client.get('/beta/loadprojects/', HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Copy to Dofus 3"')
        self.assertNotContains(page, 'Copy to Dofus 3 Beta')
        dofus2 = get_structure('dofus2')
        hat = next(item for item in dofus2.types[LEVEL]['Hat'] if not item.removed
                   and dofus2.get_item_by_name(item.name) is item)
        self.addCleanup(_PREFIX.pop, 'dofus2')
        _PREFIX['dofus2'] = '/dofus2'
        built = self._import('dofus2', [dofus2.get_item_name_in_language(hat, 'en')])
        page = self.client.get('/dofus2/loadprojects/', HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'button-duplicate-project')
        self.assertContains(page, built.name)
        self.assertNotContains(page, 'Copy to')
        page = self.client.get('/dofus2/solution/%d/' % built.id, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, page.status_code)
        self.assertContains(page, 'Duplicate')
        self.assertNotContains(page, 'Copy to')

    def test_the_list_copies_under_the_readers_language(self):
        self._dofus3_build()
        page = self.client.get('/fr/loadprojects/').content.decode('utf-8')
        self.assertRegex(page, r'data-action="?/fr/copytoversion/0/')
        self.assertNotIn('"/copytoversion/', page)
        self.assertNotIn('}}/copytoversion/', page)

    def test_a_shared_build_offers_the_copy_to_its_visitors(self):
        char = self._dofus3_build()
        char.link_shared = True
        char.save()
        self.client.force_login(User.objects.create_user('v', 'v@x.test', 'pw-42-solid'))
        from chardata.util import shared_build_path
        page = self.client.get(shared_build_path(char), HTTP_ACCEPT_LANGUAGE='en',
                               follow=True)
        self.assertRegex(page.content.decode('utf-8'),
                         r'action="?/copysharedtoversion/%s/'
                         % re.escape(encode_char_id(char.id)))


class ACopyWritesTheTargetsOwnIdsTests(_Builds):
    """The Beta renumbered: every stored id must be the Beta's, never the source's."""

    SHIFT = 1

    def _source_with_locks_bans_and_rolls(self):
        char = self._dofus3_build()
        dofus3, beta = get_structure('dofus3'), get_structure('beta')
        source_minimal = _read_back(Char.objects.get(pk=char.pk).minimal_solution)
        hat = dofus3.get_item_by_id(source_minimal.item_per_slot['hat'])
        other_hat = next(item for item in dofus3.types[LEVEL]['Hat']
                         if not item.removed and item.ankama_id != hat.ankama_id
                         and beta.get_item_by_ankama_id(item.ankama_id) is not None)
        vitality = dofus3.get_stat_by_key('vit')
        Char.objects.filter(pk=char.pk).update(
            inclusions=pickle.dumps({'hat': hat.id}),
            exclusions=pickle.dumps([other_hat.id]),
            stat_overrides=pickle.dumps({hat.id: {vitality.id: 55}}))
        return Char.objects.get(pk=char.pk), source_minimal, hat, other_hat

    def _beta_id(self, item):
        return get_structure('beta').get_item_by_ankama_id(item.ankama_id).id + self.SHIFT

    def test_the_set_locks_bans_and_rolls_carry_the_betas_ids(self):
        char, source_minimal, hat, other_hat = self._source_with_locks_bans_and_rolls()
        dofus3 = get_structure('dofus3')
        stored_sets = []
        with mock.patch('chardata.version_copy.get_structure', renumbered_beta(self.SHIFT)), \
                mock.patch('chardata.version_copy._store_the_set',
                           lambda char, minimal, item_per_slot: stored_sets.append(item_per_slot)):
            self.assertEqual(302, self._copy(char, 'beta').status_code)
        copy = self._newest('beta')
        self.assertEqual(1, len(stored_sets))
        worn = {slot: item_id for slot, item_id in source_minimal.item_per_slot.items()
                if item_id is not None}
        self.assertEqual(3, len(worn))
        self.assertEqual({slot: self._beta_id(dofus3.get_item_by_id(item_id))
                          for slot, item_id in worn.items()},
                         {slot: item_id for slot, item_id in stored_sets[0].items()
                          if item_id is not None})
        for slot, item_id in worn.items():
            self.assertNotEqual(item_id, stored_sets[0][slot])
        stored = Char.objects.get(pk=copy.pk)
        self.assertEqual({'hat': self._beta_id(hat)}, _read_back(stored.inclusions))
        exclusions = _read_back(stored.exclusions)
        self.assertIn(self._beta_id(other_hat), exclusions)
        self.assertNotIn(other_hat.id, exclusions)
        vitality = get_structure('beta').get_stat_by_key('vit')
        self.assertEqual({self._beta_id(hat): {vitality.id: 55}},
                         _read_back(stored.stat_overrides))
