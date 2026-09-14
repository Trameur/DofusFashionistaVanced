# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un nom pose a cote d'un nombre s'accorde avec lui.

Le lot 72 avait corrige les quatre compteurs du bandeau. Un balayage des 90
gabarits en a trouve **neuf autres**, dont quatre que la recherche a la main
avait manques parce qu'ils s'ecrivent autrement.

**Mesure du 13 septembre 2026, avant le changement.** Le pire n'etait pas le
compte de un: la page de profil appliquait le filtre `pluralize`, c'est-a-dire
la morphologie **anglaise**, au resultat d'une traduction:

| langue | ce que le profil affichait a deux |
|--------|-----------------------------------|
| fr | 2 abonnes (juste, par chance) |
| es | 2 **seguidors** (le pluriel est <<seguidores>>) |
| pt | 2 **seguidors** (le pluriel est <<seguidores>>) |
| de | 2 **Followers** (le pluriel est <<Follower>>) |

Trois langues sur quatre etaient fausses **a chaque compte au-dessus de un**,
pas seulement a un. Les autres compteurs posaient un pluriel fige et etaient
faux a un: <<1 Favoris>>, <<1 pieces>>, <<1 panoplies>>, <<1 vues>>.

**Ce qui n'est pas touche, et pourquoi.** Le balayage laisse sept cas qui ne
comptent rien: <<Page 3 of 12>>, <<lvl>>, deux phrases de description, le
total d'unites de l'atelier, et <<degats>>, qui est indenombrable. Reste le
ratio <<x/y pieces>> de la page de build: le nom y suit le **total** de la
panoplie, et aucune panoplie n'a une seule piece, mesure sur les cinq versions
le 13 septembre 2026 (les tailles vont de 2 a 8). Son pluriel est donc
toujours juste, et le faire varier serait un changement sans cause.

**Le contexte de traduction.** Quatre de ces noms s'ecrivent comme un libelle
de bouton deja traduit (<<Like>>, <<Favorite>>) ou comme une ancienne entree
au singulier (<<follower>>, <<following>>). Un pluriel portant le meme msgid
serait refuse par msgfmt, donc ceux-la portent le contexte <<counter>>. Les
autres n'en ont pas besoin et n'en ont pas.
"""

import io
import os
import re

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: `{{ quelque.chose|filtre }}` suivi d'une chaine traduite figee. C'est la
#: forme qui ne peut pas s'accorder.
_NOM_FIGE = re.compile(
    r'\{\{\s*([^}]+?)\s*\}\}\s*(?:</[a-z]+>)?\s*\{%\s*trans\s+'
    r'([\'"])(.+?)\2\s*%\}', re.S)

#: Le filtre `pluralize` ajoute un <<s>> anglais. Applique au resultat d'une
#: traduction, il invente un pluriel dans la langue du lecteur.
_FILTRE_ANGLAIS = re.compile(
    r'\{%\s*trans\s+[\'"](.+?)[\'"]\s*%\}\s*\{\{[^}]*\|pluralize[^}]*\}\}')

#: Ce que le balayage a le droit de trouver, avec la raison. Une entree ici
#: est une DECISION: un nom comptable qui apparaitrait sans y figurer fait
#: echouer le test plutot que de passer inapercu.
_NE_COMPTE_RIEN = {
    'of': 'preposition de pagination, <<Page 3 of 12>>',
    'lvl': 'abreviation de niveau, pas un compte',
    'build optimized on Dofus Fashionista': 'phrase de description',
    'build optimized on Dofus Fashionista. Like it, comment it, copy it.':
        'phrase de description',
    'damage': 'indenombrable',
    # <<total>> a quitte cette liste au lot 83: l'atelier ne compose plus
    # sa phrase mot a mot, le serveur la rend entiere. Le test l'a dit
    # lui-meme, une exemption qui ne correspond plus a rien echoue.
    # Le nom suit le TOTAL de la panoplie, et aucune n'a une seule piece:
    # tailles de 2 a 8 sur les cinq versions, mesure le 13 septembre 2026.
    'pieces': 'ratio x/y, dont le y est au moins 2 sur les cinq versions',
}

#: Les neuf compteurs que ce lot fait accorder, avec leur contexte quand ils
#: en portent un.
_COMPTEURS = (
    ('counter', 'follower', 'followers'),
    ('counter', 'following', 'following'),
    ('counter', 'Like', 'Likes'),
    ('counter', 'Favorite', 'Favorites'),
    ('counter', 'piece', 'pieces'),
    ('counter', 'set', 'sets'),
    (None, 'like received', 'likes received'),
    (None, 'favorite received', 'favorites received'),
    (None, 'view', 'views'),
)

#: Les formes qui etaient fausses avant le lot, et qui ne doivent plus
#: reapparaitre. Le pluriel anglais plaque sur une autre langue.
_PLURIELS_INVENTES = {('es', 'seguidors'), ('pt', 'seguidors'),
                      ('de', 'Followers')}


def _gabarits():
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates')
    for dossier, _sous, noms in os.walk(racine):
        for nom in noms:
            if nom.endswith('.html'):
                yield nom, os.path.join(dossier, nom)


def _rendu(contexte, singulier, pluriel, langue, nombre):
    marque = ' context "%s"' % contexte if contexte else ''
    gabarit = Template(
        '{%% load i18n %%}{%% blocktrans count n=n%s %%}%s{%% plural %%}%s'
        '{%% endblocktrans %%}' % (marque, singulier, pluriel))
    with translation.override(langue):
        return gabarit.render(Context({'n': nombre}))


class NoTemplatePutsAFixedNounNextToANumberTests(SimpleTestCase):

    def test_the_scan_actually_reads_the_templates(self):
        """Le plancher: un balayage qui ne lit plus rien ne garde rien."""
        vus = list(_gabarits())
        self.assertGreater(len(vus), 80,
                           'only %d templates found, down from the 90 '
                           'measured on 2026-09-17' % len(vus))

    def test_every_fixed_noun_left_is_one_that_counts_nothing(self):
        inconnus = []
        for nom, chemin in _gabarits():
            texte = io.open(chemin, encoding='utf-8', errors='replace').read()
            for m in _NOM_FIGE.finditer(texte):
                chaine = m.group(3)
                if chaine not in _NE_COMPTE_RIEN:
                    inconnus.append((nom, m.group(1).strip(), chaine))
        self.assertFalse(
            inconnus,
            'these put a fixed word next to a number and nobody decided '
            'whether it counts: %s' % inconnus[:6])

    def test_no_template_appends_an_english_s_to_a_translated_word(self):
        """Le defaut le plus grave, parce qu'il ne depend pas du compte.

        `pluralize` applique la morphologie anglaise; sur un mot traduit il
        fabrique <<seguidors>> et <<Followers>>.
        """
        fautifs = []
        for nom, chemin in _gabarits():
            texte = io.open(chemin, encoding='utf-8', errors='replace').read()
            for m in _FILTRE_ANGLAIS.finditer(texte):
                fautifs.append((nom, m.group(1)))
        self.assertFalse(
            fautifs,
            'these build a plural with the English rule on a translated '
            'word: %s' % fautifs)

    def test_the_exemptions_still_describe_something_real(self):
        """Une exemption qui ne designe plus rien exempte dans le vide."""
        vues = set()
        for _nom, chemin in _gabarits():
            texte = io.open(chemin, encoding='utf-8', errors='replace').read()
            for m in _NOM_FIGE.finditer(texte):
                vues.add(m.group(3))
        fantomes = sorted(set(_NE_COMPTE_RIEN) - vues)
        self.assertFalse(fantomes,
                         'these exemptions match no template any more: %s'
                         % fantomes)


class EveryCounterHasTwoFormsInEveryLanguageTests(SimpleTestCase):

    def test_one_and_two_are_told_apart_where_the_language_does(self):
        """Sans distinction, le compteur ne peut pas s'accorder. Les cas ou
        une langue est invariante sont reels et restent egaux."""
        distincts = 0
        for contexte, singulier, pluriel in _COMPTEURS:
            for langue in LANGUES:
                un = _rendu(contexte, singulier, pluriel, langue, 1)
                deux = _rendu(contexte, singulier, pluriel, langue, 2)
                if un != deux:
                    distincts += 1
        self.assertGreater(
            distincts, 30,
            'only %d of the 45 counter-language pairs tell one from two; the '
            'catalogue is not compiled or the entries are gone' % distincts)

    def test_the_english_plural_is_never_glued_onto_another_language(self):
        """Les trois formes que le filtre fabriquait. Si l'une revient, c'est
        que quelqu'un a remis la regle anglaise."""
        for langue, forme in sorted(_PLURIELS_INVENTES):
            with self.subTest(langue=langue, forme=forme):
                rendu = _rendu('counter', 'follower', 'followers', langue, 2)
                self.assertNotEqual(forme, rendu)

    def test_the_spanish_and_portuguese_plurals_are_the_real_ones(self):
        for langue in ('es', 'pt'):
            with self.subTest(langue=langue):
                self.assertEqual(
                    'seguidores',
                    _rendu('counter', 'follower', 'followers', langue, 2))
                self.assertEqual(
                    'seguidor',
                    _rendu('counter', 'follower', 'followers', langue, 1))

    def test_each_language_answers_with_its_own_words(self):
        """Un catalogue non compile laisserait l'anglais partout et les
        accords ci-dessus seraient vrais sur la mauvaise langue."""
        muettes = []
        for contexte, singulier, pluriel in _COMPTEURS:
            anglais = _rendu(contexte, singulier, pluriel, 'en', 2)
            for langue in ('fr', 'es', 'pt', 'de'):
                if _rendu(contexte, singulier, pluriel, langue, 2) == anglais:
                    muettes.append((langue, singulier))
        # <<set>> est <<sets>> en espagnol et en portugais, <<Sets>> en
        # allemand: trois egalites reelles, pas des traductions manquantes.
        self.assertLessEqual(
            len(muettes), 3,
            'too many counters answer in English: %s' % muettes)
