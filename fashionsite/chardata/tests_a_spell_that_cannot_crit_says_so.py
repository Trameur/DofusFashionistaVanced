# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell that cannot crit says so."""

from django.test import SimpleTestCase, TestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

_SANS_CRITIQUE = {'dofus3': 55, 'beta': 56, 'dofus2': 52, 'touch': 0,
                  'retro': 0}

_PHRASES = {
    'en': ('No critical hit', 'This spell never lands one.'),
    'fr': ('Pas de coup critique', "Ce sort n'en fait jamais."),
    'es': ('Sin golpe crítico', 'Este hechizo nunca lo consigue.'),
    'pt': ('Sem golpe crítico', 'Este feitiço nunca o consegue.'),
    'de': ('Kein kritischer Treffer', 'Dieser Zauber landet nie einen.'),
}


def _lignes(valeur):
    if not valeur:
        return 0
    return sum(len(niveau or []) for niveau in valeur)


def _etat_des_sorts(version):
    from chardata.spell_combo import castable_spells
    from chardata.version_compat import filter_classes_for_version
    from fashionistapulp.dofus_constants import CHARACTER_CLASSES
    from fashionistapulp.structure import set_current_game_version

    set_current_game_version(version)
    vus, sans, sans_ni_taux, inverse = 0, 0, 0, []
    noms = set()
    for classe in filter_classes_for_version(CHARACTER_CLASSES, version):
        for castable in castable_spells(classe, 200, version):
            if not getattr(castable, 'is_spell', True):
                continue
            if castable.name in noms:
                continue
            noms.add(castable.name)
            spell = getattr(castable, 'spell', None)
            if spell is None:
                continue
            digest = spell.get_effects_digest()
            if digest is None:
                continue
            vus += 1
            normal = _lignes(digest.non_crit_dams)
            crit = _lignes(digest.crit_dams)
            if normal and not crit:
                sans += 1
                if not (getattr(castable, 'crit_rate', 0) or 0):
                    sans_ni_taux += 1
            if crit and not normal:
                inverse.append(castable.name)
    return vus, sans, sans_ni_taux, inverse


class TheGameSaysTwiceThatTheseSpellsCannotCritTests(SimpleTestCase):

    def test_each_version_has_the_measured_number(self):
        compte = {}
        for version in VERSIONS:
            vus, sans, _sans_ni_taux, _inverse = _etat_des_sorts(version)
            self.assertGreater(vus, 100, version)
            compte[version] = sans
        self.assertEqual(_SANS_CRITIQUE, compte)

    def test_none_of_them_carries_a_critical_rate_either(self):
        ecarts = []
        for version in VERSIONS:
            _vus, sans, sans_ni_taux, _inverse = _etat_des_sorts(version)
            if sans != sans_ni_taux:
                ecarts.append((version, sans, sans_ni_taux))
        self.assertFalse(
            ecarts,
            'these spells have no critical rows but do carry a critical rate, '
            'so saying they never land one would be a guess: %s' % ecarts)

    def test_no_spell_has_a_critical_block_without_a_normal_one(self):
        trouves = []
        for version in VERSIONS:
            _vus, _sans, _ni, inverse = _etat_des_sorts(version)
            trouves.extend((version, nom) for nom in inverse)
        self.assertFalse(trouves, 'these would print an empty normal block: %s'
                         % trouves[:6])

    def test_touch_and_retro_are_not_concerned(self):
        for version in ('touch', 'retro'):
            with self.subTest(version=version):
                _vus, sans, _ni, _inverse = _etat_des_sorts(version)
                self.assertEqual(0, sans)


class TheCardSaysItRatherThanLeavingTheLabelEmptyTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _build(self):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Amulet'):
            item = next((i for i in structure.types[200].get(type_name, [])
                         if not i.removed and i.ankama_id), None)
            if item is not None:
                noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _gabarit(self):
        import os
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'chardata', 'spells.html')
        with open(chemin, encoding='utf-8') as fichier:
            return fichier.read()

    def test_the_heading_is_no_longer_printed_whatever_happens(self):
        source = self._gabarit()
        self.assertIn('var can_crit = !!spell.crit_dams;', source)
        self.assertIn("hit-block-label no-crit", source)
        self.assertEqual(
            1, source.count("+ \"{% trans 'Critical hit' %}</div>\");"),
            'the critical heading is appended somewhere else again')

    def test_the_reader_gets_both_sentences_in_five_languages(self):
        char = self._build()
        manquants = []
        for langue in LANGUES:
            reponse = self.client.get('/spells/%d/' % char.id,
                                      headers={'accept-language': langue},
                                      follow=True)
            self.assertEqual(200, reponse.status_code, langue)
            corps = reponse.content.decode('utf-8')
            for phrase in _PHRASES[langue]:
                if phrase not in corps:
                    manquants.append((langue, phrase))
        self.assertFalse(
            manquants,
            'the catalogue compiled but these never reached the page: %s'
            % manquants)

    def test_the_five_languages_do_not_all_answer_in_english(self):
        titres = set(paire[0] for paire in _PHRASES.values())
        notes = set(paire[1] for paire in _PHRASES.values())
        self.assertEqual(5, len(titres))
        self.assertEqual(5, len(notes))
