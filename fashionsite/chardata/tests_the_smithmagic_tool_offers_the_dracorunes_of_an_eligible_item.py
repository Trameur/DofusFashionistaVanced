# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Beta smithmagic tool previews the Dracorunes of an eligible item on the lines the player targets, by the same rune module and the same label as the build card."""
import json
import re

from django.test import TestCase

from chardata.dracorune_fixtures import eligible_items, runes, structure
from chardata.forgemagie_view import DRACORUNE_UI, _dracorune_text
from chardata.solution_result import dracorune_change_label
from fashionistapulp import dracorunes
from fashionistapulp.structure import set_current_game_version

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
LINES = {'str': 100, 'earthdam': 10, 'cha': 50, 'waterdam': 5}


def config_of(html):
    found = re.search(r'id="fm-config" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(found.group(1))


class TheSmithmagicToolOffersTheDracorunesOfAnEligibleItemTests(TestCase):

    def setUp(self):
        set_current_game_version('beta')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.hat = next(eligible_items('Hat'))

    def ask(self, lines, language='en', item=None, extra=()):
        parameters = [('item', (item or self.hat).id)]
        parameters += [('line', '%s:%s' % pair) for pair in lines.items()]
        parameters += list(extra)
        return self.client.get('/beta/forgemagie/dracorunes/', parameters, HTTP_ACCEPT_LANGUAGE=language).json()

    def computed(self, lines):
        return dict(dracorunes.variants(list(lines.items()), runes()))

    def test_the_endpoint_returns_the_variants_the_rune_module_computes_for_the_posted_lines(self):
        data = self.ask(LINES)
        computed = self.computed(LINES)
        self.assertTrue(data['eligible'])
        self.assertEqual(list(computed), [variant['key'] for variant in data['variants']])
        for variant in data['variants']:
            after = dict(computed[variant['key']])
            self.assertEqual({key: value for key, value in after.items() if value},
                             {line['key']: line['after'] for line in variant['lines'] if line['after']})
            for line in variant['lines']:
                self.assertEqual(LINES.get(line['key'], 0), line['before'])
                self.assertEqual(after.get(line['key'], 0), line['after'])

    def test_each_variant_label_is_the_label_of_the_build_card(self):
        computed = self.computed(LINES)
        for variant in self.ask(LINES)['variants']:
            rune = dracorunes.rune_of(variant['key'], runes())
            expected = dracorune_change_label(dracorunes.rune_name(rune, 'en'), LINES, dict(computed[variant['key']]))
            self.assertEqual(expected, variant['label'])

    def test_a_lower_target_changes_the_power_line_the_rune_module_gives(self):
        for strength in (100, 50):
            lines = {'str': strength}
            power = next(variant for variant in self.ask(lines)['variants'] if variant['key'] == 'power')
            self.assertEqual(dict(self.computed(lines)['power'])[dracorunes.POWER_LINE],
                             next(line['after'] for line in power['lines'] if line['key'] == dracorunes.POWER_LINE))
        self.assertNotEqual(self.computed({'str': 100})['power'], self.computed({'str': 50})['power'])

    def test_a_line_the_item_already_has_removes_the_runes_that_aim_at_its_element(self):
        keys = [variant['key'] for variant in self.ask({'str': 100, 'agi': 10})['variants']]
        self.assertTrue(keys)
        self.assertFalse([key for key in keys if key.endswith('>agi')])
        self.assertTrue([key for key in [variant['key'] for variant in self.ask({'str': 100})['variants']]
                         if key.endswith('>agi')])

    def test_an_item_type_the_runes_file_leaves_out_is_not_eligible(self):
        found = structure()
        shield = next(item for item in found.get_available_items_list()
                      if found.get_type_name_by_id(item.type) == 'Shield')
        self.assertEqual({'eligible': False, 'variants': []}, self.ask(LINES, item=shield))

    def test_an_unknown_item_or_none_is_not_eligible(self):
        self.assertEqual({'eligible': False, 'variants': []},
                         self.client.get('/beta/forgemagie/dracorunes/', {'item': 'x'}).json())
        self.assertEqual({'eligible': False, 'variants': []},
                         self.client.get('/beta/forgemagie/dracorunes/', {'item': 987654321}).json())

    def test_an_unknown_key_or_a_value_that_is_not_a_number_is_ignored(self):
        clean = self.ask({'str': 100})
        noisy = self.ask({'str': 100}, extra=[('line', 'nokey:5'), ('line', 'agi:abc'), ('line', 'int:1.5'),
                                              ('line', 'cha'), ('line', ':7'), ('line', 'earthdam:')])
        self.assertEqual(clean, noisy)

    def test_only_the_first_forty_lines_are_read(self):
        extra = [('line', 'str:1')] * 45 + [('line', 'cha:7')]
        data = self.ask({}, extra=extra)
        self.assertTrue(data['variants'])
        self.assertNotIn(7, [line['before'] for variant in data['variants'] for line in variant['lines']])

    def test_the_beta_page_carries_the_block_and_the_endpoint_url(self):
        html = self.client.get('/beta/forgemagie/', {'item': self.hat.id}).content.decode('utf-8')
        for marker in ('id="fm-draco"', 'id="fm-draco-select"', 'id="fm-draco-preview-label"',
                       'id="fm-draco-label"'):
            self.assertEqual(1, html.count(marker), marker)
        self.assertEqual('/beta/forgemagie/dracorunes/', config_of(html)['dracorunes']['url'])

    def test_the_option_labels_carry_the_game_rune_name_in_each_of_the_five_languages(self):
        for language in LANGUAGES:
            variants = self.ask(LINES, language)['variants']
            self.assertTrue(variants, language)
            for variant in variants:
                rune = dracorunes.rune_of(variant['key'], runes())
                self.assertIn(rune['names'][language], variant['label'], (language, variant['key']))

    def test_the_rune_named_by_the_link_is_preselected_only_when_the_item_offers_it(self):
        from fashionistapulp import dracorune_terms
        found = structure()
        item = next(one for one in eligible_items('Hat') if dracorune_terms.item_variants(one, runes(), found))
        key = dracorune_terms.item_variants(item, runes(), found)[0].key
        offered = config_of(self.client.get('/beta/forgemagie/', {'item': item.id, 'dracorune': key})
                            .content.decode('utf-8'))
        self.assertEqual(key, offered['preload']['dracorune'])
        for asked in ('element:str>nothing', 'power;', ''):
            refused = config_of(self.client.get('/beta/forgemagie/', {'item': item.id, 'dracorune': asked})
                                .content.decode('utf-8'))
            self.assertNotIn('dracorune', refused['preload'])
        shield = next(one for one in found.get_available_items_list() if found.get_type_name_by_id(one.type) == 'Shield')
        other = config_of(self.client.get('/beta/forgemagie/', {'item': shield.id, 'dracorune': key})
                          .content.decode('utf-8'))
        self.assertNotIn('dracorune', other['preload'])

    def test_the_note_names_each_assumption_the_runes_file_marks_unverified(self):
        file = runes()
        for language in LANGUAGES:
            text = _dracorune_text(language, file, structure())['unverified']
            texts = DRACORUNE_UI[language]
            self.assertTrue(text, language)
            self.assertNotIn('%', text)
            self.assertIn(texts['rounding_%s' % file['rounding']].split('%')[0], text)
            self.assertIn(dracorunes.rune_name(dracorunes.rune_of('power', file), language), text)

    def test_the_note_is_empty_when_nothing_is_unverified(self):
        sure = dict(runes(), unverified=[])
        self.assertEqual('', _dracorune_text('en', sure, structure())['unverified'])

    def test_every_rounding_mode_and_neutral_assumption_has_a_phrase_in_every_language(self):
        file = runes()
        for language in LANGUAGES:
            texts = DRACORUNE_UI[language]
            for mode in dracorunes._ROUNDINGS:
                self.assertIn('rounding_%s' % mode, texts, language)
            for flag in ('true', 'false'):
                self.assertIn('neutral_%s' % flag, texts, language)
            seen = set()
            for mode in dracorunes._ROUNDINGS:
                for neutral in (False, True):
                    note = _dracorune_text(language, dict(file, rounding=mode, power_takes_neutral=neutral,
                                                          unverified=['rounding', 'power_takes_neutral']),
                                           structure())['unverified']
                    self.assertTrue(note)
                    seen.add(note)
            self.assertEqual(len(dracorunes._ROUNDINGS) * 2, len(seen), language)

    def test_a_line_posted_at_zero_removes_the_runes_that_aim_at_its_element(self):
        keys = [variant['key'] for variant in self.ask({'str': 40, 'agi': 0})['variants']]
        self.assertTrue(keys)
        self.assertFalse([key for key in keys if key.endswith('>agi')])
        self.assertTrue([variant['key'] for variant in self.ask({'str': 40})['variants']
                         if variant['key'].endswith('>agi')])

    def test_the_page_script_posts_every_line_that_is_not_an_exo_even_at_zero(self):
        html = self.client.get('/beta/forgemagie/', {'item': self.hat.id}).content.decode('utf-8')
        body = html[html.index('function dracoFetch'):]
        body = body[:body.index('fetch(url')]
        self.assertIn('parseInt(row.target, 10) || 0', body)
        self.assertIn('value || !row.exo', body)

    def test_a_runes_file_with_two_conflicting_runes_of_one_kind_offers_nothing_instead_of_failing(self):
        from unittest import mock
        file = runes()
        power = dracorunes.rune_of('power', file)
        twin = dict(power, keep=0.5, item_id=power['item_id'] + 1)
        conflicting = dict(file, runes=list(file['runes']) + [twin])
        with mock.patch('chardata.forgemagie_view.readable_runes', return_value=conflicting):
            response = self.client.get('/beta/forgemagie/dracorunes/',
                                       [('item', self.hat.id), ('line', 'str:100')])
        self.assertEqual(200, response.status_code)
        self.assertEqual({'eligible': False, 'variants': []}, response.json())

    def test_the_note_discloses_that_an_exo_line_blocking_a_rune_is_unconfirmed(self):
        file = runes()
        self.assertIn('exo_blocks', file['unverified'])
        for language in LANGUAGES:
            phrase = DRACORUNE_UI[language]['exo_blocks']
            self.assertIn(phrase, _dracorune_text(language, file, structure())['unverified'], language)
        shown = _dracorune_text('fr', file, structure())['unverified']
        self.assertIn('\u00a0; ', shown)

    def test_a_percent_sign_in_the_rules_sticks_to_its_number_in_every_language(self):
        for language in LANGUAGES:
            for rule in _dracorune_text(language, runes(), structure())['rules']:
                self.assertNotRegex(rule, r'\d %', (language, rule))

    def test_the_power_rule_names_the_game_keep_rate_and_the_rune_names(self):
        file = runes()
        power = dracorunes.rune_of('power', file)
        for language in LANGUAGES:
            rules = _dracorune_text(language, file, structure())['rules']
            ebony = next(rule for rule in rules if dracorunes.rune_name(power, language) in rule)
            self.assertIn('70', ebony)
            self.assertEqual(8, len(rules))

    def test_a_rule_whose_rune_kind_the_file_lacks_is_dropped(self):
        file = dict(runes(), runes=[rune for rune in runes()['runes'] if rune['kind'] != 'power'])
        self.assertEqual(7, len(_dracorune_text('en', file, structure())['rules']))

    def test_the_reference_card_lists_every_rune_with_its_game_text(self):
        html = self.client.get('/beta/forgemagie/').content.decode('utf-8')
        card = html[html.index('id="fm-draco-label"'):]
        card = card[:card.index('</table>')]
        self.assertEqual(len(runes()['runes']), card.count('<tr><td>'))
        for rune in runes()['runes']:
            self.assertIn(rune['names']['en'], card)
            self.assertIn(dracorunes.rune_description(rune, 'en').split('\n')[0], card)
