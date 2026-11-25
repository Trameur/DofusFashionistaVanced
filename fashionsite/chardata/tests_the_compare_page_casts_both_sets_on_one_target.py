# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The compare page casts both sets on one ?target=, side by side; without one its best-turn row is the target-free one, and a refused target says so and shows nothing of it."""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from django.utils.html import escape

from chardata import compare_sets_view, spells_view
from chardata.models import Char
from chardata.spells_view import _SUMMONS_NOTE, _TARGET_REFUSED_NOTE
from chardata.targets import _monster_index

SECRET = 'Stranger-hidden-build'


class TheCompareTargetTests(TestCase):

    def a_build(self, name, char_class):
        self.client.post('/createproject/', {
            'project': name, 'charname': name, 'level': '150',
            'class': char_class, 'where_to_go': 'wizard', 'publish_choice': '1'})
        char = Char.objects.order_by('-id').first()
        self.client.get('/solution/%d/' % char.id, follow=True)
        char.refresh_from_db()
        return char

    def test_one_target_for_both_sets_and_none_without_it(self):
        stranger = User.objects.create_user('stranger', 's@x.test', 'pw-42-solid')
        self.client.force_login(stranger)
        hidden = self.a_build(SECRET, 'Cra')
        owner = User.objects.create_user('owner', 'o@x.test', 'pw-42-solid')
        self.client.force_login(owner)
        first = self.a_build('First-set', 'Iop')
        second = self.a_build('Second-set', 'Cra')
        url = '/compare_sets/%d/%d/' % (first.id, second.id)
        seen = []
        real = compare_sets_view._best_combo

        def recorded(char, solution, game_version, *args, **kwargs):
            combo = real(char, solution, game_version, *args, **kwargs)
            seen.append((char.id, kwargs.get('target'), combo['total'] if combo else None))
            return combo

        for module in (compare_sets_view, spells_view):
            self.addCleanup(setattr, module, '_best_combo', module._best_combo)
            module._best_combo = recorded

        plain = self.client.get(url)
        self.assertEqual(200, plain.status_code)
        body = plain.content.decode('utf-8')
        self.assertIn('<b>Best turn</b>', body)
        self.assertNotIn('best_turn_target', plain.context)
        self.assertEqual([None, None], [target for _id, target, _total in seen])
        self.assertEqual({char_id: total for char_id, _target, total in seen},
                         plain.context['best_turn_by_char'])

        monster_id, _names, grades = _monster_index('dofus3')[0][0]
        token = 'm%d.%d' % (monster_id, grades[0][0])
        del seen[:]
        on_monster = self.client.get(url + '?target=' + token)
        name = on_monster.context['best_turn_target']['name']
        self.assertIn('<b>Best turn (%s)</b>' % escape(name), on_monster.content.decode('utf-8'))
        self.assertEqual([token, token], [target.token() for _id, target, _total in seen])
        self.assertEqual({char_id: total for char_id, _target, total in seen},
                         on_monster.context['best_turn_by_char'])

        del seen[:]
        on_build = self.client.get(url + '?target=b%d' % second.id)
        self.assertEqual('Second-set', on_build.context['best_turn_target']['name'])
        self.assertEqual(['build', 'build'], [target.kind for _id, target, _total in seen])
        self.assertEqual({char_id: total for char_id, _target, total in seen},
                         on_build.context['best_turn_by_char'])

        del seen[:]
        refused = self.client.get(url + '?target=b%d' % hidden.id)
        text = refused.content.decode('utf-8')
        self.assertEqual(200, refused.status_code)
        self.assertNotIn(SECRET, text)
        self.assertIn('<b>Best turn</b>', text)
        self.assertIn(str(_TARGET_REFUSED_NOTE), refused.context['best_turn_note'])
        self.assertEqual([None, None], [target for _id, target, _total in seen])

    def test_a_build_target_discloses_what_it_does_not_count_and_that_the_rows_are_raw(self):
        owner = User.objects.create_user('owner2', 'o2@x.test', 'pw-42-solid')
        self.client.force_login(owner)
        first = self.a_build('First-set', 'Iop')
        second = self.a_build('Second-set', 'Cra')
        stats = {'earthres': 20, 'waterres': 20, 'respermee': 5, 'airresper': 999, 'hp': 3000}
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = stats
        with mock.patch('chardata.solution.get_solution', return_value=solution):
            response = self.client.get('/compare_sets/%d/%d/?target=b%d' % (
                first.id, second.id, second.id))
        note = response.context['best_turn_note']
        self.assertIn('Not counted yet: ', note)
        self.assertIn('Earth Resist 20', note)
        self.assertIn('% Melee Resist 5', note)
        self.assertIn(str(_SUMMONS_NOTE), note)
        self.assertIn('Percent resistances above the cap count as the cap.', note)
        self.assertIn('The spell rows below show raw damage, before any resistance.', note)
        plain = self.client.get('/compare_sets/%d/%d/' % (first.id, second.id))
        self.assertNotIn('Not counted yet', plain.context['best_turn_note'])
        self.assertNotIn('raw damage', plain.context['best_turn_note'])
