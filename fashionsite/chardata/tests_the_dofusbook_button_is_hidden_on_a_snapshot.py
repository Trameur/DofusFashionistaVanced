# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The 'Open on DofusBook' button always exports the current build, so it
must not appear on a generation snapshot, which shows an older one."""
from django.test import TestCase


class TheDofusbookButtonNeverAppearsOnASnapshotTests(TestCase):

    def _char_with_a_snapshot(self):
        from chardata.char_blobs import read_char_blob
        from chardata.models import Char
        from chardata.solution_history import record_solution_generation
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        nom = structure.get_item_name_in_language(
            next(i for i in structure.types[200]['Hat'] if not i.removed), 'en')
        self.client.post('/import/text/', {
            'text': nom, 'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        minimal_solution = read_char_blob(char.minimal_solution, None,
                                          'minimal_solution', char)
        generation = record_solution_generation(char, minimal_solution)
        return char, generation

    def test_the_button_shows_on_the_current_build(self):
        char, _generation = self._char_with_a_snapshot()
        page = self.client.get('/solution/%d/' % char.id)
        self.assertEqual(200, page.status_code)
        self.assertTrue(page.context['dofusbook_export'])
        self.assertContains(page, '/export/dofusbook/%d/' % char.id)

    def test_the_button_is_gone_on_a_generation_snapshot(self):
        char, generation = self._char_with_a_snapshot()
        page = self.client.get(
            '/solutiongeneration/%d/%d/' % (char.id, generation.id))
        self.assertEqual(200, page.status_code)
        self.assertTrue(page.context['is_generation_snapshot'])
        self.assertFalse(page.context['dofusbook_export'])
        self.assertNotContains(page, '/export/dofusbook/%d/' % char.id)
