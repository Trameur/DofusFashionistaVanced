"""The load link answers only for the build's owner, like the pages it redirects to."""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char


class LoadingAProject(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('owner', 'o@x.test', 'pw')
        self.client.force_login(self.owner)
        self.client.post('/createproject/', {
            'project': 'p', 'charname': 'Perso', 'level': '150',
            'class': 'Iop', 'where_to_go': 'wizard'})
        self.char = Char.objects.order_by('-id').first()

    def load(self, prefix=''):
        return self.client.get('%s/loadproject/%d/' % (prefix, self.char.id))

    def test_the_owner_is_sent_on(self):
        self.assertEqual(302, self.load().status_code)

    def test_a_stranger_is_refused(self):
        self.client.force_login(User.objects.create_user('other', 'x@x.test', 'pw'))
        self.assertEqual(403, self.load().status_code)

    def test_a_visitor_is_refused(self):
        self.client.logout()
        self.assertEqual(403, self.load().status_code)

    def test_a_missing_build_is_a_404(self):
        self.assertEqual(404, self.client.get('/loadproject/999999/').status_code)

    def test_a_build_of_another_game_version_is_a_404(self):
        self.assertEqual(404, self.load('/retro').status_code)
