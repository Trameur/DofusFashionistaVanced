import collections
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.append(SCRAPER)
import get_spells_wakfu as harvest  # noqa: E402


def spell(wakfu_class, name):
    return {'class': wakfu_class, 'name': name, 'element': 'FIRE',
            'levels': {'245': {'ap': 3}}}


class APartialWakfuSpellRefreshKeepsTheOtherClassesTests(SimpleTestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.out = Path(folder.name)
        self.build = self.out / '1.93.1.62'
        self.build.mkdir()
        self.calls = []

    def write(self, spells, meta):
        (self.build / 'spells_fr.json').write_text(
            json.dumps(spells), encoding='utf-8')
        if meta is not None:
            (self.build / 'spells_fr.meta.json').write_text(
                json.dumps(meta), encoding='utf-8')

    def read(self, name):
        return json.loads((self.build / name).read_text(encoding='utf-8'))

    def run_main(self, *arguments, found=None):
        def collect(language, classes, limit, report, known, save, pace):
            self.calls.append({'classes': list(classes), 'known': dict(known),
                               'pace': pace})
            out = dict(known)
            out.update(found or {})
            save(out)
            return out

        with mock.patch.object(harvest, 'collect', collect), \
                contextlib.redirect_stdout(io.StringIO()):
            return harvest.main(['--lang', 'fr', '--out', str(self.out),
                                 '--version', '1.93.1.62'] + list(arguments))

    def test_a_refresh_of_one_class_keeps_every_other_class(self):
        self.write({'1': spell(1, 'Kept'), '2': spell(11, 'Old sacrier'),
                    '3': spell(11, 'Gone sacrier')},
                   {'parser': 'older', 'spells': 3})
        self.run_main('--refresh', '--classes', '11',
                      found={'2': spell(11, 'New sacrier')})
        self.assertEqual({'1': spell(1, 'Kept')}, self.calls[0]['known'])
        self.assertEqual([11], self.calls[0]['classes'])
        self.assertEqual({'1': spell(1, 'Kept'), '2': spell(11, 'New sacrier')},
                         self.read('spells_fr.json'))

    def test_the_stamp_says_which_parser_read_each_class(self):
        self.write({'1': spell(1, 'Kept'), '2': spell(11, 'Old sacrier')},
                   {'parser': 'older', 'spells': 2})
        self.run_main('--refresh', '--classes', '11',
                      found={'2': spell(11, 'New sacrier')})
        meta = self.read('spells_fr.meta.json')
        self.assertEqual({'1': 'older', '11': harvest.fingerprint()},
                         meta['classes'])
        self.assertTrue(meta['parser'].startswith('mixed-'))
        self.assertEqual(2, meta['spells'])

    def test_a_run_that_reads_nothing_keeps_the_stamp_it_had(self):
        self.write({'1': spell(1, 'Kept')}, {'parser': 'older', 'spells': 1})
        self.run_main()
        self.assertEqual('older', self.read('spells_fr.meta.json')['parser'])

    def test_a_full_refresh_is_stamped_with_this_parser(self):
        self.write({'1': spell(1, 'Old')}, {'parser': 'older', 'spells': 1})
        self.run_main('--refresh', found={'1': spell(1, 'New')})
        meta = self.read('spells_fr.meta.json')
        self.assertEqual(harvest.fingerprint(), meta['parser'])
        self.assertEqual({'1': harvest.fingerprint()}, meta['classes'])

    def test_spells_a_known_parser_did_not_read_leave_no_stamp(self):
        self.write({'1': spell(1, 'Kept')}, None)
        self.run_main('--classes', '11', found={'2': spell(11, 'New')})
        meta = self.read('spells_fr.meta.json')
        self.assertIsNone(meta['parser'])
        self.assertIsNone(meta['classes']['1'])

    def test_one_class_read_by_two_parsers_leaves_no_stamp(self):
        self.write({'1': spell(1, 'Kept')}, {'parser': 'older', 'spells': 1})
        self.run_main('--classes', '1', found={'2': spell(1, 'New')})
        meta = self.read('spells_fr.meta.json')
        self.assertIsNone(meta['classes']['1'])
        self.assertIsNone(meta['parser'])

    def test_the_two_harvests_of_one_mix_carry_the_same_stamp(self):
        stamps = [harvest.parser_stamps(
            {'1': spell(1, name), '2': spell(11, name)}, {'2'},
            {'parser': 'older'})['parser'] for name in ('fr', 'en')]
        self.assertEqual(stamps[0], stamps[1])
        other = harvest.parser_stamps(
            {'1': spell(1, 'x'), '2': spell(11, 'x')}, {'1'},
            {'parser': 'older'})['parser']
        self.assertNotEqual(stamps[0], other)

    def test_the_pace_reaches_the_harvest(self):
        self.write({}, None)
        self.run_main('--pace', '1.5')
        self.assertEqual(1.5, self.calls[0]['pace'])
        self.run_main()
        self.assertEqual(harvest.PACE, self.calls[1]['pace'])

    def test_the_pace_is_the_wait_after_each_spell_page(self):
        with mock.patch.object(harvest, 'opener'), \
                mock.patch.object(harvest, 'read_page', return_value='page'), \
                mock.patch.object(harvest, 'spell_links',
                                  return_value=[('/a', 7, 'Seven', 'FIRE'),
                                                ('/b', 8, 'Eight', 'FIRE')]), \
                mock.patch.object(harvest, 'read_spell', return_value={245: {}}), \
                mock.patch.object(harvest.time, 'sleep') as sleep, \
                contextlib.redirect_stdout(io.StringIO()):
            found = harvest.collect('fr', [1], None, collections.Counter(),
                                    pace=1.5)
        self.assertEqual(['7', '8'], sorted(found))
        self.assertEqual([mock.call(1.5), mock.call(1.5)], sleep.call_args_list)

    def test_a_negative_pace_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            self.run_main('--pace', '-1')
        self.assertEqual([], self.calls)
