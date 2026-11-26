# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
from django.test import SimpleTestCase

from chardata.tests import reviewed_wakfu_page_disagreements, wakfu_page_disagreement_problems


class AnUnreviewedWakfuBuildMayFixAPageButNotBreakOneTests(SimpleTestCase):
    """A page Ankama fixed must not block an import, a new disagreement must."""

    def problems(self, build, found, key='rows_differ'):
        _version, entry, exact = reviewed_wakfu_page_disagreements(build)
        return wakfu_page_disagreement_problems(entry[key], found, exact)

    def test_a_reviewed_build_keeps_its_own_entry_and_exact_equality(self):
        for build, version in (('1.93.1.62', '1.93'), ('1.94.3.64', '1.94'), ('1.94', '1.94')):
            with self.subTest(build=build):
                chosen, _entry, exact = reviewed_wakfu_page_disagreements(build)
                self.assertEqual((version, True), (chosen, exact))

    def test_a_reviewed_build_fails_when_a_recorded_disagreement_vanishes(self):
        self.assertEqual([5029], self.problems('1.94.3.64', {5041}))

    def test_a_reviewed_build_fails_on_a_new_disagreement(self):
        self.assertEqual([9999], self.problems('1.94.3.64', {5029, 5041, 9999}))

    def test_an_unreviewed_build_takes_the_newest_entry_below_it(self):
        chosen, entry, exact = reviewed_wakfu_page_disagreements('1.95.0.66')
        self.assertEqual(('1.94', False), (chosen, exact))
        self.assertEqual(frozenset((5029, 5041)), entry['rows_differ'])
        self.assertEqual('1.93', reviewed_wakfu_page_disagreements('1.93.9.1')[0])

    def test_an_unreviewed_build_passes_when_a_recorded_disagreement_vanished(self):
        self.assertEqual([], self.problems('1.95.0.66', {5041}))
        self.assertEqual([], self.problems('1.95.0.66', set()))

    def test_an_unreviewed_build_fails_on_an_extra_disagreement(self):
        self.assertEqual([9999], self.problems('1.95.0.66', {5029, 5041, 9999}))
        self.assertEqual([9999], self.problems('1.95.0.66', {9999}))

    def test_a_build_older_than_every_entry_has_none_to_lean_on(self):
        chosen, _entry, exact = reviewed_wakfu_page_disagreements('1.90.0.1')
        self.assertEqual((None, False), (chosen, exact))
        self.assertEqual([5029], self.problems('1.90.0.1', {5029}))
