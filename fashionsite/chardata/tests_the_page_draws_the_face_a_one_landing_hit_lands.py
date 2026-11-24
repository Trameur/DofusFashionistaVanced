# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The spell page and the set compare pick the face a best or worst element hit lands, run under node."""
import json
import os
import re
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')

_DRIVER = r"""
var vm = require('vm');
var out = {};
global.$ = {
  each: function (items, callback) {
    var keys = Array.isArray(items) ? items.map(function (_v, i) { return i; }) : Object.keys(items);
    for (var i = 0; i < keys.length; i++) {
      if (callback.call(items[keys[i]], keys[i], items[keys[i]]) === false) break;
    }
  },
  extend: function (target) {
    for (var i = 1; i < arguments.length; i++) Object.assign(target, arguments[i]);
    return target;
  }
};
global.isCompareDirectDamageHit = function () { return true; };
global.resolveCompareBestElement = function (element) { return element; };
global.calculateCompareDamageValue = function (hit, isCrit, isMin) { return isMin ? hit.min_dam : hit.max_dam; };
vm.runInThisContext(source);
out.cases = cases.map(function (probe) {
  if (probe.kind == 'face') {
    return indexOfLandedFace(probe.faces, probe.oneLands);
  }
  var hits = probe.values.map(function (value) { return {min_dam: value, max_dam: value}; });
  var faces = hits.map(function (_hit, index) { return [index]; });
  var summary = summarizeCompareHits(probe.spell, hits, false, {}, faces, null);
  return summary && summary.avg;
});
console.log(JSON.stringify(out));
"""


def _source(template, start, end):
    with open(os.path.join(TEMPLATES, template), encoding='utf-8') as handle:
        text = handle.read()
    found = re.search(r'^[ ]*function %s\b.*?(?=^[ ]*function %s\b)' % (start, end), text,
                      re.S | re.M)
    assert found, start
    return found.group(0)


def _run(testcase, source, cases):
    node = shutil.which('node')
    if node is None:
        testcase.skipTest('node is not installed')
    with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as handle:
        handle.write('var source = %s;\nvar cases = %s;\n%s'
                     % (json.dumps(source), json.dumps(cases), _DRIVER))
        name = handle.name
    try:
        done = subprocess.run([node, name], capture_output=True, text=True, encoding='utf-8')
    finally:
        os.unlink(name)
    testcase.assertEqual(done.returncode, 0, done.stderr[-800:])
    return json.loads(done.stdout)['cases']


def _face(low, high):
    return {'min_dam': low, 'max_dam': high}


class ThePagePicksTheLandedFaceTests(SimpleTestCase):

    def _faces(self, one_lands):
        return {'kind': 'face', 'oneLands': one_lands,
                'faces': [_face(10, 12), _face(4, 6), _face(8, 9), _face(4, 6)]}

    def test_a_best_element_hit_shows_its_strongest_face(self):
        source = _source('spells.html', 'indexOfLandedFace', 'getHits')
        self.assertEqual([0], _run(self, source, [self._faces('best')]))

    def test_a_worst_element_hit_shows_its_least_face_and_keeps_the_first_of_a_tie(self):
        source = _source('spells.html', 'indexOfLandedFace', 'getHits')
        self.assertEqual([1], _run(self, source, [self._faces('worst')]))


class TheComparePicksTheLandedFaceTests(SimpleTestCase):

    BLOCKS = [10, 20, 30, 40, 50, 5, 60, 70, 15, 16, 17, 18, 1, 2, 3, 4]

    def _summary(self, scored):
        source = _source('compare_sets.html', 'summarizeCompareHits', 'compareStatsForSpell')
        return _run(self, source, [{'kind': 'sum', 'spell': {'scored': scored},
                                    'values': self.BLOCKS}])[0]

    def test_a_worst_element_hit_scores_the_best_of_the_least_faces(self):
        self.assertEqual(15, self._summary({'worst': 4}))

    def test_without_a_worst_hit_the_best_face_scores(self):
        self.assertEqual(70, self._summary({}))

    def test_a_drawn_hit_scores_the_average_of_its_faces(self):
        self.assertEqual(round(sum(self.BLOCKS) / 16.0), self._summary({'draw': True}))
