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


def last_change(char, generation=None):
    """The snapshot's time, else the later of the last solve and the last save."""
    if generation is not None:
        return generation.created_time
    moments = [moment for moment in (char.solved_time, char.modified_time)
               if moment is not None]
    return max(moments) if moments else None


def build_patch_info(char, generation=None, has_solution=None):
    """has_solution says whether a set is stored, read from the char when None."""
    game_version = char.game_version
    current = patch_of(current_data_version(game_version))
    if has_solution is None:
        has_solution = bool(char.minimal_solution)
    patch = None
    if has_solution:
        patch = patch_in_force(game_version, last_change(char, generation))
    return {
        'patch': patch,
        'current_patch': current,
        'older': bool(patch and current and patch_key(patch) < patch_key(current)),
    }
