# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What a page calls itself when it is published once per game version.

The same list exists five times -- once for Dofus 3, Beta, Dofus 2, Retro and
Touch -- and all five are submitted. If they share a title and a description,
the five results Google can show are indistinguishable, and it has to pick one
and drop the rest. That is the same failure the canonical had before it was
fixed, moved from the address to the words.

The families are read from the site's own sitemap rather than typed out here.
A hand-written list only ever covers the pages someone thought of; the sitemap
covers what is actually submitted, so a family added later arrives already
checked.
"""
import re
from html import unescape

from django.test import TestCase

VERSIONS = ('beta', 'dofus2', 'retro', 'touch')
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def sans_version(chemin):
    """The path with its game version removed, and the version."""
    morceaux = [m for m in chemin.split('/') if m]
    if morceaux and morceaux[0] in VERSIONS:
        reste = morceaux[1:]
        # Sans ce cas, /beta/ rend '//' et ne se regroupe pas avec '/' : la
        # famille de la page d'accueil disparaissait de la comparaison sans
        # que rien ne le signale.
        return ('/' + '/'.join(reste) + '/') if reste else '/', morceaux[0]
    return chemin, 'dofus3'


class EveryVersionOfAListNamesItselfDifferentlyTests(TestCase):
    """/setup/ and /sharedbuilds/ each answered with one title for five pages.

    Both carry the version in the address and in the page, and neither carried
    it in the title or the description. The other families already did -- the
    encyclopedia, its sets, the forgemagie, the home page -- so this was two
    templates left behind by a convention the rest of the site follows.
    """

    def _page(self, url):
        reponse = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en',
                                  HTTP_USER_AGENT=NAVIGATEUR)
        self.assertEqual(reponse.status_code, 200,
                         '%s answered %s' % (url, reponse.status_code))
        html = reponse.content.decode('utf-8', 'replace')
        titre = re.search('<title>(.*?)</title>', html, re.S)
        description = ''
        for tag in re.findall('<meta[^>]*>', html):
            if 'name="description"' in tag:
                trouve = re.search('content="([^"]*)"', tag)
                if trouve:
                    description = trouve.group(1)
                break
        return (titre.group(1).strip() if titre else ''), description

    def _familles(self):
        """Paths published in every game version, from the site's own sitemap."""
        reponse = self.client.get('/sitemap-pages.xml')
        self.assertEqual(reponse.status_code, 200, 'no sitemap to read')
        xml = reponse.content.decode('utf-8', 'replace')
        groupes = {}
        for loc in re.findall('<loc>([^<]*)</loc>', xml):
            chemin = re.sub('^https?://[^/]*', '', loc)
            # Les builds partages n'existent qu'a une adresse chacun : ils ne
            # forment pas une famille de cinq et n'ont rien a departager.
            if '/s/' in chemin:
                continue
            racine, version = sans_version(chemin)
            groupes.setdefault(racine, {})[version] = chemin
        return {racine: versions for racine, versions in groupes.items()
                if len(versions) == len(VERSIONS) + 1}

    def test_five_versions_of_a_page_do_not_share_one_title(self):
        familles = self._familles()
        self.assertTrue(familles, 'the sitemap lists no versioned family')
        collisions = []
        verifiees = 0
        for racine, versions in sorted(familles.items()):
            titres = {}
            for version, chemin in sorted(versions.items()):
                titre, _ = self._page(chemin)
                titres.setdefault(titre, []).append(version)
            verifiees += 1
            for titre, portees in titres.items():
                if len(portees) > 1:
                    collisions.append((racine, portees, titre))
        self.assertFalse(
            collisions, 'these versions answer with one title '
            '(family, versions, title): %s' % collisions[:4])
        # Sans ce compte, un plan de site vide rendrait ce test vert en ne
        # comparant rien du tout.
        self.assertGreaterEqual(verifiees, 4,
                                'only %d versioned families found' % verifiees)

    def test_five_versions_of_a_page_do_not_share_one_description(self):
        # Le titre et la description sont deux moities de la meme reponse :
        # corriger l'une et laisser l'autre laisse cinq resultats dont quatre
        # sont encore interchangeables sous le titre.
        collisions = []
        for racine, versions in sorted(self._familles().items()):
            vues = {}
            for version, chemin in sorted(versions.items()):
                _, description = self._page(chemin)
                self.assertTrue(description,
                                '%s has no description at all' % chemin)
                vues.setdefault(description, []).append(version)
            for description, portees in vues.items():
                if len(portees) > 1:
                    collisions.append((racine, portees, description[:60]))
        self.assertFalse(
            collisions, 'these versions answer with one description '
            '(family, versions, description): %s' % collisions[:4])

    def test_the_version_shown_is_the_version_asked_for(self):
        """Distinct is not enough: five different wrong titles would pass.

        A Retro page has to say Retro, not merely differ from the Beta one.
        """
        faux = []
        for racine, versions in sorted(self._familles().items()):
            for version, chemin in sorted(versions.items()):
                if version == 'dofus3':
                    continue
                titre, _ = self._page(chemin)
                if version.lower() not in titre.lower().replace(' ', ''):
                    faux.append((chemin, titre))
        self.assertFalse(faux, 'these titles do not name their own version: %s'
                         % faux[:4])


class HomeMetadataTests(TestCase):

    # (words the title and description must carry, the create button's label)
    LANGUAGES = {
        'en': (('set builder', 'optimizer'), 'Create a build'),
        'fr': (('créateur', 'optimiseur'), 'Créer un build'),
        'es': (('creador', 'optimizador'), 'Crear un build'),
        'pt': (('criador', 'otimizador'), 'Criar um build'),
        'de': (('set-baukasten', 'optimierer'), 'Build erstellen'),
    }
    VERSIONS = {'': '', 'beta': '3 Beta', 'dofus2': '2',
                'retro': 'Retro', 'touch': 'Touch'}

    def _homes(self):
        for language in self.LANGUAGES:
            for version, label in self.VERSIONS.items():
                parts = [part for part in
                         (language if language != 'en' else '', version) if part]
                path = '/' + '/'.join(parts) + ('/' if parts else '')
                response = self.client.get(path, HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(response.status_code, 200, path)
                yield language, label, path, response.content.decode('utf-8')

    def test_the_title_names_the_tool_first_and_the_brand_last(self):
        titles = set()
        for language, version, path, page in self._homes():
            with self.subTest(path=path):
                title = unescape(re.search(r'<title>(.*?)</title>', page,
                                          re.S).group(1)).strip()
                self.assertTrue(title.endswith(' - Dofus Fashionista'), title)
                builder, optimizer = self.LANGUAGES[language][0]
                self.assertIn(builder, title.lower())
                self.assertIn(optimizer, title.lower())
                if version:
                    self.assertIn('Dofus ' + version, title)
                self.assertLessEqual(len(title), 70, title)
                self.assertNotIn(title, titles)
                titles.add(title)

    def test_the_description_leads_with_the_optimizer_and_fits_a_result(self):
        descriptions = set()
        for language, version, path, page in self._homes():
            with self.subTest(path=path):
                tag = re.search(r'<meta\b[^>]*name="description"[^>]*>', page)
                self.assertIsNotNone(tag)
                description = unescape(re.search(r'content="([^"]*)"',
                                                 tag.group(0)).group(1))
                self.assertIn('Dofus' + (' ' + version if version else ''),
                              description)
                self.assertLessEqual(len(description), 160, description)
                optimizer = self.LANGUAGES[language][0][1]
                self.assertLess(description.lower().index(optimizer), 40,
                                description)
                self.assertNotIn(description, descriptions)
                descriptions.add(description)

    def test_the_optimizer_comes_first_and_the_quick_build_is_one_click_away(self):
        for language, version, path, page in self._homes():
            with self.subTest(path=path):
                self.assertLess(page.index('id="home-optimizer-intro"'),
                                page.index('id="home-workshop-intro"'))
                body = page[page.index('id="home-workshop-intro"'):]
                self.assertLess(body.index('href="%squickstart/"' % path),
                                body.index('href="%ssharedbuilds/"' % path))
                button = re.search(
                    r'<a\b[^>]*class="giant-button-text"[^>]*>.*?</a>',
                    page, re.S).group(0)
                self.assertIn('href="%ssetup/"' % path, button)
                self.assertIn(self.LANGUAGES[language][1], unescape(button))
