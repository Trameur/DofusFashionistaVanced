# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une copie version-prefixee qui ne montre rien de neuf le dit.

Trouve en relevant le titre de chaque page atteinte depuis les 25 racines.
Mesure du 14 septembre 2026, sur les 584 pages lues: **360 se declaraient
canoniques d'elles-memes, et 150 d'entre elles partageaient leur titre avec
quatre soeurs de la meme langue** -- les copies version-prefixees de pages
identiques.

Le site avait deja la regle, ecrite dans `about.html`:

    Version-prefixed copies (/beta/about/ etc.) are duplicates
    -> canonical to the global page.

Elle etait posee sur `/about/`, `/faq/`, `/license/`, `/support/` et
`/privacy/`, et nulle part ailleurs.

**Quelles pages y ont droit est une mesure, pas une intuition.** Rendues sous
les cinq versions et comparees corps a corps, pied de page exclu:

| famille | ressemblance entre versions | verdict |
|---------|-----------------------------|---------|
| /contact/ | 0,98 a 0,99 | identique, seule la ligne de version du pied change |
| /login_page/ | 0,98 a 0,99 | identique |
| /smartbuild/ | 0,99 | identique |
| **/quickstart/** | 0,96 a 0,99 | **differente**: Retro y montre sept classes de moins |
| /sharedbuilds/ | 0,33 a 0,39 | differente |
| /loadprojects/ | 0,50 a 0,62 | differente |
| /encyclopedia/ | 0,26 a 0,98 | differente |

`/quickstart/` est le cas qui aurait rendu le site faux: son corps se
ressemble a 0,96, et le diff mot a mot dit pourquoi les quatre pour cent
manquants comptent. Elle garde donc son propre canonique sur chaque version.

Apres: 300 pages se declarent d'elles-memes au lieu de 360, et les 15 titres
encore partages sont ceux de trois familles qui montrent vraiment autre chose
(`loadprojects` et `choose_compare_sets`, derriere la connexion, et
`quickstart`).

Deux choses sont retirees avant de comparer, et le premier parcours mesure
qu'elles le sont: le pied de page, qui nomme la version du jeu sur les 584
pages, et le jeton anti-CSRF du formulaire, tire au sort a chaque requete.
Sans ces deux coupes aucune page ne serait jamais identique a sa copie.

Ce garde ne lit pas une liste: il rend les pages et compare, donc il tombe
aussi bien si une page identique cesse de le dire que si une page differente
se met a le dire.
"""
import re

from django.test import TestCase

SITE = 'https://dofusfashionista.gg'
VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
PREFIX = {'dofus3': '', 'beta': '/beta', 'dofus2': '/dofus2',
          'touch': '/touch', 'retro': '/retro'}

#: Les pages publiques servies sous les cinq versions. Les pages derriere la
#: connexion en sont absentes: elles sont noindex, donc leur canonique ne
#: decide de rien.
FAMILIES = ('/about/', '/faq/', '/license/', '/support/', '/contact/',
            '/login_page/', '/smartbuild/', '/quickstart/')

#: Ce que le corps de la page dit, sans l'en-tete qui marque la version
#: active ni le pied qui la nomme.
_BODY = re.compile(r'id="main-content"(.*?)class="footer"', re.S)
_TAG = re.compile(r'<[^>]+>')
_LINK = re.compile(r'<link\b[^>]*>', re.I)
_ATTR = {name: re.compile(r'\b%s="([^"]*)"' % name, re.I)
         for name in ('rel', 'href')}

#: Le jeton anti-CSRF: 64 caracteres tires au sort a chaque requete, donc
#: different entre deux rendus de la meme page, version ou pas.
_CSRF = re.compile(r'\b[A-Za-z0-9]{64}\b')


def _attr(tag, name):
    found = _ATTR[name].search(tag)
    return found.group(1) if found else None


def _canonical_of(html):
    for tag in _LINK.findall(html):
        if _attr(tag, 'rel') == 'canonical':
            return _attr(tag, 'href')
    return None


def _read_body(html):
    found = _BODY.search(html)
    return ' '.join(_TAG.sub(' ', found.group(1) if found else html).split())


def _body_of(html):
    return _CSRF.sub('<csrf>', _read_body(html))


class AVersionCopySaysWhetherItShowsAnythingNewTests(TestCase):

    def _page(self, path):
        answer = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(answer.status_code, 200, path)
        return answer.content.decode('utf-8', 'replace')

    def _read(self, family):
        bodies, canonicals = {}, {}
        for version in VERSIONS:
            html = self._page(PREFIX[version] + family)
            bodies[version] = _body_of(html)
            canonicals[version] = _canonical_of(html)
        return bodies, canonicals

    def test_the_two_cuts_are_what_make_a_copy_comparable(self):
        """Le plancher du parcours. Chaque coupe est mesuree: sans elle les
        deux pages different, avec elle elles se confondent."""
        page = self._page('/retro/about/')
        self.assertIn('Items up to', page,
                      'the footer no longer names the game version')
        self.assertNotIn('Items up to', _body_of(page),
                         'the footer is still inside the body')
        self.assertGreater(len(_body_of(page)), 400)

        raw = [_read_body(self._page(path))
               for path in ('/login_page/', '/retro/login_page/')]
        self.assertNotEqual(raw[0], raw[1],
                            'the csrf token no longer varies per request')
        self.assertEqual(_CSRF.sub('<csrf>', raw[0]),
                         _CSRF.sub('<csrf>', raw[1]))

    def test_each_family_answers_the_question_it_is_asked(self):
        identical, different = [], []
        for family in FAMILIES:
            bodies, canonicals = self._read(family)
            same = all(bodies[version] == bodies['dofus3']
                       for version in VERSIONS)
            (identical if same else different).append(family)
            for version in VERSIONS[1:]:
                own = SITE + PREFIX[version] + family
                free = SITE + family
                with self.subTest(family=family, version=version):
                    if same:
                        self.assertEqual(
                            free, canonicals[version],
                            '%s%s shows nothing the global page does not, so '
                            'it must not claim to be its own page'
                            % (PREFIX[version], family))
                    else:
                        self.assertEqual(
                            own, canonicals[version],
                            '%s%s shows something else, so it is its own page'
                            % (PREFIX[version], family))
        self.assertGreaterEqual(len(identical), 5, identical)
        self.assertGreaterEqual(len(different), 1, different)

    def test_quickstart_is_the_family_that_shows_something_else(self):
        """Le temoin nomme du cote <<differente>>. Sans lui, une regle qui
        canoniserait tout passerait le parcours le jour ou plus rien ne
        differe."""
        bodies, canonicals = self._read('/quickstart/')
        self.assertNotEqual(bodies['dofus3'], bodies['retro'])
        missing = [name for name in ('Eliotrope', 'Foggernaut', 'Forgelance',
                                     'Huppermage', 'Masqueraider', 'Ouginak',
                                     'Rogue')
                   if name in bodies['dofus3'] and name not in bodies['retro']]
        self.assertEqual(7, len(missing), missing)
        self.assertEqual(SITE + '/retro/quickstart/', canonicals['retro'])

    def test_a_copy_that_disclaims_itself_publishes_no_hreflang(self):
        """Les deux moities du <head> repondent a la meme question: un groupe
        qui nommerait cette page la contredirait."""
        html = self._page('/retro/contact/')
        self.assertEqual(SITE + '/contact/', _canonical_of(html))
        self.assertNotIn('hreflang=', html)
        global_page = self._page('/contact/')
        self.assertIn('hreflang=', global_page)
