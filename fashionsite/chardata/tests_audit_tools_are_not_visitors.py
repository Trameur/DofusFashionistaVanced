# -*- coding: utf-8 -*-
"""A tool auditing this site is not one of its readers.

An audit walks every page in a single pass. On a site whose ordinary day holds
about thirty views, one such sweep put 8 420 into a single day -- 77 % of a
whole month -- and every ratio read off that month came out inverted: the tool
looked thirty times smaller than the content, the beta ten times larger than it
is, and a page type that gets six views in a fortnight looked like the most
visited on the site.

`looks_like_a_robot` already catches what crawlers call themselves. It could
not catch an audit, because an audit is not a crawler and does not say so.
"""
from django.test import RequestFactory, TestCase

from chardata.middleware import looks_like_a_robot

AUDIT = 'FashionistaAudit/1.0 (owner site audit; not a visitor)'
A_READER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
A_PHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
           'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148')


class AnAuditIsNotAVisitor(TestCase):

    def agent(self, ua):
        return looks_like_a_robot(RequestFactory().get('/', HTTP_USER_AGENT=ua))

    def test_the_audit_tool_is_not_counted(self):
        self.assertTrue(self.agent(AUDIT))
        self.assertTrue(self.agent(AUDIT.lower()))
        self.assertTrue(self.agent('fashionistaaudit'))

    def test_a_reader_still_is(self):
        """The half that matters: a filter that answered "robot" to everything
        would pass the test above and count nobody at all."""
        for ua in (A_READER, A_PHONE):
            self.assertFalse(self.agent(ua), 'a reader was filtered out: %s' % ua)

    def test_the_known_crawlers_are_still_caught(self):
        for ua in ('Googlebot/2.1', 'curl/8.4.0', 'python-requests/2.31',
                   'facebookexternalhit/1.1', ''):
            self.assertTrue(self.agent(ua), '%r slipped through' % ua)
