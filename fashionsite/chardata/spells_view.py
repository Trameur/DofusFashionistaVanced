# -*- coding: utf-8 -*-

# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from chardata.encoded_char_id import decode_char_id
from chardata.fashion_action import fashion
from chardata.image_store import get_image_url, list_static_dir
from chardata.models import Char
from chardata.solution import get_solution
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_localization import get_localized_spell_name
from chardata.spell_reference import (localized, reference_by_spell_id,
                                      state_name)
from chardata.util import set_response, get_char_or_raise
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from static_s3.templatetags.static_s3 import static
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from fashionistapulp.reserved_filenames import safe_asset_stem
from fashionistapulp.translation import get_supported_language

from fashionistapulp.dofus_constants import (DAMAGE_TYPES, NEUTRAL,
                                             NON_ELEMENTAL_HIT_TYPES)

import jsonpickle
import re

def _spells(request, char, is_guest, char_id, encoded_char_id=None):
    char_class = char.char_class
    
    solution = get_solution(char)
    if solution is None:
        return fashion(request, char_id, True)    

    digests = []
    weapons = solution.items['Weapon']
    if len(weapons) > 0:
        weapon = weapons[0]
        if weapon.item_added and hasattr(weapon, 'non_crit_hits'):
            web_digest = _create_weapon_web_digest(weapon)
            digests.append(web_digest)
    game_version = getattr(request, 'game_version', 'dofus3')
    spells_by_class = get_damage_spells_for_version(game_version)
    class_spells = spells_by_class.get(char_class, [])
    reference = reference_by_spell_id(game_version, char_class)
    for spell in class_spells + spells_by_class.get('default', []):
        web_digest = _create_spell_web_digest(spell, game_version)
        entry = reference.get(getattr(spell, 'spell_id', None))
        if entry is not None:
            web_digest['reference'] = _reference_digest(entry)
        digests.append(web_digest)
    # The spells the class has that neither hurt nor buff: they were missing
    # from the page entirely.
    shown = {getattr(spell, 'spell_id', None) for spell in class_spells}
    for spell_id, entry in reference.items():
        if spell_id not in shown:
            digests.append(_create_reference_web_digest(entry, game_version))
    digests_json = jsonpickle.encode(digests, unpicklable=False)
    stats_json = jsonpickle.encode(solution.get_stats_total(), unpicklable=False)
    return set_response(request, 
                        'chardata/spells.html', 
                        {'request': request,
                         'is_guest': is_guest,
                         'encoded_char_id': encoded_char_id,
                         'user': request.user,
                         'digests_json': digests_json,
                         # The page must call a hit type non-elemental exactly
                         # where the damage formula does.
                         'non_elemental_hits_json': jsonpickle.encode(
                             list(NON_ELEMENTAL_HIT_TYPES), unpicklable=False),
                         'char_id': char_id,
                         'char_level': char.level,
                         # Retro states a critical rate as the X of 1/X.
                         'crit_is_fraction': game_version == 'retro',
                         'char_stats_json': stats_json,
                         'best_combo': _best_combo(char, solution, game_version),
                         # Only a shared build has a public url to name; an
                         # owner reading their own would otherwise point at a
                         # page that refuses everyone else.
                         'canonical_path': (
                             spells_linked_path(char, encoded_char_id)
                             if char.link_shared and encoded_char_id else ''),
                         'no_class_spells': len(class_spells) == 0},
                        char)

def _reference_digest(entry):
    """What the game says about a spell, in the reader's language."""
    language = get_supported_language()
    return {'description': localized(entry, 'description', language),
            'kind': localized(entry, 'kind', language),
            'ap': entry.get('ap'),
            'range': entry.get('range'),
            'per_turn': entry.get('per_turn'),
            'per_target': entry.get('per_target'),
            'cooldown': entry.get('cooldown'),
            'crit': entry.get('crit')}


def _create_reference_web_digest(entry, game_version):
    """A spell that neither hurts nor buffs: the page still lists it, with what
    the game says and no damage table."""
    language = get_supported_language()
    name = localized(entry, 'name', language)
    return {'type': 'spell',
            'name': name,
            'canonical': name,
            'level': entry.get('levels') or [1],
            'stacks': None,
            'image_url': _spell_image_url(_reference_icon_name(entry, name),
                                          game_version),
            'hit_number': 0,
            'non_crit_dams': None,
            'crit_dams': None,
            'aggregates': None,
            'is_linked': None,
            'special': None,
            'buff_scaling': None,
            'reference': _reference_digest(entry)}


def _reference_icon_name(entry, shown_name):
    """The icon file is named after the English spell name."""
    return localized(entry, 'name', 'en') or shown_name


def _create_weapon_web_digest(weapon):
    web_digest = {}
    if weapon.is_mageable:
        web_digest['type'] = 'weapon'
        web_digest['element_maged'] = weapon.element_maged
    else:
        web_digest['type'] = 'weapon_non_mageable'
    web_digest['name'] = weapon.localized_name
    web_digest['level'] = weapon.level
    web_digest['image_url'] = static(get_image_url(weapon.type, weapon.name))
    # The same numbers the spells carry, so a weapon can be read beside them.
    web_digest['reference'] = {
        'description': '',
        'kind': getattr(weapon, 'weapon_type', '') or '',
        'ap': [weapon.ap] if getattr(weapon, 'ap', None) else None,
        'range': None,
        'per_turn': ([weapon.uses_per_turn]
                     if getattr(weapon, 'uses_per_turn', None) else None),
        'per_target': None,
        'cooldown': None,
        'crit': ([weapon.crit_chance]
                 if getattr(weapon, 'crit_chance', None) else None)}
    web_digest['hit_number'] = len(weapon.non_crit_hits)
    web_digest['non_crit_dams'] = _convert_weapon_damage(weapon.non_crit_hits)
    web_digest['crit_dams'] = _convert_weapon_damage(weapon.crit_hits)
    damage_indexes = []
    healing_indexes = []
    effect_indexes = []
    for i, hit_instance in enumerate(weapon.non_crit_hits[NEUTRAL]):
        if hit_instance.element in NON_ELEMENTAL_HIT_TYPES:
            effect_indexes.append(i)
        elif hit_instance.heals:
            healing_indexes.append(i)
        else:
            damage_indexes.append(i)
    aggregates = []
    if damage_indexes:
        aggregates.append(('', damage_indexes))
    if healing_indexes:
        aggregates.append(('', healing_indexes))
    for idx in effect_indexes:
        aggregates.append(('', [idx]))
    web_digest['aggregates'] = convert_aggregates(aggregates)
    
    return web_digest

def _localized_spell_name(name, language, game_version):
    # Retro and Touch spell names live in a version-specific map keyed by the French
    # name (Spell.name); other versions use the shared English-keyed localization.
    version_names = None
    if game_version == 'retro':
        from fashionistapulp.dofus_constants_retro_spells import RETRO_SPELL_NAMES
        version_names = RETRO_SPELL_NAMES
    elif game_version == 'touch':
        from fashionistapulp.dofus_constants_touch_spells import TOUCH_SPELL_NAMES
        version_names = TOUCH_SPELL_NAMES
    if version_names is not None:
        names = version_names.get(name)
        if names:
            lang = (language or 'en').split('-')[0].lower()
            return names.get(lang) or names.get('fr') or name
        return name
    return get_localized_spell_name(name, language)


_dofus2_spell_icons = None


def _dofus2_spell_icon_names():
    """The spells Dofus 2 keeps its own icon for; the rest come from the
    Dofus 3 folder."""
    global _dofus2_spell_icons
    if _dofus2_spell_icons is None:
        _dofus2_spell_icons = frozenset(
            name[:-4] for name in list_static_dir('chardata/spells/dofus2')
            if name.endswith('.png'))
    return _dofus2_spell_icons


def _spell_image_url(spell_name, game_version):
    # The Sram's Con is the one spell whose name Windows reserves, and it
    # reserves it whatever the extension. Git cannot index such a file at all:
    # `git add` answers "no such file" on a name Python has just written. So
    # Con.png was ignored rather than fixed, never reached a deploy, and the
    # spell showed a broken icon while the file sat on the scraper's disk. The
    # scrapers write the escaped stem and the page has to ask for the same one,
    # which is why the rule lives in fashionistapulp rather than in either.
    stem = safe_asset_stem(spell_name)
    if game_version in ('beta', 'retro', 'touch'):
        spell_dir = 'chardata/spells/%s/' % game_version
    elif game_version == 'dofus2' and stem in _dofus2_spell_icon_names():
        spell_dir = 'chardata/spells/dofus2/'
    else:
        spell_dir = 'chardata/spells/'
    return static(spell_dir + stem + '.png')


def _weapon_castable(solution):
    """The equipped weapon as one more thing the turn can spend its AP on."""
    from chardata.spell_combo import WeaponCastable
    weapons = (getattr(solution, 'items', None) or {}).get('Weapon') or []
    if not weapons:
        return None
    weapon = weapons[0]
    if not weapon.item_added or not hasattr(weapon, 'non_crit_hits'):
        return None
    if not getattr(weapon, 'ap', 0):
        return None
    castable = WeaponCastable(weapon)
    return castable if castable.alternatives else None


def _best_combo(char, solution, game_version, buff_state=None, levels=None,
                pushback=False):
    """Best cast order for one turn, or None when there is nothing to say."""
    from chardata.spell_combo import (best_turn, buffs_in_force,
                                      castable_spells, combat_ap,
                                      conditional_extras, delayed_damage,
                                      delayed_moments, stacks_in_force)
    stats = dict(solution.get_stats_total())
    for stat, delta in buffs_in_force(char.char_class, char.level,
                                      game_version, buff_state,
                                      levels).items():
        stats[stat] = stats.get(stat, 0) + delta
    ap = combat_ap(stats.get('ap'), game_version)
    spells = castable_spells(char.char_class, char.level, game_version,
                             levels=levels)
    weapon = _weapon_castable(solution)
    if weapon is not None:
        spells = spells + [weapon]
    if not ap or not spells:
        return None
    standing = stacks_in_force(char.char_class, char.level, game_version,
                               buff_state)
    total, order = best_turn(stats, spells, ap, standing=standing,
                             game_version=game_version, pushback=pushback,
                             caster_level=char.level)
    if not order:
        return None
    language = get_supported_language()
    by_name = {spell.name: spell for spell in spells}
    # A poison is the spell's damage and belongs in what the search compares,
    # but it is not what the turn puts on the target now, so the panel counts
    # it apart instead of letting it read as burst.
    later = delayed_damage(stats, spells, order, standing=standing,
                           game_version=game_version)
    moments = delayed_moments(spells, order)
    times_cast = {}
    for name, _damage in order:
        times_cast[name] = times_cast.get(name, 0) + 1
    casts = []
    running = 0
    for name, damage in order:
        damage -= (later.get(name, 0) / times_cast[name]) if name in later else 0
        running += damage
        castable = by_name[name]
        if castable.is_spell:
            shown_name = _localized_spell_name(name, language, game_version)
            image_url = _spell_image_url(name, game_version)
        else:
            shown_name = castable.weapon.localized_name
            image_url = static(get_image_url(castable.weapon.type,
                                             castable.weapon.name))
        casts.append({'name': shown_name,
                      'image_url': image_url,
                      'ap': castable.cost,
                      'damage': int(round(damage)),
                      'running': int(round(running))})
    late = []
    for name in sorted(later):
        castable = by_name[name]
        late.append({
            'name': (_localized_spell_name(name, language, game_version)
                     if castable.is_spell else castable.weapon.localized_name),
            'damage': int(round(later[name])),
            'label': ', '.join(str(_DELAYED_LABELS.get(when, when))
                               for when in moments.get(name, [])),
        })
    extras = []
    for name, trigger, damage in conditional_extras(
            stats, spells, order, standing=standing,
            game_version=game_version, caster_level=char.level,
            pushback=pushback):
        castable = by_name[name]
        extras.append({
            'name': (_localized_spell_name(name, language, game_version)
                     if castable.is_spell else castable.weapon.localized_name),
            'damage': int(round(damage)),
            'label': str(_CONDITIONAL_LABELS.get(trigger, trigger)),
        })
    return {'casts': casts,
            'later': late,
            'later_total': int(round(sum(later.values()))),
            'pushback': bool(pushback),
            'can_push': any(getattr(spell, 'push_cells', 0)
                            for spell in spells),
            'total': int(round(total - sum(later.values()))),
            'ap_used': sum(cast['ap'] for cast in casts),
            'ap_available': ap,
            'conditional': extras}


def _create_spell_web_digest(spell, game_version='dofus3'):
    web_digest = {}
    digest = spell.get_effects_digest()
    current_language = get_supported_language()
    web_digest['type'] = 'spell'
    web_digest['name'] = _localized_spell_name(spell.name, current_language, game_version)
    # 'name' is translated; the combo endpoint matches on the untranslated name.
    web_digest['canonical'] = spell.name
    web_digest['level'] = spell.level_req
    web_digest['stacks'] = spell.stacks
    web_digest['image_url'] = _spell_image_url(spell.name, game_version)
    web_digest['hit_number'] = digest.hit_number
    web_digest['non_crit_dams'] = _convert_spell_damage(digest.non_crit_dams)
    web_digest['crit_dams'] = _convert_spell_damage(digest.crit_dams)
    web_digest['aggregates'] = convert_aggregates(digest.aggregates,
                                                  game_version)
    web_digest['is_linked'] = (
        spell.is_linked[0],
        get_localized_spell_name(spell.is_linked[1], current_language)
    ) if spell.is_linked else None
    web_digest['special'] = spell.special
    web_digest['conditional'] = {
        str(index): str(_CONDITIONAL_LABELS.get(trigger, trigger))
        for index, trigger in (getattr(spell, 'conditional', None) or {}).items()}
    web_digest['delayed'] = {
        str(index): str(_DELAYED_LABELS.get(when, when))
        for index, when in (getattr(spell, 'delayed', None) or {}).items()}
    # A critical hit can carry a different row list; when it does, the card
    # labels its block from that one.
    crit_delayed = getattr(spell, 'delayed_crit', None)
    web_digest['delayed_crit'] = (
        {str(index): str(_DELAYED_LABELS.get(when, when))
         for index, when in crit_delayed.items()}
        if crit_delayed is not None else None)
    web_digest['buff_scaling'] = spell.buff_scaling
    return web_digest

def best_combo_json(request, char_id=0):
    import json
    from django.http import JsonResponse
    char = get_char_or_raise(request, char_id)
    return _best_combo_response(request, char)


def best_combo_linked_json(request, encoded_char_id):
    char_id = decode_char_id(encoded_char_id)
    if char_id is None:
        raise Http404('Could not decode char id: %s' % encoded_char_id)
    char = get_object_or_404(Char, pk=char_id)
    if not char.link_shared:
        raise PermissionDenied
    return _best_combo_response(request, char)


def _best_combo_response(request, char):
    import json
    from django.http import JsonResponse
    solution = get_solution(char)
    if solution is None:
        return JsonResponse({'best_combo': None})
    def posted(key):
        try:
            value = json.loads(request.POST.get(key) or '{}')
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    game_version = getattr(request, 'game_version', 'dofus3')
    return JsonResponse({'best_combo': _best_combo(
        char, solution, game_version, posted('buff_state'),
        posted('spell_levels'),
        request.POST.get('pushback') == 'true')})


def spells(request, char_id=0):
    char = get_char_or_raise(request, char_id)
    return _spells(request, char, False, char_id)

def spells_linked_path(char, encoded_char_id):
    """The one url a shared build's spell page should be indexed under.

    The route captures a name and the view never reads it, so
    /spells_linked/ANYTHING/<id>/ serves the same page, and the template
    canonicalised each of them to itself. A build that is renamed keeps
    answering 200 under its old name, which is how a single page ends up
    indexed twice. `/s/` was given `shared_build_path` for exactly this and
    this page was left behind.

    The slug is the one base.html emits, so the canonical IS the link the site
    hands out rather than a third spelling.
    """
    from urllib.parse import quote
    prefix = ('' if char.game_version in (None, '', 'dofus3')
              else '/' + char.game_version)
    slug = char.char_name or 'shared'
    return '%s/spells_linked/%s/%s/' % (
        prefix, quote(str(slug).encode('utf-8'), safe=''), encoded_char_id)


def spells_linked(request, char_name, encoded_char_id):
    char_id = decode_char_id(encoded_char_id)
    if char_id is None:
        raise Http404('Could not decode char id: %s' % encoded_char_id)

    char = get_object_or_404(Char, pk=char_id)
    if not char.link_shared:
        raise PermissionDenied
    if char.game_version != getattr(request, 'game_version', 'dofus3'):
        raise Http404
    
    return _spells(request, char, True, char_id, encoded_char_id)
    
def _convert_spell_damage(base):
    if len(base[0]) == 0:
        return None
    return base
    
def _convert_weapon_damage(base):
    if base is None:
        return None
    actual_damages = []
    for element in DAMAGE_TYPES:
        actual_damages.append(base[element])
    return actual_damages
    

_BEST_ELEMENT = 'Hit in best element'
#: Retro's Bluff: Ankama says it hits "aleatoirement" in Air OR Water, so the
#: reader has to be told the two rows are one roll and not two hits.
_RANDOM_ELEMENT = 'Hit in one random element'
_STACK_LABEL = re.compile(r'^Stack (\d+)(?: - (.+))?$')
_MP_LABEL = re.compile(r'^(\d+) MP used this turn$')
_STATE_LABEL = re.compile(r'^State (!?\d+(?:,!?\d+)*)$')


def _localized_state_label(token, game_version):
    """The states the generator wrote as ids, under the names the game gives
    them. An unknown id leaves the whole label out rather than showing a
    number."""
    language = get_supported_language()
    needed, absent = [], []
    for part in token.split(','):
        without = part.startswith('!')
        name = state_name(game_version, part.lstrip('!'), language)
        if not name:
            return ''
        (absent if without else needed).append(name)
    parts = []
    if needed:
        parts.append(_('With %(states)s') % {'states': ', '.join(needed)})
    if absent:
        text = _('Without %(states)s') % {'states': ', '.join(absent)}
        parts.append(text if not parts else text[0].lower() + text[1:])
    return ', '.join(parts)


def _localized_aggregate_label(label, game_version=None):
    """The generator writes these labels in English and builds them by hand,
    so they are translated by shape rather than one msgid per number."""
    if label == _BEST_ELEMENT:
        return _('Hit in best element')
    if label == _RANDOM_ELEMENT:
        return _('Hit in one random element')
    match = _MP_LABEL.match(label)
    if match:
        return _('%(count)s MP used this turn') % {'count': match.group(1)}
    match = _STATE_LABEL.match(label)
    if match:
        return _localized_state_label(match.group(1), game_version)
    match = _STACK_LABEL.match(label)
    if match:
        stack = _('Stack %(count)s') % {'count': match.group(1)}
        rest = match.group(2)
        if rest:
            return '%s - %s' % (stack,
                                _localized_aggregate_label(rest, game_version))
        return stack
    return _(label)


# What a waiting damage row is waiting for, in the reader's words. Lazy: this
# dict is built at import, and gettext there would freeze the first language
# the process happened to serve.
_DELAYED_LABELS = {
    'turn_begin': _lazy('at the start of a turn'),
    'turn_end': _lazy('at the end of a turn'),
}

_CONDITIONAL_LABELS = {
    'pushback': _lazy('only when the target suffers pushback damage'),
    'pushback into an obstacle':
        _lazy('if the whole push lands against an obstacle'),
    'pushback into an obstacle at a state':
        _lazy('if the whole push lands against an obstacle, and only at the '
              'state the spell needs'),
    'out_of_sight':
        _lazy("on the following turn, and only if the target is out of the "
              "caster's line of sight"),
    'critical_hit': _lazy("only if the target lands a critical hit"),
    'no_critical_hit':
        _lazy("at the end of the target's turn, and only if it landed no "
              "critical hit"),
    'healed': _lazy("only if the target is healed"),
    'displaced':
        _lazy("only if the target attracts, repels, switches places or "
              "deals pushback damage"),
    'ap_removal': _lazy("only if the target is hit by an attempted AP reduction"),
    'mp_removal': _lazy("only if the target is hit by an attempted MP reduction"),
    'range_removal': _lazy("only if the target suffers a Range reduction"),
    'telefragged':
        _lazy("at the end of the caster's next turn, and only if the "
              "target has Telefrag"),
    'on_ally': _lazy("only on an ally, never on an enemy"),
}


def convert_aggregates(aggregates, game_version=None):
    if aggregates is None:
        return None
    new_aggr = []
    for tup in aggregates:
        lis = []
        for ele in tup:
            if isinstance(ele, str) and ele != '':
                lis.append(_localized_aggregate_label(ele, game_version))
            else:
                lis.append(ele)
        new_aggr.append(lis)
    if new_aggr == []:
        return None
    return new_aggr
