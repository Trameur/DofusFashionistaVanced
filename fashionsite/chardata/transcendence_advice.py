# -*- coding: utf-8 -*-
"""The transcendence rune worth the most on a generated item.

A rune finalises the item at 100% and then locks it, so there is exactly one
worth naming per item: the one whose bonus the build values most. The game
gates it on a piece a smithmagic skill works on, carrying no over, no exotic
line and no Dracorune, and on the rune's own weight plus the current weight of
the stat it raises staying within the cap.
"""
from chardata.forgemagie_data import OVER_WEIGHT_CAP, get_fm_stat
from chardata.forgemagie_transcendance import get_transcendence_runes
from fashionistapulp.transcendence_terms import takes_transcendence_rune


def _fits(game_version, rune, item_stats):
    stat = get_fm_stat(game_version, rune['stat_key'])
    if stat is None:
        return False
    current = max(item_stats.get(rune['stat_key'], 0) or 0, 0)
    return rune['weight'] + current * stat['density'] <= OVER_WEIGHT_CAP


def best_transcendence(game_version, item_stats, weights, item_type,
                       weapon_key=None, locked=False):
    """The rune the build gains most from, or None when none is worth naming."""
    if not weights or locked or not takes_transcendence_rune(item_type, weapon_key):
        return None
    best = None
    for rune in get_transcendence_runes(game_version):
        gain = rune['bonus'] * (weights.get(rune['stat_key'], 0) or 0)
        if gain <= 0 or not _fits(game_version, rune, item_stats):
            continue
        # A heavier rune of the same family always beats a lighter one it can
        # replace, so ties go to the bigger bonus.
        if best is None or (gain, rune['bonus']) > (best[0], best[1]['bonus']):
            best = (gain, rune)
    return best[1] if best else None
