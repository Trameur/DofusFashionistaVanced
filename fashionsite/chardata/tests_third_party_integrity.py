# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Third-party scripts and stylesheets must carry an integrity hash."""
import os
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.test import SimpleTestCase, TestCase

# <script src> or <link href> to another origin, single or double quotes
_EXTERNE = re.compile(
    r'<(script|link)\b[^>]*\b(?:src|href)\s*=\s*'
    r'([\'"])(https?://[^\'"]+)\2[^>]*>',
    re.I | re.S)

# Same load written in JS: el.src = 'https://...'
_EXTERNE_JS = re.compile(
    r'\.src\s*=\s*[\'"](https?://[^\'"]+)[\'"]', re.I)

# How far after .src = to look for integrity and crossOrigin
_FENETRE_JS = 400

# Origins that load no script or style
_SANS_OBJET = ('schema.org', 'www.w3.org', 'creativecommons.org')

# Updated in place by their publisher, can't be pinned (exact URLs)
_NON_EPINGLABLES = {
    'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js',
    'https://fundingchoicesmessages.google.com/i/{{ ad_publisher }}?ers=1',
    'https://www.googletagmanager.com/gtag/js?id={{ google_analytics_id }}',
    # reCAPTCHA sends no Access-Control-Allow-Origin, the browser can't hash it
    'https://www.google.com/recaptcha/api.js?hl={{language}}',
    'https://www.google.com/recaptcha/api.js',
}


def _gabarits():
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates')
    for dossier, _sous, fichiers in os.walk(racine):
        for f in fichiers:
            if f.endswith('.html'):
                yield os.path.join(dossier, f)


def _ressources_tierces():
    """[(file name, tag, url)] for every third-party load."""
    trouve = []
    for chemin in _gabarits():
        with open(chemin, encoding='utf-8', errors='replace') as f:
            texte = f.read()
        for m in _EXTERNE.finditer(texte):
            balise = m.group(0)
            url = m.group(3)
            if any(d in url for d in _SANS_OBJET):
                continue
            # Only stylesheet links load anything
            if m.group(1).lower() == 'link':
                rel = re.search(r'\brel\s*=\s*[\'"]([^\'"]*)[\'"]', balise,
                                re.I)
                if not rel or 'stylesheet' not in rel.group(1).lower():
                    continue
            trouve.append((os.path.basename(chemin), balise, url))
        for m in _EXTERNE_JS.finditer(texte):
            url = m.group(1)
            if any(d in url for d in _SANS_OBJET):
                continue
            # Fake tag so JS loads go through the same checks
            suite = texte[m.end():m.end() + _FENETRE_JS]
            # Keep the real hash, the sha384 test reads it
            empreinte = re.search(r"""integrity\s*=\s*['"]([^'"]+)['"]""",
                                  suite, re.I)
            balise = '<script src="%s"%s%s>' % (
                url,
                ' integrity="%s"' % empreinte.group(1) if empreinte else '',
                ' crossorigin="js"' if 'crossorigin' in suite.lower() else '')
            trouve.append((os.path.basename(chemin), balise, url))
    return trouve


class EveryThirdPartyResourceIsPinnedTests(SimpleTestCase):

    def test_the_scan_actually_finds_third_party_resources(self):
        """The scan must see each way of writing a third-party load."""
        trouve = _ressources_tierces()
        vus = set(f for f, _b, _u in trouve)
        for fichier, forme in (
                ('base.html', 'une balise en guillemets doubles'),
                ('contacts.html', 'une balise en apostrophes simples'),
                ('inventory.html', 'un src affecte en JavaScript')):
            self.assertIn(
                fichier, vus,
                'the scan no longer sees %s (%s), so that whole way of '
                'writing a third-party load is unguarded' % (fichier, forme))
        self.assertGreaterEqual(
            len(trouve), 10,
            'only %d third-party resources found, down from the 10 measured '
            'on 2026-09-10; the scan has narrowed' % len(trouve))

    def test_no_third_party_script_or_stylesheet_runs_unpinned(self):
        nus = [(f, u) for f, b, u in _ressources_tierces()
               if 'integrity=' not in b.lower()
               and u not in _NON_EPINGLABLES]
        self.assertFalse(
            nus,
            'these load third-party code with no subresource integrity, so a '
            'compromised CDN would run its own: %s' % nus[:4])

    def test_the_exemption_list_still_describes_real_tags(self):
        vues = set(u for _f, _b, u in _ressources_tierces())
        fantomes = sorted(_NON_EPINGLABLES - vues)
        self.assertFalse(
            fantomes,
            'these exemptions no longer match any tag, so nothing checks '
            'what they claim to excuse: %s' % fantomes)

    def test_a_pinned_resource_also_allows_the_check(self):
        """`integrity` without `crossorigin` checks nothing cross-origin."""
        boiteux = [(f, u) for f, b, u in _ressources_tierces()
                   if 'integrity=' in b.lower()
                   and 'crossorigin' not in b.lower()]
        self.assertFalse(
            boiteux,
            'these carry an integrity hash the browser cannot verify without '
            'crossorigin: %s' % boiteux[:4])

    def test_every_hash_is_sha384_or_stronger(self):
        faibles = []
        for f, b, u in _ressources_tierces():
            m = re.search(r'integrity\s*=\s*[\'"]([^\'"]*)[\'"]', b, re.I)
            if m and not re.search(r'sha(384|512)-', m.group(1)):
                faibles.append((f, m.group(1)[:24]))
        self.assertFalse(faibles, 'weaker than sha384: %s' % faibles)


# Third-party origin: brand name the privacy policy must mention
_ORIGINE_ANNONCEE = {
    'ajax.googleapis.com': 'Google Hosted Libraries',
    'cdn.jsdelivr.net': 'jsDelivr',
    'www.google.com': 'reCAPTCHA',
    'www.googletagmanager.com': 'Analytics',
    'pagead2.googlesyndication.com': 'AdSense',
    'fundingchoicesmessages.google.com': 'Consent',
}


class ThePrivacyPolicyNamesEveryThirdPartyTests(SimpleTestCase):
    """The privacy policy names every origin the templates load."""

    def _politique(self):
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'chardata', 'privacy.html')
        with open(chemin, encoding='utf-8') as f:
            return f.read()

    def _origines(self):
        return sorted(set(urlsplit(u).netloc
                          for _f, _b, u in _ressources_tierces()))

    def test_every_loaded_origin_has_been_decided_about(self):
        inconnues = [o for o in self._origines()
                     if o not in _ORIGINE_ANNONCEE]
        self.assertFalse(
            inconnues,
            'these third-party origins are loaded but nobody decided how the '
            'privacy policy should name them: %s' % inconnues)

    def test_every_loaded_origin_is_named_in_the_policy(self):
        corps = self._politique().lower()
        muettes = []
        for origine in self._origines():
            nom = _ORIGINE_ANNONCEE[origine]
            if nom.lower() not in corps:
                muettes.append((origine, nom))
        self.assertFalse(
            muettes,
            'the site loads these but the privacy policy never names them, so '
            'it describes a different site: %s' % muettes)

    def test_the_policy_does_not_promise_a_deletion_nobody_performs(self):
        """Unvisited builds keep their view IPs until the restart cleanup."""
        corps = self._politique()
        self.assertIn('when the server restarts', corps)
        self.assertNotIn('delete it after twenty-four hours', corps)

    def test_the_policy_carries_a_date_it_can_still_honour(self):
        corps = self._politique()
        self.assertIn('Last updated:', corps)
        for perime in ('June 2026', 'July 2026', 'August 2026'):
            self.assertNotIn(
                'Last updated: %s' % perime, corps,
                'the policy changed since %s but still says it did not'
                % perime)


class ThePrivacyPolicyRendersInEveryLanguageTests(TestCase):
    """Checked on the served page: gettext ignores fuzzy entries."""

    # Phrases from each translation, not brand names
    TEMOINS = {
        'en': ('reCAPTCHA to tell people apart from bots',
               'is fetched from Google Hosted Libraries and jsDelivr',
               'when the server restarts',
               'Last updated: September 2026'),
        'fr': ('pour distinguer les humains des robots',
               'depuis Google Hosted Libraries et jsDelivr',
               'au red\u00e9marrage du serveur',
               'septembre 2026'),
        'es': ('para distinguir a las personas de los bots',
               'desde Google Hosted Libraries y jsDelivr',
               'al reiniciarse el servidor',
               'septiembre de 2026'),
        'pt': ('para distinguir pessoas de bots',
               'do Google Hosted Libraries e do jsDelivr',
               'ao reiniciar o servidor',
               'setembro de 2026'),
        'de': ('um Menschen von Bots zu unterscheiden',
               'von Google Hosted Libraries und jsDelivr geladen',
               'beim Neustart des Servers',
               'September 2026'),
    }

    def test_the_policy_is_served_translated_in_all_five_languages(self):
        manquants = []
        for langue, temoins in sorted(self.TEMOINS.items()):
            reponse = self.client.get(
                '/privacy/', headers={'accept-language': langue})
            self.assertEqual(reponse.status_code, 200, langue)
            corps = reponse.content.decode('utf-8')
            for temoin in temoins:
                if temoin not in corps:
                    manquants.append((langue, temoin))
        self.assertFalse(
            manquants,
            'the catalogue compiled but these never reached the page: %s'
            % manquants)

    def test_the_old_promises_are_served_nowhere(self):
        survivants = []
        for langue in sorted(self.TEMOINS):
            corps = self.client.get(
                '/privacy/',
                headers={'accept-language': langue}).content.decode('utf-8')
            for mort in ('delete it after twenty-four hours',
                         'au bout de vingt-quatre heures',
                         'a las veinticuatro horas',
                         'ao fim de vinte e quatro horas',
                         'nach vierundzwanzig Stunden',
                         'June 2026', 'juin 2026', 'junio de 2026',
                         'junho de 2026', 'Juni 2026'):
                if mort in corps:
                    survivants.append((langue, mort))
        self.assertFalse(
            survivants,
            'these were corrected in the template but are still served: %s'
            % survivants)
