"""A browser report with fields of the wrong type is read as far as it can be and never raises, and nothing it carries can break a log line."""
import json

from django.test import SimpleTestCase, TestCase

from chardata.csp_report_view import _resume


def _post(client, document):
    return client.post('/csp-report/', data=json.dumps(document),
                       content_type='application/csp-report')


class AReportIsSummarised(SimpleTestCase):

    def test_a_field_that_is_not_text_reads_as_empty(self):
        self.assertEqual(('', '', ''), _resume({'effective-directive': 1,
                                                'blocked-uri': ['x'],
                                                'document-uri': {'a': 1}}))

    def test_control_characters_are_dropped_from_every_field(self):
        directive, blocked, page = _resume({
            'effective-directive': 'script-src\nforged line',
            'blocked-uri': 'https://a.test/\r\nWARNING fake\x00',
            'document-uri': 'https://site.test/path\n/more?q=1'})
        for value in (directive, blocked, page):
            self.assertFalse(any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value),
                             repr(value))
        self.assertEqual('script-srcforged line', directive)
        self.assertEqual('/path/more', page)

    def test_the_second_directive_is_used_when_the_first_is_not_text(self):
        directive, _blocked, _page = _resume({'effective-directive': 5,
                                              'violated-directive': 'img-src'})
        self.assertEqual('img-src', directive)


class TheReportRouteNeverFails(TestCase):

    def test_a_numeric_directive_is_an_empty_report_not_a_server_error(self):
        response = _post(self.client, {'csp-report': {'effective-directive': 1}})
        self.assertEqual(400, response.status_code)

    def test_a_dict_document_uri_with_a_real_directive_is_accepted(self):
        response = _post(self.client, {'csp-report': {
            'effective-directive': 'script-src', 'document-uri': {'a': 1}}})
        self.assertEqual(204, response.status_code)

    def test_a_deeply_nested_body_is_unreadable_not_a_server_error(self):
        response = self.client.post('/csp-report/', data='[' * 8000,
                                    content_type='application/csp-report')
        self.assertEqual(400, response.status_code)
