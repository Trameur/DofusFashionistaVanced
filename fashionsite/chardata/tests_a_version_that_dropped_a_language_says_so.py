# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une version qui ne fournit plus une langue le dit, au lieu de faire
passer l'anglais pour elle.

Trouve en lisant le panneau des sorts d'un Iop Touch en allemand. Chaque nom
etait anglais, et rien ne le disait: <<Afflux>> s'y lit <<Influx>>,
<<Aiguille>> s'y lit <<Hand>>.

**La cause est chez Ankama, et le depot la lit deja.** Le 8 septembre 2026, le
`config.json` des serveurs Touch a repondu `serverLanguages
["en", "es", "fr", "pt"]`, sans allemand; `itemscraper/download_touch_data.py`
lit cette liste avant chaque rafraichissement et refuse depuis de redemander
l'allemand. Les noms en base sont donc ceux du dernier passage qui a reussi,
c'est-a-dire l'anglais.

**Mesure du 14 septembre 2026 sur les tables generees:**

| version | noms de sorts | dont l'allemand vaut l'anglais |
|---------|---------------|--------------------------------|
| touch | 174 | **174** |
| retro | 106 | 4 |

Les quatre de Retro sont des mots identiques dans les deux langues
(<<Absorption>>), pas une absence: c'est ce qui autorise a nommer la regle
par <<tous>> et non par un seuil.

**Ce que ce lot ne fait pas.** Il ne traduit rien: personne ici ne peut
inventer les noms allemands d'Ankama, et les fabriquer serait pire que
l'anglais. Il dit au lecteur ce qu'il a sous les yeux, et la phrase
disparaitra d'elle-meme le jour ou Ankama resservira l'allemand, puisque la
condition est calculee sur les donnees et non ecrite a la main.
"""
from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.spells_view import (_languages_left_english, _names_are_english)

PHRASE = ('This game version no longer provides spell names in your language, '
          'so they are shown in English.')

LANGUES = ('en', 'fr', 'es', 'pt', 'de')


class AVersionThatDroppedALanguageSaysSoTests(SimpleTestCase):

    def test_touch_no_longer_names_a_spell_in_german(self):
        from fashionistapulp.dofus_constants_touch_spells import (
            TOUCH_SPELL_NAMES)
        noms = list(TOUCH_SPELL_NAMES.values())
        self.assertEqual(174, len(noms), len(noms))
        anglais = [par_langue for par_langue in noms
                   if par_langue.get('de') == par_langue.get('en')]
        self.assertEqual(len(noms), len(anglais),
                         '%d of %d Touch spells still carry a German name'
                         % (len(noms) - len(anglais), len(noms)))
        self.assertEqual({'de'}, _languages_left_english('touch'))

    def test_retro_still_names_its_spells_in_german(self):
        """Le temoin de l'autre cote: quatre noms identiques ne sont pas une
        absence, et Retro ne doit donc rien annoncer."""
        from fashionistapulp.dofus_constants_retro_spells import (
            RETRO_SPELL_NAMES)
        noms = list(RETRO_SPELL_NAMES.values())
        identiques = [par_langue for par_langue in noms
                      if par_langue.get('de') == par_langue.get('en')]
        self.assertEqual(4, len(identiques), len(identiques))
        self.assertGreater(len(noms), 100, len(noms))
        self.assertEqual(set(), _languages_left_english('retro'))
        self.assertEqual(set(), _languages_left_english('dofus3'))

    def test_only_the_reader_who_sees_english_is_told(self):
        for version, langue, attendu in (
                ('touch', 'de', True),
                ('touch', 'fr', False),
                ('touch', 'en', False),
                ('dofus3', 'de', False),
                ('retro', 'de', False)):
            with self.subTest(version=version, langue=langue):
                with translation.override(langue):
                    self.assertEqual(attendu, _names_are_english(version))

    def test_the_sentence_reads_in_five_languages(self):
        """Lue par gettext, donc dans le catalogue compile."""
        rendus = {}
        for langue in LANGUES:
            with translation.override(langue):
                rendus[langue] = gettext(PHRASE)
        self.assertEqual(PHRASE, rendus['en'])
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertTrue(rendus[langue])
                if langue != 'en':
                    self.assertNotEqual(PHRASE, rendus[langue],
                                        'still untranslated')
        self.assertEqual(len(set(rendus.values())), len(LANGUES),
                         'two languages read the same sentence')


class TheTouchPageCarriesTheSentenceTests(TestCase):
    """Ce que le lecteur voit vraiment, rendu par la page."""

    def _char(self):
        """Un build Touch avec un stuff, par la porte d'import du site: la
        page des sorts renvoie ailleurs tant qu'il n'y a pas de solution."""
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        from chardata.models import Char
        set_current_game_version('touch')
        structure = get_structure('touch')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/touch/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Iop', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def test_the_german_reader_is_told_and_the_french_one_is_not(self):
        char = self._char()
        allemand = self.client.get('/de/touch/spells/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE='de')
        self.assertEqual(200, allemand.status_code)
        page = allemand.content.decode('utf-8')
        self.assertIn('nicht mehr in Ihrer Sprache', page)

        francais = self.client.get('/fr/touch/spells/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(200, francais.status_code)
        self.assertNotIn('plus les noms de sorts',
                         francais.content.decode('utf-8'))
