# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Presets shared by the doors that create a build: styles, default elements, boxes, priorities, modes."""

import logging
import math
import pickle
from collections import namedtuple

from django.utils.translation import gettext, gettext_lazy, pgettext_lazy

from chardata.char_blobs import read_char_blob
from chardata.default_elements import version_element
from chardata.models import Char
from chardata.options import set_setup_choices
from chardata.smart_build import (get_char_aspects, get_elements, get_standard_weights,
                                  reapply_weights, set_char_aspects)
from chardata.stats_weights import get_stats_weights
from chardata.version_compat import class_exists_in_version, filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.game_versions import DEFAULT_VERSION
from fashionistapulp.model import EFFECTIVE_HP_MINIMUM
from fashionistapulp.structure import get_structure

logger = logging.getLogger(__name__)


# For a class default_elements/<version>.json does not list
CLASS_DEFAULT_ELEMENT = {
    'Iop': 'str',
    'Cra': 'agi',
    'Sram': 'agi',
    'Xelor': 'cha',
    'Eniripsa': 'int',
    'Feca': 'int',
    'Sacrier': 'agi',
    'Sadida': 'cha',
    'Enutrof': 'cha',
    'Osamodas': 'cha',
    'Ecaflip': 'cha',
    'Pandawa': 'str',
    'Eliotrope': 'cha',
    'Huppermage': 'int',
    'Ouginak': 'agi',
    'Masqueraider': 'agi',
    'Foggernaut': 'int',
    'Rogue': 'agi',
    'Forgelance': 'str',
}
FALLBACK_ELEMENT = 'str'

Style = namedtuple('Style', 'key label build_name_word aspects takes_element')

STYLES = (
    Style('solo_pvm', gettext_lazy('Solo PvM: focus damage'), gettext_lazy('solo PvM'),
          frozenset({'glasscannon'}), True),
    Style('group_pvm', gettext_lazy('Group PvM: tanky / support'), gettext_lazy('group PvM'),
          frozenset({'vit', 'res'}), True),
    Style('pvp', gettext_lazy('PvP: critical hits'), gettext_lazy('PvP'),
          frozenset({'pvp', 'crit'}), True),
    Style('farm', gettext_lazy('Farm / Level-up: Prospecting & Wisdom'), gettext_lazy('farm'),
          frozenset({'wis', 'pp'}), False),
)
STYLE_BY_KEY = {style.key: style for style in STYLES}
DEFAULT_STYLE = 'solo_pvm'

ELEMENT_BOXES = ('str', 'int', 'cha', 'agi', 'omni')
FOCUS_COLUMNS = (('balanced', 'vit', 'glasscannon', 'dam', 'heal', 'aprape', 'mprape', 'crit'),
                 ('res', 'wis', 'pp', 'pods', 'trap', 'summon', 'pushback', 'noncrit'))
FOCUS_LIMIT = 2

ELEMENT_DAMAGE = {'str': 'earthdam', 'int': 'firedam', 'cha': 'waterdam', 'agi': 'airdam'}
SECOND_ELEMENT_SHARE = 0.5

Priority = namedtuple('Priority', 'key label aspects')

PRIORITIES = (
    Priority('balanced', gettext_lazy('No priority'), frozenset()),
    Priority('damage', pgettext_lazy('Priority', 'Damage'), frozenset({'glasscannon'})),
    Priority('defense', gettext_lazy('Defense'), frozenset({'vit', 'res'})),
    Priority('heals', pgettext_lazy('Priority', 'Heals'), frozenset({'heal'})),
)
PRIORITY_BY_KEY = {priority.key: priority for priority in PRIORITIES}
DEFAULT_PRIORITY = 'balanced'

PlayMode = namedtuple('PlayMode', 'key label boxes')

PLAY_MODES = (
    PlayMode('general', gettext_lazy('General (all content)'), frozenset()),
    PlayMode('pvm_solo', gettext_lazy('Solo PvM'), frozenset()),
    PlayMode('koli_1v1', gettext_lazy('Kolossium 1v1'), frozenset({'pvp', 'duel'})),
    PlayMode('koli_2v2', gettext_lazy('Kolossium 2v2'), frozenset({'pvp'})),
    PlayMode('koli_3v3', gettext_lazy('Kolossium 3v3'), frozenset({'pvp'})),
    PlayMode('aggression_1v1', gettext_lazy('Aggression 1v1'), frozenset({'pvp', 'duel'})),
    PlayMode('group_pvp', gettext_lazy('Group PvP (prisms, perceptors)'), frozenset({'pvp'})),
)
PLAY_MODE_BY_KEY = {mode.key: mode for mode in PLAY_MODES}
DEFAULT_PLAY_MODE = 'general'
MODE_OPTION_BOXES = frozenset({'pvp', 'duel'})

GUARD_DEFAULT_PERCENT = 10
GUARD_PERCENTS = (5, 10, 15, 20)
GUARD_KIND = {'damage': 'effective_hp', 'defense': 'turn', 'heals': 'turn'}
PERCENT_RESIST_KEYS = ('neutresper', 'earthresper', 'fireresper', 'waterresper', 'airresper')
TURN_GUARD_ADV_MINS = {'str': ('powstr', 'damstr'), 'int': ('powint', 'damint'),
                       'cha': ('powcha', 'damcha'), 'agi': ('powagi', 'damagi')}

VERSION_PRESETS = {
    'dofus3': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
               'option_boxes': ('pvp', 'duel'),
               'modes': ('general', 'pvm_solo', 'koli_1v1', 'koli_2v2', 'koli_3v3')},
    'beta': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
             'option_boxes': ('pvp', 'duel'),
             'modes': ('general', 'pvm_solo', 'koli_1v1', 'koli_3v3')},
    'dofus2': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
               'option_boxes': ('pvp', 'duel'),
               'modes': ('general', 'pvm_solo', 'koli_1v1', 'koli_2v2', 'koli_3v3')},
    'touch': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
              'option_boxes': ('pvp', 'duel'),
              'modes': ('general', 'pvm_solo', 'koli_1v1', 'koli_3v3')},
    'retro': {'styles': ('solo_pvm', 'group_pvm', 'pvp', 'farm'),
              'option_boxes': ('pvp', 'duel'),
              'modes': ('general', 'pvm_solo', 'aggression_1v1', 'group_pvp')},
}


def version_presets(game_version):
    return VERSION_PRESETS.get(game_version, VERSION_PRESETS[DEFAULT_VERSION])


def play_styles(game_version):
    """[(key, label)] the quick start offers on this version."""
    return [(key, STYLE_BY_KEY[key].label)
            for key in version_presets(game_version)['styles']]


def offered_style(style, game_version):
    """The style if this version offers it, else the default one."""
    if style in version_presets(game_version)['styles']:
        return style
    return DEFAULT_STYLE


def version_class(char_class, game_version):
    """The class a build gets on the version: its own, else the version's first class."""
    if char_class in CHARACTER_CLASSES and class_exists_in_version(char_class, game_version):
        return char_class
    classes = filter_classes_for_version(CHARACTER_CLASSES, game_version)
    return classes[0] if classes else CHARACTER_CLASSES[0]


def default_element(char_class, game_version=None, level=None):
    """The class's element in the version's table at the nearest level, else the shared one."""
    return (version_element(char_class, game_version, level)
            or CLASS_DEFAULT_ELEMENT.get(char_class, FALLBACK_ELEMENT))


def style_aspects(style, char_class=None, element=None, game_version=None, level=None):
    """The aspects a style sets, plus the element (the class's own on the version and level unless given) when the style takes one."""
    preset = STYLE_BY_KEY.get(style)
    aspects = set(preset.aspects) if preset is not None else set()
    if preset is None or preset.takes_element:
        aspects.add(element or default_element(char_class, game_version, level))
    return aspects


def setup_columns(game_version):
    """The four box columns of the setup page; the page itself hides the version's inert aspects."""
    return ([list(ELEMENT_BOXES), list(version_presets(game_version)['option_boxes'])]
            + [list(column) for column in FOCUS_COLUMNS])


def setup_boxes(game_version):
    return {aspect for column in setup_columns(game_version) for aspect in column}


def focus_boxes(aspects):
    return {aspect for column in FOCUS_COLUMNS for aspect in column
            if aspect in aspects and aspect != 'balanced'}


def within_focus_limit(aspects):
    return len(focus_boxes(aspects)) <= FOCUS_LIMIT


def capped_focus(aspects, preferred=()):
    """At most FOCUS_LIMIT focus boxes: the preferred ones first, then column order."""
    focus = focus_boxes(aspects)
    order = [aspect for aspect in preferred if aspect in focus]
    order += [aspect for column in FOCUS_COLUMNS for aspect in column
              if aspect in focus and aspect not in order]
    return (set(aspects) - focus) | set(order[:FOCUS_LIMIT])


def priorities():
    return [(priority.key, priority.label) for priority in PRIORITIES]


def play_modes(game_version):
    """[(key, label)] the setup page offers on this version, the default mode first."""
    keys = version_presets(game_version).get('modes', (DEFAULT_PLAY_MODE,))
    return [(key, PLAY_MODE_BY_KEY[key].label) for key in keys]


def mode_boxes(game_version):
    """{mode: {option box: ticked}} for the modes of this version; the default mode leaves the boxes alone."""
    return {key: {} if key == DEFAULT_PLAY_MODE
            else {box: box in PLAY_MODE_BY_KEY[key].boxes for box in sorted(MODE_OPTION_BOXES)}
            for key, _label in play_modes(game_version)}


def offered_priority(priority):
    return priority if priority in PRIORITY_BY_KEY else DEFAULT_PRIORITY


def offered_play_mode(play_mode, game_version):
    """The mode if this version offers it, else the default one."""
    if play_mode in dict(play_modes(game_version)):
        return play_mode
    return DEFAULT_PLAY_MODE


def stored_choices(char):
    """(priority, play mode) of a build; a missing or unknown one reads as the default."""
    options = read_char_blob(char.options, {}, 'options', char)
    game_version = getattr(char, 'game_version', None) or DEFAULT_VERSION
    return (offered_priority(options.get('priority')),
            offered_play_mode(options.get('play_mode'), game_version))


def posted_choices(post, char):
    """(priority, play mode) of a setup form; a field it does not send keeps the build's own."""
    priority, play_mode = stored_choices(char)
    game_version = getattr(char, 'game_version', None) or DEFAULT_VERSION
    if post.get('priority') is not None:
        priority = offered_priority(post.get('priority'))
    if post.get('play_mode') is not None:
        play_mode = offered_play_mode(post.get('play_mode'), game_version)
    return priority, play_mode


def with_mode_boxes(aspects, play_mode):
    """The aspects with exactly the option boxes the mode ticks; the default mode leaves them as they are."""
    mode = PLAY_MODE_BY_KEY.get(play_mode)
    if mode is None or play_mode == DEFAULT_PLAY_MODE:
        return set(aspects)
    return (set(aspects) - MODE_OPTION_BOXES) | set(mode.boxes)


def solved_aspects(aspects, priority):
    """The aspects the weights and minimums are computed from: the boxes plus the priority's."""
    return set(aspects) | PRIORITY_BY_KEY[offered_priority(priority)].aspects


def apply_setup_choices(char, aspects, priority=DEFAULT_PRIORITY, play_mode=DEFAULT_PLAY_MODE,
                        reset=True, set_minimums=True, guard_pct=None):
    """Saves the boxes and the mode's as aspects, weighs them with the priority's too, keeps non-default choices; without a reset only the boxes and the safeguard change."""
    guard = {}
    if guard_pct is not None:
        guard_pct = offered_guard(guard_pct)
        guard['guard_pct'] = None if guard_pct == GUARD_DEFAULT_PERCENT else guard_pct
    if not reset:
        set_char_aspects(char, aspects, False)
        # The safeguard does not change the weights
        set_setup_choices(char, guard)
        return set(aspects)
    boxes = with_mode_boxes(aspects, play_mode)
    solved = solved_aspects(boxes, priority)
    if solved != boxes:
        set_char_aspects(char, solved, True, set_minimums)
        set_char_aspects(char, boxes, False)
    else:
        set_char_aspects(char, boxes, True, set_minimums)
    set_setup_choices(char, dict(guard, **{
        'priority': None if priority == DEFAULT_PRIORITY else priority,
        'play_mode': None if play_mode == DEFAULT_PLAY_MODE else play_mode}))
    return boxes


def reapply_build_weights(char):
    """smart_build.reapply_weights, counting the build's priority too."""
    priority, _play_mode = stored_choices(char)
    if priority == DEFAULT_PRIORITY:
        reapply_weights(char)
        return
    solved = solved_aspects(get_char_aspects(char), priority)
    char.stats_weight = pickle.dumps(get_standard_weights(Char(
        char_class=char.char_class, level=char.level, game_version=char.game_version,
        aspects=pickle.dumps(solved))))


def choices_line(char):
    """{'mode': label, 'priority': label} when the build has a non-default choice, else None."""
    priority, play_mode = stored_choices(char)
    if priority == DEFAULT_PRIORITY and play_mode == DEFAULT_PLAY_MODE:
        return None
    return {'mode': PLAY_MODE_BY_KEY[play_mode].label,
            'priority': PRIORITY_BY_KEY[priority].label}


def offered_guard(percent):
    """The safeguard percent if the setup page offers it, else the default."""
    try:
        percent = int(percent)
    except (TypeError, ValueError):
        return GUARD_DEFAULT_PERCENT
    return percent if percent in GUARD_PERCENTS else GUARD_DEFAULT_PERCENT


def stored_guard(char):
    return offered_guard(read_char_blob(char.options, {}, 'options', char).get('guard_pct'))


def posted_guard(post, char):
    """Safeguard percent of a setup form; a form without the field keeps the build's own."""
    if post.get('guard_pct') is None:
        return stored_guard(char)
    return offered_guard(post.get('guard_pct'))


def guard_plan(char):
    """(kind, percent) of the safeguard a solve of this build applies, None without a priority."""
    priority, _play_mode = stored_choices(char)
    if priority == DEFAULT_PRIORITY:
        return None
    return GUARD_KIND[priority], stored_guard(char)


def _standard_weights(char, aspects):
    build = Char(char_class=char.char_class, level=char.level, game_version=char.game_version,
                 aspects=pickle.dumps(set(aspects)))
    build.stats_weight = pickle.dumps(get_standard_weights(build))
    return get_stats_weights(build, persist=False)


def balanced_weights(char, weights):
    """The build's weights less what its priority adds, so the player's own changes stay."""
    priority, _play_mode = stored_choices(char)
    boxes = get_char_aspects(char)
    balanced = _standard_weights(char, boxes)
    with_priority = _standard_weights(char, solved_aspects(boxes, priority))
    if weights == with_priority:
        return balanced
    shifted = {}
    for key, value in weights.items():
        if not isinstance(value, (int, float)):
            shifted[key] = value
            continue
        moved = value - (with_priority.get(key, 0) - balanced.get(key, 0))
        shifted[key] = max(moved, 0) if value >= 0 else moved
    return shifted


def effective_hp(totals):
    """HP / (1 - mean of the five % resists / 100)."""
    mean = sum(totals.get(key, 0) for key in PERCENT_RESIST_KEYS) / 5.0
    return totals.get('hp', 0) / (1 - mean / 100.0)


def guard_reading(char, result, kind):
    """{'solution', 'totals', 'value'} of a solve, value being its effective HP or the panel's best turn."""
    from chardata.solution import get_solution_from_minimal
    solution = get_solution_from_minimal(char, pickle.loads(pickle.dumps(result)),
                                         refresh_base_stats=False)
    reading = {'solution': solution, 'totals': dict(solution.get_stats_total())}
    if kind == 'effective_hp':
        reading['value'] = effective_hp(reading['totals'])
    else:
        reading['value'] = _panel_turn(char, solution)
    return reading


def cross_reading(char, reading, kind):
    """What the other safeguard kind holds: the best turn for effective_hp, effective HP for turn."""
    if kind == 'effective_hp':
        return _panel_turn(char, reading['solution'])
    return effective_hp(reading['totals'])


def _panel_turn(char, solution):
    from chardata.spells_view import _best_combo
    try:
        combo = _best_combo(char, solution, char.game_version or DEFAULT_VERSION)
    except Exception:
        logger.exception('could not read the best turn of a guarded solve (char %s)', char.id)
        return None
    return combo['total'] if combo else None


def _scaled_floor(value, share):
    """share of value rounded down, never above value itself."""
    return math.floor(min(value, share * value))


def _at_least(current, value):
    return max(current, value) if isinstance(current, (int, float)) else value


def guard_minimums(minimums, kind, percent, reading, aspects):
    """A copy of the build's minimums with the safeguard's floors taken from the balanced solve."""
    share = (100 - percent) / 100.0
    guarded = dict(minimums)
    if kind == 'effective_hp':
        guarded[EFFECTIVE_HP_MINIMUM] = share * reading['value']
        return guarded
    structure = get_structure()
    totals = reading['totals']
    ap_name = structure.get_stat_by_key('ap').name
    guarded[ap_name] = _at_least(guarded.get(ap_name), int(totals.get('ap', 0)))
    crit_name = structure.get_stat_by_key('ch').name
    guarded[crit_name] = _at_least(guarded.get(crit_name),
                                   _scaled_floor(totals.get('ch', 0), share))
    adv_mins = dict(guarded.get('adv_mins') or {})
    by_key = {entry['key']: entry for entry in structure.get_adv_mins()}
    for element in get_elements(aspects):
        for key in TURN_GUARD_ADV_MINS[element]:
            entry = by_key[key]
            value = sum(totals.get(structure.get_stat_by_name(name).key, 0)
                        for name in entry['stats'])
            adv_mins[entry['name']] = _at_least(adv_mins.get(entry['name']),
                                                _scaled_floor(value, share))
    guarded['adv_mins'] = adv_mins
    return guarded


def guard_facts(minimal_solution_blob):
    """The safeguard facts a solve recorded, None on solutions without them."""
    if not minimal_solution_blob:
        return None
    try:
        facts = getattr(pickle.loads(minimal_solution_blob), 'guard', None)
    except Exception:
        return None
    return facts if isinstance(facts, dict) else None


def guard_line(facts):
    """The build page's sentences on the safeguard a solve applied, or None."""
    if not facts:
        return None
    sentences = [sentence for sentence in (_guard_sentence(facts), _trailing_sentence(facts))
                 if sentence]
    return ' '.join(sentences) or None


def _guard_sentence(facts):
    share = 100 - facts['percent']
    if facts.get('no_reference'):
        return gettext('Safeguard not applied: the solver found no balanced set to compare '
                       'with.')
    if facts.get('no_turn'):
        return gettext("Safeguard not applied: the balanced build's best turn could not be "
                       "computed.")
    if facts.get('out_of_time'):
        return gettext('Safeguard: the solver ran out of time before it found a set for the '
                       'priority, so this is the balanced build.')
    balanced, kept = facts.get('balanced'), facts.get('kept')
    if not balanced or balanced <= 0:
        return None
    values = {'share': share, 'balanced': int(round(balanced))}
    hp = facts['kind'] == 'effective_hp'
    if facts.get('fallback'):
        if hp:
            return gettext("Safeguard not applied: the solver found no set keeping %(share)s%% "
                           "of the balanced build's effective HP (%(balanced)s), so this set "
                           "does without it.") % values
        return gettext("Safeguard not applied: the solver found no set keeping %(share)s%% of "
                       "the balanced build's best turn (%(balanced)s), so this set does "
                       "without it.") % values
    if kept is None:
        return None
    values['kept'] = int(round(kept))
    if kept >= share / 100.0 * balanced - 0.5:
        if hp:
            return gettext('Safeguard: effective HP at least %(share)s%% of the balanced build '
                           '(%(kept)s of %(balanced)s).') % values
        return gettext('Safeguard: best turn at least %(share)s%% of the balanced build '
                       '(%(kept)s of %(balanced)s).') % values
    values['reached'] = int(100 * kept / balanced)
    if hp:
        return gettext('Safeguard: effective HP at %(reached)s%% of the balanced build '
                       '(%(kept)s of %(balanced)s), short of the %(share)s%% aimed for.') % values
    return gettext('Safeguard: best turn at %(reached)s%% of the balanced build '
                   '(%(kept)s of %(balanced)s), short of the %(share)s%% aimed for.') % values


def _trailing_sentence(facts):
    """Said when the set is behind the balanced build on both effective HP and best turn."""
    values = [facts.get(key) for key in ('kept', 'balanced', 'other_kept', 'other_balanced')]
    if any(value is None for value in values):
        return None
    kept, balanced, other_kept, other_balanced = (int(round(value)) for value in values)
    if kept >= balanced or other_kept >= other_balanced:
        return None
    if facts['kind'] == 'effective_hp':
        turn, hp = (other_kept, other_balanced), (kept, balanced)
    else:
        turn, hp = (kept, balanced), (other_kept, other_balanced)
    return gettext('This set trails the balanced build on both counts: best turn %(turn)s '
                   'against %(balanced_turn)s, effective HP %(hp)s against '
                   '%(balanced_hp)s.') % {'turn': turn[0], 'balanced_turn': turn[1],
                                          'hp': hp[0], 'balanced_hp': hp[1]}


def element_stat_points(char_class, level, game_version):
    """{element: {stat key: characteristic points per point}}, as the build weights price them."""
    points = {}
    for element, damage in ELEMENT_DAMAGE.items():
        weights = get_standard_weights(Char(char_class=char_class, level=level,
                                            game_version=game_version,
                                            aspects=pickle.dumps({element})))
        points[element] = {element: 1}
        for stat in (damage, 'neutdam') if element == 'str' else (damage,):
            points[element][stat] = weights.get(stat, 0) / weights[element]
    return points


def gear_elements(structure, item_ids, char_class, level, game_version, overrides=None):
    """Top two elements with SECOND_ELEMENT_SHARE of the main one's points; all four make omni."""
    counted = {element: [(structure.stat_dict_key[key].id, weight)
                         for key, weight in stats.items() if key in structure.stat_dict_key]
               for element, stats in element_stat_points(char_class, level,
                                                         game_version).items()}
    points = dict.fromkeys(counted, 0)
    for item_id in item_ids:
        item = structure.get_item_by_id(item_id)
        if item is None:
            continue
        values = dict(item.stats or ())
        values.update((overrides or {}).get(item_id) or {})
        for element, stats in counted.items():
            points[element] += sum(weight * values.get(stat_id, 0)
                                   for stat_id, weight in stats)
    ranked = sorted(points, key=points.get, reverse=True)
    if points[ranked[0]] <= 0:
        return set()
    strong = [element for element in ranked
              if points[element] >= SECOND_ELEMENT_SHARE * points[ranked[0]]]
    if len(strong) == len(points):
        return set(strong) | {'omni'}
    return set(strong[:2])
