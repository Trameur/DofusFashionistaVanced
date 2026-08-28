# -*- coding: utf-8 -*-
"""A counter that stops counting has to say so.

`PageHitMiddleware` swallows every exception on purpose: a page must not break
because a statistic could not be written. But swallowed in silence, a broken
counter is indistinguishable from a quiet day -- and the table holds runs of
eight consecutive days with no rows at all, on a site that was up.

So the swallowing stays, and a warning goes with it. Warning and not error:
this project's root logger hands ERROR to `mail_admins`, and a counter failing
on every request would mail on every request.
"""
from unittest import mock

from django.test import RequestFactory, TestCase

from chardata.middleware import PageHitMiddleware


class TheCounterSaysWhenItFails(TestCase):

    def a_request(self):
        request = RequestFactory().get('/encyclopedia/')
        request.META['HTTP_USER_AGENT'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
        return request

    def a_broken_middleware(self):
        sentinel = object()
        return PageHitMiddleware(lambda request: sentinel), sentinel

    def test_the_page_is_still_served(self):
        """The half that must never regress: counting is not worth a 500.

        Deliberately free of any assertion on logging, so that removing the
        log line fails the other test and not this one.
        """
        middleware, sentinel = self.a_broken_middleware()
        with mock.patch.object(PageHitMiddleware, 'count',
                               side_effect=RuntimeError('the table is gone')):
            self.assertIs(sentinel, middleware(self.a_request()))

    def test_the_failure_is_written_down(self):
        middleware, _ = self.a_broken_middleware()
        with mock.patch.object(PageHitMiddleware, 'count',
                               side_effect=RuntimeError('the table is gone')):
            with self.assertLogs('chardata.middleware', level='WARNING') as logs:
                middleware(self.a_request())
        output = logs.output
        self.assertEqual(1, len(output), output)
        self.assertIn('not counted', output[0])
        self.assertIn('the table is gone', output[0],
                      'the log says something failed but not what')

    def test_nothing_is_logged_when_counting_works(self):
        """Otherwise every page view would write a line."""
        middleware = PageHitMiddleware(lambda request: object())
        with mock.patch.object(PageHitMiddleware, 'count', return_value=None):
            with self.assertNoLogs('chardata.middleware', level='WARNING'):
                middleware(self.a_request())
