# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Pick each class's default element per version and Quick Start level from its best turn, into default_elements/<version>.json.

    py fashionsite/manage.py store_default_elements [--game-version dofus3 ...] [--meta FILE] [--dry-run]
"""
import hashlib
import json
import os

from django.core.management.base import BaseCommand, CommandError

from chardata.coaching_view import DEFAULT_LEVELS
from chardata.default_elements import DIRECTORY, nearest_level
from chardata.models import Char
from chardata.presets import CLASS_DEFAULT_ELEMENT, ELEMENT_DAMAGE, FALLBACK_ELEMENT
from chardata.smart_build import level_minimums, param_for_build
from chardata.spell_combo import best_turn, castable_spells, combat_ap
from chardata.spell_variants import variant_of
from chardata.util import character_own_stats
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import (ATTRIBUTE_TO_ELEMENT, CHARACTER_CLASSES,
                                             STAT_KEY_TO_NAME, STAT_NAME_TO_KEY,
                                             get_soft_caps_for, max_scroll_for_version,
                                             scrolls_push_cost_curve, tier_widths_after_scroll)
from fashionistapulp.game_versions import dofus_versions
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import (get_current_game_version, get_structure,
                                       set_current_game_version)

LEVELS = tuple(sorted(DEFAULT_LEVELS))
TOP_LEVEL = LEVELS[-1]
CHECK_LEVEL = nearest_level(LEVELS, 100)
TIE_SHARE = 0.02
NEAR_SHARE = 0.05
HEALER_SHARE = 0.5
HEAL_CHARACTERISTIC = 'int'
# What one characteristic costs in each soft cap tier, as the model charges it
TIER_COSTS = (0.5, 1, 2, 3, 4, 5)
GEAR_SLOTS = ('Hat', 'Cloak', 'Amulet', 'Ring', 'Ring', 'Belt', 'Boots', 'Weapon')
PIECES_PER_SLOT = 10
SHARED_GEAR = ('pow', 'dam', 'neutdam', 'ch', 'cridam', 'vit')
GEAR_KEYS = ('char', 'edam') + SHARED_GEAR
SCROLLED = tuple(ELEMENT_DAMAGE) + ('vit',)


# {version: {spell id: (what the turn misreads, true while the rows still misread it)}}
KNOWN_BAD_ROWS = {
    'dofus3': {},
    'beta': {},
    'dofus2': {},
}

REFERENCE = ('Reference set, the same for every element, at each Quick Start level (%(levels)s): '
             '%(scrolled)s scrolled to the version maximum, all characteristic points of '
             'the level in the element at the class cost of the version, and eight pieces (hat, '
             'cloak, amulet, two rings, belt, boots, weapon), each the mean of the %(pieces)d '
             'highest-level pieces of its slot up to that level carrying the element '
             'characteristic, averaged over the four elements. The set carries the HP the build '
             'page gives that level and that Vitality. The turn is spell_combo.best_turn '
             'on castable_spells, the mean of the level AP minimum and one AP more. The element '
             'with the best turn wins; the element a class has now stays while it is within '
             '%(tie)d%% of it. A class whose version profile weighs heals at %(healer)d%% or more '
             'keeps Intelligence, which prices heals in the weights. A new element is not taken '
             'when it rests on a spell whose rows the turn misreads (KNOWN_BAD_ROWS).')


def reference_text():
    scrolled = [STAT_KEY_TO_NAME[key] for key in SCROLLED]
    return REFERENCE % {'levels': ', '.join(str(level) for level in LEVELS),
                        'scrolled': '%s and %s' % (', '.join(scrolled[:-1]), scrolled[-1]),
                        'pieces': PIECES_PER_SLOT, 'tie': 100 * TIE_SHARE,
                        'healer': 100 * HEALER_SHARE}


def element_name(element):
    return ATTRIBUTE_TO_ELEMENT[element].capitalize()


def characteristic_from_points(game_version, char_class, element, points, scrolled):
    """What the points buy in one characteristic, cheapest tier first."""
    caps = get_soft_caps_for(game_version, char_class)[element]
    widths = tier_widths_after_scroll(
        caps, scrolled if scrolls_push_cost_curve(game_version) else 0)
    bought = 0
    for width, cost in zip(widths, TIER_COSTS):
        affordable = int(points // cost)
        taken = affordable if width is None else min(width, affordable)
        bought += taken
        points -= taken * cost
        if width is None or taken < width:
            break
    return bought


def gear_line(game_version, level=TOP_LEVEL):
    """{'char', 'edam', shared stats}: the gear every element of the reference set wears."""
    structure = get_structure(game_version)
    ids = {key: stat.id for key, stat in structure.stat_dict_key.items()}
    by_slot = {}
    for item in structure.get_available_items_list():
        if item.level <= level:
            by_slot.setdefault(structure.get_type_name_by_id(item.type), []).append(item)
    lines = []
    for element, damage in ELEMENT_DAMAGE.items():
        line = dict.fromkeys(GEAR_KEYS, 0.0)
        for slot in GEAR_SLOTS:
            carriers = sorted((item for item in by_slot.get(slot, ())
                               if dict(item.stats or ()).get(ids[element], 0) > 0),
                              key=lambda item: -item.level)
            if not carriers:
                continue
            floor = carriers[min(PIECES_PER_SLOT, len(carriers)) - 1].level
            kept = [dict(item.stats or ()) for item in carriers if item.level >= floor]
            for key, stat in (('char', element), ('edam', damage)) + tuple(
                    (key, key) for key in SHARED_GEAR):
                if stat in ids:
                    line[key] += sum(values.get(ids[stat], 0) for values in kept) / len(kept)
        lines.append(line)
    return {key: int(round(sum(line[key] for line in lines) / len(lines)))
            for key in GEAR_KEYS}


def build_hp(game_version, char_class, level, vitality):
    """The HP the build page gives a build of the class and level with that Vitality and no other life."""
    base = dict(character_own_stats(level, char_class, game_version))
    vitality_name = STAT_KEY_TO_NAME['vit']
    base[vitality_name] = base.get(vitality_name, 0) + vitality
    previous = get_current_game_version()
    set_current_game_version(game_version)
    try:
        return ModelResult({'char_level': level, 'base_stats_by_attr': base,
                            'options': {'ap_exo': False, 'range_exo': False,
                                        'mp_exo': False}}).get_stats_total()['hp']
    finally:
        set_current_game_version(previous)


def reference_stats(game_version, char_class, element, gear, ap, level=TOP_LEVEL):
    """The reference set's stats with its points and gear in one element."""
    stats = dict.fromkeys(STAT_NAME_TO_KEY.values(), 0)
    scroll = max_scroll_for_version(game_version, level)
    for characteristic in SCROLLED:
        stats[characteristic] = scroll
    stats[element] += gear['char'] + characteristic_from_points(
        game_version, char_class, element, 5 * (level - 1), scroll)
    stats[ELEMENT_DAMAGE[element]] += gear['edam']
    for key in SHARED_GEAR:
        stats[key] += gear[key]
    stats['hp'] = build_hp(game_version, char_class, level, stats['vit'])
    stats['ap'] = ap
    return stats


def turn_aps(game_version, char_class, element, level=TOP_LEVEL):
    minimum = level_minimums(Char(char_class=char_class, level=level,
                                  game_version=game_version), {element})['AP']
    return sorted({combat_ap(minimum, game_version), combat_ap(minimum + 1, game_version)})


def element_turns(game_version, char_class, gear, level=TOP_LEVEL, without=()):
    """{element: (turn, {AP: cast order})}, the turn being the mean over turn_aps."""
    spells = [spell for spell in castable_spells(char_class, level, game_version)
              if spell.name not in without]
    out = {}
    for element in ELEMENT_DAMAGE:
        totals = []
        orders = {}
        for ap in turn_aps(game_version, char_class, element, level):
            stats = reference_stats(game_version, char_class, element, gear, ap, level)
            total, order = best_turn(stats, spells, ap, game_version=game_version,
                                     caster_level=level)
            totals.append(total)
            orders[ap] = order
        out[element] = (sum(totals) / len(totals), orders)
    return out


def inputs_fingerprint(game_version, char_class, level=TOP_LEVEL, gear=None):
    """Digest of what the class's turns read: spell rows, AP, reference stats and one cast of each spell."""
    gear = gear_line(game_version, level) if gear is None else gear
    spells = castable_spells(char_class, level, game_version)
    rows = [[spell.name, spell.spell_id, spell.cost, spell.limit, spell.stacks, spell.crit_rate,
             spell.random_draw, spell.push_cells, spell.push_needs_state, spell.bonus_stats,
             spell.buffs, spell.plain_alternatives, spell.crit_alternatives,
             spell.spell.buff_scaling, variant_of(game_version, spell.spell_id)]
            + ([[spell.taken.percent, spell.taken.critical, spell.taken.stacks,
                 spell.taken.ends_on_hit]] if spell.taken is not None else [])
            for spell in spells]
    reads = []
    for element in ELEMENT_DAMAGE:
        for ap in turn_aps(game_version, char_class, element, level):
            stats = reference_stats(game_version, char_class, element, gear, ap, level)
            reads.append([element, ap, stats, [
                round(best_turn(stats, [spell], spell.cost, game_version=game_version,
                                caster_level=level)[0], 1)
                for spell in spells]])
    text = json.dumps([rows, reads], sort_keys=True, default=vars)
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]


def bad_row_problems(game_version):
    """What no longer holds in the version's KNOWN_BAD_ROWS; empty while every entry still misreads."""
    listed = KNOWN_BAD_ROWS.get(game_version) or {}
    found = {}
    for char_class in filter_classes_for_version(CHARACTER_CLASSES, game_version):
        for spell in castable_spells(char_class, TOP_LEVEL, game_version):
            if spell.spell_id in listed:
                found.setdefault(spell.spell_id, []).append(spell)
    problems = []
    for spell_id, (misread, still) in sorted(listed.items()):
        spells = found.get(spell_id)
        if not spells:
            problems.append('%s: KNOWN_BAD_ROWS lists spell %d, which no class casts at level %d.'
                            % (game_version, spell_id, TOP_LEVEL))
        elif not all(still(spell) for spell in spells):
            problems.append('%s: %s no longer reads as listed (%s); remove it from '
                            'KNOWN_BAD_ROWS and regenerate.' % (game_version, spells[0].name,
                                                                misread))
    return problems


def bad_row_reasons(game_version, spells):
    """{spell name: what the turn misreads} for the given spells listed in KNOWN_BAD_ROWS."""
    listed = KNOWN_BAD_ROWS.get(game_version) or {}
    return {spell.name: listed[spell.spell_id][0] for spell in spells
            if spell.spell_id in listed}


def heal_share(game_version, char_class):
    return param_for_build(char_class, [], 'heals_importance', game_version=game_version)


def table_path(game_version):
    return os.path.join(DIRECTORY, '%s.json' % game_version)


def stored_table(game_version):
    """The version's table on disk, empty when it has none."""
    try:
        with open(table_path(game_version), encoding='utf-8') as handle:
            return json.load(handle)
    except (IOError, OSError, ValueError):
        return {}


def today_element(char_class, stored=None, level=None):
    """The element the class has now: the stored table's at that level, else the shared one."""
    entry = (((stored or {}).get('classes') or {}).get(char_class) or {}).get(str(level))
    if isinstance(entry, dict) and entry.get('element') in ELEMENT_DAMAGE:
        return entry['element']
    return CLASS_DEFAULT_ELEMENT.get(char_class, FALLBACK_ELEMENT)


def pick(turns, today):
    """The element with the best turn; today's element while it is within TIE_SHARE of it."""
    best = max(turns.values())
    if best <= 0 or turns.get(today, 0) >= (1 - TIE_SHARE) * best:
        return today
    return max(ELEMENT_DAMAGE, key=turns.get)


def cast_names(by_ap):
    names = []
    for order in (by_ap or {}).values():
        for name, _damage in order:
            if name not in names:
                names.append(name)
    return names


def choose(game_version, char_class, level, gear, turns, by_element, today):
    """(element, notes): the pick, or the element kept for heals or held off misread rows."""
    if heal_share(game_version, char_class) >= HEALER_SHARE:
        return HEAL_CHARACTERISTIC, {'kept_for_heals': True}
    element = pick(turns, today)
    misread = bad_row_reasons(game_version, castable_spells(char_class, level, game_version))
    resting = sorted(name for name in cast_names(by_element.get(element)) if name in misread)
    if element == today or not resting:
        return element, {}
    without = {other: turn for other, (turn, _orders)
               in element_turns(game_version, char_class, gear, level, resting).items()}
    if pick(without, today) == element:
        return element, {}
    return today, {'held_by': resting}


def level_entry(game_version, char_class, level, gear, stored=None):
    """(table entry, {element: {AP: cast order}}) of the class at the level; reads only."""
    stored = stored_table(game_version) if stored is None else stored
    measured = element_turns(game_version, char_class, gear, level)
    turns = {element: round(turn, 1) for element, (turn, _orders) in measured.items()}
    by_element = {element: by_ap for element, (_turn, by_ap) in measured.items()}
    element, notes = choose(game_version, char_class, level, gear, turns, by_element,
                            today_element(char_class, stored, level))
    entry = {'element': element, 'turns': turns,
             'inputs': inputs_fingerprint(game_version, char_class, level, gear)}
    entry.update(notes)
    return entry, by_element


def build(game_version, stored=None):
    """(table, {class: {level: {element: {AP: cast order}}}}); reads only."""
    stored = stored_table(game_version) if stored is None else stored
    gears = {level: gear_line(game_version, level) for level in LEVELS}
    classes = {}
    orders = {}
    for char_class in filter_classes_for_version(CHARACTER_CLASSES, game_version):
        classes[char_class] = {}
        orders[char_class] = {}
        for level in LEVELS:
            entry, by_element = level_entry(game_version, char_class, level, gears[level],
                                            stored)
            classes[char_class][str(level)] = entry
            orders[char_class][level] = by_element
    return {'game_version': game_version, 'levels': list(LEVELS),
            'gear': {str(level): gears[level] for level in LEVELS},
            'classes': classes}, orders


def _by_level(mapping):
    return sorted(mapping.items(), key=lambda item: int(item[0]))


def dumps(table):
    """One gear line and one class level per line."""
    gear = ',\n'.join('  %s: %s' % (json.dumps(level), json.dumps(line, sort_keys=True))
                      for level, line in _by_level(table['gear']))
    classes = ',\n'.join('  %s: {\n%s\n  }' % (json.dumps(char_class), ',\n'.join(
        '   %s: %s' % (json.dumps(level), json.dumps(entry, sort_keys=True))
        for level, entry in _by_level(by_level)))
        for char_class, by_level in sorted(table['classes'].items()))
    return ('{\n "game_version": %s,\n "levels": %s,\n "gear": {\n%s\n },\n'
            ' "classes": {\n%s\n }\n}\n' % (json.dumps(table['game_version']),
                                            json.dumps(table['levels']), gear, classes))


def pivotal_spells(game_version, char_class, gear, chosen, by_ap, level, today):
    """[(spell, element picked without it, turns without it)] for the chosen turn's spells."""
    out = []
    for name in cast_names(by_ap):
        turns = {element: turn for element, (turn, _orders)
                 in element_turns(game_version, char_class, gear, level, (name,)).items()}
        winner = pick(turns, today)
        if winner != chosen:
            out.append((name, winner, turns))
    return out


def _share(turns, element):
    best = max(turns.values())
    return 100.0 * turns[element] / best if best > 0 else 0.0


def _cast_order(order):
    return ', '.join('%s %.0f' % (name, damage) for name, damage in order)


def _shares(turns):
    return '  '.join('%s %.0f (%.1f%%)' % (element_name(element), turns[element],
                                           _share(turns, element))
                     for element in ELEMENT_DAMAGE)


def _leader(turns):
    return max(ELEMENT_DAMAGE, key=turns.get)


def _entry_note(entry, misread=None):
    """Why an entry is not its best turn's element, or ''."""
    leader = _leader(entry['turns'])
    if entry.get('kept_for_heals') and leader != entry['element']:
        return 'kept for heals, %s leads the damage turn' % element_name(leader)
    if entry.get('held_by'):
        return 'kept, %s leads on %s: %s' % (
            element_name(leader), ', '.join(entry['held_by']),
            '; '.join((misread or {}).get(name, 'rows the turn misreads')
                      for name in entry['held_by']))
    return ''


def summary_lines(table, stored=None):
    lines = []
    for char_class, by_level in sorted(table['classes'].items()):
        for level, entry in _by_level(by_level):
            today = today_element(char_class, stored, level)
            turns = entry['turns']
            note = _entry_note(entry)
            if not note and entry['element'] != today:
                note = 'was %s' % element_name(today)
            elif not note and turns[entry['element']] < max(turns.values()):
                note = 'kept on a tie, %s leads' % element_name(_leader(turns))
            lines.append('%s %s %s: %s%s | %s' % (
                table['game_version'], char_class, level, element_name(entry['element']),
                ', %s' % note if note else '', _shares(entry['turns'])))
    return lines


def _misread(game_version, char_class, level):
    return bad_row_reasons(game_version, castable_spells(char_class, int(level), game_version))


class _Pivots(object):
    """pivotal_spells of each class's element at TOP_LEVEL, computed on demand."""

    def __init__(self, table, orders, stored=None):
        self.table = table
        self.orders = orders
        self.stored = stored
        self.found = {}

    def __call__(self, char_class):
        if char_class not in self.found:
            game_version = self.table['game_version']
            self.found[char_class] = pivotal_spells(
                game_version, char_class, self.table['gear'][str(TOP_LEVEL)],
                self.table['classes'][char_class][str(TOP_LEVEL)]['element'],
                ((self.orders.get(char_class) or {}).get(TOP_LEVEL) or {}).get(
                    self.table['classes'][char_class][str(TOP_LEVEL)]['element']),
                TOP_LEVEL, today_element(char_class, self.stored, TOP_LEVEL))
        return self.found[char_class]


def _pivot_lines(chosen, pivots):
    if not pivots:
        return ['%s does not rest on one spell: it still wins without any one of its spells.'
                % element_name(chosen)]
    return ['%s rests on %s: without it, %s %s (%.0f against %.0f).'
            % (element_name(chosen), name, element_name(winner),
               'wins' if turns[winner] >= turns[chosen] else 'is kept on a tie',
               turns[winner], turns[chosen])
            for name, winner, turns in pivots]


def change_lines(table, pivots, stored=None):
    """Each class level whose element moves or is kept off its best turn; at TOP_LEVEL, what a new element rests on."""
    game_version = table['game_version']
    lines = []
    for char_class, by_level in sorted(table['classes'].items()):
        for level, entry in _by_level(by_level):
            today = today_element(char_class, stored, level)
            note = _entry_note(entry, _misread(game_version, char_class, level)
                               if entry.get('held_by') else None)
            if note:
                lines.append('%s %s %s: %s %s.' % (game_version, char_class, level,
                                                   element_name(entry['element']), note))
            elif entry['element'] != today:
                lines.append('%s %s %s: %s replaces %s.' % (
                    game_version, char_class, level, element_name(entry['element']),
                    element_name(today)))
                if int(level) == TOP_LEVEL:
                    lines.extend('  ' + line for line in _pivot_lines(entry['element'],
                                                                      pivots(char_class)))
    return lines


def compare_with_sources(table, orders, sources, pivots=None, stored=None):
    """Lines saying, for each class and source, whether it names our TOP_LEVEL element, and why not."""
    game_version = table['game_version']
    pivots = pivots or _Pivots(table, orders, stored)
    lines = []
    for char_class, by_level in sorted(table['classes'].items()):
        entry = by_level[str(TOP_LEVEL)]
        chosen = entry['element']
        for source in sources.get(char_class, ()):
            label = '%s %s, %s' % (game_version, char_class, source.get('source', 'source'))
            named = [element for element in source.get('elements', ())
                     if element in ELEMENT_DAMAGE]
            if chosen in named:
                lines.append('%s: agrees (%s).' % (label, element_name(chosen)))
                continue
            lines.append('%s: names %s, we pick %s.' % (
                label, ', '.join(element_name(element) for element in named)
                or ', '.join(list(source.get('elements') or []) + list(source.get('roles') or []))
                or 'nothing', element_name(chosen)))
            lines.extend('  ' + line for line in _why(
                game_version, char_class, by_level, named, source,
                ((orders.get(char_class) or {}).get(TOP_LEVEL) or {}), pivots))
    return lines


def _uncounted_effects(spells, element):
    """{what the turn leaves out: [spell names]} for the class spells hitting in the element."""
    target = ATTRIBUTE_TO_ELEMENT[element]
    found = {}
    for spell in spells:
        rows = [row for alternative in spell.plain_alternatives for row in alternative]
        if not any(row.element == target and not row.heals for row in rows):
            continue
        if any(row.heals for row in rows):
            found.setdefault('heals', []).append(spell.name)
        if spell.pushes:
            found.setdefault('pushes', []).append(spell.name)
    return found


def _why(game_version, char_class, by_level, named, source, orders, pivots):
    entry = by_level[str(TOP_LEVEL)]
    chosen = entry['element']
    turns = entry['turns']
    best = _leader(turns)
    lines = []
    if not named:
        if 'omni' in source.get('elements', ()):
            lines.append('The source plays several elements; a default is one element.')
        if source.get('roles'):
            lines.append('The source names a role (%s), not an element.'
                         % ', '.join(source['roles']))
        if not lines:
            lines.append('The source names no element.')
        return lines
    note = _entry_note(entry, _misread(game_version, char_class, TOP_LEVEL)
                       if entry.get('held_by') else None)
    if note:
        lines.append('%s %s.' % (element_name(chosen), note))
    elif chosen != best:
        lines.append('%s is kept on a tie: %.1f%% of the best turn (%s).'
                     % (element_name(chosen), _share(turns, chosen), element_name(best)))
    spells = castable_spells(char_class, TOP_LEVEL, game_version)
    for element in named:
        share = _share(turns, element)
        if turns[element] <= 0:
            lines.append('%s: no %s damage spell castable at level %d in the %s spell data.'
                         % (element_name(element), element_name(element).lower(), TOP_LEVEL,
                            game_version))
            continue
        if share >= 100 * (1 - NEAR_SHARE):
            lines.append('%s: %.1f%% of the best turn, a near tie the turn cannot separate.'
                         % (element_name(element), share))
        else:
            lines.append('%s: %.1f%% of the best turn, %.0f against %.0f.'
                         % (element_name(element), share, turns[element], turns[best]))
            for shown in (best, element):
                by_ap = orders.get(shown) or {}
                if by_ap:
                    ap = max(by_ap)
                    lines.append('    at %d AP, %s: %s' % (ap, element_name(shown),
                                                           _cast_order(by_ap[ap])))
        uncounted = _uncounted_effects(spells, element)
        if uncounted:
            lines.append('    %s spells the turn does not credit for: %s.' % (
                element_name(element), '; '.join('%s (%s)' % (what, ', '.join(names))
                                                 for what, names in sorted(uncounted.items()))))
    if not note:
        lines.extend(_pivot_lines(chosen, pivots(char_class)))
    check = by_level[str(CHECK_LEVEL)]
    lines.append('At level %d: %s (default %s).' % (CHECK_LEVEL, ', '.join(
        '%s %.1f%%' % (element_name(element), _share(check['turns'], element))
        for element in sorted(ELEMENT_DAMAGE, key=check['turns'].get, reverse=True)),
        element_name(check['element'])))
    if check['element'] in named and check['element'] != chosen:
        lines.append('The source names the level %d default, %s: it fits a lower level better '
                     'than %d.' % (CHECK_LEVEL, element_name(check['element']), TOP_LEVEL))
    return lines


class Command(BaseCommand):
    help = "Pick each class's default element per version and Quick Start level from its best turn."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--game-version', nargs='*', default=None,
                            help='versions to build, every Dofus version by default')
        parser.add_argument('--meta', default=None,
                            help='JSON {version: {class: [{source, elements, roles}]}} to '
                                 'compare with')
        parser.add_argument('--dry-run', action='store_true', help='print, write nothing')

    def handle(self, *args, **options):
        versions = options['game_version'] or dofus_versions()
        unknown = sorted(set(versions) - set(dofus_versions()))
        if unknown:
            raise CommandError('not a Dofus version: %s' % ', '.join(unknown))
        problems = [problem for game_version in versions
                    for problem in bad_row_problems(game_version)]
        if problems:
            raise CommandError('\n'.join(problems))
        sources = {}
        if options['meta']:
            with open(options['meta'], encoding='utf-8') as handle:
                sources = json.load(handle)
        self.stdout.write(reference_text())
        for game_version in versions:
            stored = stored_table(game_version)
            table, orders = build(game_version, stored)
            for level, gear in _by_level(table['gear']):
                self.stdout.write('%s gear line at %s: %s' % (game_version, level, ', '.join(
                    '%s %d' % (key, gear[key]) for key in GEAR_KEYS)))
            for line in summary_lines(table, stored):
                self.stdout.write(line)
            if not options['dry_run']:
                os.makedirs(DIRECTORY, exist_ok=True)
                with open(table_path(game_version), 'w', encoding='utf-8',
                          newline='\n') as handle:
                    handle.write(dumps(table))
                self.stdout.write('wrote %s' % table_path(game_version))
            pivots = _Pivots(table, orders, stored)
            for line in change_lines(table, pivots, stored):
                self.stdout.write(line)
            if options['meta']:
                found = sources.get(game_version) or {}
                if not found:
                    self.stdout.write('%s: no per-class element source to compare with.'
                                      % game_version)
                for line in compare_with_sources(table, orders, found, pivots, stored):
                    self.stdout.write(line)
