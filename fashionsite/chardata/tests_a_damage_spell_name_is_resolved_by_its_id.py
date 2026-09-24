# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A shown spell name is read from the version's own spell reference by id,
not from an English-name lookup that a homonym can win instead.
"""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spells_view import _create_spell_web_digest, _localized_spell_name

# (version, char_class, spell_id, language, expected name)
RESOLVED_BY_ID = (
    ('dofus3', 'Xelor', 13288, 'fr', 'Perturbation'),
    ('dofus3', 'Sram', 12950, 'fr', 'Calamité'),
    ('dofus3', 'Foggernaut', 13828, 'fr', 'Gouvernail'),
    ('dofus2', 'Osamodas', 12548, 'fr', 'Dragonique'),
)


def _damage_spell(version, char_class, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)[char_class]
                if spell.spell_id == spell_id)


class ADamageSpellNameIsResolvedByItsIdTests(SimpleTestCase):

    def test_a_spell_shows_its_own_name_not_a_homonyms(self):
        for version, char_class, spell_id, language, expected in RESOLVED_BY_ID:
            with self.subTest(version=version, char_class=char_class):
                spell = _damage_spell(version, char_class, spell_id)
                shown = _localized_spell_name(spell.name, language, version,
                                              spell.spell_id)
                self.assertEqual(expected, shown)

    def test_the_web_digest_carries_the_resolved_name(self):
        spell = _damage_spell('dofus3', 'Xelor', 13288)
        digest = _create_spell_web_digest(spell, 'dofus3')
        digest_fr = _localized_spell_name(spell.name, 'fr', 'dofus3',
                                          spell.spell_id)
        self.assertEqual('Disruption', digest['canonical'])
        self.assertEqual('Perturbation', digest_fr)

    def test_a_spell_named_after_its_item_keeps_its_own_name(self):
        ebony = next(spell for spell in
                     get_damage_spells_for_version('dofus3')['default']
                     if spell.spell_id == 18645)
        self.assertEqual('Ebony Dofus', ebony.name)
        self.assertEqual('Dofus Ébène',
                         _localized_spell_name(ebony.name, 'fr', 'dofus3',
                                               ebony.spell_id))
        self.assertEqual('Ebenholz-Dofus',
                         _localized_spell_name(ebony.name, 'de', 'dofus3',
                                               ebony.spell_id))

    def test_a_pair_names_its_partner_as_the_partner_card_does(self):
        from django.utils import translation
        for version in ('dofus3', 'dofus2'):
            for language in ('fr', 'de'):
                with self.subTest(version=version, language=language), \
                        translation.override(language):
                    checked = 0
                    for char_class, spells in get_damage_spells_for_version(version).items():
                        digests = [_create_spell_web_digest(spell, version)
                                   for spell in spells]
                        names = {digest['name'] for digest in digests}
                        for digest in digests:
                            if digest['is_linked']:
                                checked += 1
                                self.assertIn(digest['is_linked'][1], names,
                                              (char_class, digest['canonical']))
                    self.assertGreater(checked, 50)
