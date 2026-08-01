#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import pprint
import sys
import textwrap
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

try:
    from .default_damage_spells import DefaultSpellSpec, DEFAULT_DAMAGE_SPELL_SPECS
except ImportError:
    from default_damage_spells import DefaultSpellSpec, DEFAULT_DAMAGE_SPELL_SPECS

AUTO_START = "# AUTO-GENERATED DAMAGE_SPELLS START"
AUTO_END = "# AUTO-GENERATED DAMAGE_SPELLS END"
AUTO_COMMENT = (
    "# The block below is overwritten by itemscraper/generate_damage_spells.py.\n"
    "# Do not edit it manually."
)

ELEMENT_LITERAL = {
    "NEUTRAL": "NEUTRAL",
    "EARTH": "EARTH",
    "FIRE": "FIRE",
    "WATER": "WATER",
    "AIR": "AIR",
}
BEST_ELEMENT_LABEL = "Hit in best element"

STAT_BUFF_CHARACTERISTICS = {
    10: "buff_str",
    11: "buff_vit",
    13: "buff_cha",
    14: "buff_agi",
    15: "buff_int",
    25: "buff_pow",
    49: "buff_finalheals",
    107: "buff_final",
}

ALWAYS_BUFF_TOKENS = {"buff_final", "buff_finalheals"}

BUFF_SORT_ORDER = {
    "buff_str": 0,
    "buff_int": 1,
    "buff_cha": 2,
    "buff_agi": 3,
    "buff_vit": 4,
    "buff_pow": 5,
    "buff_final": 6,
    "buff_finalheals": 7,
}

BASE_CLASSES = [
    "Eniripsa",
    "Iop",
    "Xelor",
    "Osamodas",
    "Feca",
    "Sacrier",
    "Ecaflip",
    "Enutrof",
    "Sram",
    "Sadida",
    "Cra",
    "Pandawa",
    "Rogue",
    "Masqueraider",
    "Foggernaut",
    "Eliotrope",
    "Huppermage",
    "Ouginak",
    "Forgelance",
]
CHARACTER_CLASSES = sorted(BASE_CLASSES)
GLYPH_EFFECT_IDS = {401, 402, 1091, 1165}
BESTIAL_PACT_ANKAMA_ID = 31141
MP_DAMAGE_EFFECT_ID = 293
MP_DAMAGE_TRIGGER_TOKEN = "MP"
DEFAULT_MP_DAMAGE_STACK_CAP = 10
MP_TRIGGER_EFFECT_ID = 1160


@dataclass
class SpellEntry:
    name: str
    level_requirements: List[int]
    non_crit_ranges: List[List[str]]
    crit_ranges: Optional[List[List[str]]]
    elements: List[str]
    steals: Optional[List[bool]]
    is_linked: Optional[Sequence[Any]]
    order: int
    ankama_id: int
    stacks: Optional[int] = None
    heals: Optional[List[bool]] = None
    aggregates: Optional[List[Tuple[str, List[int]]]] = None
    buff_scaling: Optional[Dict[str, Any]] = None
    casting: Optional[Dict[str, List[int]]] = None


def _parse_damage_literal(literal: str) -> tuple[int, int]:
    parts = literal.split("-", 1)
    try:
        if len(parts) == 1:
            value = int(parts[0])
            return value, value
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 0, 0


def _format_damage_literal(min_val: int, max_val: int) -> str:
    if min_val == max_val:
        return str(min_val)
    return f"{min_val}-{max_val}"


LEGACY_DEFAULT_SPELLS: Dict[str, SpellEntry] = {
    "Burnt Pie": SpellEntry(
        name="Burnt Pie",
        level_requirements=[30, 97, 164],
        non_crit_ranges=[["5-7", "6-8", "8-10"] for _ in range(4)],
        crit_ranges=[["6-8", "8-10", "10-12"] for _ in range(4)],
        elements=["EARTH", "FIRE", "WATER", "AIR"],
        steals=None,
        is_linked=(1, "Leek Pie"),
        order=0,
        ankama_id=0,
    ),
    "Ebony Dofus": SpellEntry(
        name="Ebony Dofus",
        level_requirements=[180],
        non_crit_ranges=[["14-16"], ["14-16"], ["14-16"], ["14-16"]],
        crit_ranges=None,
        elements=["EARTH", "FIRE", "WATER", "AIR"],
        steals=None,
        is_linked=None,
        order=0,
        ankama_id=0,
    ),
    "Leek Pie": SpellEntry(
        name="Leek Pie",
        level_requirements=[97, 164],
        non_crit_ranges=[["6-8", "8-10"] for _ in range(4)],
        crit_ranges=[["8-10", "10-12"] for _ in range(4)],
        elements=["EARTH", "FIRE", "WATER", "AIR"],
        steals=None,
        is_linked=(2, "Burnt Pie"),
        order=0,
        ankama_id=0,
    ),
    "Weapon Skill": SpellEntry(
        name="Weapon Skill",
        level_requirements=[1],
        non_crit_ranges=[["300"]],
        crit_ranges=[["350"]],
    elements=["'buff_pow_weapon'"],
        steals=None,
        is_linked=None,
        order=0,
        ankama_id=0,
    ),
    "Pestilential Fog": SpellEntry(
        name="Pestilential Fog",
        level_requirements=[200],
        non_crit_ranges=[["16-18"], ["16-18"], ["16-18"], ["16-18"], ["16-18"]],
        crit_ranges=None,
        elements=["NEUTRAL", "EARTH", "FIRE", "WATER", "AIR"],
        steals=None,
        is_linked=None,
        order=0,
        ankama_id=0,
    ),
    "Scurvion Toxicity": SpellEntry(
        name="Scurvion Toxicity",
        level_requirements=[200],
        non_crit_ranges=[["6-8"], ["6-8"], ["6-8"], ["6-8"], ["6-8"]],
        crit_ranges=None,
        elements=["NEUTRAL", "EARTH", "FIRE", "WATER", "AIR"],
        steals=None,
        is_linked=None,
        order=0,
        ankama_id=0,
    ),
}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--class-json",
        type=Path,
        default=Path("itemscraper/transformed_class_spells.json"),
        help="Path to transformed_class_spells.json",
    )
    parser.add_argument(
        "--spells-json",
        type=Path,
        default=Path("itemscraper/transformed_spells.json"),
        help="Path to transformed_spells.json",
    )
    parser.add_argument(
        "--constants",
        type=Path,
        default=Path("fashionistapulp/fashionistapulp/dofus_constants.py"),
        help="Path to dofus_constants.py",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_spell_lookup(all_spells: Sequence[Mapping[str, Any]]) -> Dict[int, Mapping[str, Any]]:
    lookup: Dict[int, Mapping[str, Any]] = {}
    for spell in all_spells:
        try:
            ankama_id = int(spell.get("ankama_id"))
        except (TypeError, ValueError):
            continue
        if ankama_id <= 0:
            continue
        lookup[ankama_id] = spell
    return lookup


def _apply_stackable_damage(
    damage_template: Optional[Mapping[str, Any]],
    level_requirements: Sequence[int],
    non_crit: List[List[str]],
    crit: Optional[List[List[str]]],
    elements: List[str],
    steals: Optional[List[bool]],
    heals: Optional[List[bool]],
) -> Optional[List[Tuple[str, List[int]]]]:
    if not damage_template:
        return None
    stack_info = damage_template.get("stackable_damage")
    if not stack_info or len(non_crit) != 1 or not elements:
        return None
    per_stack = stack_info.get("per_stack") or []
    if len(per_stack) != len(level_requirements):
        return None
    caps = stack_info.get("max_stacks") or []
    if len(caps) < len(level_requirements):
        caps = caps + [None] * (len(level_requirements) - len(caps))
    stack_cap = 0
    for cap in caps:
        if cap and cap > stack_cap:
            stack_cap = cap
    if stack_cap <= 0:
        return None
    base_non_crit = non_crit[0]
    base_crit = crit[0] if crit else None
    default_element = elements[0]
    default_steal = steals[0] if steals else False
    default_heal = heals[0] if heals else False
    aggregates: List[Tuple[str, List[int]]] = [("Stack 0", [0])]
    for stack_count in range(1, stack_cap + 1):
        new_non: List[str] = []
        for level_idx, base_literal in enumerate(base_non_crit):
            delta_single = per_stack[level_idx] or 0
            if delta_single == 0:
                new_non.append(base_literal)
                continue
            cap = caps[level_idx] if level_idx < len(caps) else None
            effective_stack = min(stack_count, cap) if cap else stack_count
            min_val, max_val = _parse_damage_literal(base_literal)
            delta_total = delta_single * effective_stack
            new_non.append(_format_damage_literal(min_val + delta_total, max_val + delta_total))
        non_crit.append(new_non)
        if base_crit is not None and crit is not None:
            new_crit: List[str] = []
            for level_idx, base_literal in enumerate(base_crit):
                delta_single = per_stack[level_idx] or 0
                if delta_single == 0:
                    new_crit.append(base_literal)
                    continue
                cap = caps[level_idx] if level_idx < len(caps) else None
                effective_stack = min(stack_count, cap) if cap else stack_count
                min_val, max_val = _parse_damage_literal(base_literal)
                delta_total = delta_single * effective_stack
                new_crit.append(_format_damage_literal(min_val + delta_total, max_val + delta_total))
            crit.append(new_crit)
        elements.append(default_element)
        if steals is not None:
            steals.append(default_steal)
        if heals is not None:
            heals.append(default_heal)
        aggregates.append((f"Stack {stack_count}", [len(non_crit) - 1]))
    return aggregates


def _expand_multi_row_stackable_damage(
    rows: List[Dict[str, Any]],
    crit_rows: List[Dict[str, Any]],
    stack_info: Mapping[str, Any],
    level_count: int,
    stack_cap_override: Optional[int] = None,
) -> Tuple[Optional[List[str]], int]:
    if not rows or not stack_info or level_count <= 0:
        return None, 0
    per_stack = list(stack_info.get("per_stack") or [])
    if len(per_stack) != level_count:
        return None, 0
    if stack_cap_override and stack_cap_override > 1:
        stack_cap = stack_cap_override
        effective_caps = [stack_cap] * level_count
    else:
        caps = list(stack_info.get("max_stacks") or [])
        if len(caps) < level_count:
            caps = caps + [caps[-1] if caps else None] * (level_count - len(caps))
        stack_cap = 0
        for cap in caps:
            if cap and cap > stack_cap:
                stack_cap = cap
        if stack_cap <= 1:
            return None, 0
        effective_caps = [cap or stack_cap for cap in caps[:level_count]]
    if stack_cap <= 1:
        return None, 0

    base_rows = list(rows)
    base_crit_rows = list(crit_rows or [])

    def _clone_row(source: Mapping[str, Any], stack_count: int) -> Dict[str, Any]:
        cloned: Dict[str, Any] = dict(source)
        ranges = list(source.get("ranges") or [])
        new_ranges: List[str] = []
        for idx, literal in enumerate(ranges):
            if idx >= level_count:
                new_ranges.append(str(literal))
                continue
            single = per_stack[idx] if idx < len(per_stack) and per_stack[idx] is not None else 0
            if not single:
                new_ranges.append(str(literal))
                continue
            delta = single * min(stack_count, effective_caps[idx])
            if not delta:
                new_ranges.append(str(literal))
                continue
            min_val, max_val = _parse_damage_literal(str(literal))
            new_ranges.append(_format_damage_literal(min_val + delta, max_val + delta))
        cloned["ranges"] = new_ranges
        group = cloned.get("best_element_group")
        if group is not None:
            cloned["best_element_group"] = f"{group}-stack{stack_count}"
        return cloned

    for stack_count in range(1, stack_cap + 1):
        for row in base_rows:
            rows.append(_clone_row(row, stack_count))
        if base_crit_rows:
            for row in base_crit_rows:
                crit_rows.append(_clone_row(row, stack_count))

    labels = stack_info.get("labels")
    if labels and len(labels) >= stack_cap + 1:
        stack_labels = [str(label) for label in labels[: stack_cap + 1]]
    else:
        stack_labels = [f"Stack {count}" for count in range(stack_cap + 1)]
    return stack_labels, stack_cap


def _prefix_stack_labels(
    aggregates: Optional[List[Tuple[str, List[int]]]],
    base_row_block: int,
    stack_labels: Optional[Sequence[str]],
) -> Optional[List[Tuple[str, List[int]]]]:
    if not aggregates or not stack_labels or base_row_block <= 0:
        return aggregates
    total_stack_rows = base_row_block * len(stack_labels)
    updated: List[Tuple[str, List[int]]] = []
    for label, indexes in aggregates:
        new_label = label
        if indexes:
            idx = indexes[0]
            if idx < total_stack_rows:
                stack_idx = idx // base_row_block
                if stack_idx > 0 and stack_idx < len(stack_labels):
                    prefix = stack_labels[stack_idx]
                    if label:
                        new_label = f"{prefix} - {label}"
                    else:
                        new_label = prefix
        updated.append((new_label, indexes))
    return updated


def _build_stack_row_aggregates(
    stack_row_block: int,
    base_row_count: int,
    stack_labels: Sequence[str],
) -> Optional[List[Tuple[str, List[int]]]]:
    if stack_row_block <= 0 or base_row_count <= 0 or not stack_labels:
        return None
    aggregates: List[Tuple[str, List[int]]] = []
    stacks = min(len(stack_labels), (base_row_count + stack_row_block - 1) // stack_row_block)
    for stack_idx in range(stacks):
        start = stack_idx * stack_row_block
        label = stack_labels[stack_idx]
        if not label:
            label = f"Stack {stack_idx}"
        for offset in range(stack_row_block):
            row_idx = start + offset
            if row_idx >= base_row_count:
                break
            display = label if offset == 0 else ""
            aggregates.append((display, [row_idx]))
    return aggregates


def _prepare_mp_stackable_damage(
    spell: Mapping[str, Any],
    damage_template: MutableMapping[str, Any],
    level_count: int,
) -> Optional[Dict[str, Any]]:
    if level_count <= 0 or not isinstance(damage_template, MutableMapping):
        return None
    if damage_template.get("stackable_damage"):
        return None
    spec = _detect_mp_damage_stack_spec(spell, level_count)
    if not spec:
        return None
    damage_template["stackable_damage"] = {
        "per_stack": spec["per_stack"],
        "max_stacks": spec["max_stacks"],
    }
    return spec


def _detect_mp_damage_stack_spec(spell: Mapping[str, Any], level_count: int) -> Optional[Dict[str, Any]]:
    if level_count <= 0:
        return None
    levels = sorted(
        spell.get("levels") or [],
        key=lambda lvl: ((lvl.get("grade") or 0), (lvl.get("level_id") or 0)),
    )
    if len(levels) < level_count:
        return None
    owner_id = spell.get("ankama_id")
    per_stack: List[int] = []
    for idx in range(level_count):
        effect = _mp_damage_effect_for_level(levels[idx], owner_id)
        if not effect:
            return None
        try:
            value = int(effect.get("value"))
        except (TypeError, ValueError):
            value = 0
        per_stack.append(value)
    if not any(value > 0 for value in per_stack):
        return None
    stack_cap = _infer_mp_stack_cap(levels)
    if stack_cap is None:
        stack_cap = DEFAULT_MP_DAMAGE_STACK_CAP
    if stack_cap <= 0:
        return None
    return {
        "per_stack": per_stack,
        "max_stacks": [stack_cap] * level_count,
        "labels": [f"{count} MP used this turn" for count in range(stack_cap + 1)],
    }


def _prepare_base_damage_stackable_damage(
    spell: Mapping[str, Any],
    damage_template: MutableMapping[str, Any],
    level_count: int,
) -> Optional[Dict[str, Any]]:
    if level_count <= 0 or not isinstance(damage_template, MutableMapping):
        return None
    if damage_template.get("stackable_damage"):
        return None
    normal_rows = damage_template.get("normal") or []
    if not normal_rows:
        return None
    spec = _detect_base_damage_stack_spec(spell, level_count)
    if not spec:
        return None
    damage_template["stackable_damage"] = {
        "per_stack": spec["per_stack"],
        "max_stacks": spec["max_stacks"],
    }
    return spec


def _detect_base_damage_stack_spec(
    spell: Mapping[str, Any],
    level_count: int,
) -> Optional[Dict[str, Any]]:
    if level_count <= 0:
        return None
    try:
        owner_id = int(spell.get("ankama_id"))
    except (TypeError, ValueError):
        return None
    levels = sorted(
        spell.get("levels") or [],
        key=lambda lvl: ((lvl.get("grade") or 0), (lvl.get("level_id") or 0)),
    )
    if len(levels) < level_count:
        return None
    per_stack: List[int] = []
    max_stacks: List[Optional[int]] = []
    stack_cap = 0
    for idx in range(level_count):
        level = levels[idx]
        effect = _self_base_damage_effect(level, owner_id)
        if not effect:
            return None
        try:
            value = int(effect.get("value"))
        except (TypeError, ValueError):
            value = 0
        per_stack.append(value)
        try:
            cap_value = int(level.get("max_stack"))
        except (TypeError, ValueError):
            cap_value = None
        if cap_value and cap_value > 1:
            stack_cap = max(stack_cap, cap_value)
            max_stacks.append(cap_value)
        else:
            max_stacks.append(None)
    if stack_cap <= 1:
        return None
    if not any(value > 0 for value in per_stack):
        return None
    return {"per_stack": per_stack, "max_stacks": max_stacks}


def _self_base_damage_effect(level: Mapping[str, Any], owner_id: int) -> Optional[Mapping[str, Any]]:
    for effect in level.get("effects", []):
        if effect.get("effect_id") != MP_DAMAGE_EFFECT_ID:
            continue
        dice = effect.get("dice") or {}
        try:
            linked_id = int(dice.get("min"))
        except (TypeError, ValueError):
            continue
        if linked_id != owner_id:
            continue
        triggers = (effect.get("triggers") or "").upper()
        if MP_DAMAGE_TRIGGER_TOKEN in triggers:
            continue
        try:
            value = int(effect.get("value"))
        except (TypeError, ValueError):
            value = None
        if not value or value <= 0:
            continue
        return effect
    return None


def _mp_damage_effect_for_level(level: Mapping[str, Any], owner_id: Any) -> Optional[Mapping[str, Any]]:
    for effect in level.get("effects", []):
        if effect.get("effect_id") != MP_DAMAGE_EFFECT_ID:
            continue
        triggers = (effect.get("triggers") or "").upper()
        if MP_DAMAGE_TRIGGER_TOKEN not in triggers:
            continue
        dice = effect.get("dice") or {}
        linked_id = dice.get("min")
        if linked_id not in (owner_id, None):
            continue
        return effect
    return None


def _infer_mp_stack_cap(levels: Sequence[Mapping[str, Any]]) -> Optional[int]:
    for level in levels:
        try:
            stack_value = int(level.get("max_stack"))
        except (TypeError, ValueError):
            stack_value = None
        if stack_value and stack_value > 1:
            return stack_value
    return None


def _apply_custom_stack_labels(
    aggregates: Sequence[Tuple[str, List[int]]],
    labels: Sequence[Optional[str]],
) -> List[Tuple[str, List[int]]]:
    updated: List[Tuple[str, List[int]]] = []
    for idx, aggregate in enumerate(aggregates):
        label = aggregate[0]
        if idx < len(labels):
            replacement = labels[idx]
            if replacement:
                label = str(replacement)
        updated.append((label, aggregate[1]))
    return updated

def build_spell_map(class_data: Mapping[str, Any], all_spells: Sequence[Mapping[str, Any]]) -> Dict[str, List[SpellEntry]]:
    breed_lookup = _build_breed_lookup(class_data)
    spell_lookup = _build_spell_lookup(all_spells)
    spells_by_class: Dict[str, List[SpellEntry]] = {cls: [] for cls in CHARACTER_CLASSES}

    for spell in sorted(all_spells, key=_sort_key):
        converted = convert_spell(spell, spell_lookup=spell_lookup)
        if not converted:
            continue
        matched_classes = _classes_for_spell(spell, breed_lookup)
        if matched_classes:
            for class_name in matched_classes:
                spells_by_class[class_name].append(replace(converted))

    for class_name in spells_by_class:
        spells_by_class[class_name].sort(key=lambda entry: (entry.order, entry.ankama_id))

    default_entries = _select_named_defaults(all_spells, spell_lookup)
    extras = _extract_default_entries(class_data, spell_lookup)
    if extras:
        default_entries = _merge_spell_lists(default_entries, extras)
    if not default_entries:
        default_entries = extras
    spells_by_class = {"default": default_entries, **spells_by_class}
    _prune_missing_links(spells_by_class)
    return spells_by_class


def _sort_key(spell: Mapping[str, Any]) -> tuple:
    return (spell.get("order") or 0, spell.get("ankama_id") or 0)


def _build_breed_lookup(class_data: Mapping[str, Any]) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for class_name, payload in class_data.items():
        if class_name == "default" or not isinstance(payload, Mapping):
            continue
        breed_id = payload.get("breed_id")
        if breed_id is None:
            continue
        try:
            lookup[int(breed_id)] = class_name
        except (TypeError, ValueError):
            continue
    return lookup


def _classes_for_spell(spell: Mapping[str, Any], breed_lookup: Mapping[int, str]) -> Set[str]:
    classes: Set[str] = set()
    variant = spell.get("variant_group")
    if isinstance(variant, Mapping):
        breed_id = variant.get("breed_id")
        try:
            breed_key = int(breed_id)
        except (TypeError, ValueError):
            breed_key = None
        if breed_key is not None:
            class_name = breed_lookup.get(breed_key)
            if class_name:
                classes.add(class_name)

    breed_ids = spell.get("breed_ids") or []
    for breed_id in breed_ids:
        try:
            breed_key = int(breed_id)
        except (TypeError, ValueError):
            continue
        class_name = breed_lookup.get(breed_key)
        if class_name:
            classes.add(class_name)
    return classes


def _extract_default_entries(class_data: Mapping[str, Any], spell_lookup: Mapping[int, Mapping[str, Any]]) -> List[SpellEntry]:
    payload = class_data.get("default")
    if not payload:
        return []
    entries: List[SpellEntry] = []
    for spell in sorted(payload.get("spells", []), key=_sort_key):
        converted = convert_spell(spell, spell_lookup=spell_lookup)
        if converted:
            entries.append(converted)
    return entries


def _merge_spell_lists(
    primary: Optional[Sequence[SpellEntry]],
    extras: Sequence[SpellEntry],
) -> List[SpellEntry]:
    merged: List[SpellEntry] = list(primary or [])
    seen = {entry.name for entry in merged}
    for entry in extras:
        if entry.name in seen:
            continue
        merged.append(entry)
        seen.add(entry.name)
    return merged


def _prune_missing_links(spells_by_class: Mapping[str, List[SpellEntry]]) -> None:
    for entries in spells_by_class.values():
        names = {entry.name for entry in entries}
        for entry in entries:
            if entry.is_linked and entry.is_linked[1] not in names:
                entry.is_linked = None


def _select_named_defaults(
    all_spells: Sequence[Mapping[str, Any]],
    spell_lookup: Mapping[int, Mapping[str, Any]],
) -> List[SpellEntry]:
    lookup: Dict[str, List[Mapping[str, Any]]] = {}
    for spell in all_spells:
        name = (spell.get("name_en") or "").strip().lower()
        if not name:
            continue
        lookup.setdefault(name, []).append(spell)

    entries: List[SpellEntry] = []
    missing: List[str] = []
    for spec in DEFAULT_DAMAGE_SPELL_SPECS:
        spell = _choose_default_candidate(lookup.get(spec.name.lower(), []), spec)
        if spell:
            converted = convert_spell(spell, spell_lookup=spell_lookup)
            if converted:
                entries.append(converted)
                continue
        legacy = LEGACY_DEFAULT_SPELLS.get(spec.name)
        if legacy:
            entries.append(deepcopy(legacy))
            continue
        missing.append(spec.name)
    if missing:
        print(
            "Warning: the following default spells were not found in transformed_spells.json: "
            + ", ".join(missing),
            file=sys.stderr,
        )
    return entries


def _choose_default_candidate(
    candidates: Optional[Sequence[Mapping[str, Any]]], spec
) -> Optional[Mapping[str, Any]]:
    if not candidates:
        return None

    def score(spell: Mapping[str, Any]) -> tuple:
        variant_group = spell.get("variant_group")
        has_variant = bool(variant_group)
        variant_penalty = 0
        if spec.prefer_variant and not has_variant:
            variant_penalty = 1
        elif not spec.prefer_variant and has_variant:
            variant_penalty = 0
        breed_ids = spell.get("breed_ids") or []
        breed_penalty = 0
        if breed_ids:
            if not all(_is_player_breed(bid) for bid in breed_ids):
                breed_penalty = 1
        damage_penalty = 0 if spell.get("damage_templates") else 1
        return (variant_penalty, breed_penalty, damage_penalty, spell.get("ankama_id") or 0)

    return min(candidates, key=score)


def _is_player_breed(breed_id: Any) -> bool:
    try:
        value = int(breed_id)
    except (TypeError, ValueError):
        return False
    return 1 <= value <= 19


def _extract_stat_buff_rows(spell: Mapping[str, Any], level_count: int) -> List[Dict[str, Any]]:
    levels = spell.get("levels") or []
    if not levels or level_count <= 0:
        return []
    rows: Dict[str, Dict[str, Any]] = {}

    def _ensure_row(token: str, order: int) -> Dict[str, Any]:
        row = rows.get(token)
        if row is None:
            row = {
                "token": token,
                "normal": [None] * level_count,
                "critical": None,
                "order": order,
            }
            rows[token] = row
        return row

    for level_idx, level in enumerate(levels):
        for effect in level.get("effects", []):
            token = _stat_buff_token(effect)
            if not token:
                continue
            value = _format_buff_value(effect.get("dice"))
            if not value:
                continue
            row = _ensure_row(token, effect.get("order") or 0)
            row["normal"][level_idx] = value

    for level_idx, level in enumerate(levels):
        for effect in level.get("critical_effects", []):
            token = _stat_buff_token(effect)
            if not token:
                continue
            value = _format_buff_value(effect.get("dice"))
            if not value:
                continue
            row = _ensure_row(token, effect.get("order") or 0)
            if row["critical"] is None:
                row["critical"] = [None] * level_count
            row["critical"][level_idx] = value

    supplemental: List[Dict[str, Any]] = []
    for token, row in rows.items():
        filled_normal = _fill_missing_row(row["normal"])
        filled_crit = _fill_missing_row(row["critical"]) if row["critical"] else None
        supplemental.append(
            {
                "token": token,
                "element": repr(token),
                "normal": filled_normal,
                "critical": filled_crit,
                "order": row["order"],
            }
        )

    supplemental.sort(key=lambda item: (BUFF_SORT_ORDER.get(item["token"], 1000), item["order"], item["element"]))
    return supplemental


def _stat_buff_token(effect: Mapping[str, Any]) -> Optional[str]:
    metadata = effect.get("effect_metadata") or {}
    characteristic = metadata.get("characteristic")
    token = STAT_BUFF_CHARACTERISTICS.get(characteristic)
    if not token:
        return None

    description = (metadata.get("description") or {}).get("en", "").lower()
    if token in ALWAYS_BUFF_TOKENS:
        return token
    if "steals" in description:
        return token

    bonus_type = metadata.get("bonus_type")
    try:
        bonus_value = int(bonus_type)
    except (TypeError, ValueError):
        bonus_value = None
    if bonus_value and bonus_value > 0:
        return token
    return None


def _format_buff_value(dice: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not dice:
        return None
    min_val = dice.get("min")
    max_val = dice.get("max")
    if min_val is None:
        return None
    if max_val in (None, 0, min_val):
        return str(min_val)
    return f"{min_val}-{max_val}"


def _fill_missing_row(values: Optional[Sequence[Optional[str]]]) -> List[str]:
    if not values:
        return []
    filled: List[str] = []
    last_value: Optional[str] = None
    for value in values:
        if value is None:
            filled.append(last_value or "0")
        else:
            filled.append(value)
            last_value = value
    return filled


def _extract_stack_limit(spell: Mapping[str, Any]) -> Optional[int]:
    levels = spell.get("levels") or []
    stack_values: List[int] = []
    for level in levels:
        try:
            stack = int(level.get("max_stack"))
        except (TypeError, ValueError):
            continue
        if stack <= 1:
            continue
        stack_values.append(stack)
    if not stack_values:
        return None
    return max(stack_values)


def _derive_glyph_damage(
    spell: Mapping[str, Any],
    spell_lookup: Mapping[int, Mapping[str, Any]],
    level_count: int,
) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    if level_count <= 0:
        return None
    sources = _glyph_damage_sources(spell, spell_lookup)
    if not sources:
        return None

    normal_rows: List[Dict[str, Any]] = []
    critical_rows: List[Dict[str, Any]] = []
    for _, linked_spell in sources:
        damage = linked_spell.get("damage_templates") or {}
        normal_rows.extend(_copy_damage_rows(damage.get("normal"), level_count))
        critical_rows.extend(_copy_damage_rows(damage.get("critical"), level_count))

    if not normal_rows:
        return None
    return {"normal": normal_rows, "critical": critical_rows}


def _glyph_damage_sources(
    spell: Mapping[str, Any],
    spell_lookup: Mapping[int, Mapping[str, Any]],
) -> List[tuple]:
    candidates: List[tuple] = []
    for level in spell.get("levels") or []:
        for effect_block in (level.get("effects") or []), (level.get("critical_effects") or []):
            for effect in effect_block or []:
                if effect.get("effect_id") not in GLYPH_EFFECT_IDS:
                    continue
                dice = effect.get("dice") or {}
                for key in ("min", "max"):
                    linked_id = dice.get(key)
                    if not isinstance(linked_id, int):
                        continue
                    if linked_id not in spell_lookup:
                        continue
                    candidates.append((effect.get("order") or 0, linked_id))

    ordered: List[tuple] = []
    seen: Set[int] = set()
    for order, spell_id in sorted(candidates):
        if spell_id in seen:
            continue
        seen.add(spell_id)
        linked_spell = spell_lookup.get(spell_id)
        if not linked_spell:
            continue
        damage = linked_spell.get("damage_templates") or {}
        if not (damage.get("normal") or damage.get("critical")):
            continue
        ordered.append((order, linked_spell))
    return ordered


def _copy_damage_rows(rows: Optional[Sequence[Mapping[str, Any]]], level_count: int) -> List[Dict[str, Any]]:
    if not rows or level_count <= 0:
        return []
    copied: List[Dict[str, Any]] = []
    for row in rows:
        copied.append(
            {
                "element": row.get("element"),
                "steals": row.get("steals"),
                "ranges": _fit_ranges(list(row.get("ranges", [])), level_count),
            }
        )
    return copied


def _fit_ranges(source: List[Optional[str]], target_len: int) -> List[str]:
    if target_len <= 0:
        return []
    result: List[str] = []
    last_value: Optional[str] = None
    for idx in range(target_len):
        value = source[idx] if idx < len(source) else None
        if value:
            last_value = value
            result.append(value)
        else:
            result.append(last_value or "0-0")
    return result


def _extract_best_element_groups(rows: Sequence[Mapping[str, Any]]) -> Dict[Any, List[int]]:
    groups: Dict[Any, List[int]] = {}
    for idx, row in enumerate(rows):
        group = row.get("best_element_group")
        if group is None:
            continue
        groups.setdefault(group, []).append(idx)
    return {key: sorted(indexes) for key, indexes in groups.items()}


def _build_state_aggregates(
    rows: Sequence[Mapping[str, Any]],
    total_row_count: int,
) -> Optional[List[Tuple[str, List[int]]]]:
    """A state in the target mask decides whether a row lands, so rows under
    different states are alternatives: Schnaps hits sober or drunk, Trickery
    picks one element. Rows sharing a state land together."""
    groups: Dict[Any, List[int]] = {}
    for idx, row in enumerate(rows):
        state = row.get("state_group")
        if state is None:
            return None
        groups.setdefault(state, []).append(idx)
    if len(groups) < 2:
        return None
    aggregates = [("", sorted(indexes)) for _state, indexes in
                  sorted(groups.items(), key=lambda pair: min(pair[1]))]
    for idx in range(len(rows), total_row_count):
        aggregates.append(("", [idx]))
    return aggregates


def _build_best_element_aggregates(
    group_map: Mapping[Any, Sequence[int]],
    base_row_count: int,
    total_row_count: int,
) -> Optional[List[Tuple[str, List[int]]]]:
    if not group_map or total_row_count == 0:
        return None
    index_to_group: Dict[int, Any] = {}
    for group, indexes in group_map.items():
        for idx in indexes:
            index_to_group[idx] = group
    aggregates: List[Tuple[str, List[int]]] = []
    processed_groups: Set[Any] = set()
    used_indexes: Set[int] = set()
    for idx in range(base_row_count):
        group = index_to_group.get(idx)
        if group and group not in processed_groups:
            processed_groups.add(group)
            sorted_indexes = sorted(group_map[group])
            for offset, target_idx in enumerate(sorted_indexes):
                label = BEST_ELEMENT_LABEL if offset == 0 else ""
                aggregates.append((label, [target_idx]))
                used_indexes.add(target_idx)
        elif group:
            continue
        else:
            if idx not in used_indexes:
                aggregates.append(("", [idx]))
                used_indexes.add(idx)
    for idx in range(base_row_count, total_row_count):
        aggregates.append(("", [idx]))
    return aggregates


def _casting(spell: Mapping[str, Any], level_count: int) -> Optional[Dict[str, List[int]]]:
    """Cost and cast limits per level. None if the lists do not line up; a
    limit of 0 means no limit, so all-zero keys are dropped."""
    levels = spell.get("levels") or []
    if len(levels) != level_count:
        return None
    ap_costs = [level.get("ap_cost") for level in levels]
    if any(cost is None for cost in ap_costs):
        return None
    casting: Dict[str, List[int]] = {"ap": [int(cost) for cost in ap_costs]}
    for key, field in (("per_turn", "max_cast_per_turn"),
                       ("per_target", "max_cast_per_target"),
                       ("cooldown", "min_cast_interval")):
        values = [int(level.get(field) or 0) for level in levels]
        if any(values):
            casting[key] = values
    return casting


def convert_spell(
    spell: Mapping[str, Any],
    *,
    spell_lookup: Optional[Mapping[int, Mapping[str, Any]]] = None,
) -> Optional[SpellEntry]:
    damage = spell.get("damage_templates") or {}
    level_requirements = spell.get("level_requirements") or damage.get("levels")
    if not level_requirements:
        return None
    level_count = len(level_requirements)
    mp_stack_spec = _prepare_mp_stackable_damage(spell, damage, level_count)
    if not damage.get("stackable_damage"):
        _prepare_base_damage_stackable_damage(spell, damage, level_count)
    stack_limit = _extract_stack_limit(spell)

    normal_rows = damage.get("normal") or []
    crit_rows = damage.get("critical") or []
    if not normal_rows and spell_lookup:
        glyph_damage = _derive_glyph_damage(spell, spell_lookup, level_count)
        if glyph_damage:
            normal_rows = glyph_damage["normal"]
            crit_rows = glyph_damage["critical"]

    stack_row_block = len(normal_rows)
    stack_labels: Optional[List[str]] = None
    if damage.get("stackable_damage") and len(normal_rows) > 1:
        stack_labels, stack_cap = _expand_multi_row_stackable_damage(
            normal_rows,
            crit_rows,
            damage.get("stackable_damage") or {},
            level_count,
            stack_limit,
        )
        if stack_labels:
            damage["stackable_damage"] = None
            if stack_cap:
                stack_limit = max(stack_limit or 0, stack_cap)
        stack_row_block = stack_row_block or len(normal_rows)

    best_element_groups = _extract_best_element_groups(normal_rows)
    base_row_count = len(normal_rows)

    non_crit: List[List[str]] = [
        [str(value) for value in row.get("ranges", [])]
        for row in normal_rows
    ]
    crit: Optional[List[List[str]]] = (
        [[str(value) for value in row.get("ranges", [])] for row in crit_rows]
        if crit_rows
        else None
    )
    elements: List[str] = [
        ELEMENT_LITERAL.get(row.get("element"), repr(row.get("element")))
        for row in normal_rows
    ]
    steals_raw = [bool(row.get("steals")) for row in normal_rows]
    steals = steals_raw if any(steals_raw) else None
    heals_raw = [bool(row.get("heals")) for row in normal_rows]
    heals = heals_raw if any(heals_raw) else None

    buff_rows = _extract_stat_buff_rows(spell, len(level_requirements))
    if buff_rows:
        for row in buff_rows:
            non_crit.append(row["normal"])
            if row["critical"] is not None and len(row["critical"]) == len(level_requirements):
                if crit is None:
                    crit = []
                crit.append(row["critical"])
            elif crit is not None:
                crit.append(list(row["normal"]))
            elements.append(row["element"])
        if steals is not None:
            steals.extend([False] * len(buff_rows))
        if heals is not None:
            heals.extend([False] * len(buff_rows))
    stack_aggregates = _apply_stackable_damage(
        damage,
        level_requirements,
        non_crit,
        crit,
        elements,
        steals,
        heals,
    )
    if stack_aggregates and mp_stack_spec and mp_stack_spec.get("labels"):
        stack_aggregates = _apply_custom_stack_labels(stack_aggregates, mp_stack_spec["labels"])
    best_element_aggregates = _build_best_element_aggregates(
        best_element_groups,
        base_row_count,
        len(non_crit),
    )
    state_aggregates = _build_state_aggregates(normal_rows, len(non_crit))
    aggregates = best_element_aggregates or state_aggregates or stack_aggregates
    aggregates_from_best = aggregates is best_element_aggregates and aggregates is not None
    if not aggregates and stack_labels and stack_row_block:
        aggregates = _build_stack_row_aggregates(stack_row_block, base_row_count, stack_labels)
    if aggregates_from_best and aggregates and stack_labels and stack_row_block:
        aggregates = _prefix_stack_labels(aggregates, stack_row_block, stack_labels)
    if not non_crit:
        return None
    stacks = stack_limit
    variant_link = spell.get("variant_link")
    is_linked = _convert_variant_link(variant_link)

    name = pick_name(spell)
    order = spell.get("order") or 0
    ankama_id = spell.get("ankama_id") or 0
    entry = SpellEntry(
        name=name,
        level_requirements=[int(level) for level in level_requirements],
        non_crit_ranges=non_crit,
        crit_ranges=crit,
        elements=elements,
        steals=steals,
        heals=heals,
        is_linked=is_linked,
        stacks=stacks,
        aggregates=aggregates,
        order=order,
        ankama_id=ankama_id,
        casting=_casting(spell, len(level_requirements)),
    )

    _attach_special_buff_scaling(spell, entry, spell_lookup=spell_lookup)
    return entry


def _attach_special_buff_scaling(
    spell: Mapping[str, Any],
    entry: SpellEntry,
    *,
    spell_lookup: Optional[Mapping[int, Mapping[str, Any]]] = None,
) -> None:
    scaling = _bestial_pact_scaling(spell)
    if not scaling:
        scaling = _mp_buff_scaling(spell, spell_lookup)
    if not scaling:
        return
    entry.buff_scaling = scaling
    desired_stacks = scaling.get("selection_count", 0)
    if desired_stacks <= 0:
        desired_stacks = scaling.get("max_effective", 0)
    if desired_stacks and (entry.stacks is None or desired_stacks > entry.stacks):
        entry.stacks = desired_stacks


def _bestial_pact_scaling(spell: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if spell.get("ankama_id") != BESTIAL_PACT_ANKAMA_ID:
        return None
    levels = spell.get("levels") or []
    if not levels:
        return None

    final_vals = _collect_characteristic_values(levels, 107)
    final_heal_vals = _collect_characteristic_values(levels, 49)
    if len(final_vals) < 2 or len(final_heal_vals) < 2:
        return None

    base_final = max(final_vals)
    per_final = min(final_vals)
    base_heal = max(final_heal_vals)
    per_heal = min(final_heal_vals)
    if not (base_final > per_final >= 0 and base_heal > per_heal >= 0):
        return None

    return {
        "type": "summon_final",
        "stack_offset": 1,
        "selection_count": 11,
        "stats": {
            "final": {"base": base_final, "per_stack": per_final, "max_effective": 10},
            "finalheals": {"base": base_heal, "per_stack": per_heal, "max_effective": 10},
        },
    }


def _mp_buff_scaling(
    spell: Mapping[str, Any],
    spell_lookup: Optional[Mapping[int, Mapping[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not spell_lookup:
        return None
    levels = spell.get("levels") or []
    base_value = _max_characteristic_value(levels, 25)
    if base_value is None or base_value <= 0:
        return None
    triggered_id = _extract_triggered_spell_id(levels)
    if not isinstance(triggered_id, int) or triggered_id == spell.get("ankama_id"):
        return None
    triggered_spell = spell_lookup.get(triggered_id)
    if not triggered_spell:
        return None
    triggered_levels = triggered_spell.get("levels") or []
    if not _spell_has_mp_trigger(triggered_levels):
        return None
    per_stack = _max_characteristic_value(triggered_levels, 25)
    if per_stack is None or per_stack <= 0:
        return None
    max_effective = DEFAULT_MP_DAMAGE_STACK_CAP
    selection_count = max_effective + 1
    return {
        "type": "mp_buff",
        "stack_offset": 1,
        "selection_count": selection_count,
        "stats": {
            "pow": {
                "base": base_value,
                "per_stack": per_stack,
                "max_effective": max_effective,
            }
        },
    }
def _max_characteristic_value(levels: Sequence[Mapping[str, Any]], characteristic: int) -> Optional[int]:
    values = _collect_characteristic_values(levels, characteristic)
    if not values:
        return None
    return max(values)


def _extract_triggered_spell_id(levels: Sequence[Mapping[str, Any]]) -> Optional[int]:
    for level in levels:
        for effect in level.get("effects", []):
            if effect.get("effect_id") != MP_TRIGGER_EFFECT_ID:
                continue
            dice = effect.get("dice") or {}
            linked_id = dice.get("min")
            if isinstance(linked_id, int):
                return linked_id
    return None


def _spell_has_mp_trigger(levels: Sequence[Mapping[str, Any]]) -> bool:
    for level in levels:
        for effect in level.get("effects", []):
            if effect.get("effect_id") != MP_TRIGGER_EFFECT_ID:
                continue
            triggers = (effect.get("triggers") or "").upper()
            if MP_DAMAGE_TRIGGER_TOKEN in triggers:
                return True
    return False


def _collect_characteristic_values(levels: Sequence[Mapping[str, Any]], characteristic: int) -> List[int]:
    values: List[int] = []
    for level in levels:
        for effect in level.get("effects", []):
            metadata = effect.get("effect_metadata") or {}
            if metadata.get("characteristic") != characteristic:
                continue
            dice = effect.get("dice") or {}
            try:
                value = int(dice.get("min"))
            except (TypeError, ValueError):
                continue
            values.append(value)
    return values


def _convert_variant_link(variant_link: Optional[Mapping[str, Any]]) -> Optional[Sequence[Any]]:
    if not variant_link:
        return None
    linked = variant_link.get("linked_spells") or []
    if not linked:
        return None
    linked_name = pick_name(linked[0].get("names", {}))
    if not linked_name:
        return None
    position = variant_link.get("position", 1)
    return (position, linked_name)


def pick_name(source: Mapping[str, Any]) -> str:
    for key in ("name_en", "name_fr", "name_es", "name_pt", "name_de", "en", "fr", "es", "pt", "de", "name"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def render_block(spells_by_class: Mapping[str, List[SpellEntry]]) -> str:
    ordered_keys = ["default"] + [cls for cls in CHARACTER_CLASSES if cls in spells_by_class]
    lines: List[str] = [AUTO_START, AUTO_COMMENT, "DAMAGE_SPELLS = {"]
    for idx, key in enumerate(ordered_keys):
        entries = spells_by_class.get(key, [])
        trailing = "," if idx < len(ordered_keys) - 1 else ""
        lines.append(f"    {key!r}: [")
        for entry in entries:
            lines.extend(render_spell(entry))
        lines.append(f"    ]{trailing}")
    lines.append("}")
    lines.append(AUTO_END)
    lines.append("")
    return "\n".join(lines)


def render_spell(entry: SpellEntry) -> List[str]:
    indent = " " * 8
    literal_levels = pprint.pformat(entry.level_requirements)
    lines: List[str] = [f"{indent}Spell({entry.name!r}, {literal_levels}, Effects("]
    lines.append(_format_literal(entry.non_crit_ranges, indent + "    ") + ",")
    if entry.crit_ranges is None:
        lines.append(f"{indent}    None,")
    else:
        lines.append(_format_literal(entry.crit_ranges, indent + "    ") + ",")
    elements_literal = "[" + ", ".join(entry.elements) + "]"
    lines.append(f"{indent}    {elements_literal},")
    if entry.steals is not None:
        steals_literal = "[" + ", ".join("True" if val else "False" for val in entry.steals) + "]"
        lines.append(f"{indent}    steals={steals_literal},")
    if entry.heals is not None:
        heals_literal = "[" + ", ".join("True" if val else "False" for val in entry.heals) + "]"
        lines.append(f"{indent}    heals={heals_literal},")
    closing = f"{indent})"
    extra_args: List[str] = []
    if entry.aggregates:
        aggregates_literal = pprint.pformat(entry.aggregates)
        extra_args.append(f"aggregates={aggregates_literal}")
    if entry.stacks not in (None, 1):
        extra_args.append(f"stacks={entry.stacks}")
    if entry.is_linked:
        extra_args.append(f"is_linked=({entry.is_linked[0]}, {entry.is_linked[1]!r})")
    if entry.buff_scaling:
        scaling_literal = pprint.pformat(entry.buff_scaling)
        extra_args.append(f"buff_scaling={scaling_literal}")
    if entry.casting:
        extra_args.append(f"casting={entry.casting!r}")
    if entry.ankama_id:
        # Lets the audits match DofusDB by id instead of by (homonymous)
        # name; the hand-written defaults have no id and stay name-based.
        extra_args.append(f"spell_id={entry.ankama_id}")
    if extra_args:
        closing += ", " + ", ".join(extra_args)
    closing += ")"
    closing += ","
    lines.append(closing)
    return lines


def _format_literal(value: Any, indent: str) -> str:
    text = pprint.pformat(value, width=80, compact=False)
    return textwrap.indent(text, indent)


def update_constants_file(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.find(AUTO_START)
    end_marker_index = text.find(AUTO_END)
    if start == -1 or end_marker_index == -1:
        raise RuntimeError("Auto-generated markers not found in dofus_constants.py")
    end = end_marker_index + len(AUTO_END)
    # consume trailing newline(s)
    while end < len(text) and text[end] in "\r\n":
        end += 1
    existing_block = text[start:end]
    if existing_block == block:
        print("DAMAGE_SPELLS already up to date")
        return
    new_text = text[:start] + block + text[end:]
    path.write_text(new_text, encoding="utf-8")
    print(f"Updated DAMAGE_SPELLS in {path}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    class_data = load_json(args.class_json)
    all_spells = load_json(args.spells_json)
    spells_by_class = build_spell_map(class_data, all_spells)
    block = render_block(spells_by_class)
    update_constants_file(args.constants, block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
