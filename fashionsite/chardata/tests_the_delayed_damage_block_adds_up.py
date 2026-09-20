# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The delayed damage block rounds the running total once, so its lines add up."""

from django.test import SimpleTestCase

# Chance values whose two-line panel showed a total that was not the sum of its lines
_CHANCES_TEMOINS = (550, 557, 662, 669, 704, 711)

_VERSION = 'dofus2'
_CLASSE = 'Osamodas'


class _Char(object):
    char_class = _CLASSE
    level = 200


class _Solution(object):

    def __init__(self, stats):
        self._stats = stats
        self.items = {}

    def get_stats_total(self):
        return self._stats


def _stats(chance, ap=12):
    from fashionistapulp.structure import get_structure
    stats = dict((cle, 0) for cle in get_structure(_VERSION).stat_dict_key)
    stats.update({'ap': ap, 'str': 60, 'int': 60, 'agi': 60, 'pow': 30,
                  'earthdam': 40, 'firedam': 40, 'waterdam': 40,
                  'airdam': 40, 'neutdam': 40, 'perspedam': 30, 'ch': 20,
                  'cha': chance})
    return stats


def _panneau(chance, ap=12):
    from chardata.spells_view import _best_combo
    from fashionistapulp.structure import set_current_game_version
    set_current_game_version(_VERSION)
    return _best_combo(_Char(), _Solution(_stats(chance, ap)), _VERSION)


class TheDelayedRowsAddUpToTheirTotalTests(SimpleTestCase):

    def test_the_witnesses_still_show_two_rows(self):
        maigres = []
        for chance in _CHANCES_TEMOINS:
            panneau = _panneau(chance)
            self.assertIsNotNone(panneau, chance)
            lignes = panneau.get('later') or []
            if len(lignes) < 2:
                maigres.append((chance, len(lignes)))
        self.assertFalse(
            maigres,
            'these witnesses no longer reach two delayed rows, so the check '
            'below proves nothing: %s' % maigres)

    def test_the_rows_add_up_to_the_total(self):
        faux = []
        for chance in _CHANCES_TEMOINS:
            panneau = _panneau(chance)
            lignes = panneau.get('later') or []
            somme = sum(ligne['damage'] for ligne in lignes)
            if somme != panneau.get('later_total'):
                faux.append((chance, [l['damage'] for l in lignes], somme,
                             panneau.get('later_total')))
        self.assertFalse(
            faux,
            'the delayed rows do not add up to the total printed above them, '
            'which a reader checking the addition sees: %s' % faux)

    def test_the_total_keeps_the_accurate_value(self):
        panneau = _panneau(550)
        self.assertEqual(503, panneau['later_total'])
        self.assertEqual([214, 289],
                         [ligne['damage'] for ligne in panneau['later']])

    def test_a_single_row_still_says_the_whole_total(self):
        vus = 0
        for chance in (200, 300, 400):
            panneau = _panneau(chance)
            if panneau is None:
                continue
            lignes = panneau.get('later') or []
            if len(lignes) != 1:
                continue
            vus += 1
            self.assertEqual(lignes[0]['damage'], panneau['later_total'],
                             chance)
        self.assertGreater(vus, 0, 'no single-row panel reached')
