# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Which item data a build was made with, and which patch that data is."""

from datetime import date, datetime, time, timezone

from django.conf import settings

import fashionista_version


def current_data_version(game_version):
    return settings.SITE_VERSIONS.get(game_version, '')


def patch_of(version):
    if not version:
        return None
    return '.'.join(version.split('.')[:2])


def patch_key(patch):
    return tuple(int(part) for part in patch.split('.'))


def patch_started(game_version):
    entry = fashionista_version.PATCH_STARTED.get(game_version)
    if not entry or entry[0] != patch_of(current_data_version(game_version)):
        return None
    return date.fromisoformat(entry[1])


def _solve_state(solved, current, last_solve_bound, game_version):
    if current is None:
        return None
    if solved is not None:
        if solved == current:
            return 'current'
        return 'older' if patch_key(solved) < patch_key(current) else None
    started = patch_started(game_version)
    if started is None or last_solve_bound is None:
        return None
    if last_solve_bound < datetime.combine(started, time.min, timezone.utc):
        return 'before'
    return None


def build_patch_info(char, generation=None, from_solver=True):
    solved = state = None
    current = patch_of(current_data_version(char.game_version))
    if from_solver and generation is not None:
        solved = patch_of(generation.data_version)
        state = _solve_state(solved, current, generation.created_time,
                             char.game_version)
    elif from_solver and char.minimal_solution:
        solved = patch_of(char.solved_version)
        # Every solve saves the char, so modified_time is never before it
        state = _solve_state(solved, current,
                             char.solved_time or char.modified_time,
                             char.game_version)
    return {
        'created_patch': patch_of(char.created_version),
        'solved_patch': solved,
        'current_patch': current,
        'state': state,
        'stale': state in ('older', 'before'),
    }
