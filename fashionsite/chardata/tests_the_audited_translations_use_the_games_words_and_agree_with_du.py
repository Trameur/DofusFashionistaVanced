# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The audited German and Spanish entries use the game's words and agree with their pronoun."""
import os

import polib
from django.test import SimpleTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
LOCALE = os.path.join(HERE, '..', 'locale')


def entry(lang, fragment):
    catalog = polib.pofile(os.path.join(LOCALE, lang, 'LC_MESSAGES', 'django.po'))
    found = [item for item in catalog if fragment in item.msgid and not item.obsolete]
    assert len(found) == 1, (lang, fragment, len(found))
    return found[0]


class AGermanEntryAgreesWithTheDuItAddressesTests(SimpleTestCase):

    def test_the_exo_faq_answer_gives_the_verb_of_du_and_the_gender_of_exo(self):
        text = entry('de', 'assign the exos to any particular equipment').msgstr
        self.assertIn('und möchtest es verwenden', text)
        self.assertNotIn('möchten ihn', text)

    def test_the_no_focus_hint_gives_the_verb_of_du(self):
        text = entry('de', 'No focus: every stat').msgstr
        self.assertIn('ein anderes Feld dieser Spalte ankreuzt, wird dieses', text)

    def test_the_ap_disabler_hint_gives_entzug_its_masculine_article(self):
        text = entry('de', 'Disablers that want to focus on AP reduction').msgstr
        self.assertIn('auf den AP-Entzug', text)
        self.assertNotIn('die AP-Entzug', text)


class AGermanEntryUsesTheWordAnkamaUsesTests(SimpleTestCase):

    def test_critical_resist_is_written_in_lower_case_like_ankama_writes_it(self):
        self.assertEqual('Resistenz gegen kritische Treffer', entry('de', 'Critical Resist').msgstr)

    def test_a_dungeon_is_a_dungeon_and_not_a_prison_cell(self):
        text = entry('de', "Declare items that cannot be used on your character's set").msgstr
        self.assertIn('ein Dungeon erforderlich', text)
        self.assertNotIn('Verlies', text)

    def test_a_hint_that_says_to_check_a_box_asks_the_player_to_tick_it(self):
        catalog = polib.pofile(os.path.join(LOCALE, 'de', 'LC_MESSAGES', 'django.po'))
        hints = [item for item in catalog
                 if 'should check this' in item.msgid and item.msgstr and not item.obsolete]
        self.assertGreaterEqual(len(hints), 6)
        for item in hints:
            with self.subTest(msgid=item.msgid[:40]):
                self.assertNotIn('überprüfen', item.msgstr)


class ASpanishFaqAnswerTellsTheReaderToRequestAnotherSetTests(SimpleTestCase):

    def test_the_weapon_lock_answer_uses_the_button_verb_and_no_stray_capital(self):
        text = entry('es', 'treat it like any other item, so you don' + chr(0x2019) + 't always get').msgstr
        self.assertIn('prohibirlas, confeccionar un nuevo set y esperar', text)
        self.assertNotIn('tejer', text)
        self.assertNotIn('Prohibirlas', text)
