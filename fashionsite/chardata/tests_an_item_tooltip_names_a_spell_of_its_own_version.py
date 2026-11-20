# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each spell an item tooltip explains is a spell its version's book names, in that language."""
from django.test import SimpleTestCase

VERSIONS = ('dofus3', 'beta')


def _book_names(game_version):
    from chardata.spell_reference import get_spell_reference
    names = {}
    for entries in get_spell_reference(game_version).values():
        for entry in entries or []:
            for language, name in (entry.get('name') or {}).items():
                if name:
                    names.setdefault(language, set()).add(name.strip())
    return names


class AnItemTooltipNamesASpellOfItsOwnVersionTests(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_an_item_tooltip_names_a_spell_of_its_own_version(self):
        from fashionistapulp.structure import get_structure, set_current_game_version
        for game_version in VERSIONS:
            set_current_game_version(game_version)
            names = _book_names(game_version)
            stale = sorted(
                (item.ankama_id, language, spell)
                for item in get_structure(game_version).get_available_items_list()
                for language, tooltips in (item.spell_tooltips or {}).items()
                for spell in tooltips
                if spell.strip() not in names.get(language, ()))
            with self.subTest(game_version=game_version):
                self.assertEqual([], stale)
