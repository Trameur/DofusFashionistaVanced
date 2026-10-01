# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Numbers a guide takes from the item catalogue are read from the page version's own data."""

import pathlib
import re
import sqlite3

from django.test import SimpleTestCase

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
MODERN = ('dofus3', 'beta', 'dofus2')
TOKEN = re.compile(r'\[\[[^\]]*\]\]')

_LINES = ('SELECT COUNT(DISTINCT s.item) FROM stats_of_item s'
          ' JOIN stats st ON st.id = s.stat JOIN items i ON i.id = s.item'
          ' WHERE COALESCE(i.removed, 0) = 0 AND st.key = ? AND %s')
_BOTH = ('SELECT COUNT(*) FROM items i WHERE COALESCE(i.removed, 0) = 0'
         ' AND EXISTS (SELECT 1 FROM stats_of_item s JOIN stats st ON st.id = s.stat'
         ' WHERE s.item = i.id AND st.key = ? AND s.value > 0)'
         ' AND EXISTS (SELECT 1 FROM stats_of_item s JOIN stats st ON st.id = s.stat'
         ' WHERE s.item = i.id AND st.key = ? AND s.value > 0)')
_LARGEST = ('SELECT MAX(%s) FROM stats_of_item s JOIN stats st ON st.id = s.stat'
            ' JOIN items i ON i.id = s.item JOIN item_types t ON t.id = i.type'
            ' WHERE COALESCE(i.removed, 0) = 0 AND st.key = ? AND %s')
_TYPES = {'worn': "t.name NOT IN ('Dofus', 'Pet')", 'dofus': "t.name = 'Dofus'",
          'pet': "t.name = 'Pet'", 'nopet': "t.name != 'Pet'", 'all': '1 = 1'}


def _sql(version, query, *args):
    from fashionistapulp.fashionista_config import get_items_db_path
    uri = pathlib.Path(get_items_db_path(version)).as_uri() + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True)
    try:
        return connection.execute(query, args).fetchall()
    finally:
        connection.close()


def _render(text, version, language='en'):
    from chardata.guides_content import _fill_measured_numbers
    return _fill_measured_numbers(text, version, language)


def _plain(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def _page(slug, version, language):
    from chardata.guides_content import get_guide
    guide = get_guide(slug, language, version)
    return {field: _plain(guide[field]) for field in ('title', 'desc', 'lead', 'body')}


class TheCountsAreTheDatabasesOwnTests(SimpleTestCase):

    def test_each_count_matches_the_version_database(self):
        for version in MODERN:
            for stat in ('lock', 'dodge'):
                expected = {
                    stat: _sql(version, _LINES % 's.value != 0', stat)[0][0],
                    '-' + stat: _sql(version, _LINES % 's.value < 0', stat)[0][0],
                }
                for spec, count in expected.items():
                    with self.subTest(version=version, spec=spec):
                        self.assertGreater(count, 0)
                        self.assertEqual(str(count),
                                         _render('[[count:%s]]' % spec, version))
            with self.subTest(version=version, spec='lock+dodge'):
                both = _sql(version, _BOTH, 'lock', 'dodge')[0][0]
                self.assertEqual(str(both), _render('[[count:lock+dodge]]', version))

    def test_each_top_line_matches_the_version_database(self):
        for version in MODERN:
            for stat in ('lock', 'dodge'):
                for scope, where in _TYPES.items():
                    largest = _sql(version, _LARGEST % ('s.value', where), stat)[0][0]
                    with self.subTest(version=version, stat=stat, scope=scope):
                        self.assertEqual(str(largest),
                                         _render('[[top:%s:%s]]' % (stat, scope), version))
                loss = _sql(version, _LARGEST % ('-s.value', _TYPES['nopet']), stat)[0][0]
                with self.subTest(version=version, stat='-' + stat):
                    self.assertEqual(str(loss), _render('[[top:-%s:nopet]]' % stat, version))

    def test_the_beta_trophies_reach_40_lock_and_40_dodge(self):
        self.assertEqual('40', _render('[[top:lock:dofus]]', 'beta'))
        self.assertEqual('Major Stickler, Major Obstructor',
                         _render('[[top-names:lock:dofus]]', 'beta'))
        self.assertEqual('40', _render('[[top:dodge:dofus]]', 'beta'))
        self.assertEqual('Major Vagabond, Major Deserter, Ebony Dofus',
                         _render('[[top-names:dodge:dofus]]', 'beta'))

    def test_dofus_2_keeps_its_own_ceilings(self):
        self.assertEqual('25', _render('[[top:lock:worn]]', 'dofus2'))
        self.assertEqual('Crocoshield', _render('[[top-names:lock:worn]]', 'dofus2'))
        self.assertEqual('Ebony Dofus', _render('[[top-names:dodge:dofus]]', 'dofus2'))

    def test_the_names_are_ankamas_in_each_language(self):
        expected = {'en': 'Major Stickler', 'fr': 'Bloqueur majeur',
                    'es': 'Bloqueador mayor', 'pt': 'Bloqueador maior',
                    'de': 'Großer Blocker'}
        for language, name in expected.items():
            with self.subTest(language=language):
                self.assertIn(name, _render('[[top-names:lock:dofus]]', 'beta', language))

    def test_the_version_is_named_as_readers_know_it(self):
        expected = {'dofus3': 'Dofus 3', 'beta': 'Dofus 3 Beta', 'dofus2': 'Dofus 2',
                    'touch': 'Dofus Touch', 'retro': 'Dofus Retro'}
        french = dict(expected, beta='Dofus 3 Bêta', retro='Dofus Rétro')
        for version in expected:
            for language in LANGUAGES:
                name = (french if language == 'fr' else expected)[version]
                with self.subTest(version=version, language=language):
                    self.assertEqual(name, _render('[[version]]', version, language))

    def test_a_token_can_name_another_version(self):
        for version in MODERN:
            for stat in ('lock', 'dodge'):
                with self.subTest(version=version, stat=stat):
                    self.assertEqual(_render('[[top:%s:nopet]]' % stat, 'touch'),
                                     _render('[[top:%s:nopet:touch]]' % stat, version))
        self.assertEqual('Dofus Touch', _render('[[version:touch]]', 'dofus3'))

    def test_a_rebuilt_catalogue_is_read_again(self):
        from unittest import mock
        from chardata.guides_content import _stat_lines
        from fashionistapulp import structure as module
        first = _stat_lines('dofus2', 'lock')
        self.assertIs(module.get_structure('dofus2').get_item_by_id(first[0][0].id),
                      first[0][0])
        rebuilt = module.Structure('dofus2')
        with mock.patch.object(module, 'get_structure', return_value=rebuilt):
            again = _stat_lines('dofus2', 'lock')
        self.assertEqual(len(first), len(again))
        self.assertIs(rebuilt.get_item_by_id(again[0][0].id), again[0][0])
        self.assertIsNot(first[0][0], again[0][0])


class TheSentencesAroundTheNumbersStillHoldTests(SimpleTestCase):

    def _top(self, version, spec, scope):
        return int(_render('[[top:%s:%s]]' % (spec, scope), version))

    def test_pets_top_both_stats_at_one_value_above_every_other_line(self):
        for version in MODERN:
            with self.subTest(version=version):
                pets = self._top(version, 'lock', 'pet')
                self.assertEqual(pets, self._top(version, 'dodge', 'pet'))
                self.assertGreater(pets, self._top(version, 'lock', 'nopet'))
                self.assertGreater(pets, self._top(version, 'dodge', 'nopet'))

    def test_the_dofus_slots_carry_the_biggest_lines(self):
        for version in MODERN:
            for stat in ('lock', 'dodge'):
                with self.subTest(version=version, stat=stat):
                    self.assertGreaterEqual(self._top(version, stat, 'dofus'),
                                            self._top(version, stat, 'worn'))

    def test_the_biggest_loss_outweighs_any_gain(self):
        for version in MODERN:
            with self.subTest(version=version):
                loss = self._top(version, '-dodge', 'nopet')
                self.assertGreater(loss, self._top(version, 'dodge', 'nopet'))
                self.assertGreater(loss, self._top(version, 'dodge', 'pet'))


class TheLockAndDodgePagesSayTheirVersionsNumbersTests(SimpleTestCase):

    def test_every_page_shows_its_own_counts(self):
        for version in MODERN:
            counts = [_render('[[count:%s]]' % spec, version)
                      for spec in ('lock', 'dodge', '-dodge')]
            for language in LANGUAGES:
                name = _render('[[version]]', version, language)
                page = _page('lock-and-dodge', version, language)
                with self.subTest(version=version, language=language):
                    for count in counts:
                        self.assertRegex(page['desc'], r'\b%s\b' % count)
                        self.assertRegex(page['body'], r'\b%s\b' % count)
                    self.assertIn(name, page['desc'])
                    self.assertIn(name, page['body'])
                    self.assertNotIn('[!]', page['body'])
                    self.assertFalse(TOKEN.search(''.join(page.values())))

    def test_no_counter_stays_written_by_hand(self):
        from chardata.guides_content import GUIDES
        for group in ('modern', 'touch'):
            for language, block in GUIDES['lock-and-dodge']['i18n_by_group'][group].items():
                text = _plain(TOKEN.sub('', ' '.join(
                    block[field] for field in ('title', 'desc', 'lead', 'body'))))
                with self.subTest(group=group, language=language):
                    self.assertEqual(set(), set(re.findall(r'\d+', text)))

    def test_the_touch_warning_quotes_touchs_largest_line_outside_pets(self):
        tops = {stat: _sql('touch', _LARGEST % ('s.value', _TYPES['nopet']), stat)[0][0]
                for stat in ('lock', 'dodge')}
        pets = {stat: _sql('touch', _LARGEST % ('s.value', _TYPES['pet']), stat)[0][0]
                for stat in ('lock', 'dodge')}
        for stat in ('lock', 'dodge'):
            self.assertGreater(pets[stat], tops[stat])
        for version in MODERN:
            for language in LANGUAGES:
                body = _page('lock-and-dodge', version, language)['body']
                warning = body[body.index('Dofus Touch'):]
                with self.subTest(version=version, language=language):
                    self.assertEqual(['+%d' % tops['lock'], '+%d' % tops['dodge']],
                                     re.findall(r'\+\d+', warning)[:2])

    def test_retro_carries_no_lock_or_dodge_line_on_items_or_set_bonuses(self):
        for stat in ('lock', 'dodge'):
            with self.subTest(stat=stat):
                self.assertEqual(0, _sql('retro', _LINES % 's.value != 0', stat)[0][0])
                self.assertEqual(0, _sql('retro', 'SELECT COUNT(*) FROM set_bonus b'
                                                  ' JOIN stats st ON st.id = b.stat'
                                                  ' WHERE st.key = ? AND b.value != 0',
                                         stat)[0][0])
        self.assertTrue(_sql('retro', 'SELECT COUNT(*) FROM set_bonus')[0][0])

    def test_the_beta_page_no_longer_puts_dodge_above_lock(self):
        for language in LANGUAGES:
            body = _page('lock-and-dodge', 'beta', language)['body']
            own = body[:body.index('Dofus Touch')]
            with self.subTest(language=language):
                self.assertNotRegex(own, r'\+32\b')
                self.assertNotIn('Dodge reaches further', body)

    def test_the_old_hand_written_names_are_gone(self):
        stale = ('Majeur Colleur', 'Placador Mayor', 'Placador Maior',
                 'Großer Klammerer', 'Increvable', 'Indomable', 'Indomável',
                 'Unverwüstliche')
        for version in MODERN:
            for language in LANGUAGES:
                body = _page('lock-and-dodge', version, language)['body']
                for name in stale:
                    with self.subTest(version=version, language=language, name=name):
                        self.assertNotIn(name, body)


class TheTrophyLinesFollowTheVersionTests(SimpleTestCase):

    def _stats(self, version, ankama_id):
        return _sql(version, 'SELECT st.key, s.value FROM stats_of_item s'
                             ' JOIN stats st ON st.id = s.stat JOIN items i ON i.id = s.item'
                             ' WHERE i.ankama_id = ?', ankama_id)

    def test_each_line_of_the_trophy_reaches_the_sentence(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            for ankama_id in (12712, 12713):
                stats = self._stats(version, ankama_id)
                rendered = _render('[[lines:%d]]' % ankama_id, version)
                with self.subTest(version=version, ankama_id=ankama_id):
                    self.assertTrue(stats)
                    for _key, value in stats:
                        self.assertIn('+%d' % value, rendered)
                    self.assertEqual(len(stats), rendered.count('+'))

    def test_the_beta_acrobat_shows_its_critical_line(self):
        expected = {'en': '+15 Agility and +1% Critical', 'fr': '+15 Agilité et +1% Critique',
                    'es': '+15 Agilidad y +1 % crítico', 'pt': '+15 Agilidade e +1% de crítico',
                    'de': '+15 Flinkheit und +1% KT'}
        for language, text in expected.items():
            with self.subTest(language=language):
                self.assertEqual(text, _render('[[lines:12712]]', 'beta', language))

    def test_a_version_without_that_trophy_reads_the_default_versions(self):
        self.assertFalse(_sql('retro', "SELECT 1 FROM item_flags WHERE flag = 'Trophy'"))
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(_render('[[lines:12712]]', 'dofus3', language),
                                 _render('[[lines:12712]]', 'retro', language))


class TheTrophyConditionIsTheClientsTests(SimpleTestCase):

    LABELS = {'Pk': {'en': 'Set bonus', 'fr': 'Bonus de panoplies', 'es': 'Bonus de sets',
                     'pt': 'Bônus de conjuntos', 'de': 'Set-Bonus'},
              'pk': {'en': 'Number of sets equipped', 'fr': 'Nombre de panoplies équipées',
                     'es': 'Número de sets equipados', 'pt': 'Número de conjuntos equipados',
                     'de': 'Anzahl der ausgerüsteten Sets'}}

    def _criteria(self, version):
        found = set()
        for (criteria,) in _sql(version, 'SELECT criteria FROM item_criteria'):
            found.update(re.findall(r'\b(Pk|pk)<(\d+)', criteria or ''))
        return found

    def test_the_sentence_names_the_criterion_each_version_carries(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            criteria = self._criteria(version)
            self.assertEqual(1, len(criteria), (version, criteria))
            (code, limit), = criteria
            for language in LANGUAGES:
                rendered = _render('[[trophy-condition]]', version, language)
                with self.subTest(version=version, language=language):
                    self.assertIn('%s &lt; %s' % (self.LABELS[code][language], limit), rendered)

    def test_the_beta_counts_sets_equipped(self):
        self.assertEqual({('pk', '2')}, self._criteria('beta'))
        self.assertIn('Number of sets equipped &lt; 2', _render('[[trophy-condition]]', 'beta'))

    def test_only_trophies_carry_the_set_condition(self):
        from chardata.guides_content import _TROPHY_CONDITION
        from fashionistapulp.structure import get_structure
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            items = [item for item in get_structure(version).get_available_items_list()
                     if any(item.weird_conditions.get(kind) for kind in _TROPHY_CONDITION)]
            with self.subTest(version=version):
                self.assertTrue(items)
                self.assertEqual([], [item.name for item in items if 'Trophy' not in item.flags])

    def test_a_version_without_trophies_reads_the_default_versions(self):
        self.assertFalse(self._criteria('retro'))
        self.assertEqual(_render('[[trophy-condition]]', 'dofus3'),
                         _render('[[trophy-condition]]', 'retro'))


class TheTrophyGuidesDropTheirOldClaimsTests(SimpleTestCase):

    STALE = {
        'dofus-and-trophies': {'en': ('plain bonus', 'simply +15', 'doubles it',
                                      'instead of a drawback'),
                               'fr': ('bonus simple', '+15 Agilité, point', 'double la mise',
                                      'pas de malus mais une condition'),
                               'es': ('bonus simple', 'y ya está', 'dobla la apuesta',
                                      'no traen una penalización sino'),
                               'pt': ('bônus simples', 'e pronto', 'dobra a aposta',
                                      'não trazem penalidade, e sim'),
                               'de': ('schlichten Bonus', 'mehr nicht', 'verdoppelt das',
                                      'statt eines Malus')},
        'reading-an-item': {'en': ("won't stack with other set bonuses",),
                            'fr': ("ne s'empile pas avec d'autres bonus de panoplie",),
                            'es': ('no se acumula con otros bonus de panoplia',),
                            'pt': ('não acumula com outros bônus de conjunto',),
                            'de': ('nicht mit anderen Set-Boni stapelt',)},
    }

    def test_no_page_of_any_version_keeps_them(self):
        from fashionistapulp.game_versions import version_keys
        for slug, by_language in self.STALE.items():
            for version in version_keys():
                for language, phrases in by_language.items():
                    body = _page(slug, version, language)['body']
                    for phrase in phrases:
                        with self.subTest(slug=slug, version=version, language=language):
                            self.assertNotIn(phrase, body)

    def test_every_trophy_page_carries_a_resolved_condition(self):
        from fashionistapulp.game_versions import version_keys
        for version in version_keys():
            for language in LANGUAGES:
                body = _page('dofus-and-trophies', version, language)['body']
                with self.subTest(version=version, language=language):
                    self.assertFalse(TOKEN.search(body))
                    self.assertRegex(body, r'&lt; \d')


class NoGuideFieldShipsAToken(SimpleTestCase):

    def test_title_desc_lead_and_body_are_all_resolved(self):
        from chardata.guides_content import get_guide, list_guides, ordered_slugs
        from fashionistapulp.game_versions import version_keys
        seen = 0
        for version in version_keys():
            for language in LANGUAGES:
                for entry in list_guides(language, version):
                    self.assertFalse(TOKEN.search(entry['title'] + entry['desc']), entry['key'])
                for slug in ordered_slugs():
                    guide = get_guide(slug, language, version)
                    seen += 1
                    with self.subTest(slug=slug, version=version, language=language):
                        self.assertFalse(TOKEN.search(
                            guide['title'] + guide['desc'] + guide['lead'] + guide['body']))
        self.assertGreater(seen, 500)


class TheTouchLockAndDodgePageReadsTouchsCatalogueTests(SimpleTestCase):

    def _largest(self, version, column, scope, stat):
        return _sql(version, _LARGEST % (column, _TYPES[scope]), stat)[0][0]

    def test_every_count_and_ceiling_is_touchs_own(self):
        counts = [_sql('touch', _LINES % 's.value != 0', stat)[0][0] for stat in ('lock', 'dodge')]
        losses = [_sql('touch', _LINES % 's.value < 0', stat)[0][0] for stat in ('lock', 'dodge')]
        both = _sql('touch', _BOTH, 'lock', 'dodge')[0][0]
        ceilings = {(stat, scope): self._largest('touch', 's.value', scope, stat)
                    for stat in ('lock', 'dodge') for scope in ('worn', 'dofus', 'pet', 'nopet')}
        biggest_losses = [self._largest('touch', '-s.value', 'all', stat) for stat in ('lock', 'dodge')]
        for language in LANGUAGES:
            page = _page('lock-and-dodge', 'touch', language)
            with self.subTest(language=language):
                for count in counts:
                    self.assertRegex(page['desc'], r'\b%d\b' % count)
                    self.assertRegex(page['body'], r'\b%d\b' % count)
                for stat in ('lock', 'dodge'):
                    self.assertIn('+%d' % ceilings[stat, 'nopet'], page['desc'])
                    for scope in ('worn', 'dofus', 'pet'):
                        self.assertIn('+%d' % ceilings[stat, scope], page['body'])
                for number in losses + biggest_losses + [both]:
                    self.assertRegex(page['body'], r'\b%d\b' % number)
                self.assertFalse(TOKEN.search(''.join(page.values())))

    def test_the_sentences_around_touchs_numbers_hold(self):
        for stat in ('lock', 'dodge'):
            worn, dofus, pet = (self._largest('touch', 's.value', scope, stat)
                                for scope in ('worn', 'dofus', 'pet'))
            with self.subTest(stat=stat):
                self.assertGreater(pet, dofus)
                self.assertGreater(dofus, worn)
        self.assertLess(self._largest('touch', 's.value', 'worn', 'dodge'),
                        self._largest('dofus3', 's.value', 'worn', 'dodge'))

    def test_the_largest_dofus_slot_lines_are_trophies(self):
        from chardata.guides_content import _top
        for stat in ('lock', 'dodge'):
            pieces = _top('touch', stat, 'dofus')[1]
            with self.subTest(stat=stat):
                self.assertTrue(pieces)
                self.assertEqual([], [item.name for item in pieces if 'Trophy' not in item.flags])

    def test_the_trophy_quoted_cuts_both_ways_on_touch(self):
        lines = dict(_sql('touch', 'SELECT st.key, s.value FROM stats_of_item s'
                                   ' JOIN stats st ON st.id = s.stat JOIN items i ON i.id = s.item'
                                   ' WHERE i.ankama_id = 13750 AND COALESCE(i.removed, 0) = 0'))
        self.assertGreater(lines['lock'], 0)
        self.assertLess(lines['dodge'], 0)
        for language in LANGUAGES:
            body = _page('lock-and-dodge', 'touch', language)['body']
            with self.subTest(language=language):
                self.assertIn(_render('[[lines:13750]]', 'touch', language), body)

    def test_the_lead_compares_worn_gear_in_every_language(self):
        worn = {'en': 'worn', 'fr': 'porté', 'es': 'puesto', 'pt': 'vestido', 'de': 'getragen'}
        for language, word in worn.items():
            lead = _page('lock-and-dodge', 'touch', language)['lead']
            with self.subTest(language=language):
                self.assertIn(word, lead.split('Dofus 3')[0])

    def test_the_dofus_3_comparison_quotes_dofus_3s_worn_dodge(self):
        dofus3 = self._largest('dofus3', 's.value', 'worn', 'dodge')
        for language in LANGUAGES:
            body = _page('lock-and-dodge', 'touch', language)['body']
            with self.subTest(language=language):
                self.assertIn('Dofus 3', body)
                self.assertIn('+%d' % dofus3, body)


class TheTackleWordsAreTheSitesLockLabelTests(SimpleTestCase):

    STALE = re.compile(r'(?i)placag|placad|placar\b|fessel')

    def test_every_lock_and_dodge_page_uses_the_sites_lock_label(self):
        from django.utils import translation
        from chardata.translation_util import localized_stat_name
        from fashionistapulp.game_versions import version_keys
        for version in version_keys():
            for language in ('pt', 'de'):
                with translation.override(language):
                    word = str(localized_stat_name('Lock', version))
                text = ' '.join(_page('lock-and-dodge', version, language).values())
                with self.subTest(version=version, language=language):
                    self.assertIn(word, ('Bloqueio', 'Blocken'))
                    self.assertIn(word.lower(), text.lower())
                    self.assertNotRegex(text, self.STALE)

    def test_the_addresses_keep_their_slugs(self):
        from chardata.guides_content import resolve_slug, slug_for
        for language, slug in (('pt', 'placagem-e-fuga'), ('de', 'fesseln-und-ausweichen')):
            with self.subTest(language=language):
                self.assertEqual(slug, slug_for('lock-and-dodge', language))
                self.assertEqual(('lock-and-dodge', language), resolve_slug(slug))


class TheTrophyPageNamesOnlyWhatEachVersionCarriesTests(SimpleTestCase):

    PIECES = (12712, 12713, 13748, 13829, 7043, 7115, 22018)
    WITH_TROPHIES = ('dofus3', 'beta', 'dofus2', 'touch')

    def _lines(self, version, ankama_id):
        return _sql(version, 'SELECT st.key, s.value FROM stats_of_item s'
                             ' JOIN stats st ON st.id = s.stat JOIN items i ON i.id = s.item'
                             ' WHERE i.ankama_id = ? AND COALESCE(i.removed, 0) = 0'
                             ' AND s.value != 0', ankama_id)

    def _slot_values(self, version, ankama_id):
        """Sorted line values of the piece in the version's Dofus slot, None when the slot has no such piece."""
        rows = _sql(version, 'SELECT s.value FROM items i JOIN item_types t ON t.id = i.type'
                             ' LEFT JOIN stats_of_item s ON s.item = i.id'
                             " WHERE i.ankama_id = ? AND t.name = 'Dofus'"
                             ' AND COALESCE(i.removed, 0) = 0', ankama_id)
        if not rows:
            return None
        return sorted(int(round(value)) for (value,) in rows if value)

    @staticmethod
    def _name(version, ankama_id, language):
        from fashionistapulp.structure import get_structure
        structure = get_structure(version)
        return structure.get_item_name_in_language(
            structure.get_item_by_ankama_id(ankama_id), language)

    @staticmethod
    def _values(text):
        return sorted(int(number) for number in re.findall(r'[+-]\d+', text))

    @staticmethod
    def _names(text, version, language):
        from chardata.guides_content import _version_name
        return re.search(re.escape(_version_name(version, language)) + r'(?!\s*B[eê]ta)',
                         _plain(text))

    def _pry_count(self, version, with_lines):
        return _sql(version, 'SELECT COUNT(*) FROM items i JOIN item_types t ON t.id = i.type'
                             " WHERE t.name = 'Dofus' AND i.name LIKE '%%pry%%'"
                             ' AND COALESCE(i.removed, 0) = 0 AND %s'
                             ' (SELECT 1 FROM stats_of_item s WHERE s.item = i.id AND s.value != 0)'
                             % ('EXISTS' if with_lines else 'NOT EXISTS'))[0][0]

    def test_each_piece_shows_its_own_versions_lines_or_is_left_out(self):
        for version in self.WITH_TROPHIES:
            for ankama_id in self.PIECES:
                values = self._slot_values(version, ankama_id)
                for language in LANGUAGES:
                    body = _page('dofus-and-trophies', version, language)['body']
                    with self.subTest(version=version, piece=ankama_id, language=language):
                        if values is None:
                            name = self._name('dofus3', ankama_id, language)
                            self.assertTrue(name)
                            self.assertNotIn(name, body)
                            continue
                        name = self._name(version, ankama_id, language)
                        self.assertTrue(name)
                        self.assertIn(name, body)
                        rendered = _render('[[lines:%d]]' % ankama_id, version, language)
                        self.assertEqual(values, self._values(rendered))
                        if values:
                            self.assertIn(rendered, body)

    def test_lines_from_another_version_sit_in_a_section_that_names_it(self):
        from chardata.guides_content import get_guide
        from fashionistapulp.game_versions import version_keys
        versions = list(version_keys())
        own = quoted = 0
        for version in versions:
            for language in LANGUAGES:
                sections = get_guide('dofus-and-trophies', language, version)['body'].split('<h2')
                for ankama_id in self.PIECES:
                    shown = _render('[[lines:%d]]' % ankama_id, version, language)
                    if not shown:
                        continue
                    values = self._values(shown)
                    holding = [section for section in sections if shown in section]
                    with self.subTest(version=version, piece=ankama_id, language=language):
                        self.assertTrue(holding)
                        if values == self._slot_values(version, ankama_id):
                            own += 1
                            continue
                        sources = [other for other in versions if other != version
                                   and self._slot_values(other, ankama_id) == values]
                        self.assertTrue(sources)
                        for section in holding:
                            self.assertTrue(any(self._names(section, other, language)
                                                for other in sources))
                        quoted += 1
        self.assertGreater(own, 0)
        self.assertGreater(quoted, 0)

    def test_the_retro_page_quotes_dofus_3_and_names_it(self):
        self.assertEqual([2], self._slot_values('retro', 7115))
        self.assertIsNone(self._slot_values('retro', 12712))
        for language in LANGUAGES:
            body = _page('dofus-and-trophies', 'retro', language)['body']
            with self.subTest(language=language):
                self.assertIn(_render('[[lines:7115]]', 'dofus3', language), body)
                self.assertTrue(self._names(body, 'dofus3', language))

    def test_a_prysmaradite_without_lines_is_named_without_lines(self):
        self.assertEqual([], self._slot_values('dofus2', 22018))
        for version in self.WITH_TROPHIES:
            if self._slot_values(version, 22018) != []:
                continue
            with self.subTest(version=version):
                self.assertGreater(self._pry_count(version, with_lines=False), 0)
                self.assertEqual(0, self._pry_count(version, with_lines=True))
            from fashionistapulp.structure import get_structure
            level = get_structure(version).get_item_by_ankama_id(22018).level
            for language in LANGUAGES:
                body = _page('dofus-and-trophies', version, language)['body']
                name = self._name(version, 22018, language)
                with self.subTest(version=version, language=language):
                    self.assertTrue(name)
                    self.assertRegex(body, r'%s \(\D+ %d\)' % (re.escape(name), level))

    def test_the_sentences_around_the_pieces_hold(self):
        from fashionistapulp.structure import get_structure
        for version in self.WITH_TROPHIES:
            structure = get_structure(version)

            def lines(item):
                return [(structure.get_stat_by_id(stat).key, value)
                        for stat, value in item.stats if value]

            def losses(item):
                return [value for _key, value in lines(item) if value < 0]

            def shape(item):
                return sorted((key, value > 0) for key, value in lines(item))

            trophies = [item for item in structure.get_available_items_list()
                        if 'Trophy' in item.flags]
            piece = {ankama_id: structure.get_item_by_ankama_id(ankama_id)
                     for ankama_id in self.PIECES}
            with self.subTest(version=version):
                for ankama_id in (12712, 12713):
                    self.assertTrue(lines(piece[ankama_id]))
                    self.assertEqual([], losses(piece[ankama_id]))
                for ankama_id in (13748, 13829):
                    self.assertTrue(losses(piece[ankama_id]))
                    family = [item for item in trophies if shape(item) == shape(piece[ankama_id])]
                    self.assertEqual(piece[ankama_id].level, min(item.level for item in family))
                tiers = sorted((item for item in trophies if shape(item) == shape(piece[13748])),
                               key=lambda item: item.level)
                self.assertGreater(len(tiers), 1)
                taken = [-sum(losses(item)) for item in tiers]
                self.assertEqual(sorted(set(taken)), taken)
                for ankama_id in (7115, 7043):
                    if piece[ankama_id] is None:
                        continue
                    self.assertGreater(len(lines(piece[ankama_id])), 1)
                    self.assertEqual([], losses(piece[ankama_id]))
                if self._slot_values(version, 22018):
                    self.assertTrue(losses(piece[22018]))

    def test_the_ice_dofus_line_differs_where_the_data_does(self):
        self.assertEqual({25}, {value for _key, value in self._lines('dofus3', 7043)})
        self.assertEqual({20}, {value for _key, value in self._lines('touch', 7043)})
        self.assertNotIn('+25', _render('[[lines:7043]]', 'touch'))

    def test_the_slot_counts_written_in_words_still_hold(self):
        from fashionistapulp.structure import get_structure

        def slot(version):
            structure = get_structure(version)
            return [item for item in structure.get_available_items_list()
                    if structure.get_type_name_by_id(item.type) == 'Dofus']

        for version in ('dofus3', 'beta', 'dofus2'):
            pieces = slot(version)
            with self.subTest(version=version):
                self.assertGreater(len(pieces), 300)
                self.assertTrue([item for item in pieces if 'pry' in item.name.lower()])
        touch = slot('touch')
        self.assertTrue([item for item in touch if 'Trophy' in item.flags])
        self.assertTrue([item for item in touch if 'Trophy' not in item.flags])
        self.assertEqual([], [item.name for item in touch if 'pry' in item.name.lower()])
        retro = slot('retro')
        self.assertEqual(17, len(retro))
        self.assertEqual(12, len([item for item in retro if item.level == 6]))
        self.assertEqual([], [item.name for item in retro if 'Trophy' in item.flags])


class TheSpellCountFollowsTheSpellTableTests(SimpleTestCase):

    def test_the_differing_names_are_counted_again_on_a_new_table(self):
        from types import SimpleNamespace
        from unittest import mock
        from chardata import guides_content, spell_buffs

        def spells(*names):
            return [SimpleNamespace(name=name) for name in names]

        dofus3, dofus2 = {'Iop': spells('a', 'b')}, {'Iop': spells('a')}
        tables = {'dofus3': dofus3, 'dofus2': dofus2}
        with mock.patch.dict(guides_content._DIFFERING_COUNT, clear=True), \
                mock.patch.object(spell_buffs, 'get_damage_spells_for_version',
                                  side_effect=lambda version: tables[version]):
            self.assertEqual(1, guides_content._differing_spell_names())
            dofus3['Iop'].extend(spells('c'))
            self.assertEqual(1, guides_content._differing_spell_names())
            tables['dofus2'] = {'Iop': spells('a', 'x', 'y')}
            self.assertEqual(4, guides_content._differing_spell_names())
            tables['dofus3'] = {'Iop': spells('a')}
            self.assertEqual(2, guides_content._differing_spell_names())

    def test_a_new_spell_table_is_counted_again(self):
        from unittest import mock
        from chardata import guides_content, spell_combo
        first, second = object(), object()

        def count(table, castable):
            with mock.patch.object(spell_combo, 'get_damage_spells_for_version',
                                   return_value=table), \
                    mock.patch.object(spell_combo, 'castable_spells', return_value=castable):
                return guides_content._usable_spell_count('Iop', 'dofus2')

        with mock.patch.dict(guides_content._SPELL_COUNTS, clear=True):
            self.assertEqual(2, count(first, ['a', 'b']))
            self.assertEqual(2, count(first, ['a', 'b', 'c']))
            self.assertEqual(3, count(second, ['a', 'b', 'c']))

    def test_the_count_leaves_the_game_version_as_it_found_it(self):
        from unittest import mock
        from chardata import guides_content, spell_combo
        from fashionistapulp.structure import (get_current_game_version,
                                               set_current_game_version)
        before = get_current_game_version()
        try:
            set_current_game_version('dofus3')
            with mock.patch.dict(guides_content._SPELL_COUNTS, clear=True):
                self.assertGreater(guides_content._usable_spell_count('Iop', 'retro'), 0)
                self.assertEqual('dofus3', get_current_game_version())
                with mock.patch.object(spell_combo, 'castable_spells',
                                       side_effect=RuntimeError):
                    guides_content._SPELL_COUNTS.clear()
                    with self.assertRaises(RuntimeError):
                        guides_content._usable_spell_count('Iop', 'retro')
                self.assertEqual('dofus3', get_current_game_version())
        finally:
            set_current_game_version(before)


class NoGuideSaysTheBetaClosesTests(SimpleTestCase):

    BETA = re.compile(r'(?i)\bb[eê]ta\b')
    CLOSING = re.compile(
        r'(?i)\b(clos(e|es|ed|ing)|shut\w*|disappear\w*|vanish\w*|wiped?|temporar\w*'
        r'|end(s|ed|ing)?|(is|be|are) over(?![ \w])|stop(s|ped)?'
        r'|ferm\w*|dispara\w*|supprim\w*|cierr\w*|cerrar\w*|desaparec\w*|temporal\w*'
        r'|fin|termin\w*|arr[eê]t\w*|acab\w*|encerr\w*'
        r'|fech\w*|tempor[aá]ri\w*|schlie[sß]\w*|verschwind\w*|eingestellt'
        r'|(be)?endet|vor[uü]bergehend\w*)\b')

    def _closing_sentences(self, html):
        return [sentence for block in re.split(r'</?(?:h\d|p|li|ul|ol)\b[^>]*>', html)
                for sentence in re.split(r'(?<=[.!?:;])\s', _plain(block).strip())
                if self.BETA.search(sentence) and self.CLOSING.search(sentence)]

    def test_the_guard_catches_a_closing_sentence_in_each_language(self):
        for sentence in ('The Beta closes next month.', 'The beta will disappear.',
                         'The beta ends on Monday.', 'The beta is over.',
                         'La bêta fermera bientôt.', 'La bêta se termine lundi.',
                         'Fin de la bêta lundi.', 'La beta cierra pronto.',
                         'La beta termina el lunes.', 'O Beta fecha em breve.',
                         'O beta encerra na segunda.', 'Die Beta schließt bald.',
                         'Die Beta verschwindet.', 'Die Beta endet am Montag.'):
            with self.subTest(sentence=sentence):
                self.assertEqual([sentence], self._closing_sentences(sentence))

    def test_no_guide_page_says_the_beta_closes_or_disappears(self):
        from chardata.guides_content import get_guide, ordered_slugs
        from fashionistapulp.game_versions import version_keys
        for version in version_keys():
            for language in LANGUAGES:
                for slug in ordered_slugs():
                    guide = get_guide(slug, language, version)
                    html = '<p>'.join(guide[field] for field in ('title', 'desc', 'lead', 'body'))
                    with self.subTest(slug=slug, version=version, language=language):
                        self.assertEqual([], self._closing_sentences(html))
