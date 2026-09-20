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
from chardata.spell_reference import (get_spell_reference, localized,
                                      reference_by_spell_id, state_name)
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
    shared_spells = spells_by_class.get('default', [])
    reference = reference_by_spell_id(game_version, char_class)
    # The item spells every class casts have their own block
    shared_reference = reference_by_spell_id(game_version, 'default')
    partenaires = _variant_partner_names(
        class_spells + shared_spells, game_version,
        list(reference.values()) + list(shared_reference.values()))
    for spell in class_spells + shared_spells:
        web_digest = _create_spell_web_digest(spell, game_version,
                                              char.level)
        spell_id = getattr(spell, 'spell_id', None)
        web_digest['variant_partner'] = partenaires.get(spell_id)
        entry = reference.get(spell_id) or shared_reference.get(spell_id)
        if entry is not None:
            web_digest['reference'] = _reference_digest(entry)
        digests.append(web_digest)
    # Spells that neither hurt nor buff
    shown ={getattr(spell, 'spell_id', None) for spell in class_spells}
    for spell_id, entry in reference.items():
        if spell_id not in shown:
            web_digest = _create_reference_web_digest(entry, game_version,
                                                      char.level)
            web_digest['variant_partner'] = partenaires.get(spell_id)
            digests.append(web_digest)
    # Local import: solution_view imports _best_combo from here
    from chardata.solution_view import pieces_above_the_character_level
    hors_niveau = pieces_above_the_character_level(char, solution)
    digests_json = jsonpickle.encode(digests, unpicklable=False)
    stats_json = jsonpickle.encode(solution.get_stats_total(), unpicklable=False)
    return set_response(request, 
                        'chardata/spells.html', 
                        {'request': request,
                         'is_guest': is_guest,
                         'encoded_char_id': encoded_char_id,
                         'user': request.user,
                         'digests_json': digests_json,
                         'non_elemental_hits_json': jsonpickle.encode(
                             list(NON_ELEMENTAL_HIT_TYPES), unpicklable=False),
                         'char_id': char_id,
                         'char_level': char.level,
                         'pieces_above_level': hors_niveau,
                         'pieces_above_level_text': ', '.join(
                             '%s %s' % (piece['name'], piece['level'])
                             for piece in hors_niveau),
                         # Retro states a critical rate as the X of 1/X.
                         'crit_is_fraction': game_version == 'retro',
                         'char_stats_json': stats_json,
                         'best_combo': _best_combo(char, solution, game_version),
                         'canonical_path': (
                             spells_linked_path(char, encoded_char_id)
                             if char.link_shared and encoded_char_id else ''),
                         # The url carries the version, not the language
                         'hreflang_urls': {},
                         'no_class_spells': len(class_spells) == 0,
                         'names_are_english': _names_are_english(
                             game_version)},
                        char)

def _variant_partner_names(spells, game_version, entries=()):
    """{spell id: localized name of its variant partner}"""
    from chardata.spell_variants import variant_of
    langue = get_supported_language()
    noms = {}
    for spell in spells:
        spell_id = getattr(spell, 'spell_id', None)
        if spell_id is not None and spell_id not in noms:
            noms[spell_id] = _localized_spell_name(spell.name, langue,
                                                   game_version)
    for entry in entries:
        spell_id = entry.get('id')
        if spell_id is not None and spell_id not in noms:
            noms[spell_id] = localized(entry, 'name', langue)
    par_variante = {}
    for spell_id in noms:
        variante = variant_of(game_version, spell_id)
        if variante is not None:
            par_variante.setdefault(variante, []).append(spell_id)
    partenaires = {}
    for groupe in par_variante.values():
        if len(groupe) != 2:
            continue
        premier, second = groupe
        partenaires[premier] = noms[second]
        partenaires[second] = noms[premier]
    return partenaires


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


def _create_reference_web_digest(entry, game_version, char_level=None):
    """A spell that neither hurts nor buffs, with no damage table."""
    language = get_supported_language()
    name = localized(entry, 'name', language)
    levels = entry.get('levels') or [1]
    return {'type': 'spell',
            'name': name,
            'canonical': name,
            'level': levels,
            **_reach(levels, char_level),
            'stacks': None,
            'image_url': _spell_image_url(
                _reference_icon_name(entry, name, game_version), game_version),
            'hit_number': 0,
            'non_crit_dams': None,
            'crit_dams': None,
            'aggregates': None,
            'is_linked': None,
            'special': None,
            'buff_scaling': None,
            'reference': _reference_digest(entry)}


# Retro and Touch spell icons are filed under their French names
SPELL_ICON_LANGUAGE = {'retro': 'fr', 'touch': 'fr'}

_shared_icon_names = {}


def _shared_icon_name_keepers(game_version):
    """{name: lowest id} for the names several spells share; the others are filed as "<name> (<id>)"."""
    if game_version not in _shared_icon_names:
        keepers = {}
        if game_version in SPELL_ICON_LANGUAGE:
            langue = SPELL_ICON_LANGUAGE[game_version]
            ids_by_name = {}
            for entries in get_spell_reference(game_version).values():
                for entry in entries or []:
                    name = localized(entry, 'name', langue)
                    if name and entry.get('id') is not None:
                        ids_by_name.setdefault(name, set()).add(entry['id'])
            keepers = {name: min(ids) for name, ids in ids_by_name.items()
                       if len(ids) > 1}
        _shared_icon_names[game_version] = keepers
    return _shared_icon_names[game_version]


def _reference_icon_name(entry, shown_name, game_version=None):
    """The icon file's name, in the language that version files them under."""
    langue = SPELL_ICON_LANGUAGE.get(game_version, 'en')
    name = localized(entry, 'name', langue) or shown_name
    keeper = _shared_icon_name_keepers(game_version).get(name)
    if keeper is not None and entry.get('id') not in (None, keeper):
        return '%s (%s)' % (name, entry['id'])
    return name


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
    # Same fields as a spell's reference
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
    # Retro and Touch name maps are keyed by the French name
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


_own_spell_icons = {}


def _own_spell_icon_names(game_version):
    """Spells the version has its own icon for; the rest use the Dofus 3 folder."""
    if game_version not in _own_spell_icons:
        _own_spell_icons[game_version] = frozenset(
            name[:-4] for name in list_static_dir('chardata/spells/' + game_version)
            if name.endswith('.png'))
    return _own_spell_icons[game_version]


def _spell_image_url(spell_name, game_version):
    # Same escaped stem the scrapers write (Windows reserves names like Con)
    stem = safe_asset_stem(spell_name)
    if game_version in ('retro', 'touch'):
        spell_dir = 'chardata/spells/%s/' % game_version
    elif (game_version in ('beta', 'dofus2')
          and stem in _own_spell_icon_names(game_version)):
        spell_dir = 'chardata/spells/%s/' % game_version
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
    # AP cap of the stored solve, like the stats
    from chardata.temporix_mode import solution_uses_temporix
    ap = combat_ap(stats.get('ap'), game_version,
                   temporix=solution_uses_temporix(solution, game_version))
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
    # best_turn counts delayed damage, the panel shows it apart
    later = delayed_damage(stats, spells, order, standing=standing,
                           game_version=game_version)
    moments = delayed_moments(spells, order)
    times_cast = {}
    for name, _damage in order:
        times_cast[name] = times_cast.get(name, 0) + 1
    limit_notes = _limit_notes(spells, order, times_cast, ap)
    casts = []
    running = 0
    shown = 0
    for index, (name, damage) in enumerate(order):
        damage -= (later.get(name, 0) / times_cast[name]) if name in later else 0
        running += damage
        # Round the running total once, each cast is the difference
        before = shown
        shown = int(round(running))
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
                      'damage': shown - before,
                      'running': shown,
                      'note': _cast_note(castable, name, later,
                                         shown - before, game_version),
                      'limit_mark': limit_notes.get(index, ('', ''))[0],
                      'limit_title': limit_notes.get(index, ('', ''))[1]})
    late = []
    # Same rounding as the casts above
    cumul_differe = 0.0
    montre_differe = 0
    for name in sorted(later):
        castable = by_name[name]
        avant = montre_differe
        cumul_differe += later[name]
        montre_differe = int(round(cumul_differe))
        late.append({
            'name': (_localized_spell_name(name, language, game_version)
                     if castable.is_spell else castable.weapon.localized_name),
            'damage': montre_differe - avant,
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
    au_plus_haut = all(getattr(castable, 'at_highest_rank', True)
                       for castable in spells
                       if getattr(castable, 'is_spell', False))
    return {'casts': casts,
            'without_buffs_note': _without_buffs_note(
                stats, spells, order, ap, standing, game_version, pushback,
                char.level),
            'rank_note': str(_RANK_NOTES['highest' if au_plus_haut
                                         else 'picked']),
            # standing holds the buffs really in force, not every ticked box
            'buff_note': str(_BUFF_NOTES['on' if standing else 'off']),
            'melee_note': _melee_note(stats),
            'crit_failure_note': (str(_CRIT_FAILURE_NOTE)
                                  if game_version == 'retro' else ''),
            'later': late,
            'later_total': montre_differe,
            'pushback': bool(pushback),
            'can_push': any(getattr(spell, 'push_cells', 0)
                            for spell in spells),
            'total': casts[-1]['running'],
            'ap_used': sum(cast['ap'] for cast in casts),
            'ap_available': ap,
            'conditional': extras}


def _limit_notes(spells, order, times_cast, ap):
    """{cast index: (mark, sentence)} where a spell's limit cut the turn."""
    par_nom = {}
    for castable in spells:
        nom = (castable.spell.name if getattr(castable, 'is_spell', False)
               else castable.weapon.localized_name)
        par_nom[nom] = castable
    dernier = {}
    for index, (nom, _damage) in enumerate(order):
        dernier[nom] = index
    notes = {}
    for nom, index in dernier.items():
        castable = par_nom.get(nom)
        if castable is None:
            continue
        limite = getattr(castable, 'limit', None)
        cout = getattr(castable, 'cost', 0)
        combien = times_cast.get(nom, 0)
        if not limite or not cout or combien < limite:
            continue
        if (combien + 1) * cout > ap:
            # Out of AP anyway
            continue
        notes[index] = ('%d/%d' % (combien, limite), str(_LIMIT_NOTE))
    return notes


def _melee_note(stats):
    """The % melee and % ranged sentence, or '' when the build has neither."""
    if not any(stats.get(cle) for cle in _UNCOUNTED_STATS):
        return ''
    return str(_MELEE_NOTE) % {'melee': _('% Melee Damage'),
                               'ranged': _('% Ranged Damage')}


def _cast_note(castable, name, later, damage, game_version=None):
    """Why a cast shows zero, or which group it counted, or ''."""
    if int(round(damage)):
        group = getattr(castable, 'scored_group', '')
        if group:
            label = _localized_aggregate_label(group, game_version)
            if label:
                return str(_CAST_NOTES['group']) % {'group': label}
        return ''
    if name in later:
        return str(_CAST_NOTES['delayed'])
    if getattr(castable, 'buffs', None) and not getattr(castable, 'hits', None):
        return str(_CAST_NOTES['buff'])
    return ''


def _buff_casts(spells, order):
    """Spells the turn casts that only buff, same test as _cast_note."""
    lances = {name for name, _damage in order}
    return {spell.name for spell in spells
            if spell.name in lances
            and getattr(spell, 'buffs', None)
            and not getattr(spell, 'hits', None)}


def _burst_total(stats, spells, order, standing, game_version):
    """Total as the panel shows it: the turn minus what lands later."""
    from chardata.spell_combo import delayed_damage
    later = delayed_damage(stats, spells, order, standing=standing,
                           game_version=game_version)
    times_cast = {}
    for name, _damage in order:
        times_cast[name] = times_cast.get(name, 0) + 1
    running = 0.0
    shown = 0
    for name, damage in order:
        if name in later:
            damage -= later[name] / times_cast[name]
        running += damage
        shown = int(round(running))
    return shown


def _without_buffs_note(stats, spells, order, ap, standing, game_version,
                        pushback, caster_level):
    """The same turn without the buffs it casts, on the panel's scale."""
    from chardata.spell_combo import best_turn
    buffs = _buff_casts(spells, order)
    if not buffs:
        return ''
    restants = [spell for spell in spells if spell.name not in buffs]
    if not restants:
        return ''
    _total, ordre = best_turn(stats, restants, ap, standing=standing,
                              game_version=game_version, pushback=pushback,
                              caster_level=caster_level)
    if not ordre:
        return ''
    montre = _burst_total(stats, restants, ordre, standing, game_version)
    return str(_WITHOUT_BUFFS_NOTE) % {'damage': montre}


def _reach(level_req, char_level):
    """Has the spell, and highest reachable rank; a None level allows all."""
    from chardata.spell_buffs import _decide_spell_level
    levels = list(level_req or [1])
    if char_level is None:
        return {'available': True, 'highest_level': len(levels) - 1}
    if char_level < levels[0]:
        return {'available': False, 'highest_level': 0}
    return {'available': True,
            'highest_level': _decide_spell_level(levels, char_level)}


def _always_land_by_rank(spell, digest):
    """{'non_crit': {rank: [indices]}, 'crit': {...}}, or None."""
    from chardata.spell_combo import rows_that_always_land
    attente = getattr(spell, 'conditional', None) or {}
    sortie = {}
    for cle, rangs in (('non_crit', digest.non_crit_dams),
                       ('crit', digest.crit_dams)):
        par_rang = {}
        for index, effets in enumerate(rangs or []):
            lignes = rows_that_always_land(digest, effets, attente)
            if not lignes:
                continue
            par_rang[str(index)] = list(lignes)
        if par_rang:
            sortie[cle] = par_rang
    return sortie or None


_NAMES_LEFT_ENGLISH = {}


def _languages_left_english(game_version):
    """Languages whose spell names all equal the English ones."""
    if game_version in _NAMES_LEFT_ENGLISH:
        return _NAMES_LEFT_ENGLISH[game_version]
    if game_version == 'touch':
        from fashionistapulp.dofus_constants_touch_spells import (
            TOUCH_SPELL_NAMES)
        table = TOUCH_SPELL_NAMES
    elif game_version == 'retro':
        from fashionistapulp.dofus_constants_retro_spells import (
            RETRO_SPELL_NAMES)
        table = RETRO_SPELL_NAMES
    else:
        table = None
    laissees = set()
    if table:
        langues = set()
        for par_langue in table.values():
            langues.update(par_langue)
        for langue in langues - {'en'}:
            noms = [(par_langue.get(langue), par_langue.get('en'))
                    for par_langue in table.values()]
            noms = [(mien, anglais) for mien, anglais in noms if mien]
            if noms and all(mien == anglais for mien, anglais in noms):
                laissees.add(langue)
    _NAMES_LEFT_ENGLISH[game_version] = laissees
    return laissees


def _names_are_english(game_version):
    return get_supported_language() in _languages_left_english(game_version)


def _create_spell_web_digest(spell, game_version='dofus3', char_level=None):
    web_digest = {}
    digest = spell.get_effects_digest()
    current_language = get_supported_language()
    web_digest['type'] = 'spell'
    web_digest['name'] = _localized_spell_name(spell.name, current_language, game_version)
    # 'name' is translated; the combo endpoint matches on the untranslated name.
    web_digest['canonical'] = spell.name
    web_digest['level'] = spell.level_req
    web_digest.update(_reach(spell.level_req, char_level))
    web_digest['stacks'] = spell.stacks
    web_digest['image_url'] = _spell_image_url(spell.name, game_version)
    web_digest['hit_number'] = digest.hit_number
    web_digest['non_crit_dams'] = _convert_spell_damage(digest.non_crit_dams)
    web_digest['crit_dams'] = _convert_spell_damage(digest.crit_dams)
    web_digest['aggregates'] = convert_aggregates(
        digest.aggregates, game_version,
        digest.non_crit_dams[0] if digest.non_crit_dams else None)
    # Rows that always land, outside the aggregate groups
    web_digest['always_land'] = _always_land_by_rank(spell, digest)
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
    # A critical hit can have its own row list
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
    """Canonical url of a shared build's spell page, same slug as base.html."""
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
# Retro's Bluff hits in Air or Water at random: one roll, not two hits
_RANDOM_ELEMENT = 'Hit in one random element'
# Ebony Dofus poisons in the attack's element only: its five rows are one hit
_ATTACK_ELEMENT = 'Poison in the element of the attack'
_STACK_LABEL = re.compile(r'^Stack (\d+)(?: - (.+))?$')
_MP_LABEL = re.compile(r'^(\d+) MP used this turn$')
_STATE_LABEL = re.compile(r'^State (!?\d+(?:,!?\d+)*)$')


def _localized_state_label(token, game_version):
    """State ids under their game names; '' when one is unknown."""
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
    """Generator labels are English and built by hand: translate by shape."""
    if label == _BEST_ELEMENT:
        return _('Hit in best element')
    if label == _RANDOM_ELEMENT:
        return _('Hit in one random element')
    if label == _ATTACK_ELEMENT:
        return _('Poison in the element of the attack')
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


# Lazy: gettext at import would freeze the first language served
_DELAYED_LABELS = {
    'turn_begin': _lazy('at the start of a turn'),
    'turn_end': _lazy('at the end of a turn'),
}

# calculate_damage never applies % melee or % ranged
_MELEE_NOTE = _lazy('%(melee)s and %(ranged)s are not counted here: on most '
                    'casts the caster chooses the range.')

_UNCOUNTED_STATS = ('permedam', 'perrandam')

_BUFF_NOTES = {
    'off': _lazy('One turn on a single target: average damage and critical '
                 'hit rate included. Buffs cast in the turn count; none is '
                 'assumed standing before it.'),
    'on': _lazy('One turn on a single target: average damage and critical '
                'hit rate included. Buffs cast in the turn count, on top of '
                'the ones ticked on this page.'),
}

_WITHOUT_BUFFS_NOTE = _lazy('Without the buffs it casts first, this turn '
                            'would deal %(damage)s.')

_RANK_NOTES = {
    'highest': _lazy('Spells at the highest level the character reaches.'),
    'picked': _lazy('Spells at the levels picked above.'),
}

# Not modelled: on some spells a critical failure also ends the turn
_CRIT_FAILURE_NOTE = _lazy('Critical failure is not counted; this version is '
                           'the only one that has it.')

# Castable.limit is the lowest of per turn, per target and cooldown
_LIMIT_NOTE = _lazy('at the most one turn on one target allows')

_CAST_NOTES = {
    'buff': _lazy('no damage of its own, it raises the casts that follow'),
    'delayed': _lazy('no damage now, its own lands later and is counted apart'),
    'group': _lazy('counted on %(group)s'),
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
    'melee_and_ranged':
        _lazy("only after attacking both in close combat and at range in the "
              "same turn"),
    'mp_removal': _lazy("only if the target is hit by an attempted MP reduction"),
    'range_removal': _lazy("only if the target suffers a Range reduction"),
    'telefragged':
        _lazy("at the end of the caster's next turn, and only if the "
              "target has Telefrag"),
    'on_ally': _lazy("only on an ally, never on an enemy"),
}


# Labels meaning one row of the group lands; a "Stack N - " prefix may precede
_ONE_LANDS = {
    _BEST_ELEMENT: 'best',
    _RANDOM_ELEMENT: 'one',
    _ATTACK_ELEMENT: 'one',
}


def _one_lands_kind(label):
    match = _STACK_LABEL.match(label or '')
    if match and match.group(2):
        label = match.group(2)
    return _ONE_LANDS.get(label)


def _merge_faces_of_one_hit(aggregates, rows):
    """Merge the per-element faces of one hit into a single group."""
    from chardata.spell_combo import element_runs
    runs = element_runs(aggregates, rows)
    head_of, merged_head = {}, {}
    for run in runs:
        kind = next((_one_lands_kind(label) for label, _indices in run
                     if _one_lands_kind(label)), None)
        if not kind:
            continue
        head = tuple(run[0][1])
        for _label, indices in run:
            head_of[tuple(indices)] = head
        merged_head[head] = (
            next((label for label, _indices in run if label), ''),
            [index for _label, indices in run for index in indices],
            kind)
    merged, done = [], set()
    for label, indices in aggregates:
        head = head_of.get(tuple(indices))
        if head is None:
            merged.append((label, list(indices), None))
            continue
        if head in done:
            continue
        done.add(head)
        merged.append(merged_head[head])
    return merged


def convert_aggregates(aggregates, game_version=None, rows=None):
    """Aggregates as the page reads them; no merge without rows."""
    if aggregates is None:
        return None
    if rows:
        merged = _merge_faces_of_one_hit(aggregates, rows)
    else:
        merged = [(label, list(indices), None) for label, indices in aggregates]
    new_aggr = []
    for label, indices, kind in merged:
        entry = [_localized_aggregate_label(label, game_version)
                 if isinstance(label, str) and label != '' else label,
                 indices]
        if kind:
            entry.append(kind)
        new_aggr.append(entry)
    if new_aggr == []:
        return None
    return new_aggr
