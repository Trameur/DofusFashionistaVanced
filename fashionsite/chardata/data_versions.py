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


def patch_timeline(game_version):
    """[(day, patch)] in order, empty for a version without one."""
    return [(date.fromisoformat(day), patch) for day, patch
            in fashionista_version.PATCH_TIMELINE.get(game_version, ())]


def _day_start(day):
    return datetime.combine(day, time.min, timezone.utc)


def _timeline_of_current(game_version):
    timeline = patch_timeline(game_version)
    if not timeline or timeline[-1][1] != patch_of(current_data_version(game_version)):
        return []
    return timeline


def patch_started(game_version):
    timeline = _timeline_of_current(game_version)
    return timeline[-1][0] if timeline else None


def previous_patch_window(game_version):
    """UTC start and end of the patch before the current one, or None."""
    timeline = _timeline_of_current(game_version)
    if len(timeline) < 2:
        return None
    return _day_start(timeline[-2][0]), _day_start(timeline[-1][0])


def patch_in_force(game_version, moment):
    """The patch our data was on at that moment, None before the first entry."""
    if moment is None:
        return None
    day = moment.astimezone(timezone.utc).date()
    found = None
    for started, patch in patch_timeline(game_version):
        if started > day:
            break
        found = patch
    return found


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
    if last_solve_bound < _day_start(started):
        return 'before'
    return None


def _recorded_or_estimated(version, game_version, moment):
    patch = patch_of(version)
    if patch is not None:
        return patch, False
    patch = patch_in_force(game_version, moment)
    return patch, patch is not None


def build_patch_info(char, generation=None, from_solver=True, has_solution=None):
    """has_solution says whether a set is stored, read from the char when None."""
    game_version = char.game_version
    current = patch_of(current_data_version(game_version))
    created, created_estimated = _recorded_or_estimated(
        char.created_version, game_version, char.created_time)
    solved = state = None
    solved_estimated = False
    if has_solution is None:
        has_solution = bool(char.minimal_solution)
    if from_solver and generation is not None:
        solved, solved_estimated = _recorded_or_estimated(
            generation.data_version, game_version, generation.created_time)
        state = _solve_state(solved, current, generation.created_time,
                             game_version)
    elif from_solver and has_solution:
        # Every solve saves the char, so modified_time is never before it
        moment = char.solved_time or char.modified_time
        solved, solved_estimated = _recorded_or_estimated(
            char.solved_version, game_version, moment)
        state = _solve_state(solved, current, moment, game_version)
    return {
        'created_patch': created,
        'created_estimated': created_estimated,
        'solved_patch': solved,
        'solved_estimated': solved_estimated,
        'current_patch': current,
        'state': state,
        'stale': state in ('older', 'before'),
    }
