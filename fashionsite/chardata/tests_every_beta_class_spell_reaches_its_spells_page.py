# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every spell a Beta class can cast gets a card on its spells page, linked groups of any size included."""
from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import castable_spells
from chardata.spell_reference import reference_by_spell_id
from chardata.spells_view import (_create_reference_web_digest,
                                  _create_spell_web_digest)

VERSION = 'beta'
LEVEL = 200


def page_digests(char_class):
    """The class part of the digests the spells page receives, in its order."""
    spells = get_damage_spells_for_version(VERSION).get(char_class, [])
    digests = [_create_spell_web_digest(spell, VERSION, LEVEL) for spell in spells]
    shown = {spell.spell_id for spell in spells}
    for spell_id, entry in reference_by_spell_id(VERSION, char_class).items():
        if spell_id not in shown:
            digests.append(_create_reference_web_digest(entry, VERSION, LEVEL))
    return digests


def drawn_names(digests):
    """The names createLines in spells.html draws a card for: a single, a rank-1 pair, or its rank-2 partner."""
    drawn = set()
    for digest in digests:
        link = digest['is_linked']
        if link is None:
            drawn.add(digest['name'])
        elif link[0] == 1:
            drawn.add(digest['name'])
            drawn.update(other['name'] for other in digests if other['name'] == link[1])
    return drawn


class EveryBetaClassSpellReachesItsSpellsPageTests(SimpleTestCase):

    def setUp(self):
        translation.activate('en')
        self.addCleanup(translation.deactivate)

    def classes(self):
        return [name for name in get_damage_spells_for_version(VERSION) if name != 'default']

    def test_every_castable_spell_of_every_beta_class_is_drawn(self):
        self.assertIn('Bellaphone', self.classes())
        for char_class in self.classes():
            with self.subTest(char_class=char_class):
                digests = page_digests(char_class)
                drawn = drawn_names(digests)
                names = {digest['canonical']: digest['name'] for digest in digests}
                castable = {castable.name for castable in castable_spells(char_class, LEVEL, VERSION)}
                self.assertTrue(castable, char_class)
                missing = sorted(name for name in castable if names.get(name, name) not in drawn)
                self.assertEqual([], missing, char_class)

    def test_a_linked_spell_is_a_pair_whose_two_faces_name_each_other(self):
        for char_class in self.classes():
            digests = page_digests(char_class)
            by_name = {digest['name']: digest for digest in digests}
            for digest in digests:
                link = digest['is_linked']
                if link is None:
                    continue
                with self.subTest(char_class=char_class, spell=digest['name']):
                    self.assertIn(link[0], (1, 2))
                    partner = by_name.get(link[1])
                    self.assertIsNotNone(partner, link[1])
                    self.assertEqual((3 - link[0], digest['name']), tuple(partner['is_linked']))

    def test_a_variant_group_of_more_than_two_spells_draws_each_one_on_its_own_card(self):
        from chardata.spell_variants import get_variant_by_spell_id
        groups = {}
        for spell_id, variant in get_variant_by_spell_id(VERSION).items():
            groups.setdefault(variant, set()).add(int(spell_id))
        large = [group for group in groups.values() if len(group) > 2]
        self.assertTrue(large)
        for char_class in self.classes():
            spells = {spell.spell_id: spell for spell in get_damage_spells_for_version(VERSION)[char_class]}
            drawn = drawn_names(page_digests(char_class))
            for group in large:
                for spell in (spells[spell_id] for spell_id in sorted(group) if spell_id in spells):
                    with self.subTest(char_class=char_class, spell=spell.name):
                        self.assertIsNone(spell.is_linked)
                        self.assertIn(spell.name, drawn)
