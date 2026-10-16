# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Past its own budget, a quick step's waiting screen counts towards the exact search it may run when it found no set, in the page language."""
import json
import os
import re
import shutil
import subprocess
import tempfile
from unittest import mock

from django.test import TestCase
from django.utils import translation
from django.utils.html import escapejs

from chardata import fashion_action
from chardata.models import Char
from chardata.options import set_options
from chardata.tests_a_quick_search_says_how_close_to_the_best_it_stopped_and_never_proven import (
    stopped_within_the_gap)
from chardata.tests_a_quick_step_that_runs_out_of_time_without_a_set_searches_again_exactly import (
    _RetroFlow, cut_set)
from chardata.tests_the_waiting_screen_shows_the_builds_time_budget import (
    LANGUAGES, _WaitingMixin, _trans_tag)

STILL_SEARCHING = 'Still searching: %(elapsed)s s (at most %(budget)s s)'


class AQuickStepCountsItsSearchAgainTests(_WaitingMixin, TestCase):
    version = 'retro'
    prefix = '/retro'

    def build_at(self, power):
        char = self.build()
        if power is not None:
            set_options(char, {'power': power})
            char.save()
        return Char.objects.get(pk=char.pk)

    def further(self, page):
        found = re.findall(r'<div[^>]*class="loading-progress"[^>]*>', page)
        self.assertEqual(1, len(found), 'one progress bar on the page')
        further = re.search(r'data-retry-budget="([^"]*)"', found[0])
        return further.group(1) if further else None

    def test_a_quick_step_counts_on_after_its_budget_up_to_standard(self):
        for power in ('flash', 'fast'):
            with self.subTest(power=power):
                char = self.build_at(power)
                page = self.weights_page(char)
                budget, _maximum = self.budget(page)
                self.assertLess(int(budget), fashion_action.GUARD_BUDGET_SECONDS)
                self.assertEqual(str(fashion_action.GUARD_BUDGET_SECONDS), self.further(page))

    def test_standard_has_nothing_to_count_on_to(self):
        self.assertIsNone(self.further(self.weights_page(self.build_at(None))))

    def test_each_language_says_the_search_goes_on(self):
        char = self.build_at('flash')
        for language in LANGUAGES:
            with self.subTest(language=language):
                page = self.weights_page(char, language)
                with translation.override(language):
                    still = _trans_tag(STILL_SEARCHING)
                if language != 'en':
                    self.assertNotEqual(STILL_SEARCHING, still)
                self.assertIn("'%s'" % escapejs(still), page)
                self.assertNotIn('%%(', page)

    def test_the_counter_switches_to_the_search_again_budget_once_past_its_own(self):
        page = self.weights_page(self.build_at('flash'))
        self.assertIn("Number(bar.attr('data-retry-budget'))", page)
        self.assertIn('interpolate(stillSearching, {elapsed: elapsed, budget: further}, true)',
                      page)


_PAGE_STUB = r"""
var now = 0, ticker = null, widths = [], labels = [], solveProgressTimer = null;
Date.now = function() { return now * 1000; };
function setInterval(callback) { ticker = callback; return 1; }
function clearInterval() {}
function interpolate(format, values) {
    return format.replace(/%\(\w+\)s/g, function(name) { return String(values[name.slice(2, -2)]); });
}
var fill = {css: function(name, value) { widths.push(parseFloat(value)); return fill; }};
var bar = {length: 1,
           attr: function(name, value) {
               if (value === undefined) { return attrs[name]; }
               attrs[name] = String(value);
               return bar;
           },
           children: function() { return fill; }};
var label = {text: function(value) { labels.push(value); return label; }};
function $(selector) { return selector === '.loading-progress' ? bar : label; }
"""


class TheWaitingBarOfAQuickStepNeverMovesBackTests(_WaitingMixin, TestCase):
    version = 'retro'
    prefix = '/retro'
    build_at = AQuickStepCountsItsSearchAgainTests.build_at

    def run_counter(self, page, seconds):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        found = re.findall(r'<div[^>]*class="loading-progress"[^>]*>', page)[0]
        attrs = dict(re.findall(r'(data-[\w-]+)="([^"]*)"', found))
        script = '\n'.join([
            _PAGE_STUB, 'var attrs = %s;' % json.dumps(attrs),
            re.search(r'function startSolveProgress\(budget\) \{.*?\n\}\n', page, re.S).group(0),
            'startSolveProgress();',
            'for (now = 1; now <= %d; now++) { ticker(); }' % seconds,
            'console.log(JSON.stringify({widths: widths, labels: labels}));'])
        handle, name = tempfile.mkstemp(suffix='.js')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as out:
                out.write(script)
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.remove(name)
        self.assertEqual(0, done.returncode, done.stderr)
        return json.loads(done.stdout)

    def test_the_bar_never_moves_back_when_the_counter_goes_on_to_the_search_again(self):
        counted = self.run_counter(self.weights_page(self.build_at('flash')),
                                   fashion_action.GUARD_BUDGET_SECONDS + 2)
        self.assertTrue(any(text.startswith('Still searching') for text in counted['labels']))
        self.assertEqual('Almost done', counted['labels'][-1])
        for second, (before, after) in enumerate(zip(counted['widths'], counted['widths'][1:])):
            with self.subTest(second=second + 1):
                self.assertLessEqual(before, after)


class SearchOnAQuickSetCountsTheBudgetItRunsOnTests(_RetroFlow, TestCase):

    def search_on_budget(self, page):
        form = re.search(r'<form[^>]*class="solver-continue-search"[^>]*>', page)
        self.assertIsNotNone(form, 'the page offers Search on')
        return re.search(r'onsubmit="loadingAndRunUnchecked\((\d*)\);"', form.group(0)).group(1)

    def deadline_left(self, char):
        seen = {}

        def capture(request, char, blob, minimal, solve_input, deadline):
            seen['left'] = deadline - fashion_action.time.monotonic()
        with mock.patch('chardata.fashion_action._continue_search', side_effect=capture):
            self.client.post('%s/continuesearch/%d/' % (self.prefix, char.pk))
        return seen['left']

    def test_search_on_a_quick_set_cut_by_its_clock_counts_to_the_seconds_it_searches(self):
        for power in ('flash', 'fast'):
            with self.subTest(power=power):
                char = self.build_at(power)
                self.fashion(char, cut_set(self.hat, 10))
                budget = self.search_on_budget(self.page(char))
                self.assertEqual(str(fashion_action.GUARD_BUDGET_SECONDS), budget)
                self.assertEqual(int(budget), round(self.deadline_left(char)))

    def test_search_on_a_quick_set_stopped_within_its_gap_counts_to_the_seconds_it_searches(self):
        char = self.build_at('flash')
        self.fashion(char, stopped_within_the_gap(self.hat, 1000.0, 1020.0))
        self.assertEqual(str(fashion_action.GUARD_BUDGET_SECONDS),
                         self.search_on_budget(self.page(char)))

    def test_search_on_a_standard_set_keeps_the_page_budget(self):
        char = self.build_at(None)
        self.fashion(char, cut_set(self.hat, 95))
        self.assertEqual('', self.search_on_budget(self.page(char)))
