# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every page previews as itself when its link is pasted in a chat.

Mesure du 11 septembre 2026, sur les seize pages carrefour du plan de site:
quinze portaient l'apercu generique du site (<<Dofus Fashionista - Equipment
Set Optimizer>> et sa phrase), alors que chacune a son titre et sa
description. Le constructeur de sets, la galerie, la forgemagie, le
demarrage rapide, colles dans un salon, se presentaient tous comme la meme
page. Un bloc ne peut apparaitre qu'une fois dans un gabarit; le titre et la
description sont maintenant rendus une fois par {% capture %} et repris trois
fois: <title>, meta description, et la paire Open Graph.
"""

import re

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase


def _meta(page, nom):
    balises = re.findall(r'<meta[^>]*(?:name|property)=["\']?%s["\']?[^>]*>'
                         % re.escape(nom), page)
    assert len(balises) == 1, (nom, balises)
    return re.search(r'content="([^"]*)"', balises[0]).group(1)


def _titre(page):
    return re.search(r'<title>(.*?)</title>', page, re.S).group(1).strip()


class TheCaptureTagTests(SimpleTestCase):

    def test_it_renders_once_and_hands_the_text_on(self):
        rendu = Template('{% load capture %}{% capture as x %}hello {{ y }}'
                         '{% endcapture %}[{{ x }}]').render(Context({'y': 1}))
        self.assertEqual('[hello 1]', rendu)

    def test_the_text_is_escaped_once_not_twice(self):
        rendu = Template('{% load capture %}{% capture as x %}{{ z }}'
                         '{% endcapture %}{{ x }}').render(Context({'z': 'a"b&c'}))
        self.assertEqual('a&quot;b&amp;c', rendu)

    def test_a_child_override_of_a_block_inside_the_tag_is_what_is_captured(self):
        from django.template import engines
        engine = engines['django']
        parent = engine.from_string(
            '{% load capture %}{% capture as t %}{% block title %}base'
            '{% endblock %}{% endcapture %}<title>{{ t }}</title><og>{{ t }}</og>')
        # Un enfant qui surcharge le bloc: ce que la page verra dans les
        # deux emplacements est la version de l'enfant.
        from django.template.loader_tags import ExtendsNode  # noqa: F401
        from django.template import Template as T
        enfant = T('{% extends parent %}{% block title %}child{% endblock %}')
        rendu = enfant.render(Context({'parent': parent.template}))
        self.assertEqual('<title>child</title><og>child</og>', rendu)


class EveryHubPagePreviewsItselfTests(TestCase):
    """Lu depuis le plan de site, comme tests_page_titles: une page ajoutee
    plus tard arrive deja gardee."""

    def _pages(self):
        reponse = self.client.get('/sitemap-pages.xml')
        self.assertEqual(200, reponse.status_code)
        chemins = []
        for url in re.findall(r'<loc>([^<]+)</loc>',
                              reponse.content.decode('utf-8')):
            chemin = re.sub(r'^https?://[^/]+', '', url)
            # Les builds partages ont leur propre apercu (classe, pieces,
            # verdict), garde par tests_the_link_preview_carries_the_build.
            if '/s/' in chemin:
                continue
            chemins.append(chemin)
        self.assertGreater(len(chemins), 40, 'the pages section came back thin')
        return chemins

    def test_the_preview_says_what_the_page_says(self):
        faux = []
        for chemin in self._pages():
            page = self.client.get(chemin, HTTP_ACCEPT_LANGUAGE='en')
            if page.status_code != 200:
                faux.append((chemin, page.status_code))
                continue
            html = page.content.decode('utf-8', 'replace')
            titre = _titre(html)
            og_titre = _meta(html, 'og:title')
            # Un guide previsualise son titre sans le nom du site: le titre
            # de la page commence par l'apercu, ou lui est egal.
            if not titre.startswith(og_titre):
                faux.append((chemin, 'title', titre, og_titre))
            if _meta(html, 'description') != _meta(html, 'og:description'):
                faux.append((chemin, 'description'))
        self.assertEqual([], faux[:8], '%d pages preview something else than '
                                       'what they say' % len(faux))

    def test_the_generic_sentence_is_gone_from_the_hubs(self):
        """La phrase generique ne doit rester que la ou elle est la
        description de la page: nulle part dans le plan de site des
        carrefours, chacun ayant la sienne."""
        generique = 'Create optimized Dofus equipment sets automatically'
        restes = []
        for chemin in ('/', '/setup/', '/sharedbuilds/', '/forgemagie/',
                       '/quickstart/', '/smartbuild/', '/encyclopedia/',
                       '/about/', '/faq/'):
            html = self.client.get(chemin, HTTP_ACCEPT_LANGUAGE='en'
                                   ).content.decode('utf-8', 'replace')
            if generique in _meta(html, 'og:description'):
                restes.append(chemin)
        self.assertEqual([], restes)

    def test_the_set_builder_previews_as_the_set_builder(self):
        html = self.client.get('/setup/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8', 'replace')
        self.assertIn('Set Builder', _meta(html, 'og:title'))
        self.assertEqual(_titre(html), _meta(html, 'og:title'))
