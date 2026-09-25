# -*- coding: utf-8 -*-
"""A tool auditing every page in one sweep must be filtered like a crawler, or it distorts every traffic ratio."""
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
        """The half that matters: a filter treating everything as a robot would pass the test above too."""
        for ua in (A_READER, A_PHONE):
            self.assertFalse(self.agent(ua), 'a reader was filtered out: %s' % ua)

    def test_the_known_crawlers_are_still_caught(self):
        for ua in ('Googlebot/2.1', 'curl/8.4.0', 'python-requests/2.31',
                   'facebookexternalhit/1.1', ''):
            self.assertTrue(self.agent(ua), '%r slipped through' % ua)
