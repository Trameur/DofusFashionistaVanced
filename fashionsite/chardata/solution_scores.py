# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

import math
import pickle

from fashionistapulp.structure import (get_current_game_version, get_structure,
                                       set_current_game_version)


# Build-agnostic score for public/shared build cards, on the same scale as the
# item stat weights.
GENERIC_BUILD_WEIGHTS = {
    'ap': 120,
    'mp': 90,
    'range': 55,
    'summon': 30,
    'vit': 0.25,
    'hp': 0.25,
    'wis': 1,
    'str': 1,
    'int': 1,
    'cha': 1,
    'agi': 1,
    'pow': 1,
    'ch': 12,
    'init': 0.02,
    'pp': 0.35,
    'pod': 0.005,
    'lock': 1,
    'dodge': 1,
    'apred': 2,
    'mpred': 2,
    'apres': 2,
    'mpres': 2,
    'dam': 10,
    'neutdam': 9,
    'earthdam': 9,
    'firedam': 9,
    'waterdam': 9,
    'airdam': 9,
    'cridam': 7,
    'pshdam': 7,
    'heals': 8,
    'trapdam': 7,
    'trapdamper': 25,
    'ref': 4,
    'neutres': 2,
    'earthres': 2,
    'fireres': 2,
    'waterres': 2,
    'airres': 2,
    'neutresper': 35,
    'earthresper': 35,
    'fireresper': 35,
    'waterresper': 35,
    'airresper': 35,
    'respermee': 35,
    'resperran': 35,
    'resperwea': 35,
    'pshres': 2,
    'crires': 2,
    'permedam': 35,
    'perrandam': 35,
    'perweadam': 35,
    'perspedam': 35,
    'pvpneutres': 2,
    'pvpearthres': 2,
    'pvpfireres': 2,
    'pvpwaterres': 2,
    'pvpairres': 2,
    'pvpneutresper': 35,
    'pvpearthresper': 35,
    'pvpfireresper': 35,
    'pvpwaterresper': 35,
    'pvpairresper': 35,
}


def calculate_score_from_stats(stats, weights, game_version=None):
    valid_stat_keys = set(
        stat.key for stat in get_structure(game_version).get_stats_list())
    score = 0.0
    has_weight = False
    for stat_key, raw_weight in weights.items():
        if stat_key == 'meleeness' or stat_key not in valid_stat_keys:
            continue
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            continue
        if weight == 0:
            continue
        stat_value = stats.get(stat_key, 0)
        if not isinstance(stat_value, (int, float)):
            continue
        score += stat_value * weight
        has_weight = True

    if not has_weight or not math.isfinite(score):
        return None
    return int(round(score))


def _get_stats_gear_for_version(solution, game_version=None):
    if game_version is None:
        return solution.get_stats_gear()
    previous_game_version = get_current_game_version()
    set_current_game_version(game_version)
    try:
        return solution.get_stats_gear()
    finally:
        set_current_game_version(previous_game_version)


def calculate_project_build_score(char, solution):
    if solution is None or not char.stats_weight:
        return None
    try:
        weights = pickle.loads(char.stats_weight)
    except Exception:
        return None
    if not isinstance(weights, dict):
        return None
    try:
        game_version = getattr(char, 'game_version', None) or 'dofus3'
        return calculate_score_from_stats(
            _get_stats_gear_for_version(solution, game_version),
            weights,
            game_version)
    except Exception:
        return None


def calculate_public_build_score(solution, game_version=None):
    if solution is None:
        return None
    try:
        return calculate_score_from_stats(
            _get_stats_gear_for_version(solution, game_version),
            GENERIC_BUILD_WEIGHTS,
            game_version)
    except Exception:
        return None
