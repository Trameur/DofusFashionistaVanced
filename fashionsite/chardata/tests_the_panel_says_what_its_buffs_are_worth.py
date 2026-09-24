# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The panel says what the buffs it casts are worth, on the same scale as its total."""
import io
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.spells_view import _buff_casts, _without_buffs_note

PHRASE = 'Without the buffs it casts first, this turn would deal %(damage)s.'

LANGUES = ('en', 'fr', 'es', 'pt', 'de')


class _Sort(object):

    def __init__(self, name, buffs=None, hits=None):
        self.name = name
        self.buffs = buffs
        self.hits = hits


class WhatTheRuleReadsTests(SimpleTestCase):

    def test_a_buff_cast_is_a_cast_that_does_not_hit(self):
        sorts = [_Sort('buff', buffs={'str': 100}),
                 _Sort('frappe', hits=[object()]),
                 _Sort('both', buffs={'str': 10}, hits=[object()]),
                 _Sort('never cast', buffs={'str': 10})]
        ordre = [('buff', 0), ('frappe', 120), ('both', 90)]
        self.assertEqual({'buff'}, _buff_casts(sorts, ordre))

    def test_a_turn_without_a_buff_says_nothing(self):
        sorts = [_Sort('frappe', hits=[object()])]
        self.assertEqual('', _without_buffs_note(
            {}, sorts, [('frappe', 120)], 6, None, 'dofus3', False, 200))

    def test_the_sentence_reads_in_five_languages(self):
        rendus = {}
        for langue in LANGUES:
            with translation.override(langue):
                rendus[langue] = gettext(PHRASE) % {'damage': 253}
        self.assertIn('253', rendus['en'])
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertIn('253', rendus[langue])
                if langue != 'en':
                    self.assertNotEqual(rendus['en'], rendus[langue],
                                        'still untranslated')
        self.assertEqual(len(LANGUES), len(set(rendus.values())))


class ThePanelCarriesTheSentenceTests(TestCase):

    def _char(self, char_class='Cra'):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        from chardata.models import Char
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _combo(self, char):
        import json
        reponse = self.client.get('/best_combo/%d/' % char.id)
        self.assertEqual(200, reponse.status_code)
        return json.loads(reponse.content.decode('utf-8'))['best_combo']

    def test_the_number_is_smaller_than_the_total_it_explains(self):
        vus = 0
        for char_class in ('Cra', 'Iop', 'Eniripsa', 'Xelor', 'Sadida'):
            char = self._char(char_class)
            combo = self._combo(char)
            if not combo:
                continue
            note = combo.get('without_buffs_note') or ''
            lance_un_buff = any(cast.get('note') for cast in combo['casts']
                                if cast.get('damage') == 0)
            with self.subTest(char_class=char_class):
                if not note:
                    continue
                vus += 1
                self.assertTrue(lance_un_buff,
                                'the sentence appeared on a turn that casts '
                                'no buff')
                sans = int(re.search(r'(\d+)', note).group(1))
                self.assertLess(sans, combo['total'],
                                '%s: %d without the buffs, %d with them'
                                % (char_class, sans, combo['total']))
        self.assertGreater(vus, 0, 'no class cast a buff, so nothing was read')

    def test_the_panel_total_is_the_one_the_sentence_is_measured_on(self):
        from chardata.spell_combo import castable_spells, combat_ap, best_turn
        from chardata.solution import get_solution
        from chardata.spells_view import _burst_total, _weapon_castable
        char = self._char('Cra')
        combo = self._combo(char)
        self.assertTrue(combo)
        solution = get_solution(char)
        stats = dict(solution.get_stats_total())
        ap = combat_ap(stats.get('ap'), char.game_version)
        spells = castable_spells(char.char_class, char.level,
                                 char.game_version)
        weapon = _weapon_castable(solution)
        if weapon is not None:
            spells = spells + [weapon]
        _total, order = best_turn(stats, spells, ap,
                                  game_version=char.game_version,
                                  caster_level=char.level)
        self.assertEqual(combo['total'],
                         _burst_total(stats, spells, order, None,
                                      char.game_version))

    def test_the_page_carries_the_sentence_where_the_other_notes_are(self):
        char = self._char('Cra')
        page = self.client.get('/spells/%d/' % char.id).content.decode('utf-8')
        self.assertIn('best-combo-without-buffs-note', page)
        combo = self._combo(char)
        note = combo.get('without_buffs_note') or ''
        self.assertTrue(note, 'the Cra turn no longer casts a buff, so this '
                              'witness stopped witnessing')
        self.assertIn(note, page)
        # The page rebuilds without a reload when a buff is ticked; the sentence follows the same path
        gabarit = io.open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'templates',
            'chardata', 'spells.html'), encoding='utf-8').read()
        self.assertIn('without_buffs_note', gabarit)
        self.assertIn(".best-combo-without-buffs-note'", gabarit)
