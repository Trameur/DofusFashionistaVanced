# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Deux sorts qui se partagent une place le disent.

Un sort de classe de Dofus 3 vient par paire et le joueur en arme un des deux
avant le combat, donc un tour tient l'un ou l'autre, jamais les deux. Le
modele le sait (`spell_variants.json`, tire du client), et le simulateur de
tour le fait respecter depuis `spell_combo._variant_partners`.

La page, elle, listait les deux formes sans un mot. Mesure du 11 septembre
2026 sur le catalogue Dofus 3: 423 paires au total, et **chaque classe porte
les deux faces de 10 a 17 d'entre elles** (un Cra: 17 paires sur 36 sorts
modelises). Le lecteur comptait donc deux sorts la ou il n'en armera qu'un,
et ne pouvait pas comprendre pourquoi le meilleur combo refusait la paire.

Rien n'est calcule ici de neuf: la page dit ce que le calcul faisait deja.
"""

from django.test import SimpleTestCase, TestCase

from chardata.spell_variants import variant_of
from chardata.spells_view import _variant_partner_names


class ThePairingComesFromTheGameFilesTests(SimpleTestCase):

    def test_the_two_faces_of_a_cra_pair_point_at_each_other(self):
        """Mesure sur le catalogue du 11 septembre 2026: la Fleche de Recul
        (32426) et la Fleche Eclatante (32449) portent la variante 701."""
        self.assertEqual(variant_of('dofus3', 32426),
                         variant_of('dofus3', 32449))
        self.assertIsNotNone(variant_of('dofus3', 32426))

    def test_a_version_without_variants_names_nobody(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        for version in ('retro', 'touch'):
            with self.subTest(version=version):
                sorts = get_damage_spells_for_version(version).get('Cra', [])
                self.assertEqual({}, _variant_partner_names(sorts, version))

    def test_the_dofus2_pairs_are_read_from_the_archive(self):
        from chardata.spell_variants import get_variant_by_spell_id
        table = get_variant_by_spell_id('dofus2')
        self.assertEqual(864, len(table))
        self.assertEqual(432, len(set(table.values())))
        self.assertIsNotNone(variant_of('dofus2', 13047))
        self.assertEqual(variant_of('dofus2', 13047),
                         variant_of('dofus2', 13059))

    def test_each_dofus2_class_carries_both_faces_of_several_pairs(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        par_classe = get_damage_spells_for_version('dofus2')
        comptes = {}
        for classe, sorts in par_classe.items():
            if classe == 'default':
                continue
            comptes[classe] = len(_variant_partner_names(sorts, 'dofus2')) // 2
        self.assertGreaterEqual(min(comptes.values()), 8, comptes)
        noms = _variant_partner_names(par_classe['Cra'], 'dofus2')
        self.assertEqual('Raining Arrows', noms.get(13047))
        self.assertEqual('Optical Arrow', noms.get(13059))

    def test_a_face_the_game_only_describes_names_its_partner(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        from chardata.spell_reference import reference_by_spell_id
        for version in ('dofus3', 'beta', 'dofus2'):
            with self.subTest(version=version):
                par_classe = get_damage_spells_for_version(version)
                avec_table = sans_table = 0
                for classe, sorts in par_classe.items():
                    if classe == 'default':
                        continue
                    reference = reference_by_spell_id(version, classe)
                    seuls = _variant_partner_names(sorts, version)
                    tous = _variant_partner_names(sorts, version,
                                                  reference.values())
                    ids = {spell.spell_id for spell in sorts}
                    for spell_id, partenaire in tous.items():
                        self.assertTrue(partenaire, spell_id)
                        if spell_id in ids:
                            self.assertEqual(seuls.get(spell_id, partenaire),
                                             partenaire)
                        else:
                            self.assertTrue(
                                reference[spell_id]['name'].get('en'))
                    avec_table += len(seuls) // 2
                    sans_table += len(tous) // 2 - len(seuls) // 2
                self.assertGreaterEqual(avec_table, 230)
                self.assertGreaterEqual(sans_table, 164)

    def test_each_class_carries_both_faces_of_several_pairs(self):
        """Le chiffre qui justifie ce lot. S'il tombe a zero, la page n'a plus
        rien a dire et ce test doit rougir plutot que de passer en silence."""
        from chardata.spell_buffs import get_damage_spells_for_version
        par_classe = get_damage_spells_for_version('dofus3')
        comptes = {}
        for classe, sorts in par_classe.items():
            if classe == 'default':
                continue
            comptes[classe] = len(_variant_partner_names(sorts, 'dofus3')) // 2
        self.assertGreaterEqual(min(comptes.values()), 8, comptes)
        self.assertGreaterEqual(comptes.get('Cra', 0), 15, comptes)

    def test_the_two_names_point_back_at_each_other(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        from chardata.spells_view import _localized_spell_name
        sorts = get_damage_spells_for_version('dofus3').get('Cra', [])
        noms = _variant_partner_names(sorts, 'dofus3')
        self.assertTrue(noms)
        affiche = {spell.spell_id: _localized_spell_name(spell.name, 'en',
                                                         'dofus3')
                   for spell in sorts}
        par_affichage = {nom: spell_id for spell_id, nom in affiche.items()}
        for spell_id, partenaire in noms.items():
            with self.subTest(spell_id=spell_id):
                self.assertEqual(affiche[spell_id],
                                 noms.get(par_affichage.get(partenaire)))


class TheSpellPageSaysItTests(TestCase):

    def _char(self, char_class='Cra'):
        """Par la page d'import, avec un vrai objet: c'est le chemin que les
        autres modules empruntent et il donne un build complet."""
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': char_class, 'level': '200'})
        char = Char.objects.order_by('-id').first()
        self.assertIsNotNone(char, 'le build de test n a pas ete cree')
        return char

    def test_a_card_names_the_other_face_and_the_rule(self):
        char = self._char()
        page = self.client.get('/spells/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('variant_partner', page)
        self.assertIn('Shares a grimoire slot with', page)
        self.assertIn('A fight arms one of the two', page)

    def test_the_digest_carries_the_partner_of_a_real_pair(self):
        import json
        import re
        char = self._char()
        page = self.client.get('/spells/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        trouve = re.search(r'var spellDigests = (\[.*?\]);\s*\n', page, re.S)
        self.assertTrue(trouve, 'les cartes ne sont pas dans la page')
        digests = json.loads(trouve.group(1))
        nommes = [d for d in digests if d.get('variant_partner')]
        self.assertGreaterEqual(len(nommes), 20, len(digests))
        par_nom = {d['canonical']: d.get('variant_partner') for d in digests}
        self.assertEqual('Radiant Arrow', par_nom.get('Retreat Arrow'))
        self.assertEqual('Retreat Arrow', par_nom.get('Radiant Arrow'))

    def test_the_page_says_it_in_french_too(self):
        char = self._char()
        page = self.client.get('/spells/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE='fr'
                               ).content.decode('utf-8')
        self.assertIn('Partage une place de grimoire avec', page)
        self.assertIn('un tour porte l', page)

    def test_a_card_without_a_damage_table_names_its_partner(self):
        import json
        import re
        char = self._char()
        page = self.client.get('/spells/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        trouve = re.search(r'var spellDigests = (\[.*?\]);\s*\n', page, re.S)
        digests = json.loads(trouve.group(1))
        nommes = [d for d in digests if d.get('variant_partner')]
        self.assertGreaterEqual(len(nommes), 40, len(digests))
        sans_table = [d for d in nommes if not d.get('non_crit_dams')]
        self.assertTrue(sans_table)
        noms = {d['name'] for d in digests}
        for digest in nommes:
            self.assertIn(digest['variant_partner'], noms, digest['name'])
        par_nom = {d['canonical']: d.get('variant_partner') for d in digests}
        self.assertEqual('Burnt Pie', par_nom.get('Leek Pie'))
        self.assertEqual('Leek Pie', par_nom.get('Burnt Pie'))


class TheDofus2TurnArmsOneFaceTests(SimpleTestCase):

    def test_a_rogue_turn_never_casts_both_musket_and_shot_pellets(self):
        from unittest import mock
        from chardata.spell_combo import best_turn, castable_spells
        from fashionistapulp.structure import get_structure

        stats = {stat.key: 0
                 for stat in get_structure('dofus2').get_stats_list()}
        stats.update({'str': 400, 'int': 400, 'cha': 400, 'agi': 400,
                      'pow': 100, 'dam': 40})
        spells = castable_spells('Rogue', 200, 'dofus2')
        par_nom = {spell.name: spell for spell in spells}
        paire = {'Musket', 'Shot Pellets'}
        self.assertEqual(variant_of('dofus2', par_nom['Musket'].spell_id),
                         variant_of('dofus2', par_nom['Shot Pellets'].spell_id))
        _total, ordre = best_turn(stats, spells, 12, game_version='dofus2')
        armes = {nom for nom, _damage in ordre} & paire
        self.assertEqual(1, len(armes), ordre)
        with mock.patch('chardata.spell_combo.variant_of', return_value=None):
            _total, libre = best_turn(stats, spells, 12, game_version='dofus2')
        self.assertEqual(paire, {nom for nom, _damage in libre} & paire, libre)
