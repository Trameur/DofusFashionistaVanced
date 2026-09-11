# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Ce que le SERVEUR va chercher chez un tiers, a la place du lecteur.

`tests_third_party_integrity` garde l'autre moitie: ce que le NAVIGATEUR
telecharge. Les deux familles repondent a la meme question, <<le site
decrit-il le site>>, mais aucune des deux ne voit ce que voit l'autre, et
c'est par ce trou que DofusBook est reste absent de la politique de
confidentialite pendant que deux pages entieres lui parlaient.

Un appel sortant est plus difficile a auditer qu'une balise: il ne se lit pas
dans le rendu de la page, le lecteur ne peut pas le voir dans son onglet
reseau, et il part avec les droits du serveur. Les affirmations que la
politique porte a son sujet sont donc mesurees ici, sur les octets qui
partent, et pas relues.
"""

import os
import re

from django.test import SimpleTestCase

from chardata import dofusbook_export, dofusbook_import, dofuscreator_import

#: Chaque hote que le serveur appelle pour le compte d'un lecteur, et le nom
#: sous lequel la politique doit le designer. Une entree ici est une
#: DECISION: un hote qui n'y figure pas fait echouer le test plutot que de
#: passer inapercu.
_HOTE_ANNONCE = {
    'www.dofusbook.net': 'DofusBook',
    'dofusbook.net': 'DofusBook',
    'retro.dofusbook.net': 'DofusBook',
    'touch.dofusbook.net': 'DofusBook',
    'dofuscreator.com': 'DofusCreator',
    'www.dofuscreator.com': 'DofusCreator',
    'www.google.com': 'reCAPTCHA',
}

#: Les endroits qui ont le droit d'appeler dehors, et ce qu'ils appellent.
#: Le test plus bas relit le code pour verifier qu'il n'y en a pas un
#: quatrieme: une politique exacte le jour ou elle est ecrite ne vaut que
#: jusqu'au prochain appel ajoute ailleurs.
_APPELANTS = {
    'dofusbook_import.py': 'urlopen',
    'dofusbook_export.py': 'urlopen',
    'dofuscreator_import.py': 'urlopen',
    'util.py': 'http_requests.post',
}

#: Les en-tetes par lesquelles l'adresse du lecteur, ou son identite,
#: pourraient partir sans qu'on l'ait voulu. Les trois premieres sont ce
#: qu'un serveur ajoute <<par politesse>> en relayant une requete.
_ENTETES_QUI_TRAHISSENT = (
    'x-forwarded-for', 'x-real-ip', 'forwarded', 'client-ip',
    'true-client-ip', 'cf-connecting-ip', 'x-client-ip',
    'cookie', 'authorization', 'from',
)


def _dossier():
    return os.path.dirname(os.path.abspath(__file__))


def _politique():
    chemin = os.path.join(_dossier(), 'templates', 'chardata', 'privacy.html')
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _hotes_appeles():
    """Les hotes lus DANS LE CODE, pas dans une liste tenue a la main.

    Les deux tables sont dans des sens opposes: cote import elle repond
    <<quel jeu est cet hote>>, cote export <<quel hote pour ce jeu>>. Prendre
    les cles des deux rendrait dofus3, retro et touch, qui ne sont pas des
    hotes, et le test serait vert sans avoir rien lu.
    """
    hotes = (set(dofusbook_import.HOSTS) | set(dofusbook_export.HOSTS.values())
             | set(dofuscreator_import.HOSTS))
    chemin = os.path.join(_dossier(), 'util.py')
    with open(chemin, encoding='utf-8') as f:
        for adresse in re.findall(r'https://([a-z0-9.-]+)/recaptcha/',
                                  f.read()):
            hotes.add(adresse)
    return sorted(hotes)


class EveryHostTheServerCallsIsNamedTests(SimpleTestCase):

    def test_the_scan_actually_finds_the_hosts(self):
        """Le plancher du temoin: un scan qui ne trouve rien garderait un
        site parfaitement honnete et parfaitement imaginaire."""
        hotes = _hotes_appeles()
        self.assertIn('www.dofusbook.net', hotes)
        self.assertIn('retro.dofusbook.net', hotes)
        self.assertIn('dofuscreator.com', hotes)
        self.assertIn('www.google.com', hotes)

    def test_every_host_has_been_decided_about(self):
        inconnus = [h for h in _hotes_appeles() if h not in _HOTE_ANNONCE]
        self.assertFalse(
            inconnus,
            'the server calls these on a reader behalf but nobody decided '
            'how the privacy policy should name them: %s' % inconnus)

    def test_every_host_is_named_in_the_policy(self):
        corps = _politique().lower()
        muets = []
        for hote in _hotes_appeles():
            nom = _HOTE_ANNONCE[hote]
            if nom.lower() not in corps:
                muets.append((hote, nom))
        self.assertFalse(
            muets,
            'the server calls these but the privacy policy never names them, '
            'so it describes a different site: %s' % muets)

    def _appelants(self):
        appelants = {}
        for nom in sorted(os.listdir(_dossier())):
            if not nom.endswith('.py') or nom.startswith('tests'):
                continue
            with open(os.path.join(_dossier(), nom), encoding='utf-8') as f:
                corps = f.read()
            # `urlopen(` seul ne trouvait NI l'import NI l'export: les deux
            # gardent la fonction dans une variable pour qu'un test puisse la
            # remplacer (`ouvreur = opener or urllib.request.urlopen`), donc
            # la parenthese n'est pas collee au nom. Le garde etait vert et
            # n'avait lu qu'un fichier sur trois.
            for motif in ('urllib.request.urlopen', 'urllib.request.Request(',
                          'http_requests.post(', 'http_requests.get(',
                          'requests.post(', 'requests.get('):
                if motif in corps:
                    appelants.setdefault(nom, set()).add(motif.rstrip('('))
        return appelants

    def test_the_scan_still_finds_the_three_known_callers(self):
        """La moitie du garde que le suivant ne peut pas porter: une
        recherche qui ne trouve plus rien rend une difference vide, donc un
        vert parfait sur un site qu'elle n'a pas lu."""
        self.assertEqual(set(_APPELANTS), set(self._appelants()))

    def test_no_fourth_place_calls_out_without_saying_so(self):
        """Une politique exacte le jour ou elle est ecrite ne vaut que
        jusqu'au prochain appel ajoute ailleurs."""
        nouveaux = sorted(set(self._appelants()) - set(_APPELANTS))
        self.assertFalse(
            nouveaux,
            'these now call a third party from the server and the privacy '
            'policy has not been told: %s' % nouveaux)


class TheOutgoingCallCarriesNoReaderTests(SimpleTestCase):
    """La politique dit que ces appels partent de notre adresse et non de
    celle du lecteur. C'est une affirmation sur des octets.

    Mesure du 10 septembre 2026: les deux appels sont des GET sans corps et
    portent exactement trois en-tetes, Accept, Referer et User-agent.
    """

    def _capture(self, fonction, *args):
        vues = {}

        # BaseException et non Exception: les deux modules rattrapent tout ce
        # qui derive d'Exception pour rendre <<injoignable>> au lecteur, donc
        # une sortie ordinaire serait avalee et le test mesurerait le
        # message d'erreur au lieu de la requete.
        class Arret(BaseException):
            pass

        def ouvreur(requete, timeout=None):
            vues['url'] = requete.full_url
            vues['methode'] = requete.get_method()
            vues['entetes'] = {c.lower(): v
                               for c, v in requete.header_items()}
            vues['corps'] = requete.data
            raise Arret
        try:
            fonction(*args, opener=ouvreur)
        except Arret:
            pass
        return vues

    def _les_deux(self):
        return {
            'import': self._capture(dofusbook_import.fetch_build,
                                    'retro.dofusbook.net', '2558915'),
            'export': self._capture(dofusbook_export.known_ankama_ids,
                                    'retro',
                                    [[11542]] + [[] for _ in range(9)]),
        }

    def test_nothing_that_names_the_reader_goes_out(self):
        for nom, vu in self._les_deux().items():
            for entete in _ENTETES_QUI_TRAHISSENT:
                self.assertNotIn(
                    entete, vu['entetes'],
                    'the %s call would hand DofusBook a %s header, which the '
                    'privacy policy says it does not' % (nom, entete))

    def test_the_calls_read_and_never_write(self):
        for nom, vu in self._les_deux().items():
            self.assertEqual('GET', vu['methode'], nom)
            self.assertIsNone(vu['corps'], nom)

    def test_only_the_three_measured_headers_go_out(self):
        """Une en-tete de plus est une phrase de moins qui reste vraie."""
        for nom, vu in self._les_deux().items():
            self.assertEqual({'accept', 'referer', 'user-agent'},
                             set(vu['entetes']), nom)

    def test_the_project_page_is_read_with_two_headers_and_no_referer(self):
        """DofusCreator repond 200 a un GET nu avec un User-Agent de
        navigateur (mesure du 11 septembre 2026): pas de Referer a
        fabriquer, donc il n'en part pas."""
        vu = self._capture(dofuscreator_import.fetch_project,
                           'dofuscreator.com', '6e9f4')
        self.assertEqual('https://dofuscreator.com/projet/6e9f4', vu['url'])
        self.assertEqual('GET', vu['methode'])
        self.assertIsNone(vu['corps'])
        self.assertEqual({'accept', 'user-agent'}, set(vu['entetes']))
        for entete in _ENTETES_QUI_TRAHISSENT:
            self.assertNotIn(entete, vu['entetes'])

    def test_the_export_asks_about_items_and_sends_nothing_else(self):
        vu = self._capture(dofusbook_export.known_ankama_ids, 'retro',
                           [[11542]] + [[] for _ in range(9)])
        self.assertIn('/api/items/', vu['url'])
        self.assertIn('ca-11542', vu['url'])
        self.assertNotIn('?', vu['url'])


class TheHandedLinkDoesNotSayWhereItCameFromTests(SimpleTestCase):
    """La politique dit que le navigateur n'atteint leur site que si le
    lecteur clique. Ce qu'elle ne doit pas laisser croire, c'est qu'ils
    apprennent d'ou il vient: le lien porte `noreferrer`."""

    def test_the_export_link_carries_noreferrer(self):
        chemin = os.path.join(_dossier(), 'templates', 'chardata',
                              'dofusbook_export.html')
        with open(chemin, encoding='utf-8') as f:
            corps = f.read()
        lien = re.search(r'<a[^>]*href="\{\{ link \}\}"[^>]*>', corps)
        self.assertIsNotNone(lien, 'the outgoing link is gone')
        self.assertIn('noreferrer', lien.group(0))
        self.assertIn('noopener', lien.group(0))


class ThePolicyDoesNotCountPagesTests(SimpleTestCase):
    """Elle nommait <<la page de l'inventaire>> comme seule page a lire une
    capture. Une deuxieme la lit depuis le 10 septembre 2026, et la phrase
    est devenue fausse sans que rien ne bouge. Une politique qui compte les
    pages devient fausse a la page suivante."""

    def test_the_stale_wording_is_gone(self):
        corps = _politique()
        self.assertNotIn('library on the inventory page', corps)
        self.assertIn('the pages that read a screenshot', corps)

    def test_the_reader_really_runs_on_more_than_one_page(self):
        """Sans cette moitie, la phrase generale pourrait etre vraie par
        hasard, sur une seule page."""
        gabarits = os.path.join(_dossier(), 'templates', 'chardata')
        porteurs = []
        for nom in sorted(os.listdir(gabarits)):
            if not nom.endswith('.html'):
                continue
            with open(os.path.join(gabarits, nom), encoding='utf-8') as f:
                if 'tesseract' in f.read():
                    porteurs.append(nom)
        self.assertGreaterEqual(len(porteurs), 2, porteurs)


class TheNewSentencesAreTranslatedTests(SimpleTestCase):

    CHAINES = (
        '<b>DofusBook.</b> When you paste a DofusBook link, our server '
        'fetches that build from dofusbook.net; when you open one of your '
        'builds on their site, our server first asks them which of its items '
        'they know. Both calls leave from our address and not from yours, so '
        'on those steps they do not receive your address. The link we then '
        'hand you carries the gear, the level and the characteristics of that '
        'build, and nothing that names you, and your browser only reaches '
        'their site if you click it.',
        '<b>DofusCreator.</b> When you paste a link to a public DofusCreator '
        'project, our server fetches that page from dofuscreator.com. The '
        'call leaves from our address and not from yours, carries nothing '
        'that names you, and only reads.',
        '<b>Code libraries.</b> Some of the code that makes the pages work, '
        'such as jQuery on every page and a text-reading library on the pages '
        'that read a screenshot, is fetched from Google Hosted Libraries and '
        'jsDelivr instead of from our own server, so those providers receive '
        'your IP address. Each of these files is pinned to a fingerprint, and '
        'your browser refuses to run a copy that does not match.',
    )

    def test_both_read_in_the_four_other_languages(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for chaine in self.CHAINES:
                    if gettext(chaine) == chaine:
                        muettes.append((langue, chaine[:40]))
        self.assertEqual([], muettes)
