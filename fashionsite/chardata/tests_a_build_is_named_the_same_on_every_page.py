# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un build porte le meme nom de build sur toutes les pages.

Trouve en ouvrant la page qui sert a **choisir** entre deux builds,
`/choose_compare_sets/`, en francais. Elle rendait `char.char_build`, la
chaine interne:

    Cra 200        Cra . niveau 200 . Str
    NoName 200     Cra . niveau 30 .

Deux fautes dans la meme ligne: un jeton anglais interne la ou le reste du
site dit <<Force Equilibre>>, et un separateur pendant quand le champ est
vide. Mesure du 14 septembre 2026 sur les 85 builds locaux: **42 montraient
un jeton interne, 40 un separateur suivi de rien, 2 <<Int>>, 1 <<Str Glass
Cannon>>** -- soit les 85, dans les cinq langues, l'anglais compris ou
<<Str>> se lit <<Strength>>.

C'est la faute que la section 76 a corrigee sur l'en-tete de projet. Elle
avait parcouru l'en-tete, la liste des projets et la galerie; trois lecteurs
de plus repondaient encore a leur facon:

| char_build | en-tete, projets, galerie | profil et feed | choix a comparer |
|------------|---------------------------|----------------|------------------|
| `Str` | Force Equilibre | Force | **Str** |
| `''` | Equilibre | (rien) | **(rien)** |
| `Str Glass Cannon` | Force Canon de verre | Force Canon de verre | **Str Glass Cannon** |
| `Cha/Agi` | Chance/Agilite Equilibre | Chance/Agilite | **Cha/Agi** |

`model_wrappers.build_label` repond desormais pour les quatre, et
`translate_build_name` n'existe plus qu'une fois: `shared_builds_view` en
gardait une copie de 66 lignes, que `profile_view` importait.

**Ce qui n'est pas unifie, et pourquoi.** `solution_view` garde
`build_string() if char.char_build else ''` pour sa description de recherche:
un build sans aspect choisi n'a pas a peser le mot <<Equilibre>> dans une
meta description. Le libelle du lecteur et le jeton d'un moteur ne repondent
pas a la meme question.

**Une convention, pas une mesure.** `char_build` vide veut dire <<aucun
aspect choisi>>, et le site appelle cela <<Equilibre>> depuis toujours. Ce
lot met cette convention sur la quatrieme page au lieu d'un vide; il ne la
verifie pas contre le stuff, et rien ici ne pretend le contraire.
"""
import pickle
import re

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.model_wrappers import WrappedChar, build_label
from chardata.models import Char

#: Les valeurs que le generateur d'aspects produit vraiment, plus le vide.
SHAPES = ('', 'Str', 'Int', 'Cha/Agi', 'Str Glass Cannon',
          'Int Crit Glass Cannon', 'Vit')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


class TheLabelAnswersForEveryPageTests(SimpleTestCase):

    def test_the_label_is_never_empty(self):
        """Un vide laisse un separateur pendant derriere lui."""
        for language in LANGUAGES:
            with translation.override(language):
                for shape in SHAPES:
                    with self.subTest(language=language, shape=shape):
                        self.assertTrue(build_label(shape).strip(), shape)

    def test_the_project_header_reads_the_same_answer(self):
        char = Char(char_build='Str Glass Cannon')
        with translation.override('fr'):
            self.assertEqual(WrappedChar(char).build_string(),
                             build_label('Str Glass Cannon'))

    def test_a_build_with_a_focus_keeps_its_own_name(self):
        """<<Canon de verre>> se suffit: lui coller <<Equilibre>> dirait le
        contraire de ce que le joueur a choisi."""
        with translation.override('fr'):
            balanced = build_label('')
            self.assertNotIn(balanced, build_label('Str Glass Cannon'))
            self.assertIn(balanced, build_label('Str'))

    def test_no_internal_token_reaches_the_reader(self):
        for language in LANGUAGES:
            with translation.override(language):
                for shape in ('Str', 'Int', 'Cha/Agi'):
                    with self.subTest(language=language, shape=shape):
                        self.assertNotEqual(build_label(shape), shape)

    def test_each_language_says_it_in_its_own_words(self):
        seen = {}
        for language in LANGUAGES:
            with translation.override(language):
                seen[language] = build_label('Str')
        self.assertEqual(len(set(seen.values())), len(seen), seen)
        self.assertEqual('Force Équilibré', seen['fr'])
        self.assertEqual('Strength Balanced', seen['en'])
        self.assertEqual('Stärke Ausgewogen', seen['de'])


class OnlyOneModuleTranslatesABuildNameTests(SimpleTestCase):
    """Deux copies d'une meme regle, c'est ainsi que les pages ont derive."""

    def test_the_gallery_no_longer_keeps_its_own_copy(self):
        import chardata.model_wrappers as canonical
        import chardata.shared_builds_view as gallery
        self.assertIs(gallery.translate_build_name,
                      canonical.translate_build_name)

    def test_the_profile_reads_the_same_label(self):
        import chardata.model_wrappers as canonical
        import chardata.profile_view as profile
        self.assertIs(profile.build_label, canonical.build_label)

    def test_the_compare_picker_reads_the_same_label(self):
        import chardata.compare_sets_view as compare
        import chardata.model_wrappers as canonical
        self.assertIs(compare.build_label, canonical.build_label)


class TheComparePickerShowsTheReadersNameTests(TestCase):
    """Bout en bout, sur la page qui sert a choisir."""

    @staticmethod
    def _a_solution():
        """Le selecteur ne propose que des builds resolus, et c'est juste:
        on ne compare pas un projet vide."""
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        hats = [item for item in structure.get_items_list()
                if structure.get_type_name_by_id(item.type) == 'Hat'
                and not getattr(item, 'removed', False)]
        return pickle.dumps(ModelResultMinimal(
            {'hat': hats[0].id},
            {'options': {'ap_exo': False, 'mp_exo': False},
             'origin': 'generated', 'char_level': 200,
             'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0,
                                    'Strength': 0, 'Intelligence': 0,
                                    'Chance': 0, 'Agility': 0},
             'locked_equips': {}}, {}))

    def setUp(self):
        self.owner = User.objects.create_user(
            username='build-name-witness', email='b@test.local',
            password='pw-42-solid')
        self.client.force_login(self.owner)
        solution = self._a_solution()
        self.builds = {}
        for shape in ('Str', '', 'Str Glass Cannon'):
            self.builds[shape] = Char.objects.create(
                name='projet %r' % shape, char_name='temoin',
                char_class='Iop', char_build=shape, level=200,
                minimum_stats=b'', minimum_crits=b'',
                stats_weight=pickle.dumps({'vit': 1}), options=b'',
                inclusions=b'', exclusions=b'', owner=self.owner,
                game_version='dofus3', link_shared=False, deleted=False,
                minimal_solution=solution)

    def _page(self, language):
        path = '/choose_compare_sets/' if language == 'en' \
            else '/%s/choose_compare_sets/' % language
        answer = self.client.get(path)
        self.assertEqual(answer.status_code, 200, path)
        return answer.content.decode('utf-8', 'replace')

    def test_the_page_lists_the_builds_it_seeded(self):
        """Le plancher: une page vide rendrait les tests suivants vrais sans
        rien regarder.

        On compte la balise et pas la classe: le nom de classe revient une
        fois dans le script de la page, donc le compter donnerait toujours
        une carte de plus qu'il n'y en a.
        """
        html = self._page('fr')
        self.assertEqual(
            3, html.count('<label class="compare-build-choice-card">'))
        self.assertEqual(3, len(re.findall(
            r'<span class="compare-build-meta">', html)))

    def test_every_card_shows_the_label_the_rest_of_the_site_shows(self):
        for language in LANGUAGES:
            html = self._page(language)
            with translation.override(language):
                for shape in self.builds:
                    with self.subTest(language=language, shape=shape):
                        self.assertIn(build_label(shape), html)

    def test_no_card_ends_on_a_separator_with_nothing_after_it(self):
        import re
        for language in LANGUAGES:
            html = self._page(language)
            metas = re.findall(
                r'<span class="compare-build-meta">(.*?)</span>', html,
                re.S)
            self.assertTrue(metas, language)
            dangling = [meta for meta in metas
                        if meta.strip().endswith('&middot;')
                        or meta.strip().endswith('·')]
            self.assertEqual([], dangling, language)

    def test_no_card_ends_on_the_internal_string(self):
        """Le test qui aurait attrape le defaut.

        On regarde la fin du libelle et non la page entiere: le portugais
        traduit `glasscannon` par <<Glass Cannon>>, donc le terme anglais y
        est legitime et chercher son absence accuserait une traduction.
        """
        for language in LANGUAGES:
            html = self._page(language)
            metas = re.findall(
                r'<span class="compare-build-meta">(.*?)</span>', html, re.S)
            for shape in self.builds:
                if not shape:
                    continue
                with self.subTest(language=language, shape=shape):
                    raw = [meta for meta in metas
                           if meta.strip().endswith(shape)]
                    self.assertEqual([], raw, metas)

