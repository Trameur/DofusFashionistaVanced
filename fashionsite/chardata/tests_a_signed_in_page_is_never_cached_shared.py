"""An HTML page answered to a signed-in player is private and not stored, unless the view chose its own Cache-Control."""
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.middleware import PrivateForSignedInMiddleware


def _through(body, user, content_type='text/html', cache_control=None, cookie=True):
    def view(request):
        response = HttpResponse(body, content_type=content_type)
        if cache_control:
            response['Cache-Control'] = cache_control
        return response
    request = RequestFactory().get('/')
    request.user = user
    if cookie:
        request.COOKIES['sessionid'] = 'abc'
    return PrivateForSignedInMiddleware(view)(request)


class TheMiddleware(SimpleTestCase):

    def test_a_signed_in_html_answer_becomes_private_and_not_stored(self):
        response = _through('<p>hi</p>', User(username='x'))
        self.assertEqual('private, no-store', response['Cache-Control'])

    def test_an_answer_that_set_its_own_policy_keeps_it(self):
        response = _through('<p>hi</p>', User(username='x'), cache_control='max-age=60')
        self.assertEqual('max-age=60', response['Cache-Control'])

    def test_a_visitor_gets_no_header(self):
        self.assertFalse(_through('<p>hi</p>', AnonymousUser()).has_header('Cache-Control'))

    def test_a_signed_in_answer_that_is_not_html_gets_no_header(self):
        response = _through('{}', User(username='x'), content_type='application/json')
        self.assertFalse(response.has_header('Cache-Control'))

    def test_a_request_without_a_session_cookie_is_left_alone(self):
        response = _through('<p>hi</p>', User(username='x'), cookie=False)
        self.assertFalse(response.has_header('Cache-Control'))


class ThePagesOfTheSite(TestCase):

    def test_a_signed_in_player_gets_a_private_page(self):
        self.client.force_login(User.objects.create_user('reader', 'r@x.test', 'pw'))
        response = self.client.get('/login/')
        self.assertEqual(200, response.status_code)
        self.assertIn('no-store', response['Cache-Control'])

    def test_a_visitor_page_is_not_marked_no_store(self):
        response = self.client.get('/login/')
        self.assertNotIn('no-store', response.get('Cache-Control', ''))
