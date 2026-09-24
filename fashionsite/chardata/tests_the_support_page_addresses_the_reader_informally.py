# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The support page speaks to the reader the same way the solution page's
support box does: French in tu, Portuguese in Brazilian voce."""

from unittest import mock

from django.test import TestCase

SANS_PUB = {'enabled': False, 'client': '', 'slots': {}, 'auto': False}


class SupportPageAddressTests(TestCase):

    def _page(self, langue):
        with mock.patch('chardata.context_processors.ad_config',
                        return_value=dict(SANS_PUB)):
            page = self.client.get('/support/', HTTP_ACCEPT_LANGUAGE=langue)
        return page.content.decode('utf-8')

    def test_french_uses_tu_not_vous(self):
        html = self._page('fr')
        for informel in ('Partage tes builds', 'Signale des bugs',
                         'contacte-nous', 'rejoins notre',
                         'Laisse des commentaires'):
            self.assertIn(informel, html, informel)
        for formel in ('Partagez vos', 'Signalez des', 'contactez-nous',
                       'rejoignez notre', 'Laissez des'):
            self.assertNotIn(formel, html, formel)

    def test_portuguese_is_brazilian_not_european(self):
        html = self._page('pt')
        for brasileiro in ('Compartilhe seus builds', 'Reporte bugs',
                           'fale conosco', 'entre no nosso',
                           'Deixe comentários', 'compartilhados'):
            self.assertIn(brasileiro, html, brasileiro)
        for europeu in ('Partilha os teus', 'pago-o', 'nos tempos livres',
                        'contacta-nos', 'nos builds partilhados'):
            self.assertNotIn(europeu, html, europeu)
