# -*- coding: utf-8 -*-
"""Every outgoing link must use https, except a named host with no TLS listener at all."""
import glob
import io
import os
import re

from django.test import SimpleTestCase

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'templates', 'chardata')

# hosts whose https refuses the connection outright; an https link here would be a dead link
NO_TLS_AT_ALL = ('dofustools.everhate.com',)

LINK = re.compile(r'href="(http://[^"]+)"')


class OutgoingLinksAreHttps(SimpleTestCase):

    def plain_http_links(self):
        found = []
        for path in glob.glob(os.path.join(TEMPLATES, '*.html')):
            text = io.open(path, encoding='utf-8', errors='replace').read()
            for url in LINK.findall(text):
                if 'localhost' in url or '127.0.0.1' in url:
                    continue
                found.append((os.path.basename(path), url))
        return found

    def test_only_the_host_without_tls_is_still_on_http(self):
        offenders = [(f, u) for f, u in self.plain_http_links()
                     if not any(host in u for host in NO_TLS_AT_ALL)]
        self.assertEqual(
            [], offenders,
            'these links downgrade the reader to http; if the host really has '
            'no https, add it to NO_TLS_AT_ALL with the date it was measured')

    def test_the_exception_is_still_used(self):
        """An unused exception is one nobody maintains; this fails if the host stops being linked."""
        links = [u for _f, u in self.plain_http_links()]
        for host in NO_TLS_AT_ALL:
            self.assertTrue(
                any(host in u for u in links),
                '%s is no longer linked anywhere: drop it from NO_TLS_AT_ALL'
                % host)

    def test_the_dead_forms_are_gone(self):
        """The exact dead link forms the sweep found; the hosts themselves may still be linked over https elsewhere."""
        dead = ('href="http://www.ajaxload.info',
                'href="http://projects.coin-or.org',
                'href="https://dofusdu.de"')
        found = []
        for path in glob.glob(os.path.join(TEMPLATES, '*.html')):
            text = io.open(path, encoding='utf-8', errors='replace').read()
            for needle in dead:
                if needle in text:
                    found.append((os.path.basename(path), needle))
        self.assertEqual([], found)

    def test_the_ajaxload_credit_survived_its_link(self):
        """Removing a dead link must not remove the acknowledgement with it."""
        text = io.open(os.path.join(TEMPLATES, 'license.html'),
                       encoding='utf-8').read()
        self.assertIn('ajaxload.info', text)
        self.assertNotIn('href="http://www.ajaxload.info', text)
