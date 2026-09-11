# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page d'import est trouvable et decrit ce qu'elle fait.

Mesure du 11 septembre 2026: la page lit des captures d'infobulle depuis
le 10 (commit bf8015c50), sa description disait encore <<collez les noms>>
et rien d'autre, un lien vers elle colle dans un salon portait la phrase
generique du site, et aucune section du plan de site ne la soumettait, ni
sous /import/text/ ni sous les prefixes de version. Une page qu'aucun moteur
ne connait et qu'aucun salon ne decrit n'est pas une entree.
"""

import re

from django.test import SimpleTestCase, TestCase

DESCRIPTION = ('Paste item names, a build link or tooltip screenshots and get '
               'the same build here, piece for piece. Nothing is re-optimized '
               'unless you ask for it.')
ANCIENNE = ('Paste the names of your gear and get the same build here, piece '
            'for piece. Nothing is re-optimized unless you ask for it.')
TITRE = 'Import a build'


def _meta(page, nom):
    """Le contenu d'une balise meta, par son nom ou sa propriete; le
    minifieur trie les attributs, donc la balise est isolee par le nom avant
    de lire son contenu."""
    balises = re.findall(r'<meta[^>]*(?:name|property)=["\']?%s["\']?[^>]*>'
                         % re.escape(nom), page)
    assert len(balises) == 1, (nom, balises)
    return re.search(r'content="([^"]*)"', balises[0]).group(1)


class TheSitemapSubmitsTheImportPageTests(TestCase):

    def _pages(self):
        reponse = self.client.get('/sitemap-pages.xml')
        self.assertEqual(200, reponse.status_code)
        return re.findall(r'<loc>([^<]+)</loc>',
                          reponse.content.decode('utf-8'))

    def test_the_page_and_its_version_twins_are_listed(self):
        from fashionistapulp.game_versions import prefixed_reader_versions
        urls = self._pages()
        self.assertIn('https://dofusfashionista.gg/import/text/', urls)
        for version in prefixed_reader_versions():
            self.assertIn('https://dofusfashionista.gg/%s/import/text/' % version,
                          urls, version)

    def test_every_listed_import_page_answers_200_to_a_stranger(self):
        for url in self._pages():
            if '/import/text/' not in url:
                continue
            chemin = re.sub(r'^https?://[^/]+', '', url)
            self.assertEqual(200, self.client.get(chemin).status_code, chemin)


class ThePageDescribesWhatItReadsTests(TestCase):

    def test_the_description_names_the_screenshots_the_page_reads(self):
        page = self.client.get('/import/text/',
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertEqual(DESCRIPTION, _meta(page, 'description'))
        # La promesse est tenue par la page elle-meme: le champ de captures
        # est la. Retirer le lecteur de captures rend la phrase fausse et ce
        # test rouge.
        self.assertIn('shot-file', page)

    def test_the_link_preview_says_the_same_thing_as_the_search_engine(self):
        page = self.client.get('/import/text/',
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertEqual(_meta(page, 'description'), _meta(page, 'og:description'))
        titre = re.search(r'<title>(.*?)</title>', page, re.S).group(1).strip()
        self.assertTrue(titre.startswith('Import a build'), titre)
        self.assertEqual(titre, _meta(page, 'og:title'))
        self.assertEqual('https://dofusfashionista.gg/import/text/',
                         _meta(page, 'og:url'))

    def test_the_touch_twin_previews_its_own_address_and_names_its_version(self):
        """Soumise cinq fois, une par version: si les cinq pages portaient
        le meme titre et la meme description, Google n'en garderait qu'une.
        C'est la convention de la galerie et de la forgemagie, gardee par
        tests_page_titles; ici on verifie que l'apercu la suit aussi."""
        page = self.client.get('/touch/import/text/',
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertEqual('https://dofusfashionista.gg/touch/import/text/',
                         _meta(page, 'og:url'))
        self.assertEqual('Dofus Touch. ' + DESCRIPTION,
                         _meta(page, 'og:description'))
        self.assertEqual(_meta(page, 'description'), _meta(page, 'og:description'))
        titre = re.search(r'<title>(.*?)</title>', page, re.S).group(1).strip()
        self.assertTrue(titre.startswith('Import a build (Dofus Touch)'),
                        titre)
        self.assertEqual(titre, _meta(page, 'og:title'))

    def test_the_description_speaks_the_language_of_the_reader(self):
        page = self.client.get('/import/text/',
                               HTTP_ACCEPT_LANGUAGE='fr').content.decode('utf-8')
        description = _meta(page, 'description')
        self.assertNotEqual(DESCRIPTION, description)
        self.assertIn('capture', description)
        self.assertEqual(description, _meta(page, 'og:description'))


class TheDescriptionIsInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations_and_no_orphan(self):
        import gettext
        import io
        import os
        from django.conf import settings
        vues = set()
        for langue in ('fr', 'es', 'pt', 'de'):
            dossier = os.path.join(settings.BASE_DIR, 'locale')
            phrase = gettext.translation('django', dossier,
                                         languages=[langue]).gettext(DESCRIPTION)
            self.assertNotEqual(DESCRIPTION, phrase, langue)
            vues.add(phrase)
            catalogue = io.open(os.path.join(dossier, langue, 'LC_MESSAGES',
                                             'django.po'), encoding='utf-8').read()
            self.assertNotIn('msgid "%s"' % ANCIENNE, catalogue,
                             'the old sentence is still in %s' % langue)
        self.assertEqual(4, len(vues))
