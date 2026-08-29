# -*- coding: utf-8 -*-
"""Every link the site sends a reader to uses https, with one named exception.

`check_pages` follows internal links and looks for 500s. Nothing looked at what
the site sends people *out* to, and a sweep of the 65 external addresses in the
templates found four that no longer work and eleven more that answered only
over http -- including the two credit links to Coin-Or, whose https redirects
cleanly to GitHub while the http they carried returns 404.

An http link on an https page is either a redirect the reader pays for or a
downgrade a network can tamper with. This pins the state the sweep left behind,
so a new one has to be a deliberate exception rather than a habit.
"""
import glob
import io
import os
import re

from django.test import SimpleTestCase

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'templates', 'chardata')

#: Hosts whose https refuses the connection outright -- no TLS listener at all,
#: measured on 29 August 2026. Not a preference: an https link here would be a
#: dead link. Anything else belongs in https.
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
        """A list of exceptions nobody uses is a list nobody maintains.

        If the everhate link goes away, this fails and the exception goes with
        it instead of quietly outliving its reason.
        """
        links = [u for _f, u in self.plain_http_links()]
        for host in NO_TLS_AT_ALL:
            self.assertTrue(
                any(host in u for u in links),
                '%s is no longer linked anywhere: drop it from NO_TLS_AT_ALL'
                % host)

    def test_the_dead_forms_are_gone(self):
        """The addresses the sweep found dead, in the exact form that failed.

        Not the hosts: ajaxload.info stays on the page as a credit with no
        anchor, and projects.coin-or.org is a fine link over https -- it is the
        http one that answers 404. The apex of dofusdu.de fails its certificate
        while docs.dofusdu.de serves.
        """
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
