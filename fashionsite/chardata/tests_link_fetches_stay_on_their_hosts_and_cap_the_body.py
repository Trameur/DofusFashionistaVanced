# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Link import and export fetches: redirects stay on https allowlisted hosts, bodies are capped."""

import email.message
import io
import json
import urllib.request
import urllib.response
from unittest import mock

from django.test import SimpleTestCase

from chardata import dofusbook_export, dofusbook_import, dofuscreator_import
from chardata.dofusbook_import import ImportError_, MAX_BODY

START = 'https://www.dofusbook.net/api/stuffs/x/public/123'


class _FakeHttps(urllib.request.HTTPSHandler):
    """Answers from a table instead of the network."""

    def __init__(self, answers):
        super().__init__()
        self.answers = answers
        self.seen = []

    def https_open(self, req):
        self.seen.append(req.full_url)
        code, location, body = self.answers[req.full_url]
        headers = email.message.Message()
        if location:
            headers['Location'] = location
        reponse = urllib.response.addinfourl(
            io.BytesIO(body), headers, req.full_url, code)
        reponse.msg = 'OK' if code == 200 else 'Found'
        return reponse


def _redirecting_opener(location, final_body=b'{"items": []}'):
    fake = _FakeHttps({
        START: (302, location, b''),
        location: (200, None, final_body),
    })
    ouvreur = urllib.request.build_opener(
        dofusbook_import._RedirectOnAllowlist(dofusbook_import.HOSTS), fake)
    return ouvreur.open, fake


class _Answer(object):

    def __init__(self, body):
        self.body = body
        self.asked = []

    def read(self, size=-1):
        self.asked.append(size)
        return self.body if size < 0 else self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _opener_answering(body):
    reponse = _Answer(body)

    def ouvrir(requete, timeout=None):
        return reponse
    return ouvrir, reponse


class ARedirectOffTheAllowlistIsRefusedTests(SimpleTestCase):

    def _assert_refused_without_following(self, location):
        ouvrir, fake = _redirecting_opener(location)
        with self.assertRaises(ImportError_) as ctx:
            dofusbook_import.fetch_build('www.dofusbook.net', '123', opener=ouvrir)
        self.assertEqual('refused', ctx.exception.reason)
        self.assertEqual([START], fake.seen)

    def test_a_redirect_to_another_host_is_refused(self):
        self._assert_refused_without_following('https://example.com/steal')

    def test_a_redirect_to_plain_http_on_the_same_host_is_refused(self):
        self._assert_refused_without_following(
            'http://www.dofusbook.net/api/stuffs/x/public/123')

    def test_a_redirect_to_a_private_address_is_refused(self):
        self._assert_refused_without_following('https://127.0.0.1/admin')

    def test_a_redirect_to_another_port_on_the_same_host_is_refused(self):
        self._assert_refused_without_following(
            'https://www.dofusbook.net:8443/api/stuffs/x/public/123')

    def test_a_redirect_to_https_on_an_allowlisted_host_is_followed(self):
        location = 'https://retro.dofusbook.net/api/stuffs/x/public/123'
        ouvrir, fake = _redirecting_opener(location)
        charge = dofusbook_import.fetch_build(
            'www.dofusbook.net', '123', opener=ouvrir)
        self.assertEqual({'items': []}, charge)
        self.assertEqual([START, location], fake.seen)

    def test_the_default_opener_is_given_the_host_table(self):
        with mock.patch('chardata.dofusbook_import._urlopen_allowlisted',
                        return_value=_Answer(b'{"items": []}')) as ouvrir:
            dofusbook_import.fetch_build('www.dofusbook.net', '123')
            dofuscreator_import.fetch_project('dofuscreator.com', 'abc12')
        self.assertEqual(set(dofusbook_import.HOSTS),
                         set(ouvrir.call_args_list[0].kwargs['hosts']))
        self.assertEqual(set(dofuscreator_import.HOSTS),
                         set(ouvrir.call_args_list[1].kwargs['hosts']))
        self.assertEqual(dofusbook_import.TIMEOUT,
                         ouvrir.call_args_list[0].kwargs['timeout'])


class AnOversizedBodyIsRefusedTests(SimpleTestCase):

    def test_the_import_refuses_a_body_over_the_cap(self):
        ouvrir, reponse = _opener_answering(b' ' * (MAX_BODY + 10))
        with self.assertRaises(ImportError_) as ctx:
            dofusbook_import.fetch_build('www.dofusbook.net', '123', opener=ouvrir)
        self.assertEqual('unreadable', ctx.exception.reason)
        self.assertEqual([MAX_BODY + 1], reponse.asked)

    def test_the_project_page_refuses_a_body_over_the_cap(self):
        ouvrir, reponse = _opener_answering(b' ' * (MAX_BODY + 10))
        with self.assertRaises(ImportError_) as ctx:
            dofuscreator_import.fetch_project('dofuscreator.com', 'abc12',
                                              opener=ouvrir)
        self.assertEqual('unreadable', ctx.exception.reason)
        self.assertEqual([MAX_BODY + 1], reponse.asked)

    def test_the_export_refuses_a_body_over_the_cap(self):
        ouvrir, reponse = _opener_answering(b' ' * (MAX_BODY + 10))
        with self.assertRaises(dofusbook_export.ExportError) as ctx:
            dofusbook_export.stuffer_items(
                'retro', [[11542]] + [[] for _ in range(9)], opener=ouvrir)
        self.assertEqual('unreadable', ctx.exception.reason)
        self.assertEqual([MAX_BODY + 1], reponse.asked)


class ABodyUnderTheCapStillDecodesTests(SimpleTestCase):

    def test_the_import_decodes_its_json(self):
        charge = {'items': [{'official': 1, 'name': 'x'}]}
        ouvrir, _ = _opener_answering(json.dumps(charge).encode('utf-8'))
        self.assertEqual(charge, dofusbook_import.fetch_build(
            'www.dofusbook.net', '123', opener=ouvrir))

    def test_the_project_page_decodes_its_text(self):
        ouvrir, _ = _opener_answering('<html>é</html>'.encode('utf-8'))
        self.assertEqual('<html>é</html>', dofuscreator_import.fetch_project(
            'dofuscreator.com', 'abc12', opener=ouvrir))

    def test_the_export_decodes_its_json(self):
        ouvrir, _ = _opener_answering(b'{"data": [{"official": 11542}]}')
        self.assertEqual([{'official': 11542}], dofusbook_export.stuffer_items(
            'retro', [[11542]] + [[] for _ in range(9)], opener=ouvrir))
