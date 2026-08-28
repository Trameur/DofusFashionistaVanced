# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un script servi par quelqu'un d'autre doit annoncer ce qu'il pese.

`base.html` charge jQuery depuis `ajax.googleapis.com`, donc sur CHAQUE page ;
`jqueryui.html` ajoute jQuery UI et son theme sur sept pages, dont la page de
resultat du solveur. Trois fichiers qu'un tiers sert, qui s'executent avec tous
les droits de la page, et que rien ne verifiait.

C'est a ca que sert `integrity` : le navigateur calcule l'empreinte de ce qu'il
recoit et REFUSE de l'executer si elle ne correspond pas. Sans elle, un CDN
compromis, un DNS detourne ou une autorite de certification malveillante font
tourner le code de leur choix sur toutes les pages, y compris celles ou le
lecteur est connecte.

Ce test ne verifie pas QUELLE empreinte est ecrite -- affirmer qu'une constante
egale elle-meme ne prouve rien. Il verifie qu'aucune ressource tierce n'entre
SANS empreinte, ce qui est la regression reelle : quelqu'un ajoute un `<script
src="https://...">` en 2027 et personne ne remarque qu'il n'a pas de garde.

Les empreintes posees le 28 aout 2026 ont ete calculees sur les octets decodes
et corroborees par une SECONDE origine, `code.jquery.com` -- une infrastructure
differente, pas le meme fichier lu deux fois. Les trois concordent au bit pres.

Note sur `crossorigin` : une empreinte sur une ressource d'une autre origine
n'est verifiable que si la reponse autorise la lecture. Les trois adresses
renvoient `Access-Control-Allow-Origin: *`, ce qui a ete verifie avant de poser
quoi que ce soit -- sans cet en-tete, ajouter `integrity` aurait CASSE le
chargement au lieu de le proteger.
"""
import os
import re

from django.conf import settings
from django.test import SimpleTestCase

#: Une balise <script src> ou <link href> pointant vers une autre origine.
_EXTERNE = re.compile(
    r'<(script|link)\b[^>]*\b(?:src|href)\s*=\s*"(https?://[^"]+)"[^>]*>',
    re.I | re.S)

#: Les origines qui n'executent rien et ne stylent rien : les declarer avec
#: une empreinte n'aurait pas de sens.
_SANS_OBJET = ('schema.org', 'www.w3.org', 'creativecommons.org')

#: Les scripts qu'on NE PEUT PAS epingler, et pourquoi.
#:
#: Une empreinte fige un contenu. Ces trois-la sont mis a jour en continu par
#: leur editeur, a la meme adresse : les epingler ne les protegerait pas, ca
#: les casserait -- en quelques jours, silencieusement, sur toutes les pages.
#: C'est une limite connue de la specification, pas un oubli.
#:
#: La liste est deliberement une liste d'ADRESSES et non d'origines : si
#: quelqu'un ajoute demain une bibliotheque versionnee sur `googletagmanager`,
#: elle doit rougir, parce qu'elle, on peut l'epingler.
_NON_EPINGLABLES = {
    # Regie publicitaire : le script se reecrit a chaque changement de format.
    'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js',
    # Gestion du consentement, imposee par la regie ; suit ses evolutions.
    'https://fundingchoicesmessages.google.com/i/{{ ad_publisher }}?ers=1',
    # Mesure d'audience : Google republie ce fichier en continu.
    'https://www.googletagmanager.com/gtag/js?id={{ google_analytics_id }}',
}


def _gabarits():
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates')
    for dossier, _sous, fichiers in os.walk(racine):
        for f in fichiers:
            if f.endswith('.html'):
                yield os.path.join(dossier, f)


def _ressources_tierces():
    """(chemin, balise) pour chaque ressource chargee depuis un tiers."""
    trouve = []
    for chemin in _gabarits():
        with open(chemin, encoding='utf-8', errors='replace') as f:
            texte = f.read()
        for m in _EXTERNE.finditer(texte):
            balise = m.group(0)
            url = m.group(2)
            if any(d in url for d in _SANS_OBJET):
                continue
            # Un <link rel="canonical"> ou "alternate" ne charge rien.
            if m.group(1).lower() == 'link':
                rel = re.search(r'\brel\s*=\s*"([^"]*)"', balise, re.I)
                if not rel or 'stylesheet' not in rel.group(1).lower():
                    continue
            trouve.append((os.path.basename(chemin), balise, url))
    return trouve


class EveryThirdPartyResourceIsPinnedTests(SimpleTestCase):

    def test_the_scan_actually_finds_third_party_resources(self):
        """Le plancher du temoin.

        Sans lui, un motif trop etroit rendrait zero ressource, zero faute, et
        un vert parfait qui ne garde rien. C'est l'erreur que j'ai commise
        vingt fois cette semaine, toujours dans un outil de verification.
        """
        trouve = _ressources_tierces()
        self.assertGreaterEqual(
            len(trouve), 3,
            'only %d third-party resources found; the scan is too narrow to '
            'be guarding anything' % len(trouve))

    def test_no_third_party_script_or_stylesheet_runs_unpinned(self):
        nus = [(f, u) for f, b, u in _ressources_tierces()
               if 'integrity=' not in b.lower()
               and u not in _NON_EPINGLABLES]
        self.assertFalse(
            nus,
            'these load third-party code with no subresource integrity, so a '
            'compromised CDN would run its own: %s' % nus[:4])

    def test_the_exemption_list_still_describes_real_tags(self):
        """Une exemption qui ne correspond plus a rien est un mensonge poli.

        Si l'adresse d'AdSense change, la ligne exemptee cesse de designer
        quoi que ce soit -- et la NOUVELLE adresse, elle, tombe dans le test
        precedent. Ce test-ci attrape l'autre moitie : une liste qui grossit
        de lignes mortes finit par exempter des choses qu'on croit connaitre.
        """
        vues = set(u for _f, _b, u in _ressources_tierces())
        fantomes = sorted(_NON_EPINGLABLES - vues)
        self.assertFalse(
            fantomes,
            'these exemptions no longer match any tag, so nothing checks '
            'what they claim to excuse: %s' % fantomes)

    def test_a_pinned_resource_also_allows_the_check(self):
        """`integrity` sans `crossorigin` ne verifie rien sur une autre origine.

        Le navigateur ne peut pas lire une reponse opaque, donc il ne peut pas
        la hacher. La balise a l'air protegee et ne l'est pas -- pire qu'une
        balise nue, parce qu'elle rassure.
        """
        boiteux = [(f, u) for f, b, u in _ressources_tierces()
                   if 'integrity=' in b.lower()
                   and 'crossorigin' not in b.lower()]
        self.assertFalse(
            boiteux,
            'these carry an integrity hash the browser cannot verify without '
            'crossorigin: %s' % boiteux[:4])

    def test_every_hash_is_sha384_or_stronger(self):
        """sha256 reste accepte par la specification, mais sha384 est la
        recommandation, et c'est ce qui est pose ici. Une empreinte plus
        faible glissee plus tard passerait sinon inapercue.
        """
        faibles = []
        for f, b, u in _ressources_tierces():
            m = re.search(r'integrity\s*=\s*"([^"]*)"', b, re.I)
            if m and not re.search(r'sha(384|512)-', m.group(1)):
                faibles.append((f, m.group(1)[:24]))
        self.assertFalse(faibles, 'weaker than sha384: %s' % faibles)
