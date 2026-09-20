# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Touch Ambush and Bravado add their elemental rows up, no best-element choice."""
import io
import json
import os

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version

RACINE = os.path.dirname(os.path.abspath(__file__))
REFERENCE = os.path.join(RACINE, 'spell_reference', 'touch.json')

# Spell: (class, English name, Ankama's words for the extra best-element hit)
ENSEMBLE = {
    'Embuscade': ('Foggernaut', 'Ambush',
                  'and damage in the caster’s best element'),
    'Fanfaronnade': ('Ecaflip', 'Bravado', 'and best-element damage'),
}


def _touch_spell(class_name, spell_name):
    for spell in get_damage_spells_for_version('touch')[class_name]:
        if spell.name == spell_name:
            return spell
    raise AssertionError('%s/%s left the Touch table'
                         % (class_name, spell_name))


def _reference_description(class_name, english_name):
    data = json.load(io.open(REFERENCE, encoding='utf-8', errors='replace'))
    for entry in data.get(class_name, []):
        names = entry.get('name') or {}
        if english_name in [str(value) for value in names.values()]:
            return (entry.get('description') or {}).get('en') or ''
    raise AssertionError('%s not in the Touch reference' % english_name)


class TouchRowsThatLandTogetherAreNotAChoiceTests(SimpleTestCase):

    def test_the_two_spells_add_their_rows_up(self):
        for spell_name, (class_name, _english, _quote) in sorted(
                ENSEMBLE.items()):
            spell = _touch_spell(class_name, spell_name)
            digest = spell.get_effects_digest()
            with self.subTest(sort=spell_name):
                self.assertEqual([], list(digest.aggregates or []),
                                 'grouped again, so the panel shows one hit '
                                 'of three')
                lignes = (digest.non_crit_dams or [[]])[0]
                elements = [ligne.element for ligne in lignes]
                self.assertEqual(3, len(elements), elements)
                self.assertEqual(3, len(set(elements)),
                                 'the three rows must be three elements')

    def test_ankama_says_the_named_rows_land_beside_the_best_one(self):
        for spell_name, (class_name, english, quote) in sorted(
                ENSEMBLE.items()):
            texte = _reference_description(class_name, english)
            with self.subTest(sort=spell_name):
                self.assertTrue(texte, english)
                # Ankama uses a typographic apostrophe in this file
                normalise = texte.replace('’', "'")
                self.assertIn(quote.replace('’', "'"), normalise,
                              'Ankama reworded it: %r' % texte[:160])

    def test_the_sibling_clients_write_the_same_spell_without_a_group(self):
        for version in ('dofus2', 'dofus3'):
            spell = None
            for spells in get_damage_spells_for_version(version).values():
                for candidate in spells:
                    if candidate.name == 'Ambush':
                        spell = candidate
            with self.subTest(version=version):
                self.assertIsNotNone(spell)
                digest = spell.get_effects_digest()
                self.assertEqual([], list(digest.aggregates or []))
                lignes = (digest.non_crit_dams or [[]])[0]
                self.assertEqual(4, len(lignes), lignes)

    def test_a_fabricated_best_element_group_is_untouched(self):
        """Dofus 3 builds its best-element rows from one elementless effect: one hit."""
        garde = 0
        for spells in get_damage_spells_for_version('dofus3').values():
            for spell in spells:
                # A placed thing's group carries its head before the same label
                if any(label.endswith('Hit in best element')
                       for label, _indices in (spell.aggregates or [])):
                    garde += 1
        self.assertEqual(32, garde,
                         'the Dofus 3 groups moved, and this lot did not '
                         'touch them')
        # Touch spells built from effect 1200 stay grouped, just not these two
        for spells in get_damage_spells_for_version('touch').values():
            for spell in spells:
                if spell.name not in ENSEMBLE:
                    continue
                self.assertFalse(
                    [label for label, _indices in (spell.aggregates or [])
                     if label == 'Hit in best element'],
                    '%s is grouped again' % spell.name)
