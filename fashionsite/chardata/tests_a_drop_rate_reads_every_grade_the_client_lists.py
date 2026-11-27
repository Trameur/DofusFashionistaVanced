# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A monster drop reads the per-grade rate list of the newer clients and the five grade fields of the older ones."""
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'itemscraper'))
import get_monsters  # noqa: E402

LANGUAGES = ('en', 'fr')


def _dataset(folder, drops):
    record = {'id': 7, 'nameId': 70, 'drops': {'Array': drops}, 'globalDrops': {'Array': []}}
    monsters = {'references': {'RefIds': [{'rid': 1, 'data': record}]},
                'objectsById': {'m_keys': {'Array': [7]}, 'm_values': {'Array': [{'rid': 1}]}}}
    (folder / 'monsters.json').write_text(json.dumps(monsters), encoding='utf-8')
    for lang in LANGUAGES:
        (folder / f'{lang}.json').write_text(json.dumps({'entries': {'70': 'Boss ' + lang}}), encoding='utf-8')
    return get_monsters.build_drops_index(folder, LANGUAGES)


class ADropRateReadsEveryGradeTheClientListsTests(TestCase):
    def test_a_rate_on_the_sixth_grade_alone_is_a_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = _dataset(Path(tmp), [{'objectId': 34890, 'criterions': '',
                                          'percentDropsForGrades': {'Array': [0, 0, 0, 0, 0, 32]}}])
        self.assertEqual([0, 0, 0, 0, 0, 32], index['34890'][0]['rates'])

    def test_the_five_grade_fields_are_still_read(self):
        fields = {'percentDropForGrade%d' % grade: grade for grade in range(1, 6)}
        with tempfile.TemporaryDirectory() as tmp:
            index = _dataset(Path(tmp), [dict(objectId=6900, criterions='PB=1021', **fields)])
        self.assertEqual([1, 2, 3, 4, 5], index['6900'][0]['rates'])
        self.assertEqual('PB=1021', index['6900'][0]['conditions'])

    def test_a_drop_with_no_rate_on_any_grade_is_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = _dataset(Path(tmp), [{'objectId': 1, 'percentDropsForGrades': {'Array': [0, 0, 0, 0, 0, 0]}}])
        self.assertEqual({}, index)
