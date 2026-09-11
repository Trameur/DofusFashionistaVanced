# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page d'une panoplie mene au solveur, chaque piece verrouillee.

Suite de la section 28: la fiche d'objet menait au demarrage rapide, la
page d'une panoplie non, alors qu'un joueur pense souvent en panoplie
(<<je veux la Bouftou>>). La page envoie son identifiant au demarrage
rapide de la meme version, qui verrouille chaque piece dans son
emplacement, deux bagues dans ring1 et ring2, et commence ses niveaux a la
piece la plus haute.
"""

import re

from django.test import SimpleTestCase, TestCase

from chardata.coaching_view import (DEFAULT_LEVELS, included_item_for,
                                    included_set_for)
from chardata.encyclopedia_view import LOCALIZED_UI
from chardata.lock_forbid import get_inclusions_dict
from chardata.models import Char

PHRASE = ('This build will keep the %(count_pieces)s pieces of %(set)s (level '
          '%(level)s): the solver fills the other slots around them.')


def _panoplies(version):
    from fashionistapulp.structure import get_structure
    structure = get_structure(version)
    for item_set in structure.get_sets_list():
        pieces = included_set_for(version, item_set.id, language='en')
        if pieces is not None and pieces['count'] >= 3 and pieces['level'] <= 200:
            yield structure, item_set, pieces


def _panoplie(version):
    return next(_panoplies(version))


def _panoplie_a_deux_bagues(version):
    for structure, item_set, pieces in _panoplies(version):
        slots = {p['slot'] for p in pieces['pieces']}
        if {'ring1', 'ring2'} <= slots:
            return structure, item_set, pieces
    raise AssertionError('no set with two rings on %s' % version)


def _page(client, version, item_set, pieces):
    from chardata.encyclopedia_view import get_set_link
    lien = get_set_link(item_set.id, pieces['name'], game_version=version)
    lien = re.sub(r'^https?://[^/]+', '', lien)
    reponse = client.get(lien, HTTP_ACCEPT_LANGUAGE='en', follow=True)
    assert reponse.status_code == 200, (lien, reponse.status_code)
    return reponse.content.decode('utf-8')


def _ancre(page):
    debut = page.find('encyclopedia-build-around-set')
    assert debut != -1, 'no build-around link on the set page'
    return page[page.rfind('<a', 0, debut):page.find('</a>', debut)]


class TheSetPageLinksToTheQuickStartTests(TestCase):

    def test_the_link_carries_the_set_to_the_same_version(self):
        structure, item_set, pieces = _panoplie('dofus3')
        ancre = _ancre(_page(self.client, 'dofus3', item_set, pieces))
        self.assertIn('href="/quickstart/?set=%d"' % item_set.id, ancre)
        self.assertIn(LOCALIZED_UI['en']['build_around_set_label'], ancre)

    def test_a_touch_set_page_keeps_the_reader_on_touch(self):
        structure, item_set, pieces = _panoplie('touch')
        ancre = _ancre(_page(self.client, 'touch', item_set, pieces))
        self.assertIn('href="/touch/quickstart/?set=%d"' % item_set.id, ancre)

    def test_the_label_exists_in_five_languages(self):
        phrases = {LOCALIZED_UI[l]['build_around_set_label']
                   for l in ('en', 'fr', 'es', 'pt', 'de')}
        self.assertEqual(5, len(phrases))


class TheQuickStartKeepsTheWholeSetTests(TestCase):

    def test_the_form_names_the_set_and_starts_at_its_highest_piece(self):
        structure, item_set, pieces = _panoplie('dofus3')
        page = self.client.get('/quickstart/', {'set': item_set.id},
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn('coaching-included-set', page)
        self.assertIn(pieces['name'], page)
        self.assertIn('the %d pieces of' % pieces['count'], page)
        self.assertRegex(page, r'<input[^>]*name="?set"?[^>]*value="?%d"?'
                         % item_set.id)
        niveaux = [int(v) for v in re.findall(
            r'<option[^>]*value="?(\d+)"?[^>]*>\d+</option>', page)]
        self.assertTrue(all(lvl >= pieces['level'] for lvl in niveaux), niveaux)
        self.assertIn(pieces['level'], niveaux)

    def test_submitting_locks_every_piece_in_its_own_slot(self):
        structure, item_set, pieces = _panoplie_a_deux_bagues('dofus3')
        reponse = self.client.post('/quickstart/', {
            'char_class': 'Cra', 'char_level': '200',
            'play_style': 'solo_pvm', 'set': str(item_set.id)})
        self.assertEqual(302, reponse.status_code)
        char = Char.objects.order_by('-id').first()
        attendu = {p['slot']: p['id'] for p in pieces['pieces']}
        self.assertEqual(attendu, get_inclusions_dict(char))
        self.assertIn('ring1', attendu)
        self.assertIn('ring2', attendu)
        self.assertNotEqual(attendu['ring1'], attendu['ring2'])
        self.assertEqual(len(attendu), len(set(attendu.values())))

    def test_a_level_posted_below_the_set_keeps_only_what_fits(self):
        # Une panoplie dont les pieces n'ont pas toutes le meme niveau: la
        # premiere venue en partage un seul, et un test saute n'a rien
        # prouve.
        for structure, item_set, pieces in _panoplies('dofus3'):
            bas = min(p['level'] for p in pieces['pieces'])
            haut = pieces['level']
            if bas < haut:
                break
        else:
            raise AssertionError('no dofus3 set with pieces of different levels')
        self.client.post('/quickstart/', {
            'char_class': 'Cra', 'char_level': str(bas),
            'play_style': 'solo_pvm', 'set': str(item_set.id)})
        char = Char.objects.order_by('-id').first()
        verrouilles = set(get_inclusions_dict(char).values())
        for p in pieces['pieces']:
            self.assertEqual(p['level'] <= bas, p['id'] in verrouilles, p)

    def test_the_item_wins_when_both_are_given(self):
        structure, item_set, pieces = _panoplie('dofus3')
        objet = next(i for i in structure.get_items_list()
                     if structure.get_type_name_by_id(i.type) == 'Hat'
                     and not getattr(i, 'removed', False) and i.level <= 200)
        page = self.client.get('/quickstart/', {'set': item_set.id, 'item': objet.id},
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn('coaching-included-item', page)
        self.assertNotIn('coaching-included-set', page)
        self.client.post('/quickstart/', {
            'char_class': 'Cra', 'char_level': '200', 'play_style': 'solo_pvm',
            'set': str(item_set.id), 'item': str(objet.id)})
        char = Char.objects.order_by('-id').first()
        self.assertEqual({'hat': objet.id}, get_inclusions_dict(char))

    def test_a_bogus_set_changes_nothing(self):
        for valeur in ('abc', '999999999', ''):
            page = self.client.get('/quickstart/', {'set': valeur},
                                   HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
            self.assertNotIn('coaching-included-set', page, valeur)
            niveaux = [int(v) for v in re.findall(
                r'<option[^>]*value="?(\d+)"?[^>]*>\d+</option>', page)]
            self.assertEqual(DEFAULT_LEVELS, niveaux, valeur)


class TheHelperReadsASetOfThisVersionTests(SimpleTestCase):

    def test_none_for_junk(self):
        self.assertIsNone(included_set_for('dofus3', None))
        self.assertIsNone(included_set_for('dofus3', 'x'))
        self.assertIsNone(included_set_for('dofus3', -1))

    def test_pieces_take_distinct_slots_and_the_name_follows_the_language(self):
        structure, item_set, pieces = _panoplie_a_deux_bagues('dofus3')
        slots = [p['slot'] for p in pieces['pieces']]
        self.assertEqual(len(slots), len(set(slots)))
        en_francais = included_set_for('dofus3', item_set.id, language='fr')
        self.assertEqual(item_set.localized_names.get('fr'), en_francais['name'])
        self.assertEqual(pieces['level'], max(p['level'] for p in pieces['pieces']))

    def test_the_item_helper_is_untouched(self):
        structure, item_set, pieces = _panoplie('dofus3')
        premiere = pieces['pieces'][0]
        seule = included_item_for('dofus3', premiere['id'], language='en')
        self.assertEqual(premiere['id'], seule['id'])


class TheSentenceIsInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations(self):
        import gettext
        import os
        from django.conf import settings
        vues = set()
        for langue in ('fr', 'es', 'pt', 'de'):
            phrase = gettext.translation(
                'django', os.path.join(settings.BASE_DIR, 'locale'),
                languages=[langue]).gettext(PHRASE)
            self.assertNotEqual(PHRASE, phrase, langue)
            for champ in ('%(count_pieces)s', '%(set)s', '%(level)s'):
                self.assertIn(champ, phrase, (langue, champ))
            vues.add(phrase)
        self.assertEqual(4, len(vues))
