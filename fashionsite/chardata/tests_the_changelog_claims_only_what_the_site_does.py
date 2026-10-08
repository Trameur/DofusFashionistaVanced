# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The changelog names the big features, translated, and nothing else."""

import io
import os
import re

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

MOIS = 'September 2026'
NOUVEAU_MOIS = 'October 2026'
MOIS_GARDES = (NOUVEAU_MOIS, MOIS)
LANGUES = ('fr', 'es', 'pt', 'de')
TEMPLATE = os.path.join(settings.BASE_DIR, 'chardata', 'templates',
                        'chardata', 'changelog_content.html')
_TRANS = re.compile(r'\{%\s*trans\s+"((?:[^"\\]|\\.)*)"\s*%\}')
MAX_PUCES = 4
HIDSAD_BOW = 1355
CRICK_HAMMER = 6509


def _entrees():
    source = io.open(TEMPLATE, encoding='utf-8').read()
    entrees = []
    for bloc in source.split('<div class="cl-entry">')[1:]:
        chaines = _TRANS.findall(bloc)
        date, titre = chaines[0], chaines[2]
        puces = _TRANS.findall(bloc.split('<ul>', 1)[1])
        entrees.append((date, titre, puces))
    return entrees


def _catalogue(langue):
    chemin = os.path.join(settings.BASE_DIR, 'locale', langue, 'LC_MESSAGES',
                          'django.po')
    texte = io.open(chemin, encoding='utf-8').read()
    return dict(re.findall(r'\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"\n',
                           texte))


class TheSeptemberEntriesAreFewAndShortTests(SimpleTestCase):

    def test_three_entries_of_at_most_four_bullets(self):
        entrees = _entrees()
        self.assertEqual(NOUVEAU_MOIS, entrees[0][0])
        self.assertEqual(['Dofus 3.7 update', 'Weights and minimums on one page'],
                         [e[1] for e in entrees if e[0] == NOUVEAU_MOIS])
        self.assertEqual('Dofus 3.7 update', entrees[0][1])
        de_ce_mois = [e for e in entrees if e[0] == MOIS]
        self.assertEqual(4, len(de_ce_mois), [e[1] for e in de_ce_mois])
        self.assertEqual('A workshop that knows your stock', de_ce_mois[0][1])
        for _date, titre, puces in [e for e in entrees if e[0] in MOIS_GARDES]:
            self.assertLessEqual(len(puces), MAX_PUCES, titre)
            self.assertGreaterEqual(len(puces), 1, titre)

    def test_no_small_fix_is_sold_as_a_feature(self):
        interdits = ('fixed', 'renamed', 'no longer', 'not on an error page',
                     'privacy page', 'sidebar counter', 'search engines')
        for date, titre, puces in _entrees():
            if date not in MOIS_GARDES:
                continue
            for puce in puces:
                bas = puce.lower()
                for mot in interdits:
                    self.assertNotIn(mot, bas, (titre, puce))

    def test_no_third_party_site_is_named(self):
        for date, titre, puces in _entrees():
            if date not in MOIS_GARDES:
                continue
            for phrase in [titre] + puces:
                self.assertNotIn('dofusbook', phrase.lower(), phrase)


class TheSeptemberEntriesAreTranslatedTests(SimpleTestCase):

    def test_every_sentence_of_this_month_is_translated_natively(self):
        phrases = set()
        for date, titre, puces in _entrees():
            if date not in MOIS_GARDES:
                continue
            phrases.update([date, titre] + puces)
        self.assertGreaterEqual(len(phrases), 7)
        for langue in LANGUES:
            catalogue = _catalogue(langue)
            for phrase in phrases:
                cle = phrase.replace('"', '\\"')
                self.assertIn(cle, catalogue, (langue, phrase))
                msgstr = catalogue[cle]
                self.assertTrue(msgstr, (langue, phrase))
                if not (langue == 'de' and phrase == MOIS):
                    self.assertNotEqual(msgstr, cle, (langue, phrase))
                self.assertNotIn('\u2014', msgstr, (langue, phrase))
                self.assertNotIn('\u2013', msgstr, (langue, phrase))

    def test_the_dropped_sentences_left_the_catalogues(self):
        orphelines = ('The sidebar counter now says solver answers',
                      'From the encyclopedia to the solver',
                      'Icons back, policy honest',
                      'The privacy page names DofusBook')
        for langue in LANGUES + ('en',):
            catalogue = _catalogue(langue)
            for debut in orphelines:
                self.assertFalse(any(k.startswith(debut) for k in catalogue),
                                 (langue, debut))

    def test_the_english_catalogue_carries_the_ids(self):
        catalogue = _catalogue('en')
        self.assertIn(MOIS, catalogue)
        self.assertIn(NOUVEAU_MOIS, catalogue)
        self.assertIn('Your build, in and out', catalogue)


class TheClaimsPointAtThingsThatExistTests(TestCase):

    def _template(self, nom):
        chemin = os.path.join(settings.BASE_DIR, 'chardata', 'templates',
                              'chardata', nom)
        return io.open(chemin, encoding='utf-8').read()

    def test_the_workshop_keeps_stock_and_undoes_a_craft(self):
        page = self._template('workshop.html')
        self.assertIn('ws-search-input', page)
        self.assertIn('ws-chip', page)
        self.assertIn('ws-craft-btn', page)
        for name in ('workshop_set_stock', 'workshop_add', 'workshop_add_set',
                     'workshop_craft', 'workshop_uncraft'):
            args = [] if name in ('workshop_set_stock', 'workshop_add') else [1]
            self.assertTrue(reverse(name, args=args), name)
        self.assertIn('enc-workshop-add-form', self._template('encyclopedia_item.html'))
        self.assertIn('enc-workshop-add-set-btn', self._template('encyclopedia_set.html'))

    def test_the_import_reads_names_links_and_screenshots(self):
        page = self._template('text_build.html')
        self.assertIn('shot-file', page)
        self.assertIn('textarea', page)
        from chardata.dofusbook_import import read_build  # noqa: F401
        from chardata.text_build_import import read_items  # noqa: F401
        self.assertTrue(reverse('text_build_import'))

    def test_the_export_reaches_the_three_versions_named(self):
        from chardata.dofusbook_export import HOSTS
        self.assertEqual({'dofus3', 'touch', 'retro'}, set(HOSTS))
        self.assertIn("game_url 'dofusbook_export'", self._template('solution.html'))
        self.assertTrue(reverse('dofusbook_export', args=[1]))

    def test_the_solver_panel_says_what_the_entry_promises(self):
        solution = self._template('solution.html')
        self.assertIn('Proven optimum. The solver checked that no other legal '
                      'combination scores higher on your criteria.', solution)
        self.assertIn('Best set found in {{ limit }} seconds.', solution)
        self.assertIn('items were on offer after your exclusions.', solution)
        self.assertIn('They can be arranged into more than 10 to the power of',
                      solution)

    def test_the_verdict_really_travels(self):
        from chardata.solution_view import _build_share_text  # noqa: F401
        galerie = self._template('shared_builds.html')
        self.assertIn('Proven optimum', galerie)
        self.assertIn('Best found at the time limit, not a proof', galerie)
        from chardata import api_view
        source = io.open(api_view.__file__, encoding='utf-8').read()
        self.assertIn("'proven'", source)

    def test_the_item_and_set_pages_start_a_build(self):
        from chardata.coaching_view import included_item_for, included_set_for  # noqa
        self.assertIn('encyclopedia-build-around',
                      self._template('encyclopedia_item.html'))
        self.assertIn('encyclopedia-build-around-set',
                      self._template('encyclopedia_set.html'))
        self.assertTrue(reverse('quickstart'))

    def test_the_set_page_opens_weights_and_minimums(self):
        self.assertIn("game_url 'stats' char_id", self._template('solution.html'))

    def test_the_temporix_box_is_on_touch_builds_and_nowhere_else(self):
        self.assertIn('name="temporix"', self._template('options.html'))
        from fashionistapulp.dofus_constants import get_stat_maximum
        from fashionistapulp.game_versions import GAME_VERSIONS
        self.assertEqual({'touch'}, {key for key, version in GAME_VERSIONS.items()
                                     if version.temporix})
        uncapped = get_stat_maximum('touch', temporix=True)
        for stat_name in ('AP', 'MP', 'Range', 'Summon'):
            self.assertNotIn(stat_name, uncapped)

    def test_weights_and_minimums_share_a_page_the_sidebar_and_set_page_open(self):
        self.assertTrue(reverse('weights_mins_post', args=[1]))
        self.assertIn('wm-section', self._template('weights_minimums_block.html'))
        self.assertIn("game_url 'stats' char_id", self._template('base.html'))

    def test_a_build_copies_between_dofus3_and_the_beta(self):
        from fashionistapulp.game_versions import GAME_VERSIONS
        self.assertEqual(GAME_VERSIONS['dofus3'].family, GAME_VERSIONS['beta'].family)
        self.assertTrue(reverse('copy_to_version', args=[1]))
        self.assertIn('These pieces do not exist here and were left out',
                      self._template('main-header.html'))

    def test_the_site_runs_dofus3_on_the_3_7_data(self):
        import fashionista_version as ours
        self.assertTrue(ours.FASHIONISTA_VERSION.startswith('3.7.'))

    def test_a_strong_potion_moves_the_whole_neutral_roll_and_no_steal_or_heal(self):
        from fashionistapulp.dofus_constants import FIRE, NEUTRAL
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        rows = []
        for ankama_id in (HIDSAD_BOW, CRICK_HAMMER):
            weapon = structure.get_weapon_for_item(
                structure.get_item_by_ankama_id(ankama_id))
            rows += [((base.min_dam, base.max_dam, base.element,
                       bool(base.steals), bool(base.heals)),
                      (maged.min_dam, maged.max_dam, maged.element,
                       bool(maged.steals), bool(maged.heals)))
                     for base, maged in zip(weapon.base_hit,
                                            weapon.non_crit_hits[FIRE])]
        self.assertEqual({(False, False), (True, False), (False, True)},
                         {(base[3], base[4]) for base, _maged in rows
                          if base[2] == NEUTRAL})
        for base, maged in rows:
            kept = base[3] or base[4] or base[2] != NEUTRAL
            expected = base if kept else (base[0], base[1], FIRE, False, False)
            self.assertEqual(expected, maged)

    def test_each_build_chooses_its_potion_engraving_and_shard_on_the_weapon_card(self):
        from fashionistapulp import weapon_forge
        for kind in ('damage', 'steal', 'heal'):
            self.assertTrue(weapon_forge.offer('dofus3', kind), kind)
        self.assertIn('solution-weapon-forge-select', self._template('solution_item.html'))
        self.assertIn('/setweaponforge/', self._template('solution.html'))

    def test_a_trophy_that_limits_sets_allows_one_and_paints_a_second_red(self):
        from types import SimpleNamespace
        from chardata.solution_result import SetsEquippedConditionLine
        from fashionistapulp.model import Model
        from fashionistapulp.modelresult import ModelResult
        from fashionistapulp.structure import get_structure
        caps = {item.weird_conditions.get('sets_equipped')
                for item in get_structure('dofus3').get_items_list()
                if 'Trophy' in item.flags}
        self.assertIn(1, caps)
        self.assertTrue(callable(Model.create_sets_equipped_constraints))
        for sets, formatting in (([1], ''), ([1, 2], '#r')):
            result = SimpleNamespace(sets=sets)
            result.check_sets_equipped = ModelResult.check_sets_equipped.__get__(result)
            self.assertEqual(formatting,
                             SetsEquippedConditionLine(result, 1).formatting)
        self.assertIn("{% if '#r' in line.formatting %}solution-negative-stat-text",
                      self._template('solution_item.html'))

    def test_a_monster_page_shows_power_and_pushback_resistance(self):
        import sqlite3
        from chardata.official_site import get_monster_link
        from fashionistapulp.fashionista_config import get_items_db_path
        connection = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            row = connection.execute(
                "SELECT g.monster_ankama_id, n.name FROM monster_grades g"
                " JOIN monster_names n ON n.monster_ankama_id = g.monster_ankama_id"
                " WHERE g.push_damage_reduction < 0 AND g.percent_damage_bonus <> 0"
                " AND n.language = 'en' ORDER BY g.monster_ankama_id").fetchone()
        finally:
            connection.close()
        self.assertIsNotNone(row)
        response = self.client.get(get_monster_link(row[0], row[1]), follow=True)
        self.assertEqual(200, response.status_code)
        page = response.content.decode('utf-8')
        self.assertIn('<th>Power</th>', page)
        self.assertIn('<th>Pushback Resistance</th>', page)
