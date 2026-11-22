# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Discard on the options page puts back the item source and the disabled Dofus the saved state names."""
import io
import json
import os
import shutil
import subprocess

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.coaching_view import create_build
from chardata.models import InventoryFolder
from chardata.options import set_setup_choices
from fashionistapulp.structure import set_current_game_version

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'static', 'chardata', 'options.js')

HARNESS = r"""
var radios = [{value: 'all', checked: true}, {value: 'mixed', checked: false}, {value: 'only', checked: true}];
var select = {selectedIndex: 2, value: '7'};
var disabled = [];
function wrap(list, extra) {
    var obj = {length: list.length, each: function(fn) { list.forEach(function(el) { fn.call(el); }); return obj; }};
    Object.keys(extra || {}).forEach(function(key) { obj[key] = extra[key]; });
    return obj;
}
function $(arg) {
    if (arg && typeof arg === 'object') {
        return {prop: function(name, value) { arg[name] = value; return this; }};
    }
    if (arg === 'input:radio[name=inventory_mode]') { return wrap(PRESENT ? radios : []); }
    if (arg === 'select[name=inventory_folder]') {
        return PRESENT ? {
            length: 1,
            prop: function(name, value) {
                if (arguments.length === 1) { return select[name]; }
                select[name] = value; return this;
            },
            val: function(value) { select.value = value; select.selectedIndex = value === '3' ? 1 : -1; return this; }
        } : wrap([], {prop: function() { return this; }, val: function() { return this; }});
    }
    if (arg.charAt(0) === '.') {
        return {prop: function(name, value) { if (name === 'disabled') { disabled.push(arg); } return this; },
                css: function() { return this; }, attr: function() { return this; }};
    }
    var none = {length: 0, prop: function() { return none; }, val: function() { return none; },
                filter: function() { return none; }, each: function() { return none; }};
    return none;
}
function gettext(s) { return s; }
"""


def run_script(case, present, state):
    node = shutil.which('node')
    if node is None:
        case.skipTest('node is not installed')
    source = io.open(SCRIPT, encoding='utf-8').read()
    program = '\n'.join(['var PRESENT = %s;' % ('true' if present else 'false'), HARNESS, source,
                         'optionsInit(%s);' % json.dumps(state),
                         'console.log(JSON.stringify({radios: radios, select: select, disabled: disabled}));'])
    done = subprocess.run([node, '-e', program], capture_output=True, timeout=60)
    case.assertEqual(0, done.returncode, done.stderr.decode('utf-8', 'replace'))
    return json.loads(done.stdout.decode('utf-8'))


class DiscardRestoresTheItemSourceTests(SimpleTestCase):

    BASE = {'dofuses': {}, 'dofusnotforchar': {}}

    def _state(self, **extra):
        state = dict(self.BASE)
        state.update(extra)
        return state

    def test_the_radio_and_the_folder_follow_the_state(self):
        out = run_script(self, True, self._state(inventory_mode='mixed', inventory_folder=3))
        self.assertEqual(['mixed'], [r['value'] for r in out['radios'] if r['checked']])
        self.assertEqual('3', out['select']['value'])

    def test_no_folder_puts_back_all_and_the_first_folder(self):
        out = run_script(self, True, self._state(inventory_mode='all', inventory_folder=None))
        self.assertEqual(['all'], [r['value'] for r in out['radios'] if r['checked']])
        self.assertEqual(0, out['select']['selectedIndex'])

    def test_a_page_without_the_controls_does_not_throw(self):
        run_script(self, False, self._state(inventory_mode='all', inventory_folder=None))

    def test_a_state_without_an_item_source_leaves_the_controls_alone(self):
        out = run_script(self, True, self._state())
        self.assertEqual(['all', 'only'], [r['value'] for r in out['radios'] if r['checked']])

    def test_the_dofus_too_high_for_the_level_are_disabled_again(self):
        out = run_script(self, True, {'dofuses': {}, 'dofusnotforchar': {'ochre': True}})
        self.assertEqual(['.ochre'], out['disabled'])


class TheOptionsStateCarriesTheItemSourceTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('itemsource', 'itemsource@test.local', 'pw-1234')
        self.client.force_login(self.owner)
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Iop', 200, {'str'}, 'dofus3')
        self.folder = InventoryFolder.objects.create(user=self.owner, name='f', game_version='dofus3')

    def _page_state(self):
        page = self.client.get('/options/%d/' % self.char.id).content.decode('utf-8')
        raw = page.split('var initialOptions = ', 1)[1].split(';\n', 1)[0]
        return json.loads(raw)

    def test_the_page_and_the_save_reply_carry_the_mode_and_folder_the_solver_reads(self):
        reply = json.loads(self.client.post('/optionspost/%d/' % self.char.id,
                                            {'inventory_mode': 'only',
                                             'inventory_folder': str(self.folder.id)}).content)
        self.assertEqual(('only', self.folder.id), (reply['inventory_mode'], reply['inventory_folder']))
        state = self._page_state()
        self.assertEqual(('only', self.folder.id), (state['inventory_mode'], state['inventory_folder']))

    def test_a_mode_without_a_folder_reads_as_all(self):
        self.client.post('/optionspost/%d/' % self.char.id, {'inventory_mode': 'only'})
        state = self._page_state()
        self.assertEqual(('all', None), (state['inventory_mode'], state['inventory_folder']))

    def test_a_build_that_never_chose_an_item_source_reads_as_all(self):
        state = self._page_state()
        self.assertEqual(('all', None), (state['inventory_mode'], state['inventory_folder']))

    def test_a_folder_saved_before_the_mode_existed_reads_as_only(self):
        set_setup_choices(self.char, {'inventory_mode': None, 'inventory_folder': self.folder.id})
        state = self._page_state()
        self.assertEqual(('only', self.folder.id), (state['inventory_mode'], state['inventory_folder']))
