import contextlib
import io
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError

from fashionistapulp import wakfu_criteria as criteria
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, AMULET, BELT, BOOTS, CATALOGUE, CHEST, CLOAK, HELMET, SHOULDERS,
    InventedItemsCase, item)

STASIS_HELM, WAKFU_AMULET, NATION_CHEST, OWN_CLOAK, PVP_BOOTS, COMPANY_BELT, GUILD_SHOULDERS = (
    3001, 3002, 3003, 3004, 3005, 3006, 3007)
NATION, OTHER_NATION = 31, 32

STATE_ITEMS = [
    item(STASIS_HELM, HELMET, 'Stasis Helm', criteria='GetStasisGauge() >= 56', hp=900),
    item(WAKFU_AMULET, AMULET, 'Wakfu Amulet', criteria='GetWakfuGauge() >= 41', hp=800),
    item(NATION_CHEST, CHEST, 'Nation Chest', criteria='GetCrimeScore(31) >= 500', hp=700),
    item(OWN_CLOAK, CLOAK, 'Own Cloak', criteria='GetCrimeScore() >= 500', hp=600),
    item(PVP_BOOTS, BOOTS, 'Pvp Boots', criteria='HasPvpRank(7)', hp=500),
    item(COMPANY_BELT, BELT, 'Company Belt', criteria='GetCompanyRank() >= 10', hp=400),
    item(GUILD_SHOULDERS, SHOULDERS, 'Guild Shoulders', criteria='GetGuildLevel() >= 9', hp=600),
]
STATE_IDS = {one['id'] for one in STATE_ITEMS}


class AWakfuPlayerStateOptionUnlocksItsItemsTests(InventedItemsCase):
    NATIONS = {language: {str(NATION): 'Nation %d' % NATION,
                          str(OTHER_NATION): 'Nation %d' % OTHER_NATION}
               for language in ('fr', 'en', 'es', 'pt')}

    @classmethod
    def catalogue(cls):
        return CATALOGUE + STATE_ITEMS

    def state(self, **given):
        return criteria.player_state(self.structure, **given)

    def worn_ids(self, **given):
        _build, worn = self.solve({'hp': 1}, class_id=ALPHA, state=self.state(**given))
        return {one.id for one in worn.values()}

    def test_at_the_start_values_a_gauge_piece_is_left_out_and_its_unlock_is_named(self):
        self.assertEqual(set(), self.worn_ids() & STATE_IDS)
        unlocks = dict(criteria.state_unlocks(
            [one for one in self.structure.get_available_items_list() if one.id in STATE_IDS],
            criteria.start_state()))
        self.assertEqual({'stasis_gauge': 56}, unlocks[STASIS_HELM])
        self.assertEqual({'wakfu_gauge': 41}, unlocks[WAKFU_AMULET])
        self.assertEqual({('citizenship', NATION): 500}, unlocks[NATION_CHEST])
        self.assertEqual({('citizenship', None): 500}, unlocks[OWN_CLOAK])
        self.assertEqual({'pvp_rank': 7}, unlocks[PVP_BOOTS])
        self.assertEqual({'company_rank': 10}, unlocks[COMPANY_BELT])
        self.assertEqual({'guild_level': 9}, unlocks[GUILD_SHOULDERS])
        from fashionistapulp import wakfu_solve
        result = wakfu_solve.solve_weights(self.structure, level=100, weights={'hp': 1},
                                           class_id=ALPHA, allow_legacy=True)
        self.assertEqual(STATE_IDS, {ident for ident, _needs in result.state_unlocks})
        self.assertEqual(STASIS_HELM, result.state_unlocks[0][0])

    def test_raising_the_gauge_past_the_bound_lets_the_solver_wear_it(self):
        self.assertNotIn(STASIS_HELM, self.worn_ids(stasis_gauge=55))
        self.assertIn(STASIS_HELM, self.worn_ids(stasis_gauge=56))
        self.assertNotIn(WAKFU_AMULET, self.worn_ids(wakfu_gauge=40))
        self.assertIn(WAKFU_AMULET, self.worn_ids(wakfu_gauge=41))
        self.assertIn(PVP_BOOTS, self.worn_ids(pvp_rank=7))
        self.assertIn(COMPANY_BELT, self.worn_ids(company_rank=10))
        self.assertIn(GUILD_SHOULDERS, self.worn_ids(guild_level=9))

    def test_citizenship_reads_the_points_of_the_named_nation(self):
        self.assertIn(NATION_CHEST, self.worn_ids(citizenship={NATION: 500}))
        self.assertNotIn(NATION_CHEST, self.worn_ids(citizenship={NATION: 499}))
        self.assertNotIn(NATION_CHEST, self.worn_ids(citizenship={OTHER_NATION: 900}))

    def test_citizenship_without_a_nation_reads_the_own_nation_or_the_start_value(self):
        self.assertNotIn(OWN_CLOAK, self.worn_ids(citizenship={NATION: 900}))
        self.assertIn(OWN_CLOAK, self.worn_ids(nation=NATION, citizenship={NATION: 500}))
        self.assertNotIn(OWN_CLOAK, self.worn_ids(nation=OTHER_NATION, citizenship={NATION: 900}))

    def test_a_lock_on_a_piece_the_state_forbids_is_refused_with_the_value_that_unlocks_it(self):
        with self.assertRaisesRegex(ValueError, r'Stasis Helm needs stasis_gauge >= 56'):
            self.solve({'hp': 1}, locked=[(STASIS_HELM, None)], class_id=ALPHA)
        with self.assertRaisesRegex(ValueError, r'citizenship of nation 31 >= 500'):
            self.solve({'hp': 1}, locked=[(NATION_CHEST, None)], class_id=ALPHA)
        _build, worn = self.solve({'hp': 1}, locked=[(STASIS_HELM, None)], class_id=ALPHA,
                                  state=self.state(stasis_gauge=60))
        self.assertEqual(STASIS_HELM, worn['HEAD'].id)

    def test_the_checker_reports_player_state_on_a_set_the_state_forbids(self):
        from fashionistapulp import wakfu_legality
        worn = {'HEAD': self.by_id(STASIS_HELM)}
        found = wakfu_legality.violations(self.structure, 100, worn, class_id=ALPHA)
        self.assertEqual([wakfu_legality.STATE], [rule for rule, _text in found])
        self.assertIn('GetStasisGauge() >= 56', found[0][1])
        self.assertEqual([], wakfu_legality.violations(
            self.structure, 100, worn, class_id=ALPHA, state=self.state(stasis_gauge=56)))

    def test_an_out_of_range_or_unknown_option_is_refused(self):
        for given in ({'stasis_gauge': 101}, {'wakfu_gauge': -1}, {'company_rank': -2},
                      {'nation': 99}, {'citizenship': {99: 5}}, {'citizenship': {0: 5}},
                      {'colour': 3}, {'pvp_rank': True}, {'guild_level': 1.5}):
            with self.subTest(given=given):
                with self.assertRaises(ValueError):
                    criteria.player_state(self.structure, **given)
        self.assertEqual(criteria.start_state(), criteria.player_state(self.structure))

    def run_command(self, *args):
        out = io.StringIO()
        with mock.patch('fashionistapulp.fashionista_config.get_items_db_path',
                        return_value=str(self.db)), \
                mock.patch('fashionistapulp.structure.get_structure', return_value=self.structure), \
                contextlib.redirect_stderr(io.StringIO()):
            call_command('wakfu_build', *args, stdout=out, no_color=True)
        return out.getvalue()

    def test_the_wakfu_build_command_passes_every_state_flag(self):
        base = ('--level', '100', '--weights', 'hp=1', '--allow-legacy', '--class-id', str(ALPHA))
        plain = self.run_command(*base)
        self.assertIn("player state: the game's start values", plain)
        self.assertIn('the player state keeps out %d pieces; the highest:' % len(STATE_IDS), plain)
        self.assertIn('Stasis Helm', plain)
        self.assertIn('needs stasis_gauge >= 56', plain)
        out = self.run_command(
            *base, '--wakfu-gauge', '41', '--stasis-gauge', '56', '--nation', str(NATION),
            '--citizenship', '500', '--citizenship', '%d=500' % OTHER_NATION,
            '--company-rank', '10', '--pvp-rank', '7', '--guild-level', '9')
        self.assertIn('player state: wakfu_gauge 41, stasis_gauge 56, nation 31, '
                      'citizenship ((31, 500), (32, 500)), company_rank 10, pvp_rank 7, '
                      'guild_level 9', out)
        self.assertNotIn('the player state keeps out', out)
        for name in ('Stasis Helm', 'Wakfu Amulet', 'Nation Chest', 'Own Cloak', 'Pvp Boots',
                     'Company Belt', 'Guild Shoulders'):
            self.assertIn(name, out)
        with self.assertRaisesMessage(CommandError, '--citizenship POINTS needs --nation'):
            self.run_command(*base, '--citizenship', '500')
        with self.assertRaises(CommandError):
            self.run_command(*base, '--stasis-gauge', '101')
