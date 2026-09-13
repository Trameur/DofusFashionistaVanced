# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Les compteurs du bandeau s'accordent en nombre avec ce qu'ils comptent.

Le bandeau est sur **toutes** les pages du site. Ses quatre compteurs posaient
un nom fige au pluriel a cote d'un nombre, et disaient donc <<1 joueurs>>,
<<1 personnages crees>>, <<1 reponses du solveur>>, <<1 stuffs partages>>.

**Mesure du 16 septembre 2026**: sur les vingt combinaisons (quatre compteurs,
cinq langues), une seule etait juste pour un compte de un, l'allemand
<<Spieler>>, et par accident: le mot est invariant. Les dix-neuf autres
etaient fausses.

Chaque langue applique maintenant **sa propre** regle, ce que le catalogue
declare et que ces tests fixent:

| compte | en | fr | es | de |
|--------|----|----|----|----|
| 0 | users | **joueur** | jugadores | Spieler |
| 1 | user | joueur | jugador | Spieler |
| 2 | users | joueurs | jugadores | Spieler |

Le francais garde le singulier a zero (`plural=(n > 1)`), les autres passent au
pluriel. Ce n'est pas une bizarrerie a corriger, c'est l'usage de chaque
langue, et le catalogue le declare deja.

Le nombre, lui, reste dans sa balise et garde ses separateurs de milliers. Le
pluriel a besoin de l'entier: une chaine <<1,234>> ne peut pas choisir une
forme, donc le processeur de contexte publie les deux.
"""

from django.template import Context, Template
from django.test import TestCase
from django.utils import translation

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Les quatre compteurs, avec le gabarit exact que le bandeau emploie.
_COMPTEURS = {
    'user': ('user', 'users'),
    'character': ('character created', 'characters created'),
    'answer': ('solver answer', 'solver answers'),
    'build': ('shared build', 'shared builds'),
}

#: Ce que rend chaque langue pour zero, mesure le 16 septembre 2026. Le
#: francais garde le singulier, les autres non.
_ZERO_EST_SINGULIER = {'en': False, 'fr': True, 'es': False, 'pt': False,
                       'de': False}

#: L'allemand ne distingue pas <<Spieler>> au singulier et au pluriel. C'est
#: la langue qui le veut, pas un oubli de traduction: nomme ici pour que
#: personne ne le <<corrige>>.
_INVARIABLES = {('de', 'user')}


def _rendu(cle, langue, nombre):
    singulier, pluriel = _COMPTEURS[cle]
    gabarit = Template(
        '{%% load i18n %%}{%% blocktrans count n=n %%}%s{%% plural %%}%s'
        '{%% endblocktrans %%}' % (singulier, pluriel))
    with translation.override(langue):
        return gabarit.render(Context({'n': nombre}))


class EachLanguageUsesItsOwnRuleTests(TestCase):

    def test_one_is_never_rendered_with_the_plural_form(self):
        """Le defaut lui-meme: <<1 joueurs>> sur chaque page du site."""
        fautifs = []
        for cle in _COMPTEURS:
            for langue in LANGUES:
                un = _rendu(cle, langue, 1)
                deux = _rendu(cle, langue, 2)
                if (langue, cle) in _INVARIABLES:
                    continue
                if un == deux:
                    fautifs.append((langue, cle, un))
        self.assertFalse(
            fautifs,
            'these read the same at one and at two, so the counter cannot '
            'agree: %s' % fautifs)

    def test_the_invariable_ones_are_named_and_still_invariable(self):
        """Une exemption qui ne correspond plus a rien exempte dans le vide."""
        for langue, cle in sorted(_INVARIABLES):
            with self.subTest(langue=langue, cle=cle):
                self.assertEqual(_rendu(cle, langue, 1),
                                 _rendu(cle, langue, 2),
                                 'this one now has two forms, so the '
                                 'exemption is stale')

    def test_zero_follows_each_language_and_not_english(self):
        for cle in _COMPTEURS:
            for langue in LANGUES:
                if (langue, cle) in _INVARIABLES:
                    continue
                with self.subTest(cle=cle, langue=langue):
                    zero = _rendu(cle, langue, 0)
                    attendu = _rendu(cle, langue,
                                     1 if _ZERO_EST_SINGULIER[langue] else 2)
                    self.assertEqual(attendu, zero)

    def test_every_language_answers_with_its_own_words(self):
        """Sans cela, un catalogue non compile laisserait l'anglais partout et
        les accords ci-dessus seraient vrais sur la mauvaise langue."""
        for cle in _COMPTEURS:
            vus = dict((langue, _rendu(cle, langue, 2)) for langue in LANGUES)
            for langue in ('fr', 'es', 'pt', 'de'):
                with self.subTest(cle=cle, langue=langue):
                    self.assertNotEqual(vus['en'], vus[langue])


class TheBannerCarriesTheIntegerBesideTheFormattedNumberTests(TestCase):

    def _stats(self):
        from django.core.cache import cache
        from chardata.context_processors import site_stats
        cache.delete('site_stats_v3')
        return site_stats(None)

    def test_the_counters_publish_the_integer_the_plural_needs(self):
        """Une chaine <<1,234>> ne peut pas choisir une forme de pluriel."""
        stats = self._stats()
        self.assertIsInstance(stats['stat_users_n'], int)
        self.assertIsInstance(stats['stat_users'], str)
        for entree in stats['stat_per_version']:
            for champ in ('characters', 'solver_runs', 'shared_builds'):
                self.assertIsInstance(entree['%s_n' % champ], int, champ)
                self.assertIsInstance(entree[champ], str, champ)

    def test_the_banner_uses_the_plural_form_for_each_counter(self):
        """Les quatre, pas seulement celui qui affichait un localement."""
        import os
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'chardata', 'sidebar-stats.html')
        with open(chemin, encoding='utf-8') as fichier:
            source = fichier.read()
        self.assertEqual(4, source.count('{% blocktrans count '))
        for singulier, pluriel in _COMPTEURS.values():
            self.assertIn('%s{%% plural %%}%s' % (singulier, pluriel), source)


class ThePageItselfSaysTheSingularTests(TestCase):

    def test_a_site_with_one_user_says_one_user(self):
        """De bout en bout: le bandeau est rendu sur une vraie page."""
        from django.contrib.auth.models import User
        from django.core.cache import cache
        User.objects.all().delete()
        User.objects.create_user('seul', 'seul@x.test', 'pw')
        cache.delete('site_stats_v3')
        attendu = {'en': '1</span> user', 'fr': '1</span> joueur',
                   'es': '1</span> jugador', 'pt': '1</span> jogador',
                   'de': '1</span> Spieler'}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                cache.delete('site_stats_v3')
                reponse = self.client.get(
                    '/support/', headers={'accept-language': langue},
                    follow=True)
                self.assertEqual(200, reponse.status_code, langue)
                corps = reponse.content.decode('utf-8')
                self.assertIn(attendu[langue], corps)
                # Et le pluriel ne doit pas trainer juste a cote.
                if langue != 'de':
                    self.assertNotIn(attendu[langue] + 's', corps)
