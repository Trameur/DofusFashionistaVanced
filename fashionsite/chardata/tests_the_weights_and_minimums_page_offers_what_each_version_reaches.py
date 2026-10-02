# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One page edits weights and minimums: its rows follow each version, its save keeps what it does not show."""
import json
import os
import pickle
import re
import subprocess
import tempfile
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.coaching_view import create_build
from chardata.min_stats import get_min_stats
from chardata.options import get_options, set_options
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.weights_minimums import minimum_keys
from fashionistapulp.structure import set_current_game_version

PREFIX = {'dofus3': '', 'beta': '/beta', 'dofus2': '/dofus2', 'touch': '/touch',
          'retro': '/retro'}
HERE = os.path.dirname(os.path.abspath(__file__))


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.scripts = []
        self._script = None

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == 'script':
            self._script = dict(attrs)
            self.scripts.append([self._script, ''])

    def handle_endtag(self, tag):
        if tag == 'script':
            self._script = None

    def handle_data(self, data):
        if self._script is not None:
            self.scripts[-1][1] += data


def _parse(html):
    parser = _Tags()
    parser.feed(html)
    parser.close()
    return parser


class EachVersionOffersTheMinimumsItsSolverCanReachTests(SimpleTestCase):

    def test_critical_failure_and_weapon_resist_are_offered_nowhere(self):
        for version in PREFIX:
            with self.subTest(version=version):
                keys = minimum_keys(version)
                self.assertNotIn('cf', keys)
                self.assertNotIn('resperwea', keys)
                self.assertIn('vit', keys)
                self.assertIn('hp', keys)

    def test_retro_keeps_the_minimums_wisdom_and_agility_reach(self):
        keys = minimum_keys('retro')
        for key in ('lock', 'dodge', 'apred', 'apres', 'mpred', 'mpres'):
            self.assertIn(key, keys)

    def test_touch_offers_only_its_own_pvp_resists(self):
        keys = minimum_keys('touch')
        self.assertIn('pvpwaterres', keys)
        self.assertIn('pvpairres', keys)
        self.assertNotIn('pvpneutres', keys)


class _PageMixin(object):
    version = 'dofus3'
    level = 200

    def setUp(self):
        set_current_game_version(self.version)
        self.owner = User.objects.create_user('wm-owner', 'wm@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Iop', self.level, {'str'}, self.version)

    def tearDown(self):
        set_current_game_version('dofus3')

    def url(self, path, language=''):
        return '%s%s/%s/%d/' % (language, PREFIX[self.version], path, self.char.pk)

    def page(self, path='stats', language=''):
        response = self.client.get(self.url(path, language))
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def post(self, data):
        response = self.client.post(self.url('weightsminspost'), data)
        self.assertEqual(200, response.status_code)
        self.char.refresh_from_db()
        return json.loads(response.content.decode('utf-8'))

    def inputs(self, html):
        return {attrs.get('id'): attrs for tag, attrs in _parse(html).tags
                if tag == 'input' and attrs.get('id', '').startswith(('weight_', 'min_'))}


class TheWeightsAndMinimumsPageTests(_PageMixin, TestCase):

    def test_both_old_addresses_open_the_page_with_their_own_focus(self):
        for path, focus in (('stats', 'weights'), ('min_stats', 'minimums')):
            forms = [attrs for tag, attrs in _parse(self.page(path)).tags
                     if tag == 'form' and attrs.get('id') == 'main_form']
            self.assertEqual(1, len(forms), path)
            self.assertEqual(focus, forms[0].get('data-focus'))
            self.assertIn('data-save-before-tailor', forms[0])

    def test_no_input_carries_a_number_the_template_wrote(self):
        for language in ('', '/fr'):
            for key, attrs in self.inputs(self.page(language=language)).items():
                self.assertNotIn('value', attrs, key)
                for name in ('max', 'min'):
                    if name in attrs:
                        self.assertRegex(attrs[name], r'^-?\d+$', (key, name))

    def test_the_state_reaches_the_script_as_json(self):
        weights = get_stats_weights(self.char)
        weights['vit'] = 1234
        set_stats_weights(self.char, weights)
        scripts = _parse(self.page(language='/fr')).scripts
        states = [json.loads(body) for attrs, body in scripts if attrs.get('id') == 'wm-state']
        self.assertEqual(1, len(states))
        self.assertEqual(1234, states[0]['weights']['vit'])
        defaults = [json.loads(body) for attrs, body in scripts
                    if attrs.get('id') == 'wm-defaults']
        self.assertEqual(1, len(defaults))
        self.assertIn('vit', defaults[0])
        self.assertNotIn('perres', defaults[0])

    def test_aggregates_and_the_derived_damage_post_nothing(self):
        inputs = self.inputs(self.page())
        self.assertNotIn('name', inputs['weight_perres'])
        self.assertNotIn('name', inputs['min_perres'])
        self.assertIn('disabled', inputs['weight_dam'])
        self.assertNotIn('name', inputs['weight_dam'])
        self.assertEqual('min_dam', inputs['min_dam']['name'])
        self.assertEqual('weight_vit', inputs['weight_vit']['name'])
        self.assertEqual('min_hp', inputs['min_hp']['name'])

    def test_ap_mp_and_range_show_the_version_cap(self):
        inputs = self.inputs(self.page())
        self.assertEqual('12', inputs['min_ap']['max'])
        self.assertEqual('6', inputs['min_mp']['max'])
        self.assertEqual('6', inputs['min_range']['max'])
        self.assertNotIn('min_cf', inputs)
        self.assertNotIn('min_resperwea', inputs)
        self.assertNotIn('weight_resperwea', inputs)

    def test_a_save_keeps_every_weight_and_minimum_it_is_not_sent(self):
        weights = get_stats_weights(self.char)
        weights.update({'hp': 33, 'meleeness': 7})
        set_stats_weights(self.char, weights)
        self.char.minimum_stats = pickle.dumps(dict(get_min_stats(self.char), **{
            'Wisdom': 400, 'Effective HP': 9000, 'adv_mins': {'Power + Strength': 800}}))
        self.char.save()
        self.post({'weight_str': '77', 'min_ap': '11'})
        stored = get_stats_weights(self.char)
        self.assertEqual(77, stored['str'])
        self.assertEqual(33, stored['hp'])
        self.assertEqual(7, stored['meleeness'])
        minimums = get_min_stats(self.char)
        self.assertEqual(11, minimums['AP'])
        self.assertEqual(400, minimums['Wisdom'])
        self.assertEqual(9000, minimums['Effective HP'])
        self.assertEqual({'Power + Strength': 800}, minimums['adv_mins'])

    def test_an_emptied_minimum_is_removed_and_a_typed_one_is_saved(self):
        self.char.minimum_stats = pickle.dumps({'Wisdom': 400, 'adv_mins': {}})
        self.char.save()
        state = self.post({'min_wis': ' ', 'min_powstr': '650', 'min_hp': '3000',
                           'min_ap': '14'})
        minimums = get_min_stats(self.char)
        self.assertNotIn('Wisdom', minimums)
        self.assertEqual(3000, minimums['HP'])
        self.assertEqual(12, minimums['AP'])
        self.assertEqual({'Power + Strength': 650}, minimums['adv_mins'])
        self.assertEqual('', state['minimums']['wis'])
        self.assertEqual(650, state['minimums']['powstr'])

    def test_a_reset_saves_the_build_defaults_under_what_was_typed(self):
        from chardata.presets import default_build_weights
        weights = get_stats_weights(self.char)
        weights.update({'vit': 999, 'str': 1})
        set_stats_weights(self.char, weights)
        self.post({'weights_reset': '1', 'weight_str': '55'})
        stored = get_stats_weights(self.char)
        self.assertEqual(int(default_build_weights(self.char)['vit']), stored['vit'])
        self.assertEqual(55, stored['str'])

    def test_a_reset_posting_every_box_saves_what_the_boxes_show(self):
        html = self.page()
        defaults = json.loads(re.search(
            r'<script[^>]*id="?wm-defaults"?[^>]*>(.*?)</script>', html, re.S).group(1))
        data = {'weights_reset': '1'}
        for attrs in self.inputs(html).values():
            if attrs.get('name', '').startswith('weight_'):
                data[attrs['name']] = str(defaults.get(attrs['name'][len('weight_'):], 0))
        self.assertGreater(len(data), 20)
        self.post(data)
        stored = get_stats_weights(self.char)
        for key, value in defaults.items():
            with self.subTest(key=key):
                self.assertEqual(value, round(stored[key]))

    def test_the_sidebar_leads_here_outside_more(self):
        html = self.page('options')
        start = html.index('id="menu-collapse"')
        collapse = html[start:html.index('id="advanced-button"', start)]
        self.assertNotIn('/stats/%d/' % self.char.pk, collapse)
        self.assertNotIn('/min_stats/%d/' % self.char.pk, collapse)
        links = [attrs for tag, attrs in _parse(html).tags
                 if tag == 'a' and attrs.get('href') == '/stats/%d/' % self.char.pk]
        self.assertEqual(1, len(links))

    def test_the_inline_script_and_the_page_script_parse(self):
        scripts = [body for attrs, body in _parse(self.page()).scripts
                   if 'src' not in attrs and attrs.get('type') != 'application/json'
                   and 'wmInit' in body]
        self.assertEqual(1, len(scripts))
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False,
                                         encoding='utf-8') as handle:
            handle.write(scripts[0])
            path = handle.name
        try:
            for source in (path, os.path.join(HERE, 'static', 'chardata', 'weights_minimums.js')):
                proc = subprocess.run(['node', '--check', source], capture_output=True, text=True)
                self.assertEqual(0, proc.returncode, proc.stderr[:400])
        finally:
            os.unlink(path)


class ALowLevelBuildGetsThePageTooTests(TheWeightsAndMinimumsPageTests):
    level = 20


class RetroOffersItsOwnRowsTests(_PageMixin, TestCase):
    version = 'retro'

    def test_retro_has_no_ap_cap_and_its_damage_takes_a_weight(self):
        inputs = self.inputs(self.page('min_stats'))
        self.assertNotIn('max', inputs['min_ap'])
        self.assertEqual('weight_dam', inputs['weight_dam']['name'])
        self.assertIn('min_lock', inputs)
        self.assertNotIn('weight_lock', inputs)
        self.post({'min_ap': '17'})
        self.assertEqual(17, get_min_stats(self.char)['AP'])

    def test_a_stored_minimum_this_version_cannot_reach_is_listed_apart(self):
        self.char.minimum_stats = pickle.dumps({'Critical Damage': 40, 'adv_mins': {}})
        self.char.save()
        html = self.page()
        self.assertIn('id="section-others"', html)
        self.assertEqual('min_cridam', self.inputs(html)['min_cridam']['name'])
        self.post({'min_cridam': ''})
        self.assertNotIn('Critical Damage', get_min_stats(self.char))


class TouchFollowsTemporixTests(_PageMixin, TestCase):
    version = 'touch'

    def test_temporix_lifts_the_cap_the_page_shows(self):
        self.assertEqual('12', self.inputs(self.page())['min_ap']['max'])
        options = get_options(self.char)
        options['temporix'] = True
        set_options(self.char, options)
        html = self.page()
        self.assertNotIn('max', self.inputs(html)['min_ap'])
        self.post({'min_ap': '14'})
        self.assertEqual(14, get_min_stats(self.char)['AP'])

    def test_touch_shows_its_pvp_weights_and_keeps_them_on_save(self):
        inputs = self.inputs(self.page())
        self.assertIn('weight_pvpwaterres', inputs)
        weights = get_stats_weights(self.char)
        weights['pvpwaterres'] = 21
        set_stats_weights(self.char, weights)
        self.post({'weight_str': '5'})
        self.assertEqual(21, get_stats_weights(self.char)['pvpwaterres'])
