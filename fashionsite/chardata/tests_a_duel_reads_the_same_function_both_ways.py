# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What A deals to B on A's page is what B takes from A on B's page, from one function, to the integer."""
import json
from contextlib import ExitStack
from unittest import mock

from django.core.cache import caches
from django.test import RequestFactory, SimpleTestCase

from chardata import duels, spells_view
from chardata.targets import build_target, read_target
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
BUILDS = {
    'A': ('Iop', {'str': 900, 'pow': 120, 'dam': 40, 'cridam': 30, 'ch': 40, 'ap': 11,
                  'hp': 4100, 'perspedam': 12, 'final': 4, 'earthresper': 22,
                  'fireresper': 31, 'earthres': 25, 'crires': 40, 'pshres': 30,
                  'respermee': 8}),
    'B': ('Cra', {'agi': 800, 'int': 300, 'pow': 60, 'dam': 25, 'cridam': 20, 'ch': 35,
                  'ap': 12, 'hp': 3600, 'perspedam': 20, 'airresper': 44, 'waterresper': 18,
                  'neutresper': 12, 'airres': 30, 'fireres': 12, 'crires': 25}),
}


def _stats(version, wanted):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in wanted.items():
        if key in stats:
            stats[key] = value
    return stats


def fake_build(version, pk, name, char_class, wanted):
    char = mock.Mock(pk=pk, char_class=char_class, level=200, game_version=version,
                     deleted=False)
    char.name = name
    solution = mock.Mock(item_list=[])
    solution.get_stats_total.return_value = _stats(version, wanted)
    return char, solution


def turn_patches():
    """The patches that let _best_combo run on a fake build with no worn item."""
    return [mock.patch('chardata.spell_combo.buffs_in_force', return_value={}),
            mock.patch('chardata.spell_combo.stacks_in_force', return_value={}),
            mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False),
            mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}),
            mock.patch.object(spells_view, '_weapon_castable', return_value=None)]


class ADuelTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        stack = ExitStack()
        for patch in turn_patches():
            stack.enter_context(patch)
        self.addCleanup(stack.close)

    def _builds(self, version):
        return {key: fake_build(version, index + 1, 'Build %s' % key, char_class, wanted)
                for index, (key, (char_class, wanted)) in enumerate(sorted(BUILDS.items()))}

    def _post(self, version, page, other, builds):
        """The payload of page's best_combo with the other build as the posted target."""
        char, solution = builds[page]
        request = RequestFactory().post('/best_combo/', {'target': 'b%d' % builds[other][0].pk,
                                                         'pushback': 'false'})
        request.game_version = version

        def reader(game_version, value, language=None, request=None):
            other_char, other_solution = builds[other]
            return build_target(other_char, other_solution, game_version, value), ''

        with mock.patch.object(spells_view, 'get_solution', return_value=solution), \
                mock.patch('chardata.targets.read_target', reader):
            response = spells_view._best_combo_response(request, char)
        return json.loads(response.content)

    def test_what_a_deals_on_its_page_is_what_b_takes_from_a_on_its_page(self):
        for version in VERSIONS:
            set_current_game_version(version)
            builds = self._builds(version)
            on_a = self._post(version, 'A', 'B', builds)
            on_b = self._post(version, 'B', 'A', builds)
            with self.subTest(version=version):
                dealt = on_a['best_combo']['total']
                taken = on_b['their_turn']['total']
                self.assertIs(int, type(dealt))
                self.assertGreater(dealt, 0)
                self.assertEqual(dealt, taken)
                self.assertEqual(on_b['best_combo']['total'], on_a['their_turn']['total'])
                self.assertEqual([cast['damage'] for cast in on_a['best_combo']['casts']],
                                 [cast['damage'] for cast in on_b['their_turn']['casts']])
                self.assertEqual(on_a['best_combo']['target']['hp_share'],
                                 on_b['their_turn']['hp_share'])

    def test_the_headline_and_the_reverse_turn_both_call_turn_on(self):
        version = 'dofus3'
        set_current_game_version(version)
        builds = self._builds(version)
        calls = []
        real = duels.turn_on

        def counted(attacker, *args, **kwargs):
            calls.append((attacker.name, kwargs['target'].label))
            return real(attacker, *args, **kwargs)

        with mock.patch.object(duels, 'turn_on', counted):
            self._post(version, 'A', 'B', builds)
        self.assertEqual([('Build A', 'Build B'), ('Build B', 'Build A')], calls)

    def test_a_monster_target_has_no_reverse_turn(self):
        version = 'dofus3'
        set_current_game_version(version)
        char, solution = self._builds(version)['A']
        from chardata.targets import _monster_index
        monster_id, _names, grades = _monster_index(version)[0][0]
        request = RequestFactory().post('/best_combo/', {'target': 'm%d.%d' % (
            monster_id, grades[0][0]), 'pushback': 'false'})
        request.game_version = version
        with mock.patch.object(spells_view, 'get_solution', return_value=solution):
            payload = json.loads(spells_view._best_combo_response(request, char).content)
        self.assertNotIn('their_turn', payload)
        self.assertIn('target', payload['best_combo'])
        target, refused = read_target(version, 'm%d.%d' % (monster_id, grades[0][0]))
        self.assertEqual(('', 'monster'), (refused, target.kind))
