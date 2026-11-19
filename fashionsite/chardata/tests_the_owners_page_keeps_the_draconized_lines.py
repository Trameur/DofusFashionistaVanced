# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On the owner's page a draconized piece with a recorded roll keeps the server's moved lines and offers no stat customization."""

import io
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile

from django.template.loader import render_to_string

from chardata.dracorune_fixtures import (OPTIONS, BetaModelTestCase, eligible_items,
                                         element_key, element_move, runes, structure)
from chardata.solution_result import SolutionResult
from chardata.translation_util import localized_stat_name
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, 'templates', 'chardata', 'solution.html')

_PAGE_STUB = r"""
var nodes = {};
var posts = [];
var isGuest = false;
var apiBase = '';
var EXO_PER_ITEM = false;
var statFilterOptions = [];
var exoStatIds = {};
var trueExoOverrides = {};
var exoBaselineByItem = {};
function update_stats() {}
function $(selector) {
    if (selector.charAt(0) === '#') {
        var state = nodes[selector] = nodes[selector] || {emptied: 0};
        var found = {length: present.indexOf(selector.slice(1)) >= 0 ? 1 : 0,
                     empty: function() { state.emptied += 1; return found; },
                     append: function() { return found; }};
        return found;
    }
    var made = {length: 1};
    ['append', 'addClass', 'css', 'attr'].forEach(function(name) {
        made[name] = function() { return made; };
    });
    return made;
}
$.each = function(items, run) {
    Object.keys(items).forEach(function(key) { run(key, items[key]); });
};
$.post = function(url, data, done) { posts.push(done); };
"""


def _page_functions():
    page = io.open(PAGE, encoding='utf-8').read()
    names = ('exoCountsOf', 'rebuildStatsDisplay', 'rebuildOverriddenItems')
    return '\n'.join(re.search(r'\n        function %s\(.*?\n        \}\n' % name, page, re.S).group(0)
                     for name in names)


def lines_of(item):
    lines = {}
    for stat_id, value in item.stats:
        key = structure().get_stat_by_id(stat_id).key
        lines[key] = lines.get(key, 0) + value
    return lines


class TheOwnersPageKeepsTheDraconizedLinesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.key = element_key(self.source, self.target)
        self.hat, self.cloak = (
            next(item for item in eligible_items(type_name)
                 if lines_of(item).get(self.source, 0) > 1
                 and self.key in dict(dracorunes.variants(list(lines_of(item).items()), runes())))
            for type_name in ('Hat', 'Cloak'))
        self.source_id = structure().get_stat_by_key(self.source).id
        self.rolled = lines_of(self.hat)[self.source] - 1
        self.overrides = {self.hat.id: {self.source_id: self.rolled},
                          self.cloak.id: {self.source_id: lines_of(self.cloak)[self.source] - 1}}

    def cards(self):
        minimal = ModelResultMinimal(
            {'hat': self.hat.id, 'cloak': self.cloak.id},
            {'options': dict(OPTIONS), 'char_level': 200,
             'base_stats_by_attr': dict({name: 0 for name, _key in STATS_NAMES}, AP=7, MP=3)},
            None)
        minimal.dracorunes = {'hat': (self.hat.id, self.key)}
        result = model_result_from_minimal(pickle.loads(pickle.dumps(minimal)), self.overrides)
        params = SolutionResult(result).get_params()
        return {item.slot: item for item in params['all_items'] if item.item_added}

    def run_page(self, pages):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        present = sorted({name for page in pages for name in re.findall(r'id="([^"]+)"', page)})
        overrides = {str(item_id): {str(stat_id): value for stat_id, value in lines.items()}
                     for item_id, lines in self.overrides.items()}
        source = '\n'.join([
            'var present = %s;' % json.dumps(present),
            'var itemIds = %s;' % json.dumps({'hat': self.hat.id, 'cloak': self.cloak.id}),
            'var statOverrides = %s;' % json.dumps(overrides),
            _PAGE_STUB, _page_functions(),
            'rebuildOverriddenItems();',
            'posts.forEach(function(done) { done({stats: []}); });',
            'console.log(JSON.stringify({hat: (nodes["#stat-lines-hat"] || {}).emptied || 0,'
            ' cloak: (nodes["#stat-lines-cloak"] || {}).emptied || 0}));'])
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write(source)
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_rolled_line_is_drawn_moved(self):
        hat = self.cards()['hat']
        self.assertEqual(self.rolled, hat.stats[self.target])
        self.assertNotIn(self.source, hat.stats)
        page = render_to_string('chardata/solution_item.html', {'item': hat})
        drawn = page[page.index('id="stat-lines-hat"'):page.index('id="dracorune-hat"')]
        target = localized_stat_name(structure().get_stat_by_key(self.target).name)
        self.assertIn('%d %s' % (self.rolled, target), drawn)

    def test_only_the_undraconized_piece_offers_its_stat_customization(self):
        cards = self.cards()
        hat = render_to_string('chardata/solution_item.html', {'item': cards['hat']})
        cloak = render_to_string('chardata/solution_item.html', {'item': cards['cloak']})
        self.assertNotIn('stat-override-btn-sol-hat', hat)
        self.assertIn('stat-override-btn-sol-cloak', cloak)

    def test_the_page_script_redraws_only_the_undraconized_piece(self):
        cards = self.cards()
        pages = [render_to_string('chardata/solution_item.html', {'item': card})
                 for card in cards.values()]
        self.assertEqual({'hat': 0, 'cloak': 1}, self.run_page(pages))
