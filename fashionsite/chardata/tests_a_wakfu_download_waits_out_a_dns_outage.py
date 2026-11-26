# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import importlib.util
import os
import socket
import sys
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

ITEMSCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if ITEMSCRAPER not in sys.path:
    sys.path.insert(0, ITEMSCRAPER)

import wakfu_http  # noqa: E402


def _images():
    spec = importlib.util.spec_from_file_location(
        'get_item_images_wakfu', os.path.join(ITEMSCRAPER, 'get_item_images_wakfu.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dns():
    return urllib.error.URLError(socket.gaierror(11001, 'getaddrinfo failed'))


def _http(code):
    return urllib.error.HTTPError('url', code, 'refused', {}, None)


class _Reader:

    def __init__(self, failures, body=b'page'):
        self.failures = list(failures)
        self.body = body
        self.calls = 0

    def open(self, url, timeout=60):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        reader = mock.Mock()
        reader.read.return_value = self.body
        return reader


class _Answer:

    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body


class AWakfuDownloadWaitsOutADnsOutageTests(SimpleTestCase):

    def _page(self, failures):
        reader = _Reader(failures)
        with mock.patch('time.sleep') as sleep, mock.patch('builtins.print'):
            try:
                result = wakfu_http.read_page(reader, 'https://x/y')
            except Exception as error:
                result = error
        return result, [call.args[0] for call in sleep.call_args_list], reader

    def test_a_page_is_returned_after_as_many_dns_failures_as_there_are_dns_waits(self):
        result, waits, _ = self._page([_dns() for _ in wakfu_http.DNS_WAITS])
        self.assertEqual('page', result)
        self.assertEqual(list(wakfu_http.DNS_WAITS), waits)

    def test_one_dns_failure_more_than_the_dns_waits_raises(self):
        result, waits, reader = self._page([_dns() for _ in range(len(wakfu_http.DNS_WAITS) + 1)])
        self.assertIsInstance(result, urllib.error.URLError)
        self.assertEqual(list(wakfu_http.DNS_WAITS), waits)
        self.assertEqual(len(wakfu_http.DNS_WAITS) + 1, reader.calls)

    def test_a_non_dns_url_error_gives_up_after_the_retry_waits(self):
        failures = [urllib.error.URLError(ConnectionResetError('reset'))
                    for _ in range(len(wakfu_http.RETRY_WAITS) + 1)]
        result, waits, _ = self._page(failures)
        self.assertIsInstance(result, urllib.error.URLError)
        self.assertEqual(list(wakfu_http.RETRY_WAITS), waits)

    def test_a_403_is_retried_with_the_retry_waits_then_raised(self):
        failures = [_http(403) for _ in range(len(wakfu_http.RETRY_WAITS) + 1)]
        result, waits, _ = self._page(failures)
        self.assertIsInstance(result, urllib.error.HTTPError)
        self.assertEqual(list(wakfu_http.RETRY_WAITS), waits)

    def test_a_404_returns_none_without_waiting(self):
        result, waits, reader = self._page([_http(404)])
        self.assertIsNone(result)
        self.assertEqual([], waits)
        self.assertEqual(1, reader.calls)

    def test_a_non_retryable_http_code_raises_at_once(self):
        result, waits, _ = self._page([_http(400)])
        self.assertIsInstance(result, urllib.error.HTTPError)
        self.assertEqual([], waits)

    def test_dns_and_other_failures_each_use_their_own_counter(self):
        failures = [_dns(), urllib.error.URLError(ConnectionResetError('reset')), _dns()]
        result, waits, _ = self._page(failures)
        self.assertEqual('page', result)
        self.assertEqual([5, 5, 15], waits)

    def _picture(self, failures):
        module = _images()
        answers = [error if isinstance(error, Exception) else _Answer(error)
                   for error in failures]

        def urlopen(request, timeout=40):
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        with mock.patch('time.sleep') as sleep, mock.patch('builtins.print'), \
                mock.patch.object(module.urllib.request, 'urlopen', side_effect=urlopen):
            try:
                result = module.fetch(123, 64)
            except Exception as error:
                result = error
        return result, [call.args[0] for call in sleep.call_args_list]

    def test_a_picture_is_returned_after_the_dns_outage_is_waited_out(self):
        result, waits = self._picture([_dns() for _ in wakfu_http.DNS_WAITS] + [b'png'])
        self.assertEqual(b'png', result)
        self.assertEqual(list(wakfu_http.DNS_WAITS), waits)

    def test_a_picture_download_raises_when_the_dns_outage_outlasts_the_waits(self):
        result, waits = self._picture([_dns() for _ in range(len(wakfu_http.DNS_WAITS) + 1)])
        self.assertIsInstance(result, urllib.error.URLError)
        self.assertEqual(list(wakfu_http.DNS_WAITS), waits)

    def test_a_picture_server_error_is_retried_with_the_retry_waits(self):
        result, waits = self._picture([_http(503), b'png'])
        self.assertEqual(b'png', result)
        self.assertEqual([wakfu_http.RETRY_WAITS[0]], waits)

    def test_a_picture_the_bucket_refuses_raises_at_once_for_main_to_skip(self):
        for code in (403, 404):
            result, waits = self._picture([_http(code)])
            self.assertIsInstance(result, urllib.error.HTTPError)
            self.assertEqual(code, result.code)
            self.assertEqual([], waits)
