# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One build's turn on another: the headline and the reverse turn both come from turn_on."""

from chardata.targets import build_target

REVERSE_CAST_FIELDS = ('name', 'image_url', 'ap', 'damage', 'late', 'late_title', 'running')


def turn_on(attacker, attacker_solution, game_version, buff_state=None, levels=None,
            pushback=False, note_without_buffs=True, target=None):
    """The attacker's best turn on a build target, the same payload as the spells page."""
    from chardata.spells_view import _best_combo
    return _best_combo(attacker, attacker_solution, game_version, buff_state, levels, pushback,
                       note_without_buffs, target=target)


def their_turn(char, solution, target, game_version, pushback=False):
    """The target build's best turn on this build, by turn_on with the roles swapped; None without one."""
    if target is None or target.kind != 'build' or not target.source:
        return None
    other, other_solution = target.source
    combo = turn_on(other, other_solution, game_version, pushback=pushback,
                    note_without_buffs=False,
                    target=build_target(char, solution, game_version))
    if not combo:
        return None
    return {'name': target.label,
            'total': combo['total'],
            'raw_total': combo.get('raw_total'),
            'later_total': combo['later_total'],
            'hp_share': combo['target']['hp_share'],
            'casts': [{field: cast[field] for field in REVERSE_CAST_FIELDS}
                      for cast in combo['casts']],
            'not_counted': combo['not_counted']}
