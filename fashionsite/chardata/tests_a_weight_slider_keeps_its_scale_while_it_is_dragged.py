# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weight slider keeps its scale while it is dragged, and widens it once the handle is released."""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'static', 'chardata', 'weights_minimums.js')
FUNCTIONS = ('widened', 'refreshSlider', 'buildSlider')

PAGE_STUB = r"""
var ranges = {pa: [0, 100]};
var box = {value: '40'};
var slider = {length: 1, store: {}, options: {}, value: null,
    data: function(name, value) {
        if (value === undefined) { return this.store[name]; }
        this.store[name] = value;
        return this;
    },
    slider: function(first, second, third) {
        if (typeof first === 'object') {
            this.options = first;
            this.value = first.value;
        } else if (first === 'option') {
            this.options[second] = third;
        } else if (first === 'value') {
            this.value = second;
        }
        return this;
    },
    find: function() { return {attr: function() {}}; }};
var $row = {find: function() { return slider; }, attr: function() { return 'pa'; }};
function boxOf() {
    return {val: function(value) {
                if (value === undefined) { return box.value; }
                box.value = String(value);
                return this;
            },
            trigger: function() { refreshSlider($row); return this; }};
}
function type(value) { box.value = String(value); refreshSlider($row); }
function drag(fractions) {
    var event = {originalEvent: {}};
    if (slider.options.start) { slider.options.start(event, {value: slider.value}); }
    fractions.forEach(function(fraction) {
        var low = slider.options.min, high = slider.options.max;
        var value = Math.round(low + fraction * (high - low));
        slider.options.slide(event, {value: value});
        slider.value = value;
    });
    if (slider.options.stop) { slider.options.stop(event, {value: slider.value}); }
    slider.options.change(event, {value: slider.value});
}
function state() { return {box: box.value, handle: slider.value, top: slider.options.max}; }
"""


def _functions():
    source = io.open(SCRIPT, encoding='utf-8').read()
    found = []
    for name in FUNCTIONS:
        match = re.search(r'\n    function %s\(.*?\n    \}\n' % name, source, re.S)
        if match is None:
            raise AssertionError('weights_minimums.js has no function %s' % name)
        found.append(match.group(0))
    return '\n'.join(found)


def run_page_script(case, body):
    node = shutil.which('node')
    if node is None:
        case.skipTest('node is not installed')
    source = '\n'.join([PAGE_STUB, _functions(), 'buildSlider($row);',
                        'console.log(JSON.stringify((function() {%s})()));' % body])
    with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as handle:
        handle.write(source)
        name = handle.name
    try:
        done = subprocess.run([node, name], capture_output=True, text=True)
    finally:
        os.unlink(name)
    case.assertEqual(0, done.returncode, done.stderr[-800:])
    return json.loads(done.stdout)


class AWeightSliderKeepsItsScaleTests(SimpleTestCase):

    def test_a_handle_held_near_the_end_stays_on_the_value_under_the_pointer(self):
        self.assertEqual({'box': '90', 'handle': 90, 'top': 135}, run_page_script(self, """
            drag([0.5, 0.7, 0.8, 0.9, 0.9, 0.9, 0.9, 0.9]);
            return state();"""))

    def test_a_handle_pushed_to_the_end_stops_at_the_top_of_the_scale(self):
        self.assertEqual({'box': '100', 'handle': 100, 'top': 150}, run_page_script(self, """
            drag([0.6, 1, 1, 1, 1, 1, 1, 1]);
            return state();"""))

    def test_the_scale_widens_between_two_drags(self):
        self.assertEqual({'box': '150', 'handle': 150, 'top': 225}, run_page_script(self, """
            drag([1, 1, 1]);
            drag([1, 1, 1]);
            return state();"""))

    def test_a_typed_weight_still_widens_the_scale_at_once(self):
        self.assertEqual({'box': '300', 'handle': 300, 'top': 450}, run_page_script(self, """
            type(300);
            return state();"""))

    def test_a_drag_below_two_thirds_leaves_the_scale_alone(self):
        self.assertEqual({'box': '20', 'handle': 20, 'top': 100}, run_page_script(self, """
            drag([0.3, 0.2, 0.2]);
            return state();"""))
