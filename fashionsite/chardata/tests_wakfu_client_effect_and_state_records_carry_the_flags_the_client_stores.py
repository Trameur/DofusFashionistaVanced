import os
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import wakfu_client  # noqa: E402
from chardata.tests_wakfu_client_decoder_reads_a_table_it_wrote import (  # noqa: E402
    container)
from chardata.tests_wakfu_client_tables_read_back_every_record import (  # noqa: E402
    jar, write_layout)

BIG_MASK = 2 ** 50 + 5

EFFECTS = [
    {'id': 1, 'action_id': 1010, 'container_type': 'SPELL', 'root_container_type': 'SPELL',
     'normal_or_critical': 'NORMAL', 'longs_esY': [BIG_MASK], 'flag_etA': True,
     'byte_etg': 2, 'byte_eth': 5, 'byte_eti': 4},
    {'id': 2, 'action_id': 1010, 'container_type': 'SPELL', 'root_container_type': 'SPELL',
     'normal_or_critical': 'NORMAL', 'longs_esY': [], 'flag_etA': False,
     'byte_etg': 3, 'byte_eth': 1, 'byte_eti': 2},
    {'id': 3, 'action_id': 20, 'container_type': 'ITEM_EQUIP',
     'root_container_type': 'ITEM_EQUIP', 'normal_or_critical': 'NORMAL',
     'longs_esY': [0], 'flag_etA': True},
    {'id': 4, 'action_id': 20, 'container_type': 'ITEM_EQUIP',
     'root_container_type': 'ITEM_EQUIP', 'normal_or_critical': 'NORMAL',
     'longs_esY': [2], 'flag_etA': False},
]
STATES = [{'id': 5, 'bcw': 'one', 'efW': [1], 'aYh': 6, 'esA': True},
          {'id': 6, 'bcw': 'two', 'efW': [], 'aYh': 1, 'esA': False}]


class TheClientEffectAndStateRecordsCarryTheFlagsTheClientStoresTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def table(self, number, records, layout):
        blob = container(number, records, write_layout(layout))
        return jar(self.folder / ('%d.jar' % number), '%d.bin' % number, blob)

    def effects(self):
        return wakfu_client.read_effects(
            self.table(68, EFFECTS, wakfu_client.STATIC_EFFECT_LAYOUT))

    def test_the_target_mask_is_the_first_value_of_the_filter_array_and_zero_when_it_is_empty(self):
        self.assertEqual([BIG_MASK, 0, 0, 2], [one.target_mask for one in self.effects()])

    def test_a_filter_array_with_two_values_stops_the_decoder(self):
        records = [dict(EFFECTS[0], longs_esY=[2, 8])]
        with self.assertRaises(ValueError):
            wakfu_client.read_effects(
                self.table(68, records, wakfu_client.STATIC_EFFECT_LAYOUT))

    def test_the_display_flag_is_the_flag_the_record_was_written_with(self):
        self.assertEqual([True, False, True, False], [one.display for one in self.effects()])

    def test_the_three_trigger_bytes_are_the_bytes_the_record_was_written_with(self):
        self.assertEqual([(2, 5, 4), (3, 1, 2), (0, 0, 0), (0, 0, 0)],
                         [(one.trigger_side, one.trigger_target, one.trigger_caster)
                          for one in self.effects()])

    def test_the_action_mask_and_display_flag_read_the_same_beside_the_trigger_bytes(self):
        read = self.effects()
        self.assertEqual([1010, 1010, 20, 20], [one.action_id for one in read])
        self.assertEqual([BIG_MASK, 0, 0, 2], [one.target_mask for one in read])
        self.assertEqual([True, False, True, False], [one.display for one in read])

    def test_the_records_keep_their_table_order_and_their_ids(self):
        self.assertEqual([1, 2, 3, 4], [one.id for one in self.effects()])

    def test_a_state_record_carries_the_stack_cap_and_the_cumulable_flag(self):
        read = wakfu_client.read_states(
            self.table(67, STATES, wakfu_client.STATE_LAYOUT))
        self.assertEqual([(5, 6, True), (6, 1, False)],
                         [(one.id, one.max_level, one.cumulable) for one in read])

    def test_an_effect_built_without_the_new_fields_shows_its_line_and_has_no_filter(self):
        bare = wakfu_client.EffectRecord(1, 2, 3, '', '', '', 0, [], [])
        self.assertEqual((0, True), (bare.target_mask, bare.display))
        self.assertEqual((0, 0, 0), (bare.trigger_side, bare.trigger_target, bare.trigger_caster))
        state = wakfu_client.StateRecord(1, 'k', [], 3)
        self.assertFalse(state.cumulable)
