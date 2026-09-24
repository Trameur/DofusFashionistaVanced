# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Critical failure exists only in Retro item data; the panel names it instead of estimating its effect."""

import json
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

PHRASE = ('Critical failure is not counted; this version is the only one '
          'that has it.')

NOTE = re.compile(
    r'<span[^>]*best-combo-crit-failure-note[^>]*>(.*?)</span>', re.S)
LIGNE_BUILD = re.compile(r'<tr[^>]*solution-best-turn-row[^>]*>(.*?)</tr>',
                         re.S)
NOTE_COMPARE = re.compile(r'<td[^>]*compare-best-turn-note[^>]*>(.*?)</td>',
                          re.S)
TITRE = re.compile(r'title="([^"]*)"')


def _texte(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


class OnlyRetroHasTheMechanicTests(SimpleTestCase):

    def test_no_item_of_any_version_sells_critical_failure(self):
        """Not shown or optimized anywhere; only the weapon and the spell carry it in game data."""
        from fashionistapulp.game_versions import version_keys
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        for version in version_keys():
            with self.subTest(version=version):
                set_current_game_version(version)
                structure = get_structure(version)
                self.assertIn('cf', structure.stat_dict_key,
                              'the stat disappeared from the catalogue')
                sid = structure.stat_dict_key['cf'].id
                porteurs = 0
                vus = set()
                for items in structure.types[200].values():
                    for item in items:
                        if item.id in vus:
                            continue
                        vus.add(item.id)
                        if any(x == sid and v for x, v in (item.stats or [])):
                            porteurs += 1
                self.assertEqual(0, porteurs)

    def test_the_retro_reader_names_the_field_and_the_modern_one_does_not(self):
        """If the modern reader ever picks up a critical failure field, this test must be revisited."""
        import os

        racine = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        retro = os.path.join(racine, 'itemscraper', 'get_equipments_retro.py')
        moderne = os.path.join(racine, 'itemscraper', 'get_equipments2.py')
        with open(retro, encoding='utf-8') as fichier:
            source_retro = fichier.read()
        with open(moderne, encoding='utf-8') as fichier:
            source_moderne = fichier.read()
        self.assertIn('crit_failure', source_retro)
        self.assertNotIn('crit_failure', source_moderne)
        self.assertIn('critical_hit_probability', source_moderne)


class TheNoteIsRetroOnlyTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _build(self, version):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version(version)
        structure = get_structure(version)
        noms = []
        for type_name in ('Hat', 'Amulet'):
            item = next((i for i in structure.types[200].get(type_name, [])
                         if not i.removed and i.ankama_id), None)
            if item is not None:
                noms.append(structure.get_item_name_in_language(item, 'en'))
        prefixe = '' if version == 'dofus3' else version + '/'
        self.client.post('/%simport/text/' % prefixe, {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char, prefixe

    def _note(self, char, prefixe, langue='en'):
        page = self.client.get('/%sspells/%d/' % (prefixe, char.id),
                               HTTP_ACCEPT_LANGUAGE=langue,
                               follow=True).content.decode('utf-8')
        trouve = NOTE.search(page)
        return _texte(trouve.group(1)) if trouve else None

    def test_retro_is_told(self):
        char, prefixe = self._build('retro')
        self.assertEqual(gettext(PHRASE), self._note(char, prefixe))

    def test_the_four_other_versions_are_not_bothered(self):
        """The mechanic doesn't exist there; the note would be wrong."""
        from fashionistapulp.game_versions import version_keys
        vues = 0
        for version in version_keys():
            if version == 'retro':
                continue
            with self.subTest(version=version):
                char, prefixe = self._build(version)
                vues += 1
                self.assertEqual('', self._note(char, prefixe) or '')
        self.assertGreater(vues, 2, 'trop peu de versions verifiees')

    def test_the_five_languages_answer(self):
        char, prefixe = self._build('retro')
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    attendu = gettext(PHRASE)
                self.assertEqual(attendu, self._note(char, prefixe, langue))
                vus[langue] = attendu
        for langue, phrase in vus.items():
            if langue != 'en':
                self.assertNotEqual(vus['en'], phrase, langue)

    def test_the_ajax_answer_carries_it(self):
        char, prefixe = self._build('retro')
        reponse = self.client.post('/%sbest_combo/%d/' % (prefixe, char.id), {
            'buff_state': json.dumps({}), 'spell_levels': json.dumps({}),
            'pushback': 'false'})
        self.assertEqual(200, reponse.status_code)
        combo = json.loads(reponse.content.decode('utf-8'))['best_combo']
        self.assertEqual(gettext(PHRASE), combo['crit_failure_note'])

    def test_the_build_page_and_the_comparison_repeat_it(self):
        """Three pages announcing the same number must state the same assumptions."""
        char, prefixe = self._build('retro')
        autre, _p = self._build('retro')
        attendu = gettext(PHRASE)

        build = self.client.get('/%ssolution/%d/' % (prefixe, char.id),
                                follow=True).content.decode('utf-8')
        ligne = LIGNE_BUILD.search(build)
        self.assertIsNotNone(ligne, 'no best-turn row')
        titre = TITRE.search(ligne.group(1))
        self.assertIsNotNone(titre)
        self.assertIn(attendu, titre.group(1))

        compare = self.client.get(
            '/%scompare_sets/%d/%d/' % (prefixe, char.id, autre.id),
            follow=True).content.decode('utf-8')
        note = NOTE_COMPARE.search(compare)
        self.assertIsNotNone(note)
        self.assertIn(attendu, _texte(note.group(1)))
