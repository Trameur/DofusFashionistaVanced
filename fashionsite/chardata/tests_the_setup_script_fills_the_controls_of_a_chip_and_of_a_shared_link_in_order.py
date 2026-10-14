# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ script changes the form the way a chip or a shared link says: what it unticks, what it ticks, in which order, and what it leaves alone."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_script_fills_the_form_from_a_preset_and_the_share_link import run

CONTROLS = r"""
function controls(start) {
    var form = Object.assign({ticked: [], priority: 'balanced', mode: 'general', guard: 10, calls: []}, start);
    return {
        form: form,
        tick: function(aspect, on) {
            form.calls.push((on ? '+' : '-') + aspect);
            var at = form.ticked.indexOf(aspect);
            if (on && at === -1) { form.ticked.push(aspect); }
            if (!on && at !== -1) { form.ticked.splice(at, 1); }
        },
        priority: function(value) { form.calls.push('priority:' + value); form.priority = value; },
        mode: function(value) { form.calls.push('mode:' + value); form.mode = value; },
        guard: function(value) { form.calls.push('guard:' + value); form.guard = value; }
    };
}
function fill(env, recipeData) {
    var target = setupRecipeTarget(recipe(recipeData), page);
    setupFillControls({scope: page.focus, boxes: target.focus, priority: target.priority,
                       mode: target.mode, guard: target.guard}, env);
    return env.form;
}
function sorted(list) { return list.slice().sort(); }
"""


def script(case, body):
    return run(case, CONTROLS + body)


class AChipUntickstheFocusBoxesItDoesNotNameAndTicksTheOnesItNamesTests(SimpleTestCase):

    def test_switching_from_critical_to_farm_unticks_critical_and_ticks_wisdom_and_prospecting(self):
        self.assertEqual({'ticked': ['pp', 'str', 'wis'], 'priority': 'balanced'}, script(self, r"""
var env = controls({ticked: ['crit', 'str'], priority: 'damage'});
var form = fill(env, {key: 'farm', focus: 'wis pp', priority: 'balanced', mule: 'true'});
return {ticked: sorted(form.ticked), priority: form.priority};
"""))

    def test_switching_to_the_glass_cannon_unticks_the_other_focus_boxes_and_ticks_its_own(self):
        self.assertEqual({'ticked': ['glasscannon', 'str'], 'priority': 'balanced'}, script(self, r"""
var env = controls({ticked: ['crit', 'dam', 'str']});
var form = fill(env, {key: 'glass_cannon', focus: 'glasscannon', priority: 'balanced'});
return {ticked: sorted(form.ticked), priority: form.priority};
"""))

    def test_a_chip_without_focus_unticks_every_focus_box_and_keeps_the_element(self):
        self.assertEqual(['int'], script(self, r"""
var env = controls({ticked: ['crit', 'wis', 'int']});
return sorted(fill(env, {key: 'balanced'}).ticked);
"""))

    def test_a_chip_never_touches_a_box_outside_the_focus_column(self):
        self.assertEqual({'outside': [], 'kept': ['agi', 'cha', 'int', 'omni', 'str']}, script(self, r"""
var env = controls({ticked: ['str', 'int', 'cha', 'agi', 'omni', 'crit']});
var form = fill(env, {key: 'farm', focus: 'wis pp', priority: 'balanced'});
var named = form.calls.filter(function(call) { return call.charAt(0) === '+' || call.charAt(0) === '-'; })
    .map(function(call) { return call.substring(1); });
return {outside: named.filter(function(aspect) { return page.focus.indexOf(aspect) === -1; }),
        kept: sorted(form.ticked.filter(function(aspect) { return aspect !== 'wis' && aspect !== 'pp'; }))};
"""))

    def test_a_chip_unticks_every_box_it_does_not_name_before_it_ticks_the_ones_it_names(self):
        self.assertEqual({'ticked': ['+wis', '+pp'], 'unticksFirst': True}, script(self, r"""
var env = controls({ticked: ['crit']});
var calls = fill(env, {key: 'farm', focus: 'wis pp', priority: 'balanced'}).calls.filter(function(call) {
    return call.charAt(0) === '-' || call.charAt(0) === '+';
});
var firstOn = calls.findIndex(function(call) { return call.charAt(0) === '+'; });
var lastOff = calls.map(function(call) { return call.charAt(0); }).lastIndexOf('-');
return {ticked: calls.filter(function(call) { return call.charAt(0) === '+'; }),
        unticksFirst: calls.indexOf('-crit') !== -1 && lastOff < firstOn};
"""))

    def test_a_box_the_page_does_not_offer_is_never_ticked(self):
        self.assertEqual([], script(self, r"""
var env = controls({});
var narrow = Object.assign({}, page, {focus: page.focus.filter(function(a) { return a !== 'trap'; })});
var target = setupRecipeTarget(recipe({focus: 'trap'}), narrow);
setupFillControls({scope: narrow.focus, boxes: target.focus, priority: target.priority,
                   mode: target.mode, guard: target.guard}, env);
return env.form.ticked;
"""))


class AChipSetsThePriorityTheModeAndTheSafeguardEvenWhenTheyAreAlreadyChangedTests(SimpleTestCase):

    def test_switching_from_a_kolossium_chip_to_a_plain_one_sets_the_general_mode_and_the_default_guard(self):
        self.assertEqual({'mode': 'general', 'guard': 10, 'priority': 'balanced'}, script(self, r"""
var env = controls({mode: 'koli_1v1', guard: 20, priority: 'defense'});
var form = fill(env, {key: 'balanced'});
return {mode: form.mode, guard: form.guard, priority: form.priority};
"""))

    def test_a_chip_with_a_mode_a_priority_and_a_safeguard_sets_all_three(self):
        self.assertEqual({'mode': 'koli_3v3', 'guard': 5, 'priority': 'damage'}, script(self, r"""
var form = fill(controls({}), {key: 'x', priority: 'damage', mode: 'koli_3v3', guard: '5'});
return {mode: form.mode, guard: form.guard, priority: form.priority};
"""))

    def test_applying_the_same_chip_twice_leaves_the_form_as_after_the_first_time(self):
        self.assertEqual(True, script(self, r"""
var env = controls({ticked: ['crit', 'str'], priority: 'defense', mode: 'koli_2v2'});
var data = {key: 'critical', focus: 'crit', priority: 'damage'};
var once = JSON.stringify(fill(env, data), ['ticked', 'priority', 'mode', 'guard']);
var twice = JSON.stringify(fill(env, data), ['ticked', 'priority', 'mode', 'guard']);
return once === twice;
"""))


class ARestoreFillsOnlyWhatTheLinkNamesTests(SimpleTestCase):

    RESTORE = r"""
function restoreEnv(start) {
    var env = controls(start);
    var order = env.form.calls;
    ['clearPanel', 'finished'].forEach(function(name) {
        env[name] = function() { order.push(name); };
    });
    env.setLevel = function(value) { order.push('level:' + value); };
    env.setClass = function(value) { order.push('class:' + value); };
    env.setTemporix = function(value) { order.push('temporix:' + value); };
    env.setItem = function(value) { order.push('item:' + value); };
    env.restorePanel = function(edits, now) { order.push('panel:' + JSON.stringify(edits) + ':' + now); };
    env.order = order;
    return env;
}
function fragment(text) { return setupShareParse('setup=1&game=dofus3' + text, page); }
"""

    def restore(self, body):
        return script(self, self.RESTORE + body)

    def test_the_panel_is_cleared_first_the_values_are_set_in_order_and_the_panel_is_restored_last(self):
        self.assertEqual(
            ['clearPanel', 'level:200', 'class:Cra', 'temporix:true', 'item:30001', 'priority:damage',
             'mode:koli_1v1', 'guard:5', 'panel:{"ap":{"weight":true,"min":false,"aggregate":false,'
             '"now":{"weight":5}}}:true', 'finished'],
            self.restore(r"""
var env = restoreEnv({});
var state = fragment('&class=Cra&level=200&temporix=on&item=30001&priority=damage&mode=koli_1v1&guard=5&weight_ap=5');
setupRestore(state, true, page, env);
return env.order;
"""))

    def test_a_field_the_link_leaves_out_is_not_touched(self):
        self.assertEqual({'order': ['clearPanel', 'panel:{}:false', 'finished'], 'ticked': ['crit'],
                          'priority': 'damage'}, self.restore(r"""
var env = restoreEnv({ticked: ['crit'], priority: 'damage'});
setupRestore(fragment(''), false, page, env);
return {order: env.order, ticked: env.form.ticked, priority: env.form.priority};
"""))

    def test_the_boxes_the_link_names_are_ticked_and_every_other_box_of_the_page_is_unticked(self):
        self.assertEqual(['dam', 'str'], self.restore(r"""
var env = restoreEnv({ticked: ['crit', 'int', 'wis']});
setupRestore(fragment('&boxes=dam.str'), true, page, env);
return sorted(env.form.ticked);
"""))

    def test_a_link_with_no_boxes_unticks_every_box_of_the_page(self):
        self.assertEqual([], self.restore(r"""
var env = restoreEnv({ticked: ['crit', 'int', 'wis', 'omni']});
setupRestore(fragment('&boxes='), true, page, env);
return env.form.ticked;
"""))

    def test_the_boxes_a_link_names_outside_the_page_are_not_ticked(self):
        self.assertEqual([], self.restore(r"""
var env = restoreEnv({});
var narrow = Object.assign({}, page, {boxes: page.boxes.filter(function(a) { return a !== 'trap'; })});
setupRestore({boxes: ['trap'], touched: []}, true, narrow, env);
return env.form.ticked;
"""))

    def test_the_edits_of_the_link_reach_the_panel_with_the_flag_that_says_whether_to_apply_them_now(self):
        self.assertEqual({'now': 'panel:{"hp":{"weight":false,"min":true,"aggregate":false,"now":{"min":""}}}:true',
                          'later': 'panel:{"hp":{"weight":false,"min":true,"aggregate":false,"now":{"min":""}}}:false'},
                         self.restore(r"""
function panelCall(now) {
    var env = restoreEnv({});
    setupRestore(fragment('&min_hp='), now, page, env);
    return env.order.filter(function(call) { return call.indexOf('panel:') === 0; })[0];
}
return {now: panelCall(true), later: panelCall(false)};
"""))

    def test_a_state_without_temporix_or_item_fields_leaves_both_alone(self):
        self.assertEqual([], self.restore(r"""
var env = restoreEnv({});
setupRestore({level: '50', className: 'Iop', boxes: null, priority: null, mode: null, guard: null, touched: []},
             false, page, env);
return env.order.filter(function(call) { return call.indexOf('temporix') === 0 || call.indexOf('item') === 0; });
"""))

    def test_a_temporix_switched_off_is_still_applied(self):
        self.assertEqual(['temporix:false'], self.restore(r"""
var env = restoreEnv({});
setupRestore(fragment('&temporix=off'), false, page, env);
return env.order.filter(function(call) { return call.indexOf('temporix') === 0; });
"""))


class ThePanelDropsWhatItHeldBeforeALinkFillsTheFormTests(SimpleTestCase):

    PANEL = r"""
function panel(options) {
    var log = [];
    var shown = {baseline: options.baseline};
    var gate = setupEditGate({
        hasBaseline: function() { return options.hasBaseline; },
        edited: function() { return options.edited; },
        same: function(state) { return state === shown.baseline; },
        apply: function(state, keep) { log.push('apply:' + state + ':' + keep); shown.baseline = state; },
        ask: function(on) { log.push('ask:' + on); }
    });
    var actions = setupPanelActions(gate, {
        forgetPending: function() { log.push('forget'); },
        hasBaseline: function() { return options.hasBaseline; },
        restorePreset: function() { log.push('show:' + shown.baseline); }
    });
    return {gate: gate, actions: actions, log: log};
}
"""

    def test_a_state_held_behind_the_question_is_applied_without_the_edits_before_the_form_is_filled(self):
        self.assertEqual(['ask:true', 'forget', 'ask:false', 'apply:Y:false', 'show:Y'], run(self, self.PANEL + r"""
var p = panel({hasBaseline: true, edited: 2, baseline: 'X'});
p.gate.arrive('Y');
p.actions.clear();
return p.log;
"""))

    def test_the_panel_shows_the_held_state_and_not_the_old_one_so_a_link_that_gives_the_same_query_finds_it(self):
        self.assertEqual('Y', run(self, self.PANEL + r"""
var p = panel({hasBaseline: true, edited: 1, baseline: 'X'});
p.gate.arrive('Y');
p.actions.clear();
return p.log.filter(function(call) { return call.indexOf('show:') === 0; })[0].substring(5);
"""))

    def test_nothing_held_means_nothing_applied_and_the_current_preset_is_shown_again(self):
        self.assertEqual(['forget', 'ask:false', 'show:X'], run(self, self.PANEL + r"""
var p = panel({hasBaseline: true, edited: 0, baseline: 'X'});
p.actions.clear();
return p.log;
"""))

    def test_before_the_first_preview_there_is_nothing_to_show_again(self):
        self.assertEqual(['forget', 'ask:false'], run(self, self.PANEL + r"""
var p = panel({hasBaseline: false, edited: 0, baseline: null});
p.actions.clear();
return p.log;
"""))

    def test_the_question_is_closed_once_the_panel_is_cleared(self):
        self.assertEqual(False, run(self, self.PANEL + r"""
var p = panel({hasBaseline: true, edited: 3, baseline: 'X'});
p.gate.arrive('Y');
p.actions.clear();
return p.gate.holding();
"""))


class TheSavedSetupsAreOfferedOnlyWhenTheBrowserKeepsThemTests(SimpleTestCase):

    HOSTS = r"""
function memory() {
    var data = {};
    return {data: data, setItem: function(key, value) { data[key] = String(value); },
            removeItem: function(key) { delete data[key]; }};
}
"""

    def test_a_working_storage_is_returned_and_the_probe_is_removed(self):
        self.assertEqual({'same': True, 'left': []}, run(self, self.HOSTS + r"""
var store = memory();
var opened = setupOpenStorage({localStorage: store});
return {same: opened === store, left: Object.keys(store.data)};
"""))

    def test_a_browser_that_throws_when_the_storage_is_read_has_no_storage(self):
        self.assertEqual(None, run(self, r"""
return setupOpenStorage({get localStorage() { throw new Error('blocked'); }});
"""))

    def test_a_storage_that_refuses_to_write_has_no_storage(self):
        self.assertEqual({'quota': None, 'remove': None}, run(self, r"""
var quota = {setItem: function() { throw new Error('quota'); }, removeItem: function() {}};
var remove = {setItem: function() {}, removeItem: function() { throw new Error('blocked'); }};
return {quota: setupOpenStorage({localStorage: quota}), remove: setupOpenStorage({localStorage: remove})};
"""))

    def test_a_browser_without_storage_has_no_storage(self):
        self.assertEqual({'missing': None, 'nothing': None}, run(self, r"""
return {missing: setupOpenStorage({}), nothing: setupOpenStorage(null)};
"""))
