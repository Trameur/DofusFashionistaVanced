# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un sort que le niveau n'atteint pas le dit, au lieu de se replier en silence.

Trouve en jouant: un Cra **Retro de niveau 30** cree depuis les propres pages
du site, jusqu'a sa page de degats. Onze de ses vingt et un sorts n'affichaient
rien. Le calcul etait juste (le serveur retenait bien les degats hors de
portee) mais le lecteur n'avait aucun moyen de distinguer trois causes:

- le sort ne fait pas de degats (Maitrise de l'Arc, Invocation de Dopeul);
- son personnage est trop bas (Fleche Destructrice, niveau 60);
- le calcul aurait echoue.

**Ce que le site en disait.** La phrase existait, deja traduite dans les cinq
langues, mais seulement dans un attribut `title` pose sur un rond de **douze
pixels a 30% d'opacite**, qu'aucun doigt ne declenche et qu'aucun lecteur de
la page ne voit.

**Combien de lecteurs.** Part des sorts entierement hors de portee, mesuree le
20 septembre 2026 sur les catalogues de chaque version:

| version | niveau 1 | 30 | 100 | 199 | 200 |
|---------|----------|----|-----|-----|-----|
| dofus3 | 86% | 76% | 44% | 2% | **0%** |
| dofus2 | 86% | 76% | 43% | 2% | **0%** |
| touch | 75% | 55% | 0% | 0% | **0%** |
| retro | 84% | 49% | 0% | 0% | **0%** |

Ce **zero a 200** est la raison pour laquelle le defaut a tenu: toutes les
fixtures du depot sont au niveau 200, ou le filtrage par niveau ne fait rien.
Voir [[feedback-fixtures-at-the-cap-hide-defects]].

**Une regle de moins en double.** `setVisible` recalculait
`char_level < spell.level[0]` en JavaScript alors que le serveur envoie deja
`available`. C'etait la derniere des trois copies: `decideLevel` et
`isOutOfReach` avaient deja rendu la leur, chacune apres s'etre ecartee du
serveur. Voir [[feedback-call-the-function-do-not-retype-it]].
"""

import io
import json
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.spells_view import _reach

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Le msgid de la phrase. Il existait avant ce lot, pose en infobulle.
_PHRASE = 'Needs level %(level)s'

#: Un sort Retro reel et son echelle, lus dans le module des degats le
#: 20 septembre 2026. Un personnage de 30 ne l'a pas; un de 60 l'a.
_DESTRUCTRICE = [60, 60, 60, 60, 60, 160]

#: La part des sorts entierement hors de portee, par version, a niveau 1 et
#: a 200. Le zero a 200 est ce qui explique que rien ne l'ait attrape.
_PART_HORS_DE_PORTEE = {
    'dofus3': (86, 0),
    'dofus2': (86, 0),
    'touch': (75, 0),
    'retro': (84, 0),
}


def _source(nom):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', nom)
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class TheSpellsPageSaysWhyItShowsNoDamageTests(SimpleTestCase):

    def test_the_header_carries_the_reason_next_to_the_spell_name(self):
        """Le test qui aurait attrape le defaut.

        La phrase doit etre dans l'en-tete, qui reste visible quand le bloc
        se replie, et non dans le contenu replie ni dans une infobulle.
        """
        source = _source('spells.html')
        self.assertIn("$(\"<div class='spell-out-of-reach'></div>\")", source)
        self.assertIn('outOfReachText(spell.level[0])', source)

    def test_the_reason_is_built_from_the_string_that_is_already_translated(
            self):
        """Une phrase neuve aurait demande cinq traductions et laisse deux
        formulations pour une meme chose."""
        source = _source('spells.html')
        self.assertIn('function outOfReachText(', source)
        self.assertIn("data('out-of-reach')", source)
        self.assertIn('data-out-of-reach=', source)

    def test_every_language_says_it_in_its_own_words(self):
        rendus = {}
        for langue in LANGUES:
            with translation.override(langue):
                rendus[langue] = gettext(_PHRASE) % {'level': 60}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertIn('60', rendus[langue])
        for langue in ('fr', 'es', 'pt', 'de'):
            with self.subTest(langue=langue):
                self.assertNotEqual(
                    rendus['en'], rendus[langue],
                    '%s falls back to English for the only sentence that '
                    'explains an empty row' % langue)

    def test_the_page_reads_the_servers_answer_instead_of_recomputing_it(self):
        """La regle de niveau n'a plus qu'une source.

        `decideLevel` et `isOutOfReach` avaient deja rendu la leur. Trois
        copies restaient, et je n'en avais d'abord vu qu'une: `setVisible`
        repliait le bloc, `checkIfSpellToDisplay` filtrait la liste et
        `fullyBuff` decidait quels buffs se lancent. L'assertion porte donc
        sur **tout** le gabarit, et non sur la fonction que je regardais.
        """
        source = _source('spells.html')
        debut = source.index('function setVisible(')
        self.assertIn('spell.available === false', source[debut:debut + 700])
        restes = re.findall(r'[^\n]*\{\{ *char_level *\}\}[^\n]*', source)
        self.assertEqual(
            [], restes,
            'the page compares the level itself again, so it can drift from '
            'the server as its three predecessors did: %s' % restes)


class WithoutTheGateThereWouldBeNothingToExplainTests(TestCase):
    """Les planchers. Sans eux, les tests ci-dessus garderaient une phrase
    que rien n'affiche jamais."""

    def test_a_spell_above_the_level_is_out_of_reach_and_one_below_is_not(
            self):
        trop_bas = _reach(_DESTRUCTRICE, 30)
        assez_haut = _reach(_DESTRUCTRICE, 60)
        self.assertFalse(trop_bas['available'])
        self.assertTrue(assez_haut['available'])

    def test_the_required_level_the_sentence_shows_is_the_games_own(self):
        """La phrase affiche `spell.level[0]`. Ce doit etre le niveau que le
        jeu demande, sinon elle rassure sur un chiffre invente."""
        self.assertEqual(60, _DESTRUCTRICE[0])
        self.assertFalse(_reach(_DESTRUCTRICE, _DESTRUCTRICE[0] - 1)['available'])
        self.assertTrue(_reach(_DESTRUCTRICE, _DESTRUCTRICE[0])['available'])

    def test_at_the_level_cap_no_spell_is_out_of_reach(self):
        """Pourquoi aucune fixture ne l'a jamais vu: elles sont toutes a 200.

        Si ce test tombait, c'est que le catalogue porte desormais un sort
        au-dessus de 200, et la mesure du module serait a refaire.
        """
        from chardata.spell_buffs import get_damage_spells_for_version
        for version in _PART_HORS_DE_PORTEE:
            with self.subTest(version=version):
                sorts = [sort for classe in
                         get_damage_spells_for_version(version).values()
                         for sort in classe]
                hors = [sort.name for sort in sorts
                        if not _reach(list(sort.level_req), 200)['available']]
                self.assertEqual([], hors)

    def test_a_low_level_reader_really_meets_a_lot_of_them(self):
        """La mesure qui justifie le lot. Si elle tombait a presque rien, la
        phrase ne vaudrait plus son emplacement."""
        from chardata.spell_buffs import get_damage_spells_for_version
        for version, (attendu_a_1, _) in _PART_HORS_DE_PORTEE.items():
            with self.subTest(version=version):
                sorts = [sort for classe in
                         get_damage_spells_for_version(version).values()
                         for sort in classe]
                hors = len([1 for sort in sorts
                            if not _reach(list(sort.level_req), 1)['available']])
                part = round(100.0 * hors / len(sorts))
                self.assertGreaterEqual(
                    part, attendu_a_1 - 5,
                    '%s showed %d%% of its spells out of reach at level 1 and '
                    'now shows %d%%' % (version, attendu_a_1, part))

    def test_the_shipped_page_carries_what_the_sentence_needs(self):
        """Sans ce test, le garde ne surveille que la source.

        La phrase est batie dans la page, a partir de deux choses que le
        serveur envoie: le drapeau `available` et le tableau `level`. Si le
        serveur cessait d'envoyer l'un des deux, la phrase disparaitrait de
        l'ecran sans qu'une seule assertion de source ne bouge.
        """
        from django.contrib.auth.models import User
        user = User.objects.create_user('hors-portee',
                                        'hors-portee@test.local', 'pw-1234')
        self.client.force_login(user)
        # Les noms de champ sont ceux que la vue lit vraiment: `charname`,
        # `level`, `class`. Les ecrire autrement ne rate pas, cela retombe
        # sur le niveau 200 par defaut, ou ce test ne mesurerait plus rien.
        cree = self.client.post('/retro/createproject/', {
            'charname': 'trente', 'class': 'Cra', 'level': '30',
            'project': 'trente', 'byhand': '1'})
        trouve = re.search(r'/(\d+)/', cree.headers.get('Location', ''))
        self.assertIsNotNone(trouve, 'could not create a level 30 Retro Cra')
        from chardata.models import Char
        self.assertEqual(
            30, Char.objects.get(id=int(trouve.group(1))).level,
            'the character came out at another level, so nothing below '
            'would be measuring the level gate')
        page = self.client.get('/retro/spells/%s/' % trouve.group(1),
                               follow=True)
        self.assertEqual(200, page.status_code)
        corps = page.content.decode('utf-8')
        self.assertIn('data-out-of-reach=', corps)
        digests = re.search(r'var spellDigests = (\[.*?\]);\n', corps, re.S)
        self.assertIsNotNone(digests, 'the page ships no spell digests')
        sorts = json.loads(digests.group(1))
        hors = [sort for sort in sorts if sort.get('available') is False]
        self.assertTrue(
            hors,
            'a level 30 Retro Cra reaches every one of its spells, so the '
            'sentence would never show: %d spells' % len(sorts))
        for sort in hors:
            with self.subTest(sort=sort.get('name')):
                self.assertIsInstance(
                    sort.get('level'), list,
                    'the sentence reads level[0]; this spell ships none')

    def test_the_comparison_page_still_gets_every_rank(self):
        """`char_level` a None veut dire <<l'appelant ne parle pas d'un
        niveau>>. La page de comparaison decide par colonne, et ne doit pas
        heriter du gate."""
        sans_niveau = _reach(_DESTRUCTRICE, None)
        self.assertTrue(sans_niveau['available'])
        self.assertEqual(len(_DESTRUCTRICE) - 1, sans_niveau['highest_level'])
