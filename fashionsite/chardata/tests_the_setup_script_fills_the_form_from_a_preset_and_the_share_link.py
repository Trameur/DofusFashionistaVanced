# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The pure parts of the /setup/ script: what a preset fills, what the share link carries and rejects, and what the saved setups keep."""
import json

from django.test import SimpleTestCase

from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script

PAGE = r"""
var page = {
    game: 'dofus3',
    classes: ['Cra', 'Iop', 'Féca'],
    boxes: ['str', 'int', 'cha', 'agi', 'omni', 'dam', 'heal', 'aprape', 'mprape', 'crit', 'res', 'wis',
            'pp', 'pods', 'trap', 'summon', 'pushback', 'noncrit', 'vit', 'glasscannon'],
    focus: ['dam', 'heal', 'aprape', 'mprape', 'crit', 'res', 'wis', 'pp', 'pods', 'trap', 'summon',
            'pushback', 'noncrit', 'vit', 'glasscannon'],
    priorities: ['balanced', 'damage', 'defense', 'heals'],
    modes: ['general', 'pvm_solo', 'koli_1v1', 'koli_2v2', 'koli_3v3'],
    guards: [0, 5, 10, 15, 20],
    guardDefault: 10
};
function recipe(extra) {
    return setupRecipeFromData(Object.assign({key: 'r', focus: '', priority: 'balanced', mode: 'general'}, extra));
}
"""


def run(case, body):
    return run_script(case, PAGE + body)


class AChipReadsItsRecipeFromItsDataTests(SimpleTestCase):

    def test_the_data_of_a_chip_become_a_recipe(self):
        self.assertEqual({
            'farm': {'key': 'farm', 'focus': ['wis', 'pp'], 'priority': 'balanced', 'mode': 'general',
                     'guard': None, 'mule': True},
            'cannon': {'key': 'cannon', 'focus': [], 'priority': 'damage', 'mode': 'general',
                       'guard': 0, 'mule': False},
            'spaced': ['crit'], 'blank': [], 'missing': {'focus': [], 'guard': None, 'mule': False}},
            run(self, r"""
return {
    farm: setupRecipeFromData({key: 'farm', focus: 'wis pp', priority: 'balanced', mode: 'general', mule: 'true'}),
    cannon: setupRecipeFromData({key: 'cannon', focus: '', priority: 'damage', mode: 'general', guard: '0'}),
    spaced: setupRecipeFromData({key: 'k', focus: '  crit  '}).focus,
    blank: setupRecipeFromData({key: 'k', focus: ' '}).focus,
    missing: (function() {
        var found = setupRecipeFromData({});
        return {focus: found.focus, guard: found.guard, mule: found.mule};
    })()
};
"""))

    def test_a_guard_that_is_not_a_number_reads_as_no_guard(self):
        self.assertEqual({'word': None, 'empty': None, 'undefined': None, 'ten': 10},
                         run(self, r"""
return {
    word: recipe({guard: 'many'}).guard, empty: recipe({guard: ''}).guard,
    undefined: recipe({}).guard, ten: recipe({guard: '10'}).guard
};
"""))


class AChipFillsOnlyControlsThePageOffersTests(SimpleTestCase):

    def test_a_recipe_the_page_offers_in_full_is_filled_as_it_is(self):
        self.assertEqual({'focus': ['crit'], 'priority': 'damage', 'mode': 'koli_1v1', 'guard': 0},
                         run(self, r"""
return setupRecipeTarget(recipe({focus: 'crit', priority: 'damage', mode: 'koli_1v1', guard: '0'}), page);
"""))

    def test_a_focus_box_the_page_does_not_offer_is_left_out(self):
        self.assertEqual(['crit'], run(self, r"""
var narrow = Object.assign({}, page, {focus: page.focus.filter(function(a) { return a !== 'trap'; })});
return setupRecipeTarget(recipe({focus: 'trap crit'}), narrow).focus;
"""))

    def test_at_most_two_focus_boxes_are_filled_and_never_the_same_twice(self):
        self.assertEqual({'three': ['crit', 'dam'], 'twice': ['crit']}, run(self, r"""
return {three: setupRecipeTarget(recipe({focus: 'crit dam heal'}), page).focus,
        twice: setupRecipeTarget(recipe({focus: 'crit crit'}), page).focus};
"""))

    def test_an_element_is_never_filled_even_when_the_data_names_one(self):
        self.assertEqual([], run(self, r"""
return setupRecipeTarget(recipe({focus: 'str int cha agi omni'}), page).focus;
"""))

    def test_a_priority_a_mode_or_a_guard_the_page_does_not_offer_falls_back_to_its_default(self):
        self.assertEqual({'focus': [], 'priority': 'balanced', 'mode': 'general', 'guard': 10},
                         run(self, r"""
return setupRecipeTarget(recipe({priority: 'tempo', mode: 'koli_9v9', guard: '99'}), page);
"""))

    def test_a_guard_the_recipe_leaves_out_is_the_page_default(self):
        self.assertEqual(10, run(self, "return setupRecipeTarget(recipe({}), page).guard;"))

    def test_a_target_matches_the_controls_in_any_order_and_the_guard_as_text_or_number(self):
        self.assertEqual({'same': True, 'textGuard': True, 'otherFocus': False, 'otherPriority': False,
                          'otherMode': False, 'otherGuard': False, 'extra': False},
                         run(self, r"""
var target = setupRecipeTarget(recipe({focus: 'wis pp', guard: '5'}), page);
function current(extra) {
    return Object.assign({focus: ['pp', 'wis'], priority: 'balanced', mode: 'general', guard: 5}, extra);
}
return {
    same: setupRecipeMatches(target, current({})),
    textGuard: setupRecipeMatches(target, current({guard: '5'})),
    otherFocus: setupRecipeMatches(target, current({focus: ['pp']})),
    otherPriority: setupRecipeMatches(target, current({priority: 'damage'})),
    otherMode: setupRecipeMatches(target, current({mode: 'koli_1v1'})),
    otherGuard: setupRecipeMatches(target, current({guard: 10})),
    extra: setupRecipeMatches(target, current({focus: ['pp', 'wis', 'crit']}))
};
"""))


class TheNoteUnderTheChipsSaysWhatTheElementRowNeedsTests(SimpleTestCase):

    def test_a_mule_always_gets_the_mule_hint_and_another_recipe_only_without_an_element(self):
        self.assertEqual({'nothing': '', 'mule': 'mule', 'muleWithElement': 'mule',
                          'plain': 'element', 'plainWithElement': ''},
                         run(self, r"""
var mule = recipe({focus: 'wis', mule: 'true'});
var plain = recipe({focus: 'crit'});
return {
    nothing: setupRecipeNote(null, false), mule: setupRecipeNote(mule, false),
    muleWithElement: setupRecipeNote(mule, true), plain: setupRecipeNote(plain, false),
    plainWithElement: setupRecipeNote(plain, true)
};
"""))

    def test_the_note_text_follows_the_kind_and_is_empty_otherwise(self):
        said = run(self, r"""
return {mule: setupRecipeNoteText('mule'), element: setupRecipeNoteText('element'),
        none: setupRecipeNoteText(''), other: setupRecipeNoteText('x')};
""")
        self.assertIn('Mules need no element', said['mule'])
        self.assertIn('Elements column', said['mule'])
        self.assertIn('Presets never choose an element', said['element'])
        self.assertEqual({'none': '', 'other': ''}, {key: said[key] for key in ('none', 'other')})


class TheShareLinkCarriesTheWholeSetupInTheFragmentTests(SimpleTestCase):

    STATE = r"""
var state = {game: 'dofus3', className: 'Cra', level: '200', boxes: ['str', 'crit'], priority: 'damage',
             mode: 'koli_1v1', guard: 0, touched: [['min_hp', ''], ['weight_ap', '5']]};
"""

    def test_the_fragment_spells_class_level_boxes_priority_mode_guard_and_touched_values(self):
        self.assertEqual(
            'setup=1&game=dofus3&class=Cra&level=200&boxes=crit.str&priority=damage&mode=koli_1v1'
            '&guard=0&min_hp=&weight_ap=5',
            run(self, self.STATE + "return setupShareEncode(state);"))

    def test_what_is_encoded_comes_back_the_same_once_parsed(self):
        self.assertEqual({'className': 'Cra', 'level': '200', 'boxes': ['crit', 'str'],
                          'priority': 'damage', 'mode': 'koli_1v1', 'guard': 0, 'temporix': None,
                          'item': None, 'touched': [['min_hp', ''], ['weight_ap', '5']]},
                         run(self, self.STATE + "return setupShareParse(setupShareEncode(state), page);"))

    def test_a_class_with_an_accent_survives_the_round_trip(self):
        self.assertEqual('Féca', run(self, r"""
var state = {game: 'dofus3', className: 'Féca', level: '50', boxes: [], touched: []};
var fragment = setupShareEncode(state);
return {fragment: fragment, parsed: setupShareParse(fragment, page)};
""")['parsed']['className'])

    def test_the_fragment_also_spells_temporix_and_the_item_to_build_around(self):
        self.assertEqual({
            'on': 'setup=1&game=dofus3&boxes=&temporix=on&item=12345',
            'off': 'setup=1&game=dofus3&boxes=&temporix=off',
            'neither': 'setup=1&game=dofus3&boxes='},
            run(self, r"""
return {
    on: setupShareEncode({game: 'dofus3', boxes: [], temporix: true, item: '12345'}),
    off: setupShareEncode({game: 'dofus3', boxes: [], temporix: false, item: null}),
    neither: setupShareEncode({game: 'dofus3', boxes: [], temporix: null})
};
"""))

    def test_temporix_and_the_item_come_back_the_same_once_parsed(self):
        self.assertEqual({'temporix': True, 'item': '12345', 'off': False},
                         run(self, r"""
var parsed = setupShareParse(setupShareEncode({game: 'dofus3', boxes: [], temporix: true, item: '12345'}), page);
var off = setupShareParse(setupShareEncode({game: 'dofus3', boxes: [], temporix: false}), page);
return {temporix: parsed.temporix, item: parsed.item, off: off.temporix};
"""))

    def test_an_item_that_is_not_a_catalogue_number_is_not_written(self):
        self.assertEqual({'word': False, 'float': False, 'empty': False, 'long': False, 'number': False,
                          'ok': True}, run(self, r"""
function has(item) {
    return setupShareEncode({game: 'dofus3', boxes: [], item: item}).indexOf('item=') !== -1;
}
return {word: has('abc'), float: has('1.5'), empty: has(''), long: has('1234567890'), number: has(12345),
        ok: has('123456789')};
"""))

    def test_a_fragment_that_fits_is_one_the_parser_reads_back_and_a_longer_one_is_not(self):
        self.assertEqual({'atLimit': True, 'overLimit': False, 'readBack': True, 'refused': None}, run(self, r"""
var touched = [];
for (var i = 0; i < 400; i++) { touched.push(['weight_k' + i, '5']); }
var huge = setupShareEncode({game: 'dofus3', boxes: [], touched: touched});
var short = setupShareEncode({game: 'dofus3', boxes: [], touched: touched.slice(0, 40)});
return {atLimit: setupShareFits(new Array(SETUP_RECIPES.fragmentLimit + 1).join('x')),
        overLimit: setupShareFits(new Array(SETUP_RECIPES.fragmentLimit + 2).join('x')),
        readBack: setupShareFits(short) && setupShareParse(short, page) !== null,
        refused: setupShareFits(huge) ? 'fits' : setupShareParse(huge, page)};
"""))

    def test_a_leading_hash_is_ignored(self):
        self.assertEqual('Iop', run(self, r"""
return setupShareParse('#' + setupShareEncode({game: 'dofus3', className: 'Iop', level: '10', boxes: []}), page).className;
"""))

    def test_a_setup_without_boxes_parses_to_an_empty_list_and_not_to_nothing(self):
        self.assertEqual([], run(self, r"""
return setupShareParse(setupShareEncode({game: 'dofus3', className: 'Iop', level: '10', boxes: []}), page).boxes;
"""))

    def test_a_field_the_fragment_leaves_out_comes_back_as_nothing_to_restore(self):
        self.assertEqual({'className': None, 'level': None, 'boxes': None, 'priority': None,
                          'mode': None, 'guard': None, 'temporix': None, 'item': None, 'touched': []},
                         run(self, "return setupShareParse('setup=1&game=dofus3', page);"))

    def test_no_name_and_no_personal_field_ever_reaches_the_fragment(self):
        fragment = run(self, r"""
return setupShareEncode({game: 'dofus3', className: 'Cra', level: '200', boxes: ['str'], charName: 'Secret Name',
                         buildName: 'My private build', email: 'someone@example.com', touched: []});
""")
        for leak in ('Secret', 'private', 'someone', 'example', 'charName', 'email'):
            self.assertNotIn(leak, fragment)

    def test_a_level_out_of_range_is_not_written(self):
        self.assertEqual({'zero': False, 'high': False, 'word': False, 'ok': True}, run(self, r"""
function has(level) {
    return setupShareEncode({game: 'dofus3', level: level, boxes: []}).indexOf('level=') !== -1;
}
return {zero: has('0'), high: has('201'), word: has('abc'), ok: has('200')};
"""))

    def test_a_missing_level_class_priority_mode_or_guard_is_not_written(self):
        self.assertEqual('setup=1&game=dofus3&boxes=',
                         run(self, "return setupShareEncode({game: 'dofus3', boxes: []});"))

    def test_the_fragment_stays_inside_what_the_parser_accepts_even_with_every_box_ticked(self):
        self.assertEqual(True, run(self, r"""
var fragment = setupShareEncode({game: 'dofus3', className: 'Cra', level: '200', boxes: page.boxes.slice(0, 2),
                                  priority: 'heals', mode: 'koli_3v3', guard: 20, touched: []});
return fragment.length < SETUP_RECIPES.fragmentLimit && setupShareParse(fragment, page) !== null;
"""))


class AnInvalidOrForeignFragmentIsIgnoredTests(SimpleTestCase):

    BASE = 'setup=1&game=dofus3'

    def parsed(self, fragments):
        """{fragment: parsed state or null} for every fragment, through the real parser."""
        return run(self, "var fragments = %s;\nvar found = {};\n"
                         "fragments.forEach(function(f) { found[f] = setupShareParse(f, page); });\n"
                         "return found;" % json.dumps(fragments))

    def assertIgnored(self, fragments):
        found = self.parsed(fragments)
        self.assertEqual({fragment: None for fragment in fragments}, found)

    def test_a_fragment_of_another_use_is_ignored(self):
        self.assertIgnored(['', '#', '#top', 'section-2', '#/route/42', '#access_token=abc&state=1',
                            '=value', '&', 'a=1', 'setup', 'setup=', 'x=y&setup=1'])

    def test_another_format_or_another_game_is_ignored(self):
        self.assertIgnored(['setup=2&game=dofus3', 'setup=1&game=touch', 'setup=1', 'game=dofus3',
                            'setup=1&game=', 'setup=0&game=dofus3', 'setup=1&game=DOFUS3'])

    def test_an_unknown_or_repeated_key_is_ignored(self):
        self.assertIgnored([self.BASE + '&foo=1', self.BASE + '&class=Cra&class=Iop',
                            self.BASE + '&__proto__=1', self.BASE + '&constructor=1',
                            self.BASE + '&toString=1', self.BASE + '&hasOwnProperty=1',
                            self.BASE + '&weight_=1', self.BASE + '&weights=1'])

    def test_a_class_the_page_does_not_know_is_ignored(self):
        self.assertIgnored([self.BASE + '&class=Dragon', self.BASE + '&class=', self.BASE + '&class=cra'])

    def test_a_level_out_of_range_or_not_a_number_is_ignored(self):
        self.assertIgnored([self.BASE + '&level=' + level
                            for level in ('0', '201', '1000', '-1', 'abc', '', '1.5', '20%200', '0200x')])

    def test_a_box_the_page_does_not_offer_or_a_repeated_one_is_ignored(self):
        self.assertIgnored([self.BASE + '&boxes=' + boxes
                            for boxes in ('pvp', 'str.str', 'crit.nope', '.', 'str..int', 'str.', 'CRIT')])

    def test_more_than_two_focus_boxes_or_crit_with_noncrit_is_ignored(self):
        self.assertIgnored([self.BASE + '&boxes=' + boxes
                            for boxes in ('crit.dam.heal', 'crit.noncrit', 'dam.heal.res')])

    def test_two_focus_boxes_and_the_elements_are_accepted(self):
        found = self.parsed([self.BASE + '&boxes=crit.dam.str.int'])
        self.assertEqual(['crit', 'dam', 'str', 'int'], found[self.BASE + '&boxes=crit.dam.str.int']['boxes'])

    def test_a_temporix_value_other_than_on_or_off_is_ignored(self):
        self.assertIgnored([self.BASE + '&temporix=' + value
                            for value in ('', 'yes', 'ON', '1', 'true', 'on.off')])

    def test_an_item_that_is_not_a_catalogue_number_is_ignored(self):
        self.assertIgnored([self.BASE + '&item=' + value
                            for value in ('', 'abc', '-5', '1.5', '1e5', '0x10', '1234567890', '12%2034')])

    def test_temporix_and_an_item_are_accepted_when_well_formed(self):
        fragment = self.BASE + '&temporix=on&item=30001'
        found = self.parsed([fragment])[fragment]
        self.assertEqual({'temporix': True, 'item': '30001'},
                         {key: found[key] for key in ('temporix', 'item')})

    def test_a_priority_a_mode_or_a_guard_the_page_does_not_offer_is_ignored(self):
        self.assertIgnored([self.BASE + '&priority=tempo', self.BASE + '&priority=', self.BASE + '&mode=koli_9v9',
                            self.BASE + '&mode=', self.BASE + '&guard=25', self.BASE + '&guard=abc',
                            self.BASE + '&guard=-5', self.BASE + '&guard=', self.BASE + '&guard=5.5'])

    def test_a_touched_value_that_is_not_a_whole_number_is_ignored(self):
        self.assertIgnored([self.BASE + '&weight_ap=1.5', self.BASE + '&weight_ap=abc',
                            self.BASE + '&weight_ap=', self.BASE + '&min_ap=x', self.BASE + '&min_ap=2.5',
                            self.BASE + '&weight_ap=1234567', self.BASE + '&weight_a%20b=1',
                            self.BASE + '&weight_' + 'x' * 41 + '=1'])

    def test_a_touched_value_that_is_a_whole_number_or_an_empty_minimum_is_kept(self):
        fragment = self.BASE + '&weight_ap=-3&min_ap=&min_hp=12'
        found = self.parsed([fragment])[fragment]
        self.assertEqual([['min_ap', ''], ['min_hp', '12'], ['weight_ap', '-3']], found['touched'])

    def test_a_broken_percent_encoding_or_an_oversized_fragment_is_ignored(self):
        self.assertIgnored([self.BASE + '&class=%E0%A4%A', self.BASE + '&class=%', self.BASE + '&' + '%zz=1',
                            self.BASE + '&weight_ap=' + '1' * 2000, 'setup=1&game=dofus3&boxes=' + 'str.' * 600])

    def test_a_missing_or_null_fragment_is_ignored(self):
        self.assertEqual([None, None, None], run(self, r"""
return [setupShareParse(undefined, page), setupShareParse(null, page), setupShareParse('', page)];
"""))

    def test_the_parser_leaves_the_page_description_untouched(self):
        self.assertEqual(True, run(self, r"""
var before = JSON.stringify(page);
setupShareParse('setup=1&game=dofus3&boxes=str&class=Cra', page);
setupShareParse('garbage', page);
return JSON.stringify(page) === before;
"""))


class TheSharedPanelValuesComeBackAsTheEditsTheScriptRestoresTests(SimpleTestCase):

    def test_the_touched_fields_become_edits_the_restore_function_reads(self):
        self.assertEqual({
            'ap': {'weight': True, 'min': True, 'aggregate': False, 'now': {'weight': 5, 'min': 2}},
            'hp': {'weight': False, 'min': True, 'aggregate': False, 'now': {'min': ''}},
            'restoredAp': {'weight': 5, 'min': 2}, 'cappedAp': {'weight': 5, 'min': 1},
            'restoredHp': {'min': ''}},
            run(self, r"""
var edits = setupSharedEdits([['weight_ap', '5'], ['min_ap', '2'], ['min_hp', '']]);
return {ap: edits.ap, hp: edits.hp, restoredAp: setupRestoredValues(edits.ap),
        cappedAp: setupRestoredValues(edits.ap, 1), restoredHp: setupRestoredValues(edits.hp)};
"""))

    def test_the_edits_give_back_the_same_touched_fields(self):
        self.assertEqual([['weight_ap', '5'], ['min_ap', '2'], ['min_hp', '']],
                         run(self, r"""
return setupTouchedFields(setupSharedEdits([['weight_ap', '5'], ['min_ap', '2'], ['min_hp', '']]));
"""))

    def test_a_negative_weight_survives(self):
        self.assertEqual([['weight_res', '-4']], run(self, r"""
return setupTouchedFields(setupSharedEdits([['weight_res', '-4']]));
"""))

    def test_no_touched_field_means_no_edit(self):
        self.assertEqual({}, run(self, "return setupSharedEdits([]);"))


class TheSavedSetupsLiveInOneStorageKeyPerGameVersionTests(SimpleTestCase):

    STORAGE = r"""
function memory(initial) {
    var data = Object.assign({}, initial || {});
    return {data: data,
            getItem: function(key) { return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null; },
            setItem: function(key, value) { data[key] = String(value); }};
}
var throwing = {getItem: function() { throw new Error('blocked'); },
                setItem: function() { throw new Error('blocked'); }};
function names(list) { return list.map(function(item) { return item.name; }); }
function many(count) {
    var list = [];
    for (var i = 0; i < count; i++) { list.push({name: 'setup ' + i, fragment: 'setup=1&game=dofus3'}); }
    return list;
}
"""

    def saved(self, body):
        return run(self, self.STORAGE + body)

    def test_nothing_stored_reads_as_no_setup(self):
        self.assertEqual([], self.saved("return setupSavedRead(memory(), 'dofus3');"))

    def test_a_storage_that_throws_or_is_missing_reads_as_no_setup_and_refuses_to_write(self):
        self.assertEqual({'throwing': [], 'missing': [], 'writeThrowing': False, 'writeMissing': False},
                         self.saved(r"""
return {throwing: setupSavedRead(throwing, 'dofus3'), missing: setupSavedRead(null, 'dofus3'),
        writeThrowing: setupSavedWrite(throwing, 'dofus3', []), writeMissing: setupSavedWrite(null, 'dofus3', [])};
"""))

    def test_stored_text_that_is_not_a_list_of_setups_reads_as_no_setup(self):
        self.assertEqual([[], [], [], [], []], self.saved(r"""
var key = SETUP_RECIPES.storagePrefix + 'dofus3';
return ['not json', '{"name":"a"}', '"text"', '42', 'null'].map(function(text) {
    var data = {}; data[key] = text;
    return setupSavedRead(memory(data), 'dofus3');
});
"""))

    def test_an_entry_with_a_wrong_shape_or_size_is_dropped_and_the_good_ones_stay(self):
        self.assertEqual(['good', 'also good'], self.saved(r"""
var key = SETUP_RECIPES.storagePrefix + 'dofus3';
var data = {};
data[key] = JSON.stringify([
    {name: 'good', fragment: 'setup=1&game=dofus3'}, null, 'text', {name: 'no fragment'},
    {fragment: 'no name'}, {name: '', fragment: 'x'}, {name: 5, fragment: 'x'}, {name: 'n', fragment: 5},
    {name: new Array(42).join('x'), fragment: 'x'}, {name: 'long', fragment: new Array(2002).join('x')},
    {name: 'also good', fragment: 'setup=1&game=dofus3', extra: 'dropped'}]);
return names(setupSavedRead(memory(data), 'dofus3'));
"""))

    def test_only_the_name_and_the_fragment_are_kept_from_an_entry(self):
        self.assertEqual([{'name': 'a', 'fragment': 'f'}], self.saved(r"""
var data = {};
data[SETUP_RECIPES.storagePrefix + 'dofus3'] = JSON.stringify([{name: 'a', fragment: 'f', email: 'x@y.z'}]);
return setupSavedRead(memory(data), 'dofus3');
"""))

    def test_a_name_stored_twice_is_read_once_and_no_more_than_five_are_read(self):
        self.assertEqual({'twice': ['a', 'b'], 'six': 5}, self.saved(r"""
var key = SETUP_RECIPES.storagePrefix + 'dofus3';
var data = {}; data[key] = JSON.stringify([{name: 'a', fragment: '1'}, {name: 'b', fragment: '2'}, {name: 'a', fragment: '3'}]);
var big = {}; big[key] = JSON.stringify(many(9));
return {twice: names(setupSavedRead(memory(data), 'dofus3')), six: setupSavedRead(memory(big), 'dofus3').length};
"""))

    def test_each_game_version_has_its_own_list(self):
        self.assertEqual({'key': 'fashionista.setups.dofus3', 'touch': [], 'dofus3': ['mine']}, self.saved(r"""
var store = memory();
setupSavedWrite(store, 'dofus3', [{name: 'mine', fragment: 'setup=1&game=dofus3'}]);
return {key: Object.keys(store.data)[0], touch: setupSavedRead(store, 'touch'),
        dofus3: names(setupSavedRead(store, 'dofus3'))};
"""))

    def test_what_is_written_is_read_back(self):
        self.assertEqual(['one', 'two'], self.saved(r"""
var store = memory();
var ok = setupSavedWrite(store, 'retro', [{name: 'one', fragment: 'f1'}, {name: 'two', fragment: 'f2'}]);
return ok ? names(setupSavedRead(store, 'retro')) : null;
"""))

    def test_a_name_loses_its_extra_spaces_and_stops_at_forty_characters(self):
        self.assertEqual({'spaces': 'a b', 'long': 40, 'cut': 39, 'blank': '', 'tabs': 'a b',
                          'missing': ''}, self.saved(r"""
return {spaces: setupSavedName('  a   b  '), long: setupSavedName(new Array(60).join('x')).length,
        cut: setupSavedName(new Array(40).join('x') + ' yyyy').length, blank: setupSavedName('   '),
        tabs: setupSavedName('a\t\n b'), missing: setupSavedName(undefined)};
"""))

    def test_a_blank_name_saves_nothing(self):
        self.assertEqual({'result': 'blank', 'count': 1}, self.saved(r"""
var put = setupSavedPut(many(1), '   ', 'f');
return {result: put.result, count: put.list.length};
"""))

    def test_a_new_name_is_added_at_the_end(self):
        self.assertEqual({'result': 'saved', 'names': ['setup 0', 'fresh']}, self.saved(r"""
var put = setupSavedPut(many(1), ' fresh ', 'f');
return {result: put.result, names: names(put.list)};
"""))

    def test_a_name_already_saved_is_replaced_in_place(self):
        self.assertEqual({'result': 'saved', 'names': ['setup 0', 'setup 1', 'setup 2'], 'fragment': 'new'},
                         self.saved(r"""
var put = setupSavedPut(many(3), 'setup 1', 'new');
return {result: put.result, names: names(put.list), fragment: put.list[1].fragment};
"""))

    def test_a_setup_the_parser_would_refuse_for_its_length_is_not_saved_and_the_one_of_that_name_stays(self):
        self.assertEqual({'long': 'long', 'kept': ['setup 0', 'setup 1'], 'oldFragment': 'setup=1&game=dofus3',
                          'replace': 'long', 'atLimit': 'saved'}, self.saved(r"""
var tooLong = new Array(SETUP_RECIPES.fragmentLimit + 2).join('x');
var atLimit = new Array(SETUP_RECIPES.fragmentLimit + 1).join('x');
var fresh = setupSavedPut(many(2), 'fresh', tooLong);
var replace = setupSavedPut(many(2), 'setup 1', tooLong);
return {long: fresh.result, kept: names(fresh.list), oldFragment: replace.list[1].fragment,
        replace: replace.result, atLimit: setupSavedPut(many(2), 'fresh', atLimit).result};
"""))

    def test_a_blank_name_is_reported_before_a_fragment_that_is_too_long(self):
        self.assertEqual('blank', self.saved(r"""
return setupSavedPut(many(1), ' ', new Array(SETUP_RECIPES.fragmentLimit + 2).join('x')).result;
"""))

    def test_a_sixth_setup_is_refused_and_the_five_stay_but_a_replacement_still_works(self):
        self.assertEqual({'full': 'full', 'kept': 5, 'replaced': 'saved', 'size': 5}, self.saved(r"""
var refused = setupSavedPut(many(5), 'sixth', 'f');
var replaced = setupSavedPut(many(5), 'setup 4', 'f');
return {full: refused.result, kept: refused.list.length, replaced: replaced.result, size: replaced.list.length};
"""))

    def test_a_put_does_not_change_the_list_it_was_given(self):
        self.assertEqual(True, self.saved(r"""
var list = many(2); var before = JSON.stringify(list);
setupSavedPut(list, 'fresh', 'f'); setupSavedPut(list, 'setup 0', 'g'); setupSavedDrop(list, 0);
return JSON.stringify(list) === before;
"""))

    def test_deleting_removes_the_setup_of_that_name_and_ignores_a_name_nobody_saved(self):
        self.assertEqual({'middle': ['setup 0', 'setup 2'], 'unknown': 3, 'blank': 3, 'number': 3},
                         self.saved(r"""
return {middle: names(setupSavedDrop(many(3), 'setup 1')), unknown: setupSavedDrop(many(3), 'nobody').length,
        blank: setupSavedDrop(many(3), '').length, number: setupSavedDrop(many(3), 1).length};
"""))

    def test_a_setup_is_found_by_its_name_and_not_by_its_place_in_the_list(self):
        self.assertEqual({'found': 'f2', 'unknown': None, 'empty': None}, self.saved(r"""
var list = [{name: 'a', fragment: 'f1'}, {name: 'b', fragment: 'f2'}];
return {found: setupSavedFind(list, 'b').fragment, unknown: setupSavedFind(list, 'c'),
        empty: setupSavedFind([], 'a')};
"""))

    def test_deleting_by_name_after_an_unreadable_entry_shifted_the_list_removes_the_setup_that_was_asked_for(self):
        self.assertEqual({'shown': ['A', 'C'], 'afterDelete': ['A'], 'loaded': 'fc'}, self.saved(r"""
var data = {};
data[SETUP_RECIPES.storagePrefix + 'dofus3'] = JSON.stringify([
    {name: 'A', fragment: 'fa'}, {name: 'B', fragment: new Array(SETUP_RECIPES.fragmentLimit + 2).join('x')},
    {name: 'C', fragment: 'fc'}]);
var shown = setupSavedRead(memory(data), 'dofus3');
return {shown: names(shown), afterDelete: names(setupSavedDrop(shown, 'C')),
        loaded: setupSavedFind(shown, 'C').fragment};
"""))
