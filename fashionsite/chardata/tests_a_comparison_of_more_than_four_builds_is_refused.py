"""The compare page and its share link answer 404 past the four builds the picker allows."""
from django.contrib.auth.models import User
from django.http import Http404
from django.test import SimpleTestCase, TestCase

from chardata.compare_sets_view import MAX_COMPARED_BUILDS, _process_parameters
from chardata.models import Char


class TheComparedListIsCapped(SimpleTestCase):

    def test_the_cap_matches_the_picker(self):
        self.assertEqual(4, MAX_COMPARED_BUILDS)

    def test_four_entries_are_read_as_they_come(self):
        self.assertEqual(['1', '1', '1', '1'], _process_parameters('1/1/1/1/'))

    def test_five_entries_are_refused_even_when_they_repeat(self):
        with self.assertRaises(Http404):
            _process_parameters('/'.join(['s1'] * 5))


class TheCompareRoutesRefuseALongList(TestCase):

    def setUp(self):
        self.client.force_login(User.objects.create_user('comparer', 'c@x.test', 'pw'))
        self.ids = []
        for number in range(5):
            self.client.post('/createproject/', {
                'project': 'b%d' % number, 'charname': 'b%d' % number, 'level': '150',
                'class': 'Iop', 'where_to_go': 'wizard', 'publish_choice': '1'})
            char = Char.objects.order_by('-id').first()
            self.client.get('/solution/%d/' % char.id, follow=True)
            self.ids.append(char.id)

    def path(self, route, count):
        return '/%s/%s' % (route, '/'.join(str(i) for i in self.ids[:count]))

    def test_the_compare_page_answers_four_builds_and_refuses_five(self):
        self.assertEqual(200, self.client.get(self.path('compare_sets', 4)).status_code)
        self.assertEqual(404, self.client.get(self.path('compare_sets', 5)).status_code)

    def test_the_sharing_link_answers_four_builds_and_refuses_five(self):
        self.assertEqual(200, self.client.get(
            self.path('get_compare_sharing_link', 4)).status_code)
        self.assertEqual(404, self.client.get(
            self.path('get_compare_sharing_link', 5)).status_code)

    def test_a_deeply_nested_list_of_links_is_a_message_not_a_server_error(self):
        response = self.client.post('/choose_compare_sets_post/',
                                    {'links': '[' * 100000})
        self.assertEqual(200, response.status_code)
