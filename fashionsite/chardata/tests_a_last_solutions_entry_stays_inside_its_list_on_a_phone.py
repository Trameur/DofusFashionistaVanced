# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A last solutions entry may shrink below its unwrapped row of item icons, so on a phone it stays inside its list."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet

ENTRY = '.solution-history-entry'
PREVIEW = '.solution-history-preview'


class ALastSolutionsEntryStaysInsideItsListOnAPhoneTests(SimpleTestCase):
    def setUp(self):
        self.rules = stylesheet('solution.css')

    def test_the_entry_may_shrink_below_its_content(self):
        self.assertEqual(('0', False), declared(self.rules, ENTRY, 'min-width'))

    def test_the_icon_row_still_clips_instead_of_wrapping(self):
        self.assertEqual(('nowrap', False), declared(self.rules, PREVIEW, 'flex-wrap'))
        self.assertEqual(('hidden', False), declared(self.rules, PREVIEW, 'overflow'))
