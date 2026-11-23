# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The damage a Bellaphone state pays out later is not counted on the cast that applies it."""

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, _average
from chardata.spell_reference import get_spell_reference

SCARLET_CRUCIBLE = 33220
IVORY_TOWER = 33227
SHADOW_REALM = 33233

PAYOUT_ROWS = (4, 5, 6, 7)

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

SAYS = {
    SCARLET_CRUCIBLE: {'en': 'when the target uses ap or mp',
                       'fr': "lorsqu'elle utilise des pa ou des pm",
                       'es': 'cuando utiliza pa o pm',
                       'pt': 'quando este utiliza pa ou pm',
                       'de': 'wenn es ap oder bp verwendet'},
    IVORY_TOWER: {'en': 'enter the bellaura', 'fr': 'entrent dans sa bellaura',
                  'es': 'entran dentro de la belaura', 'pt': 'entram na belaura',
                  'de': 'betreten'},
    SHADOW_REALM: {'en': 'exit the bellaura', 'fr': 'sortent de sa bellaura',
                   'es': 'salen de su belaura', 'pt': 'saem da belaura',
                   'de': 'verlassen'},
}


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _card(version, spell_id, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                return ((entry.get('description') or {}).get(language) or '').lower()
    return ''


class TheStatePayoutWaitsForItsTriggerTests(SimpleTestCase):

    def test_the_four_faces_of_the_tooltip_row_wait_for_the_state(self):
        for spell_id in SAYS:
            with self.subTest(spell=spell_id):
                spell = _spell('beta', spell_id)
                self.assertEqual(set(PAYOUT_ROWS), set(spell.conditional or {}))
                self.assertEqual(1, len(set(spell.conditional.values())))

    def test_the_three_spells_wait_for_three_different_triggers(self):
        triggers = {next(iter((_spell('beta', spell_id).conditional or {'': ''}).values()))
                    for spell_id in SAYS}
        self.assertEqual(3, len(triggers))

    def test_the_cast_scores_only_the_hit_it_lands(self):
        _in_version(self, 'beta')
        scarlet = Castable(_spell('beta', SCARLET_CRUCIBLE), 0, crit=False)
        self.assertEqual(44.0, _average(scarlet.hits))
        shadow = Castable(_spell('beta', SHADOW_REALM), 0, crit=False)
        self.assertEqual(48.0, _average(shadow.hits))
        for cast in (scarlet, shadow):
            self.assertEqual(4, len(cast.waiting_plain))

    def test_a_cast_that_only_heals_scores_no_damage(self):
        _in_version(self, 'beta')
        ivory = Castable(_spell('beta', IVORY_TOWER), 0, crit=False)
        self.assertEqual([], ivory.hits)
        self.assertEqual(4, len(ivory.waiting_plain))

    def test_each_trigger_is_said_in_every_language_in_the_games_own_words(self):
        from chardata.spells_view import _CONDITIONAL_LABELS
        for spell_id, says in SAYS.items():
            trigger = next(iter((_spell('beta', spell_id).conditional or {'': ''}).values()))
            self.assertIn(trigger, _CONDITIONAL_LABELS)
            english = str(_CONDITIONAL_LABELS[trigger])
            for language in LANGUAGES:
                with self.subTest(spell=spell_id, language=language):
                    self.assertIn(says[language], _card('beta', spell_id, language))
                    with translation.override(language):
                        label = str(_CONDITIONAL_LABELS[trigger])
                    self.assertTrue(label)
                    if language != 'en':
                        self.assertNotEqual(english, label)

    def test_the_other_versions_have_no_such_spell(self):
        for version in ('dofus3', 'dofus2'):
            ids = {spell.spell_id for spells in get_damage_spells_for_version(version).values()
                   for spell in spells}
            self.assertFalse(ids & set(SAYS))
