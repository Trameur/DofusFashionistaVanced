# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A cast of the build page's best turn that deals no damage of its own carries the same reason as on the spells page, so its 0 never reads as a mistake."""
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils.html import escape

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet
from chardata.tests_the_solution_best_turn_card_gets_its_casts import TheBestTurnCardTests

BUFF_NOTE = 'no damage of its own, it raises the casts that follow'


def combo_with_a_buff(real, last_damage=None):
    def combo(*args, **kwargs):
        found = real(*args, **kwargs)
        if found:
            casts = [dict(found['casts'][0], damage=0, note=BUFF_NOTE)] + found['casts'][1:]
            if last_damage is not None:
                casts[-1] = dict(casts[-1], damage=last_damage, late=0, late_title='')
            found = dict(found, casts=casts)
        return found
    return combo


class ABestTurnCastWithNoDamageSaysWhyTests(TestCase):

    setUp = TheBestTurnCardTests.setUp
    _response = TheBestTurnCardTests._response

    def test_a_cast_with_a_note_prints_it_under_its_name(self):
        from chardata import spells_view
        with mock.patch.object(spells_view, '_best_combo', combo_with_a_buff(spells_view._best_combo)):
            response = self._response()
        cast = response.context['best_turn_casts'][0]
        self.assertEqual(BUFF_NOTE, cast['note'])
        self.assertContains(response, '<span class="fm-sol-cast-name">%s<span class="fm-sol-cast-note">%s</span></span>'
                            % (escape(cast['name']), BUFF_NOTE))

    def test_a_cast_without_a_note_prints_its_name_alone(self):
        response = self._response()
        for cast in response.context['best_turn_casts']:
            if not cast['note']:
                self.assertContains(response, '<span class="fm-sol-cast-name">%s</span>' % escape(cast['name']))
                return
        self.fail('every cast had a note')

    def test_each_cast_groups_its_thousands_like_the_total_above_it(self):
        from chardata import spells_view
        with mock.patch.object(spells_view, '_best_combo', combo_with_a_buff(spells_view._best_combo, 12345)):
            response = self._response()
        self.assertContains(response, '<span class="fm-sol-cast-dmg fm-num">12,345</span>')
        self.assertNotContains(response, '>12345<')


class TheCastNoteStyleTests(SimpleTestCase):

    def test_the_note_sits_on_its_own_line_in_the_muted_ink(self):
        sheet = stylesheet('modern-solution.css')
        self.assertEqual('block', declared(sheet, 'html.fm-modern .fm-sol-cast-note', 'display')[0])
        self.assertEqual('var(--fm-muted)', declared(sheet, 'html.fm-modern .fm-sol-cast-note', 'color')[0])
