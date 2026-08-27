# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une adresse traduite soumise implique sa jumelle anglaise soumise.

Les douze `/{fr,es,pt}/{beta,dofus2,retro,touch}/guides/` etaient dans le plan
de site ; les quatre `/{beta,dofus2,retro,touch}/guides/` n'y etaient pas. Or
l'anglais est le `x-default` ET le canonique de chacun de ces quatre groupes :
on soumettait douze pages qui pointent toutes vers une treizieme qu'on ne
signalait pas.

La cause n'est pas un oubli isole, c'est **deux listes de carrefours** : celle
de la boucle des langues contient `/guides/`, celle de la boucle des versions
anglaises ne le contenait pas. Un carrefour ajoute d'un seul cote produit
exactement ce trou, en silence.

Ce module n'enumere donc pas les quatre adresses -- ce serait la meme faute a
l'envers, une troisieme liste a tenir a jour. Il verifie la RELATION, sur tout
ce que les plans soumettent.
"""
import re

from django.test import TestCase


class EveryTranslatedUrlHasAnEnglishTwinTests(TestCase):

    def _adresses(self):
        """Toutes les adresses de tous les plans, chemins seuls."""
        index = self.client.get('/sitemap.xml')
        self.assertEqual(200, index.status_code)
        sections = re.findall(r'<loc>([^<]+)</loc>',
                              index.content.decode('utf-8', 'replace'))
        self.assertTrue(sections, 'the sitemap index lists no section')
        chemins = set()
        for url in sections:
            chemin = re.sub(r'^https?://[^/]+', '', url)
            corps = self.client.get(chemin).content.decode('utf-8', 'replace')
            for loc in re.findall(r'<loc>([^<]+)</loc>', corps):
                chemins.add(re.sub(r'^https?://[^/]+', '', loc))
        return chemins

    def test_no_translated_page_is_submitted_without_its_english_twin(self):
        from django.conf import settings

        chemins = self._adresses()
        codes = tuple('/%s/' % code for code, _nom in settings.LANGUAGES
                      if code != settings.LANGUAGE_CODE)
        prefixes = [c for c in chemins if c.startswith(codes)]
        # Controle positif : sans adresse prefixee, la boucle ci-dessous ne
        # tourne pas et le test passe en ne mesurant rien.
        self.assertTrue(
            prefixes,
            'no translated url is submitted at all, so this test proves '
            'nothing about their english twins')

        orphelines = []
        for chemin in sorted(prefixes):
            anglais = '/' + chemin.split('/', 2)[2]
            if anglais not in chemins:
                orphelines.append(chemin)
        self.assertFalse(
            orphelines,
            '%d translated urls are submitted while their english twin is '
            'not: %s' % (len(orphelines), orphelines[:6]))

    # Un second test lisait les deux listes dans le source et exigeait qu'elles
    # s'accordent. Il rougissait sur `/encyclopedia/monsters/`, present dans la
    # liste des langues et absent de celle des versions anglaises -- pour une
    # bonne raison : ce carrefour-la est soumis par `sitemap-monsters.xml`, un
    # autre constructeur. Le test affirmait donc une COINCIDENCE d'implementation
    # et non une verite. Le test ci-dessus porte sur les adresses reellement
    # soumises, quelle que soit la section qui les emet, et c'est le bon niveau.
