# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solution page hands its best turn card the cast sequence next to the unchanged total."""

import re

from django.test import TestCase


class TheBestTurnCardTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.owner = User.objects.create_user('owner', 'o@x.test', 'pw')
        self.client.force_login(self.owner)

    def _response(self):
        from chardata.models import Char
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name] if not i.removed and i.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {'text': '\n'.join(names), 'confirm': '1',
                                           'char_class': 'Cra', 'level': '200'})
        self.char = Char.objects.order_by('-id').first()
        return self.client.get('/solution/%d/' % self.char.id, follow=True)

    def test_the_casts_come_with_the_total_the_panel_shows(self):
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        response = self._response()
        context = response.context
        casts = context['best_turn_casts']
        self.assertIsNotNone(context['best_turn'])
        self.assertTrue(casts)
        for cast in casts:
            for key in ('name', 'image_url', 'ap', 'damage', 'running'):
                self.assertIn(key, cast)
        combo = _best_combo(self.char, get_solution(self.char), 'dofus3', note_without_buffs=False)
        self.assertEqual(combo['total'], context['best_turn'])
        self.assertEqual(casts[-1]['running'], context['best_turn'])
        self.assertEqual(sum(cast['ap'] for cast in casts), context['best_turn_ap_used'])
        self.assertEqual(combo['ap_available'], context['best_turn_ap_available'])
        self.assertLessEqual(context['best_turn_ap_used'], context['best_turn_ap_available'])

    def test_the_card_prints_the_same_total_as_the_header(self):
        response = self._response()
        page = response.content.decode('utf-8')
        self.assertIsNotNone(response.context['best_turn'])
        self.assertIn('<div class="fm-sol-turn-total fm-num">%s</div>' % response.context['best_turn'], page)
        self.assertEqual(len(response.context['best_turn_casts']), page.count('class="fm-sol-cast"'))

    def test_the_resistance_cap_reaches_the_page(self):
        self.assertEqual(50, self._response().context['resist_cap'])

    def test_the_new_cards_add_no_duplicate_id(self):
        page = self._response().content.decode('utf-8')
        ids = re.findall(r'(?<![\w-])id="([^"]+)"', page)
        self.assertEqual([], sorted({i for i in ids if ids.count(i) > 1}))
