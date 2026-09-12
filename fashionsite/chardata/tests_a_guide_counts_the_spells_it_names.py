# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Les comptes de sorts d'un guide sont mesures, plus recopies.

Le guide <<best turn damage>> annoncait deux nombres ecrits en dur, et les
deux avaient vieilli. Mesure du 12 septembre 2026 avec la fonction que le
panneau lui-meme utilise, `castable_spells` au niveau 200:

| guide   | annonce | reel |
|---------|--------:|-----:|
| Dofus 2 |      16 |  **31** |
| Retro   |      12 |  **15** |

Les tables de sorts sont regenerees et le texte ne suivait pas: Dofus 2 a recu
ses rangs, Retro a ete re-scrape. Les nombres passent donc derriere un jeton,
`[[spells:Iop]]` pour la version de la page et `[[spells:Iop:dofus3]]` pour une
version nommee, resolus au rendu par la meme fonction que le panneau. Un guide
ne peut plus annoncer un nombre que la page dement.

**La substitution seule aurait rendu le guide Dofus 2 creux.** Sa phrase
opposait 16 a 31; avec la mesure elle aurait dit <<31 contre 31>>. Elle dit
maintenant ce qui separe vraiment les deux jeux, et que le guide affirme deja
plus bas: ce ne sont pas les memes sorts. Sur les dix-huit classes communes,
sept ont une liste identique et **137 noms de sorts different** en tout.

Les nombres du guide voisin, <<lock and dodge>>, ont ete verifies dans le meme
mouvement et sont **tous encore exacts** (549 et 606 objets sur Dofus 3, 476 et
520 sur Dofus 2, 339 et 453 sur Touch, aucun sur Retro). Ce ne sont donc pas
les guides qui derivent, mais les comptes de sorts, et c'est pour cela que
seuls ceux-la passent derriere un jeton.

Cout mesure: 9,1 ms au premier comptage, 0,74 ms ensuite, et une page de guide
en resout deux au plus.
"""

import re

from django.test import SimpleTestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

JETON = re.compile(r'\[\[spells:')


def _compte(char_class, version):
    from chardata.spell_combo import castable_spells
    from fashionistapulp.structure import set_current_game_version
    set_current_game_version(version)
    return len(castable_spells(char_class, 200, version))


class TheTokenResolvesTests(SimpleTestCase):

    def test_it_answers_the_count_the_panel_would_use(self):
        from chardata.guides_content import _fill_measured_numbers
        for version in ('dofus3', 'dofus2', 'retro', 'touch', 'beta'):
            with self.subTest(version=version):
                attendu = str(_compte('Iop', version))
                self.assertEqual(
                    attendu, _fill_measured_numbers('[[spells:Iop]]', version))

    def test_a_named_version_wins_over_the_page_version(self):
        from chardata.guides_content import _fill_measured_numbers
        attendu = str(_compte('Iop', 'dofus3'))
        self.assertEqual(
            attendu, _fill_measured_numbers('[[spells:Iop:dofus3]]', 'retro'))

    def test_an_unknown_class_leaves_no_token_behind(self):
        """Un jeton non resolu s'afficherait tel quel au lecteur."""
        from chardata.guides_content import _fill_measured_numbers
        rendu = _fill_measured_numbers('[[spells:Nexistepas]]', 'dofus3')
        self.assertNotIn('[[', rendu)

    def test_text_without_a_token_is_untouched(self):
        from chardata.guides_content import _fill_measured_numbers
        texte = '<p>Rien a remplacer ici, 16 et 31 compris.</p>'
        self.assertEqual(texte, _fill_measured_numbers(texte, 'dofus2'))


class TheGuideSaysTheMeasuredNumberTests(SimpleTestCase):

    def _corps(self, version, langue):
        from chardata.guides_content import get_guide
        guide = get_guide('best-turn-damage', langue, version)
        self.assertIsNotNone(guide)
        return re.sub(r'\s+', ' ',
                      re.sub(r'<[^>]+>', ' ', guide['body']))

    def test_no_guide_ships_an_unresolved_token(self):
        """Sur tous les guides et toutes les langues, pas seulement celui-ci."""
        from chardata.guides_content import get_guide, ordered_slugs
        from fashionistapulp.game_versions import version_keys
        vus = 0
        for slug in ordered_slugs():
            for version in version_keys():
                for langue in LANGUES:
                    guide = get_guide(slug, langue, version)
                    if guide is None:
                        continue
                    vus += 1
                    with self.subTest(slug=slug, version=version,
                                      langue=langue):
                        self.assertFalse(JETON.search(guide['body']))
        self.assertGreater(vus, 100, 'trop peu de guides rendus')

    def test_the_retro_guide_says_what_a_retro_iop_really_reads(self):
        attendu = str(_compte('Iop', 'retro'))
        autre = str(_compte('Iop', 'dofus3'))
        self.assertNotEqual(attendu, autre,
                            'sans cet ecart le guide ne dirait rien')
        from chardata.guides_content import GUIDES
        blocs = GUIDES['best-turn-damage']['i18n_by_group']['retro']
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertIn('[[spells:Iop]]', blocs[langue]['body'])
                corps = self._corps('retro', langue)
                self.assertIn(attendu, corps)
                self.assertIn(autre, corps)

    def test_the_dofus2_guide_says_what_a_dofus2_iop_really_reads(self):
        """La version rendue porte la mesure, et la version STOCKEE porte le
        jeton et non un nombre: l'ancienne phrase contenait deja <<31>> pour
        parler de Dofus 3, donc verifier le rendu seul ne garderait rien."""
        from chardata.guides_content import GUIDES
        attendu = str(_compte('Iop', 'dofus2'))
        blocs = GUIDES['best-turn-damage']['i18n_by_group']['dofus2']
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertIn('[[spells:Iop]]', blocs[langue]['body'])
                self.assertIn(attendu, self._corps('dofus2', langue))

    def test_no_guide_keeps_the_two_stale_numbers(self):
        """16 sorts sur Dofus 2 et 12 sur Retro: les deux chiffres que la
        mesure a dementis. S'ils reviennent, c'est qu'on a reecrit en dur."""
        for version, perime in (('dofus2', '16'), ('retro', '12')):
            for langue in LANGUES:
                with self.subTest(version=version, langue=langue):
                    corps = self._corps(version, langue)
                    motif = re.compile(
                        r'\b%s\b\s*(?:usable|sorts|hechizos|feiti|nutzbare)'
                        % perime, re.I)
                    self.assertIsNone(motif.search(corps), corps[:200])


class TheDofus2SentenceStaysMeaningfulTests(SimpleTestCase):

    def test_it_no_longer_opposes_two_equal_numbers(self):
        """Substituer le nombre sans toucher a la phrase aurait donne
        <<31 contre 31>>, une opposition vide."""
        from chardata.guides_content import get_guide
        self.assertEqual(_compte('Iop', 'dofus2'), _compte('Iop', 'dofus3'),
                         'les deux comptes ont diverge, relire la phrase')
        corps = re.sub(r'\s+', ' ', re.sub(
            r'<[^>]+>', ' ', get_guide('best-turn-damage', 'en', 'dofus2')['body']))
        self.assertIn('as many as on Dofus 3 but not the same ones', corps)
        self.assertIn('137 spell names differ', corps)

    def test_the_hundred_and_thirty_seven_is_still_what_the_tables_say(self):
        """Le seul nombre reste ecrit en dur dans cette phrase. Mesure du 12
        septembre 2026; s'il bouge, ce test le dit."""
        from chardata.spell_buffs import get_damage_spells_for_version
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        from fashionistapulp.structure import set_current_game_version
        tables = {}
        for version in ('dofus3', 'dofus2'):
            set_current_game_version(version)
            par_classe = get_damage_spells_for_version(version)
            tables[version] = {
                classe: {spell.name for spell in par_classe.get(classe, [])}
                for classe in filter_classes_for_version(CHARACTER_CLASSES,
                                                         version)}
        communes = set(tables['dofus2']) & set(tables['dofus3'])
        self.assertEqual(18, len(communes))
        differents = sum(len(tables['dofus3'][c] ^ tables['dofus2'][c])
                         for c in communes)
        self.assertEqual(137, differents)
