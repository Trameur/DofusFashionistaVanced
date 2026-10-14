# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Only a POST with its token signs a reader out: a prefetch, a crawler or an image tag on another site reaches /logout/ with a GET and must change nothing."""
import os
import re
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import resolve, reverse

from chardata import login_view


class _Forms(HTMLParser):
    """Each form of a page with its action, its method and its hidden inputs."""

    def __init__(self, html):
        super().__init__()
        self.forms = []
        self._open = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self._open = {'action': attrs.get('action', ''),
                          'method': (attrs.get('method') or 'get').lower(),
                          'fields': {}}
            self.forms.append(self._open)
        elif tag == 'input' and self._open is not None and attrs.get('name'):
            self._open['fields'][attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self._open = None


def _signed_in(client):
    return '_auth_user_id' in client.session


class ALogoutSignsOutOnlyOnAPostTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('leaver', 'lv@x.test', 'pw-42-solid')
        self.client.force_login(self.user)

    def test_a_get_is_refused_and_signs_nobody_out(self):
        self.assertEqual(405, self.client.get('/logout/').status_code)
        self.assertTrue(_signed_in(self.client))

    def test_a_get_carrying_a_next_is_refused_and_signs_nobody_out(self):
        self.assertEqual(405, self.client.get('/logout/?next=/').status_code)
        self.assertTrue(_signed_in(self.client))

    def test_a_head_is_refused_and_signs_nobody_out(self):
        self.assertEqual(405, self.client.head('/logout/').status_code)
        self.assertTrue(_signed_in(self.client))

    def test_a_post_signs_out_and_goes_home(self):
        response = self.client.post('/logout/')
        self.assertEqual(302, response.status_code)
        self.assertEqual('/', response['Location'])
        self.assertFalse(_signed_in(self.client))

    def test_a_post_goes_back_to_a_page_of_this_site(self):
        response = self.client.post('/logout/', {'next': '/sharedbuilds/'})
        self.assertEqual('/sharedbuilds/', response['Location'])
        self.assertFalse(_signed_in(self.client))

    def test_a_post_never_goes_to_another_site(self):
        response = self.client.post('/logout/', {'next': 'https://evil.example/'})
        self.assertEqual('/', response['Location'])
        self.assertFalse(_signed_in(self.client))

    def test_a_post_without_its_token_is_refused_and_signs_nobody_out(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(403, strict.post('/logout/').status_code)
        self.assertTrue(_signed_in(strict))


class TheMenuLogoutIsAPostFormTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('leaver2', 'lv2@x.test', 'pw-42-solid')

    def _logout_forms(self, client):
        html = client.get('/').content.decode('utf-8')
        return [form for form in _Forms(html).forms
                if form['action'].rstrip('/').endswith('/logout')]

    def test_the_menu_asks_to_log_out_with_a_post_form_carrying_its_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        forms = self._logout_forms(client)
        self.assertEqual(1, len(forms))
        self.assertEqual('post', forms[0]['method'])
        self.assertIn('csrfmiddlewaretoken', forms[0]['fields'])

    def test_sending_that_form_back_signs_the_reader_out(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        form = self._logout_forms(client)[0]
        response = client.post(form['action'], form['fields'])
        self.assertEqual(302, response.status_code)
        self.assertFalse(_signed_in(client))

    def test_a_signed_out_page_offers_no_logout(self):
        self.assertEqual([], self._logout_forms(self.client))

    def test_the_menu_url_is_the_route_that_signs_out(self):
        self.assertEqual('/logout/', reverse('auth:logout'))
        self.assertIs(login_view.logout_view, resolve('/logout/').func)


_ANCHOR_TO_LOGOUT = re.compile(r'<a\b[^>]*\bhref\b[^>]*logout', re.I)

LINKS_TO_LOGOUT = (
    '<a href="/logout/">',
    '<a class="menu" href="/logout/?next=/">',
    "<a href=\"{% url 'auth:logout' %}\">",
    '<a href="{% url "auth:logout" %}">',
    "<a href='{% game_url \"logout\" %}'>",
    "<a\n  href=\"{% game_url 'logout' %}\"\n  class=\"x\">",
)

LINKS_TO_OTHER_PLACES = (
    '<a href="/about/">',
    "<a href=\"{% url 'auth:login' %}\">Log in</a>",
    "<form action=\"{% url 'auth:logout' %}\" method=\"post\">",
)


class NoTemplateLinksToLogoutWithAGetTests(TestCase):

    def test_the_guard_sees_every_way_a_template_writes_a_link_to_logout(self):
        for written in LINKS_TO_LOGOUT:
            self.assertTrue(_ANCHOR_TO_LOGOUT.search(written), written)

    def test_the_guard_leaves_other_links_and_the_logout_form_alone(self):
        for written in LINKS_TO_OTHER_PLACES:
            self.assertFalse(_ANCHOR_TO_LOGOUT.search(written), written)

    def test_no_anchor_in_any_template_points_at_the_logout_route(self):
        root = os.path.join(os.path.dirname(os.path.abspath(login_view.__file__)),
                            'templates')
        offenders = []
        for folder, _dirs, names in os.walk(root):
            for name in names:
                if not name.endswith(('.html', '.txt', '.js')):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding='utf-8') as handle:
                    if _ANCHOR_TO_LOGOUT.search(handle.read()):
                        offenders.append(path)
        self.assertEqual([], offenders)
