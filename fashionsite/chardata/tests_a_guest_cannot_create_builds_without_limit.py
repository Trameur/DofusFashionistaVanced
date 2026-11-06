"""A guest who creates builds is capped per session and per address, on every door that creates one; a signed-in player is not."""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from chardata import create_project_view
from chardata.models import Char

FORM = {'project': 'p', 'charname': 'Perso', 'level': '150', 'class': 'Iop',
        'where_to_go': 'wizard'}


class AGuestsNewBuildsAreCapped(TestCase):

    def create(self, **extra):
        return self.client.post('/createproject/', FORM, **extra)

    def test_the_address_ceiling_refuses_the_next_build(self):
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_ADDRESS', 2):
            answers = [self.create() for _ in range(3)]
        self.assertEqual(2, Char.objects.count())
        self.assertNotIn('create_limit', answers[1]['Location'])
        self.assertEqual('/loadprojectserror/create_limit/', answers[2]['Location'])

    def test_the_session_ceiling_refuses_the_next_build_from_another_address(self):
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_SESSION', 2):
            answers = [self.create(REMOTE_ADDR='10.0.0.%d' % i) for i in range(3)]
        self.assertEqual(2, Char.objects.count())
        self.assertEqual('/loadprojectserror/create_limit/', answers[2]['Location'])

    def test_a_signed_in_player_is_not_counted(self):
        self.client.force_login(User.objects.create_user('maker', 'm@x.test', 'pw'))
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_ADDRESS', 1):
            answers = [self.create() for _ in range(3)]
        self.assertEqual(3, Char.objects.count())
        self.assertTrue(all('create_limit' not in a['Location'] for a in answers))


class QuickStartAndSmartBuildAreCappedToo(TestCase):

    QUICKSTART = {'char_class': 'Iop', 'char_level': '200', 'element': 'str'}
    SMARTBUILD = {'q': 'Iop 200 earth PvM', 'confirm': '1'}

    def post_all(self, path, form, times, **extra):
        return [self.client.post(path, form, **extra) for _ in range(times)]

    def test_quickstart_stops_at_the_address_ceiling(self):
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_ADDRESS', 2):
            answers = self.post_all('/quickstart/', self.QUICKSTART, 4)
        self.assertEqual(2, Char.objects.count())
        self.assertEqual('/loadprojectserror/create_limit/', answers[2]['Location'])
        self.assertEqual('/loadprojectserror/create_limit/', answers[3]['Location'])

    def test_quickstart_stops_at_the_session_ceiling(self):
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_SESSION', 2):
            answers = [self.client.post('/quickstart/', self.QUICKSTART,
                                        REMOTE_ADDR='10.0.0.%d' % i) for i in range(4)]
        self.assertEqual(2, Char.objects.count())
        self.assertEqual('/loadprojectserror/create_limit/', answers[3]['Location'])

    def test_smart_build_stops_at_the_address_ceiling(self):
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_ADDRESS', 2):
            answers = self.post_all('/smartbuild/', self.SMARTBUILD, 4)
        self.assertEqual(2, Char.objects.count())
        self.assertEqual('/loadprojectserror/create_limit/', answers[2]['Location'])

    def test_the_three_doors_share_one_count(self):
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_ADDRESS', 3):
            self.create_by_setup()
            self.post_all('/quickstart/', self.QUICKSTART, 1)
            self.post_all('/smartbuild/', self.SMARTBUILD, 1)
            refused = [self.create_by_setup(),
                       self.post_all('/quickstart/', self.QUICKSTART, 1)[0],
                       self.post_all('/smartbuild/', self.SMARTBUILD, 1)[0]]
        self.assertEqual(3, Char.objects.count())
        self.assertTrue(all(a['Location'] == '/loadprojectserror/create_limit/'
                            for a in refused))

    def create_by_setup(self):
        return self.client.post('/createproject/', FORM)

    def test_a_signed_in_player_is_not_counted(self):
        self.client.force_login(User.objects.create_user('maker2', 'm2@x.test', 'pw'))
        with mock.patch.object(create_project_view, 'GUEST_CREATES_PER_ADDRESS', 1):
            self.post_all('/quickstart/', self.QUICKSTART, 3)
            self.post_all('/smartbuild/', self.SMARTBUILD, 3)
        self.assertEqual(6, Char.objects.count())

    def test_the_refusal_page_says_created_not_copied(self):
        page = self.client.get('/loadprojectserror/create_limit/').content.decode()
        self.assertIn('You have created too many builds for now', page)
        self.assertNotIn('copied too many', page)
