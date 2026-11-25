# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A combat record turns on only sourced stages that have code, and every known field carries a dated source."""
import copy

from django.test import SimpleTestCase

from fashionistapulp.combat.rules import (APPLIED_STAGES, FIELDS, OPTIONAL_FIELDS,
                                          RecordError, UNKNOWN, check_record, read_record,
                                          record_path)

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')


class TheRecordFormatTests(SimpleTestCase):

    def _record(self, version='dofus3'):
        return copy.deepcopy(read_record(record_path(version)))

    def test_the_shipped_records_pass_and_enable_only_coded_stages(self):
        for version in VERSIONS:
            record = self._record(version)
            with self.subTest(version=version):
                check_record(record)
                self.assertEqual(list(FIELDS),
                                 [field for field in record if field not in OPTIONAL_FIELDS])
                self.assertTrue(set(record['enabled_stages']) <= set(APPLIED_STAGES))

    def test_an_enabled_stage_without_a_source_is_refused(self):
        record = self._record()
        del record['sources']['P']
        with self.assertRaises(RecordError):
            check_record(record)

    def test_a_stage_with_no_code_is_refused_even_with_a_source(self):
        record = self._record()
        record['enabled_stages'].append('V')
        record['sources']['V'] = copy.deepcopy(record['sources']['P'])
        record['order'] = ['P', 'V']
        record['sources']['order'] = copy.deepcopy(record['sources']['P'])
        with self.assertRaises(RecordError) as refused:
            check_record(record)
        self.assertIn('V', str(refused.exception))
        record['enabled_stages'].remove('V')
        check_record(record)

    def test_the_dealt_stage_needs_its_dealt_multipliers(self):
        record = self._record('dofus2')
        self.assertIn('R', record['enabled_stages'])
        del record['dealt_multipliers']
        with self.assertRaises(RecordError) as refused:
            check_record(record)
        self.assertIn('dealt_multipliers', str(refused.exception))

    def test_a_known_field_without_a_source_is_refused_and_unknown_needs_none(self):
        record = self._record()
        record['percent_below_0'] = 'amplify'
        with self.assertRaises(RecordError):
            check_record(record)
        record['percent_below_0'] = UNKNOWN
        check_record(record)

    def test_a_source_needs_a_kind_a_place_and_a_date(self):
        for broken in ({'kind': 'rumour'}, {'where': ''}, {'date': 'yesterday'}):
            record = self._record()
            record['sources']['P'][0].update(broken)
            with self.subTest(broken=broken), self.assertRaises(RecordError):
                check_record(record)

    def test_an_unknown_rounding_needs_a_tolerance(self):
        record = self._record()
        record['rounding']['P'] = UNKNOWN
        record['tolerance_per_hit'] = 0
        with self.assertRaises(RecordError):
            check_record(record)

    def test_a_missing_or_extra_field_is_refused(self):
        record = self._record()
        del record['melee_rule']
        with self.assertRaises(RecordError):
            check_record(record)
        record = self._record()
        record['notes'] = 'free text'
        with self.assertRaises(RecordError):
            check_record(record)
