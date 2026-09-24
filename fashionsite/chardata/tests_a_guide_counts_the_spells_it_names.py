# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Spell counts in a guide are computed, not written by hand."""

import re

from django.test import SimpleTestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

JETON = re.compile(r'\[\[')


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
        from chardata.guides_content import _fill_measured_numbers
        rendu = _fill_measured_numbers('[[spells:Nexistepas]]', 'dofus3')
        self.assertNotIn('[[', rendu)

    def test_text_without_a_token_is_untouched(self):
        from chardata.guides_content import _fill_measured_numbers
        texte = '<p>Nothing to replace here, 16 and 31 included.</p>'
        self.assertEqual(texte, _fill_measured_numbers(texte, 'dofus2'))


class TheGuideSaysTheMeasuredNumberTests(SimpleTestCase):

    def _corps(self, version, langue):
        from chardata.guides_content import get_guide
        guide = get_guide('best-turn-damage', langue, version)
        self.assertIsNotNone(guide)
        return re.sub(r'\s+', ' ',
                      re.sub(r'<[^>]+>', ' ', guide['body']))

    def test_no_guide_ships_an_unresolved_token(self):
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
                            'without this gap the guide would say nothing')
        from chardata.guides_content import GUIDES
        blocs = GUIDES['best-turn-damage']['i18n_by_group']['retro']
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertIn('[[spells:Iop]]', blocs[langue]['body'])
                corps = self._corps('retro', langue)
                self.assertIn(attendu, corps)
                self.assertIn(autre, corps)

    def test_the_dofus2_guide_says_what_a_dofus2_iop_really_reads(self):
        from chardata.guides_content import GUIDES
        attendu = str(_compte('Iop', 'dofus2'))
        blocs = GUIDES['best-turn-damage']['i18n_by_group']['dofus2']
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertIn('[[spells:Iop]]', blocs[langue]['body'])
                self.assertIn(attendu, self._corps('dofus2', langue))

    def test_no_guide_keeps_the_two_stale_numbers(self):
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
        from chardata.guides_content import get_guide
        self.assertEqual(_compte('Iop', 'dofus2'), _compte('Iop', 'dofus3'),
                         'the two counts diverged, reread the sentence')
        corps = re.sub(r'\s+', ' ', re.sub(
            r'<[^>]+>', ' ', get_guide('best-turn-damage', 'en', 'dofus2')['body']))
        self.assertIn('as many as on Dofus 3 but not the same ones', corps)
        from chardata.guides_content import _differing_spell_names
        self.assertIn('%d spell names differ' % _differing_spell_names(), corps)

    def test_the_differing_names_count_is_what_the_tables_say(self):
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
        from chardata.guides_content import _differing_spell_names
        self.assertGreater(differents, 100)
        self.assertEqual(differents, _differing_spell_names())
