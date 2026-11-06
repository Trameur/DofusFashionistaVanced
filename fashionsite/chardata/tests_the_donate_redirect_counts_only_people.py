# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A crawler or a HEAD on /out/donate/ is sent on to the donation page like anyone, and is not counted as a click."""
from django.conf import settings
from django.test import TestCase

from chardata.models import SupportClick

A_READER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
CRAWLERS = ('Lightpanda/1.0', 'meta-webindexer/1.1', 'GPTBot/1.2',
            'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'facebookexternalhit/1.1', 'python-requests/2.31.0', '')


def _the_donation_page():
    return settings.SUPPORT_LINKS[0]['url']


def _clicks():
    return sum(SupportClick.objects.values_list('count', flat=True))


class TheDonateRedirectCountsOnlyPeopleTests(TestCase):

    def test_a_reader_is_sent_on_and_counted_once(self):
        response = self.client.get('/out/donate/', HTTP_USER_AGENT=A_READER)
        self.assertEqual(302, response.status_code)
        self.assertEqual(_the_donation_page(), response['Location'])
        self.assertEqual(1, _clicks())

    def test_a_crawler_is_sent_on_and_not_counted(self):
        for agent in CRAWLERS:
            response = self.client.get('/out/donate/', HTTP_USER_AGENT=agent)
            self.assertEqual(302, response.status_code, agent)
            self.assertEqual(_the_donation_page(), response['Location'], agent)
        self.assertEqual(0, _clicks())

    def test_a_crawler_on_the_indexed_route_is_not_counted_either(self):
        for agent in CRAWLERS:
            response = self.client.get('/out/donate/0/', HTTP_USER_AGENT=agent)
            self.assertEqual(302, response.status_code, agent)
        self.assertEqual(0, _clicks())

    def test_a_head_is_sent_on_and_not_counted(self):
        response = self.client.head('/out/donate/', HTTP_USER_AGENT=A_READER)
        self.assertEqual(302, response.status_code)
        self.assertEqual(_the_donation_page(), response['Location'])
        self.assertEqual(0, _clicks())

    def test_a_crawler_does_not_add_to_the_count_a_reader_made(self):
        self.client.get('/out/donate/', HTTP_USER_AGENT=A_READER)
        self.client.get('/out/donate/', HTTP_USER_AGENT='Lightpanda/1.0')
        self.client.head('/out/donate/', HTTP_USER_AGENT=A_READER)
        self.assertEqual(1, _clicks())

    def test_a_crawler_that_names_a_placement_is_not_counted_there(self):
        self.client.get('/out/donate/?from=solution', HTTP_USER_AGENT='GPTBot/1.2')
        self.assertFalse(SupportClick.objects.filter(source='solution').exists())
