"""The /offline/ page exists for the service worker, which fetches it on every
install; no reader asks for it and Google has nothing to index there. It must
stay readable (200, the worker needs it) but be neither indexed nor counted."""
import re

from django.test import TestCase

from chardata.middleware import HIT_SKIP


def _metas(html, name):
    """Attributes of each <meta> whose name= is `name`, whatever the attribute
    order (django-htmlmin sorts them alphabetically)."""
    found = []
    for tag in re.findall(r'<meta\b[^>]*>', html):
        attrs = dict(re.findall(r"""([a-zA-Z:-]+)=["']([^"']*)["']""", tag))
        if attrs.get('name') == name:
            found.append(attrs)
    return found


class OfflineIsForTheWorkerNotForGoogle(TestCase):

    def test_the_offline_page_stays_readable_and_says_noindex(self):
        resp = self.client.get('/offline/')
        self.assertEqual(200, resp.status_code)
        robots = _metas(resp.content.decode('utf-8'), 'robots')
        self.assertEqual(1, len(robots), msg=robots)
        self.assertIn('noindex', robots[0].get('content', ''))

    def test_a_page_readers_ask_for_is_not_noindex(self):
        # Control: the parser must tell the two apart, or the test above
        # would pass on any page.
        resp = self.client.get('/encyclopedia/')
        self.assertEqual(200, resp.status_code)
        noindexed = [m for m in _metas(resp.content.decode('utf-8'), 'robots')
                     if 'noindex' in m.get('content', '')]
        self.assertEqual([], noindexed)

    def test_the_worker_s_fetch_is_not_a_visit(self):
        self.assertIsNotNone(HIT_SKIP.match('/offline/'))
        self.assertIsNotNone(HIT_SKIP.match('/sw.js'))
        # Controls: the counter still sees pages someone reads.
        self.assertIsNone(HIT_SKIP.match('/encyclopedia/'))
        self.assertIsNone(HIT_SKIP.match('/offline-guide/'))
