# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A transcendence rune the solution meets every row and its objective without is left off the result; a rune it needs stays."""

from fashionistapulp.dracorunes import RESISTANCE_NAMES

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input, element_key,
                                         element_move, piece, stat_id, structure)
from chardata.transcendence_fixtures import beta_rune, stat_runes, trans_input

OVER = 100
FIRE = 'fireresper'


def top_rune(stat_key):
    """The highest ranked rune of that stat."""
    return max((beta_rune(stat_key, rank) for rank in (1, 2, 3, 4, 5) if _exists(stat_key, rank)),
               key=lambda rune: rune['rank'])


def _exists(stat_key, rank):
    try:
        beta_rune(stat_key, rank)
    except StopIteration:
        return False
    return True


class WastedTranscendenceRunesLeaveTheResultTests(BetaModelTestCase):

    def cap(self):
        return SmallModel([]).stat_maximum[structure().get_stat_by_key(FIRE).name]

    def forced(self, pieces, weights, count=4, dracorunes=None, minimums=None, column_of=None):
        """The model solved with the columns column_of picks forced on, then those rows removed."""
        model = SmallModel(pieces)
        model.setup(trans_input(weights, count, dracorunes, minimums))
        lp = model.problem.pulp_lp
        names = []
        for number, column in enumerate(column_of(model) if column_of else ()):
            names.append('force_%d' % number)
            lp.addConstraint(column >= 1, names[-1])
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        for name in names:
            del lp.constraints[name]
        return model

    def values(self, model):
        return {variable.name: variable.varValue for variable in model.problem.pulp_lp.variables()}

    def fire_column(self, model, item):
        """The top fire rune's column of the class that holds item."""
        return [column for column in stat_runes(model, FIRE)
                if model.transcendence_columns[column.name][1] == top_rune(FIRE)['id']
                and item.id in model.transcendence_classes[model.transcendence_columns[column.name][0]]]

    def test_a_rune_every_row_and_the_objective_hold_without_is_dropped(self):
        for label, type_name in (('slot class', 'Hat'), ('ring class', 'Ring')):
            with self.subTest(label=label):
                held = piece(type_name, {'vit': 10})
                boots = piece('Boots', {FIRE: self.cap() + OVER, 'vit': 10})
                model = self.forced([held, boots], {FIRE: 1}, column_of=lambda model: self.fire_column(model, held))
                self.assertEqual(1, len(model.chosen_transcendences()))
                before = self.values(model)
                dracorunes, transcendences = model.useful_rune_choices(
                    model.chosen_dracorunes(), model.chosen_transcendences())
                self.assertEqual([], transcendences)
                self.assertEqual([], dracorunes)
                self.assertEqual(before, self.values(model))
                self.assertIsNone(model.get_result_minimal().transcendences)

    def test_a_rune_a_minimum_needs_stays(self):
        pow_rune = top_rune('pow')
        hat = piece('Hat', {'vit': 10})
        model = self.forced([hat], {'vit': 1}, minimums={'Power': pow_rune['bonus']})
        result = model.get_result_minimal()
        self.assertEqual({'hat': (hat.id, pow_rune['id'])}, result.transcendences)

    def test_the_dracorunes_kept_are_the_same_without_transcendences(self):
        source, target = element_move()
        key = element_key(source, target)
        hat = piece('Hat', {source: 40, 'vit': 10})
        amulet = piece('Amulet', {'vit': 300})
        amulet.min_stats_to_equip = [(stat_id(target), 40)]
        boots = piece('Boots', {target: 40, 'vit': 10})
        for label, pieces, kept in (('needed', [hat, amulet], [(hat.id, key)]),
                                    ('wasted', [hat, amulet, boots], [])):
            with self.subTest(label=label):
                model = SmallModel(pieces)
                model.setup(build_input({'vit': 1}, 1))
                column = next(model.problem.pulp_vars[name] for name, (item_id, found)
                              in model.dracorune_columns.items() if item_id == hat.id and found == key)
                model.problem.pulp_lp.addConstraint(column >= 1, 'force_the_rune')
                model.run()
                del model.problem.pulp_lp.constraints['force_the_rune']
                chosen = model.chosen_dracorunes()
                self.assertEqual([(hat.id, key)], chosen)
                self.assertEqual(kept, model.useful_dracorunes(chosen))
                self.assertEqual((kept, []), model.useful_rune_choices(chosen, []))

    def test_removals_add_up_across_both_kinds(self):
        key = 'resistance:%s>%s' % (RESISTANCE_NAMES['earth'], RESISTANCE_NAMES['fire'])
        hat = piece('Hat', {'earthresper': 30, 'vit': 10})
        cloak = piece('Cloak', {'vit': 10})
        boots = piece('Boots', {FIRE: self.cap() - 1, 'vit': 10})

        def columns(model):
            dracorune = next(model.problem.pulp_vars[name] for name, (item_id, found)
                             in model.dracorune_columns.items() if item_id == hat.id and found == key)
            return [dracorune] + self.fire_column(model, cloak)

        model = self.forced([hat, cloak, boots], {FIRE: 1}, 4, 2, column_of=columns)
        self.assertEqual([(hat.id, key)], model.chosen_dracorunes())
        self.assertEqual(1, len(model.chosen_transcendences()))
        dracorunes, transcendences = model.useful_rune_choices(
            model.chosen_dracorunes(), model.chosen_transcendences())
        self.assertEqual(1, len(dracorunes) + len(transcendences))
        self.assertEqual(([], model.chosen_transcendences()), (dracorunes, transcendences))

    def test_every_value_comes_back_after_the_check(self):
        for type_name, misfit in (('Hat', False), ('Ring', False), ('Hat', True)):
            with self.subTest(type=type_name, misfit=misfit):
                held = piece(type_name, {'vit': 10})
                boots = piece('Boots', {FIRE: self.cap() + OVER, 'vit': 10})
                pieces = [held, boots]
                if misfit:
                    pieces.append(piece('Hat', {FIRE: 10}, 1))
                weights = {FIRE: 1, 'pow': 1} if misfit else {FIRE: 1}
                model = self.forced(pieces, weights, column_of=lambda found: self.fire_column(found, held))
                lp = model.problem.pulp_lp
                self.assertEqual(misfit, any(name.startswith('trans_fit_') for name in lp.constraints))
                before = self.values(model)
                model.useful_rune_choices(model.chosen_dracorunes(), model.chosen_transcendences())
                self.assertEqual(before, self.values(model))
                self.assertTrue(model._solution_holds(()))
                self.assertTrue(all(row.valid(1e-6) for row in lp.constraints.values()))
