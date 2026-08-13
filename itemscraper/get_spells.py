#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

try:
    from .default_damage_spells import DEFAULT_DAMAGE_SPELL_NAMES
except ImportError:
    from default_damage_spells import DEFAULT_DAMAGE_SPELL_NAMES

LANGUAGES: Sequence[str] = ("en", "fr", "es", "pt", "de")
RAW_ROOT = Path("itemscraper/raw")
DEFAULT_OUTPUT = Path("itemscraper/transformed_spells.json")
DEFAULT_NAMES_OUTPUT = Path("itemscraper/transformed_spell_names.json")
DATA_FILES = (
    "spells.json",
    "spell_levels.json",
    "spell_types.json",
    "spell_variants.json",
    "effects.json",
)

ELEMENT_ID_TO_TOKEN = {
    0: "NEUTRAL",
    1: "EARTH",
    2: "FIRE",
    3: "WATER",
    4: "AIR",
}
BEST_ELEMENT_DESCRIPTION_TOKENS = ("best-element", "best element")
BEST_ELEMENT_TOKENS = ("EARTH", "FIRE", "WATER", "AIR")

# "A,*E3531" means the row lands only while the caster carries state 3531, "*e3531"
# only while it does not. The star is optional (Devouring Arrow writes "E573"). A
# state token is a letter followed by digits, which is what tells it from a target
# letter.
STATE_IN_TARGET_MASK = re.compile(r"\b\*?[eE]\d+\b")

ZONE_SIGNATURE_KEYS = ("shape", "param1", "param2")

STACK_CONTROLLER_EFFECT_IDS = {792, 1160}
SUMMON_STACK_PATTERN = re.compile(r"each of the caster's .*summon", re.IGNORECASE)
SUMMON_STACK_CAP = 10
STACKABLE_TIMES_PATTERN = re.compile(r"stackable\s*(?:up to\s*)?(\d+)", re.IGNORECASE)


def _zone_signature(zone: Optional[Mapping[str, Any]]) -> str:
    if not zone:
        return ""
    return ",".join(str(zone.get(key)) for key in ZONE_SIGNATURE_KEYS)


def _unwrap_array(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, dict) and "Array" in value:
        array_value = value.get("Array")
        return list(array_value or [])
    if isinstance(value, list):
        return value
    return [value]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_datacenter_table(path: Path) -> Dict[int, Dict[str, Any]]:
    data = _load_json(path)
    refs = {ref["rid"]: ref["data"] for ref in data.get("references", {}).get("RefIds", [])}
    keys = data.get("objectsById", {}).get("m_keys", {}).get("Array", [])
    values = data.get("objectsById", {}).get("m_values", {}).get("Array", [])
    table: Dict[int, Dict[str, Any]] = {}
    if keys and values:
        for key, value in zip(keys, values):
            record = refs.get(value.get("rid")) if isinstance(value, dict) else None
            if record is None:
                continue
            table[int(key)] = record
        return table

    # Some tables omit objectsById; fall back to the ids embedded in the records.
    for record in refs.values():
        record_id = record.get("id")
        if record_id is None:
            continue
        table[int(record_id)] = record
    return table


def _load_translations(root: Path, languages: Sequence[str]) -> Dict[str, Dict[str, str]]:
    translations: Dict[str, Dict[str, str]] = {}
    for lang in languages:
        path = root / f"{lang}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing localisation file: {path}")
        data = _load_json(path)
        entries = data.get("entries")
        if not isinstance(entries, Mapping):
            raise ValueError(f"Unexpected language payload format in {path}")
        translations[lang] = {str(key): value for key, value in entries.items()}
    return translations


def _convert_zone(zone: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if not zone:
        return None
    converted = {k: v for k, v in zone.items() if k not in {"cellIds"}}
    cell_ids = zone.get("cellIds")
    if cell_ids is not None:
        converted["cell_ids"] = _unwrap_array(cell_ids)
    return converted


def _convert_preview_zones(node: Any) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for preview in _unwrap_array(node):
        zones.append(
            {
                "id": preview.get("id"),
                "hidden": bool(preview.get("isPreviewZoneHidden")),
                "caster_mask": preview.get("casterMask"),
                "activation_mask": preview.get("activationMask"),
                "display_zone": _convert_zone(preview.get("displayZoneDescr")),
                "activation_zone": _convert_zone(preview.get("activationZoneDescr")),
            }
        )
    return zones


def _convert_script_usages(node: Any) -> List[Dict[str, Any]]:
    usages: List[Dict[str, Any]] = []
    for usage in _unwrap_array(node):
        usages.append(
            {
                "id": usage.get("id"),
                "order": usage.get("order"),
                "script_id": usage.get("scriptId"),
                "criterion": usage.get("criterion"),
                "caster_mask": usage.get("casterMask"),
                "target_mask": usage.get("targetMask"),
                "target_zone": usage.get("targetZone"),
                "activation_mask": usage.get("activationMask"),
                "activation_zone": usage.get("activationZone"),
                "random": usage.get("random"),
                "random_group": usage.get("randomGroup"),
                "sequence_group": usage.get("sequenceGroup"),
                "spell_level_ids": _unwrap_array(usage.get("spellLevels")),
                "target_treated_as_caster": bool(usage.get("isTargetTreatedAsCaster")),
                "targets_affected_concurrently": bool(usage.get("areTargetsAffectedConcurrently")),
            }
        )
    return usages


@dataclass
class VariantLink:
    variant_id: int
    breed_id: int
    spell_ids: List[int]


class SpellTransformer:
    def __init__(self, dataset_dir: Path, output_path: Path, languages: Sequence[str] = LANGUAGES) -> None:
        self.dataset_dir = dataset_dir
        self.output_path = output_path
        self.languages = tuple(languages)
        self.translations = _load_translations(dataset_dir, self.languages)

        missing_files = [name for name in DATA_FILES if not (dataset_dir / name).exists()]
        if missing_files:
            raise FileNotFoundError(f"Missing required datacenter files in {dataset_dir}: {', '.join(missing_files)}")
        self.spells = _load_datacenter_table(dataset_dir / "spells.json")
        self.spell_levels = _load_datacenter_table(dataset_dir / "spell_levels.json")
        self.spell_types = _load_datacenter_table(dataset_dir / "spell_types.json")
        self.effects = _load_datacenter_table(dataset_dir / "effects.json")
        self.variants = _load_datacenter_table(dataset_dir / "spell_variants.json")
        self.variant_lookup = self._build_variant_lookup()
        self.missing_levels: Dict[int, List[int]] = {}
        self.missing_effects: Dict[int, List[int]] = {}
        self._breeds: Optional[Dict[int, Dict[str, Any]]] = None
        self._breed_names: Optional[Dict[int, Dict[str, Optional[str]]]] = None
        self.spell_entries_by_id: Dict[int, Dict[str, Any]] = {}

    def _build_variant_lookup(self) -> Dict[int, VariantLink]:
        lookup: Dict[int, VariantLink] = {}
        for variant in self.variants.values():
            spell_ids = [int(sid) for sid in _unwrap_array(variant.get("spellIds"))]
            link = VariantLink(
                variant_id=int(variant.get("id", 0)),
                breed_id=int(variant.get("breedId", 0)),
                spell_ids=spell_ids,
            )
            for spell_id in spell_ids:
                lookup[spell_id] = link
        return lookup

    def _localized_map(self, text_id: Any) -> Optional[Dict[str, Optional[str]]]:
        if text_id in (None, "", 0, "0"):
            return None
        text_id_str = str(text_id)
        values: Dict[str, Optional[str]] = {}
        has_value = False
        for lang in self.languages:
            lang_map = self.translations.get(lang, {})
            value = lang_map.get(text_id_str)
            values[lang] = value
            if value:
                has_value = True
        return values if has_value else None

    def _assign_localized_fields(self, target: MutableMapping[str, Any], prefix: str, text_id: Any) -> None:
        localized = self._localized_map(text_id)
        if not localized:
            return
        for lang in self.languages:
            target[f"{prefix}_{lang}"] = localized.get(lang)

    def _convert_effect_metadata(self, effect_id: int) -> Optional[Dict[str, Any]]:
        meta = self.effects.get(effect_id)
        if not meta:
            return None
        block: Dict[str, Any] = {
            "icon_id": meta.get("iconId"),
            "category": meta.get("category"),
            "characteristic": meta.get("characteristic"),
            "bonus_type": meta.get("bonusType"),
            "element_id": meta.get("elementId"),
            "is_percent": meta.get("isInPercent"),
            "use_dice": meta.get("useDice"),
            "show_in_tooltip": meta.get("showInTooltip"),
            "effect_priority": meta.get("effectPriority"),
            "effect_power_rate": meta.get("effectPowerRate"),
        }
        description = self._localized_map(meta.get("descriptionId"))
        if description:
            block["description"] = description
        theoretical = self._localized_map(meta.get("theoreticalDescriptionId"))
        if theoretical:
            block["theoretical_description"] = theoretical
        action_filters = _unwrap_array(meta.get("actionFiltersId"))
        if action_filters:
            block["action_filters"] = action_filters
        return {k: v for k, v in block.items() if v not in (None, [])}

    def _convert_effect(self, effect: Mapping[str, Any]) -> Dict[str, Any]:
        effect_id = int(effect.get("effectId", 0))
        converted: Dict[str, Any] = {
            "effect_uid": effect.get("effectUid"),
            "effect_id": effect_id,
            "base_effect_id": effect.get("baseEffectId"),
            "order": effect.get("order"),
            "group": effect.get("group"),
            "spell_id": effect.get("spellId"),
            "target_id": effect.get("targetId"),
            "target_mask": effect.get("targetMask"),
            "duration": effect.get("duration"),
            "random": effect.get("random"),
            "modificator": effect.get("modificator"),
            "dispellable": effect.get("dispellable"),
            "delay": effect.get("delay"),
            "triggers": effect.get("triggers"),
            "effect_element": effect.get("effectElement"),
            "effect_trigger_duration": effect.get("effectTriggerDuration"),
            "value": effect.get("value"),
            "dice": {
                "min": effect.get("diceNum"),
                "max": effect.get("diceSide"),
            },
            "display_zero": effect.get("displayZero"),
            "zone": _convert_zone(effect.get("zoneDescr")),
            "flags": effect.get("m_flags"),
        }
        metadata = self._convert_effect_metadata(effect_id)
        if metadata:
            converted["effect_metadata"] = metadata
        else:
            self.missing_effects.setdefault(effect_id, []).append(effect.get("spellId"))
        return converted

    def _convert_effects(self, node: Any) -> List[Dict[str, Any]]:
        return [self._convert_effect(effect) for effect in _unwrap_array(node)]

    def _convert_spell_level(self, level: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "level_id": level.get("id"),
            "spell_id": level.get("spellId"),
            "grade": level.get("grade"),
            "spell_breed": level.get("spellBreed"),
            "ap_cost": level.get("apCost"),
            "range": {
                "min": level.get("minRange"),
                "max": level.get("range"),
            },
            "critical_hit_probability": level.get("criticalHitProbability"),
            "max_stack": level.get("maxStack"),
            "max_cast_per_turn": level.get("maxCastPerTurn"),
            "max_cast_per_target": level.get("maxCastPerTarget"),
            "min_cast_interval": level.get("minCastInterval"),
            "initial_cooldown": level.get("initialCooldown"),
            "global_cooldown": level.get("globalCooldown"),
            "min_player_level": level.get("minPlayerLevel"),
            "states_criterion": level.get("statesCriterion"),
            "effects": self._convert_effects(level.get("effects")),
            "critical_effects": self._convert_effects(level.get("criticalEffect")),
            "preview_zones": _convert_preview_zones(level.get("previewZones")),
            "flags": level.get("m_flags"),
        }

    def _spell_levels(self, spell: Mapping[str, Any]) -> List[Dict[str, Any]]:
        converted_levels: List[Dict[str, Any]] = []
        for level_id in _unwrap_array(spell.get("spellLevels")):
            level_data = self.spell_levels.get(int(level_id))
            if not level_data:
                self.missing_levels.setdefault(int(level_id), []).append(spell.get("id"))
                continue
            converted_levels.append(self._convert_spell_level(level_data))
        converted_levels.sort(key=lambda lvl: (lvl.get("grade") or 0, lvl.get("level_id") or 0))
        return converted_levels

    def _type_names(self, type_id: Any) -> Dict[str, Any]:
        names: Dict[str, Any] = {"type_id": type_id}
        type_entry = self.spell_types.get(int(type_id)) if type_id is not None else None
        if type_entry:
            self._assign_localized_fields(names, "type_name", type_entry.get("longNameId"))
            self._assign_localized_fields(names, "type_short_name", type_entry.get("shortNameId"))
        return names

    def _variant_block(self, spell_id: int) -> Optional[Dict[str, Any]]:
        variant = self.variant_lookup.get(spell_id)
        if not variant:
            return None
        return {
            "variant_id": variant.variant_id,
            "breed_id": variant.breed_id,
            "spell_ids": variant.spell_ids,
        }

    @staticmethod
    def _format_range(dice: Optional[Mapping[str, Any]]) -> Optional[str]:
        if not dice:
            return None
        min_val = dice.get("min")
        max_val = dice.get("max")
        if min_val is None or max_val is None:
            return None
        if min_val == max_val:
            return str(min_val)
        # A zero maximum is no maximum: Ankama's own template
        # ("#1{{~1~2 to }}#2 Fire damage") drops the "to #2" part.
        if max_val == 0:
            return str(min_val)
        return f"{min_val}-{max_val}"

    def _collect_damage_rows(self, levels: Sequence[Mapping[str, Any]], critical: bool) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        key_to_idx: Dict[tuple, int] = {}
        level_count = len(levels)
        best_element_group_counter = 0
        for level_idx, level in enumerate(levels):
            effects = level["critical_effects" if critical else "effects"]
            for effect in effects:
                metadata = effect.get("effect_metadata")
                if not metadata or metadata.get("category") != 2:
                    continue
                dice = self._format_range(effect.get("dice"))
                if not dice:
                    continue
                desc_en = (metadata.get("description") or {}).get("en", "")
                desc_lower = desc_en.lower()
                steals = "steal" in desc_lower
                heals_flag = "heal" in desc_lower
                element_token = ELEMENT_ID_TO_TOKEN.get(effect.get("effect_element"))

                # A state in the target mask gates the row: Schnaps deals its Air
                # damage sober or drunk, never both. Rows sharing a state land
                # together.
                state = STATE_IN_TARGET_MASK.findall(
                    str(effect.get("target_mask") or ""))
                state_group = ",".join(sorted(state)) if state else None

                # Mask plus zone identifies the case. Ankama writes one row per
                # case with the same damage in each (Bramble, Epidemic, Bear Cry);
                # a cast lands one of them.
                situation = "%s|%s" % (
                    effect.get("target_mask") or "",
                    _zone_signature(effect.get("zone")),
                )

                def _register_row(token: str, *, best_group: Optional[str] = None) -> None:
                    key = (effect.get("order"), token, steals, heals_flag)
                    idx = key_to_idx.get(key)
                    if idx is None:
                        idx = len(rows)
                        key_to_idx[key] = idx
                        row = {
                            "element": token,
                            "steals": steals,
                            "heals": heals_flag,
                            "ranges": [None] * level_count,
                        }
                        if best_group is not None:
                            row["best_element_group"] = best_group
                        if state_group is not None:
                            row["state_group"] = state_group
                        row["situation"] = situation
                        rows.append(row)
                    else:
                        row = rows[idx]
                        if best_group is not None and "best_element_group" not in row:
                            row["best_element_group"] = best_group
                        if state_group is not None and "state_group" not in row:
                            row["state_group"] = state_group
                    rows[idx]["ranges"][level_idx] = dice

                is_best_element = False
                if not element_token and desc_lower:
                    if any(token in desc_lower for token in BEST_ELEMENT_DESCRIPTION_TOKENS):
                        is_best_element = True
                if is_best_element:
                    group_id = f"best-element-{best_element_group_counter}"
                    best_element_group_counter += 1
                    for token in BEST_ELEMENT_TOKENS:
                        _register_row(token, best_group=group_id)
                    continue
                if not element_token:
                    continue
                _register_row(element_token)

        for row in rows:
            last_value: Optional[str] = None
            for i, value in enumerate(row["ranges"]):
                if value is None:
                    row["ranges"][i] = last_value or "0-0"
                else:
                    last_value = value
        return rows

    def _infer_stack_cap(self, spell_entry: Mapping[str, Any]) -> Optional[int]:
        descriptions: List[str] = []
        for lang in self.languages:
            text = spell_entry.get(f"description_{lang}")
            if text:
                descriptions.append(str(text).lower())
        description_en = (spell_entry.get("description_en") or "").lower()
        if description_en:
            descriptions.insert(0, description_en)
        for text in descriptions:
            match = STACKABLE_TIMES_PATTERN.search(text)
            if match:
                try:
                    cap = int(match.group(1))
                except ValueError:
                    cap = None
                if cap and cap > 0:
                    return cap
        for text in descriptions:
            if text and SUMMON_STACK_PATTERN.search(text):
                return SUMMON_STACK_CAP
        return None

    def _build_damage_templates(
        self,
        levels: Sequence[Mapping[str, Any]],
        stack_cap_override: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        normal = self._collect_damage_rows(levels, critical=False)
        critical = self._collect_damage_rows(levels, critical=True)
        if not normal and not critical:
            return None
        template: Dict[str, Any] = {
            "levels": [lvl.get("min_player_level") for lvl in levels],
            "normal": normal,
            "critical": critical,
        }
        stackable = self._extract_stackable_damage(
            levels,
            stack_cap_override=stack_cap_override,
        )
        if stackable:
            template["stackable_damage"] = stackable
        return template

    def _extract_stackable_damage(
        self,
        levels: Sequence[Mapping[str, Any]],
        *,
        stack_cap_override: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        has_controller = False
        per_stack: List[Optional[int]] = []
        max_stacks: List[Optional[int]] = []
        for level in levels:
            effects = level.get("effects") or []
            if not has_controller and any(effect.get("effect_id") in STACK_CONTROLLER_EFFECT_IDS for effect in effects):
                has_controller = True
            boost = next((effect for effect in effects if effect.get("effect_id") == 293), None)
            if boost:
                try:
                    per_stack.append(int(boost.get("value") or 0))
                except (TypeError, ValueError):
                    per_stack.append(0)
                zone = boost.get("zone") or {}
                max_apply = zone.get("maxDamageDecreaseApplyCount")
                if stack_cap_override is not None:
                    max_stacks.append(stack_cap_override)
                elif max_apply is not None:
                    try:
                        max_stacks.append(int(max_apply))
                    except (TypeError, ValueError):
                        max_stacks.append(None)
                else:
                    max_stacks.append(None)
            else:
                per_stack.append(None)
                max_stacks.append(None)
        if not (has_controller or stack_cap_override is not None) or not any(value for value in per_stack if value):
            return None
        return {
            "per_stack": per_stack,
            "max_stacks": max_stacks,
        }

    def _attach_variant_links(self, entries_by_id: Mapping[int, Dict[str, Any]]) -> None:
        for spell_id, entry in entries_by_id.items():
            variant = self.variant_lookup.get(spell_id)
            if not variant or len(variant.spell_ids) <= 1:
                continue
            try:
                position = variant.spell_ids.index(spell_id) + 1
            except ValueError:
                continue
            linked = []
            for sid in variant.spell_ids:
                if sid == spell_id:
                    continue
                target_entry = entries_by_id.get(sid)
                if target_entry:
                    names = {lang: target_entry.get(f"name_{lang}") for lang in self.languages}
                else:
                    names = self._localized_map(self.spells.get(sid, {}).get("nameId")) or {}
                linked.append({"ankama_id": sid, "names": names})

            entry["variant_link"] = {
                "variant_id": variant.variant_id,
                "position": position,
                "count": len(variant.spell_ids),
                "linked_spells": linked,
            }

    def build(self) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        entries_by_id: Dict[int, Dict[str, Any]] = {}
        for spell_id in sorted(self.spells.keys()):
            spell = self.spells[spell_id]
            entry: Dict[str, Any] = {
                "ankama_id": spell.get("id"),
                "order": spell.get("order"),
                "admin_name": spell.get("adminName"),
                "icon_id": spell.get("iconId"),
                "script_id": spell.get("scriptId"),
                "script_id_critical": spell.get("scriptIdCritical"),
                "script_params": spell.get("scriptParams"),
                "script_params_critical": spell.get("scriptParamsCritical"),
                "flags": spell.get("m_flags"),
                "base_preview_zone": _convert_zone(spell.get("basePreviewZoneDescr")),
                "bound_scripts": _convert_script_usages(spell.get("boundScriptUsageData")),
                "critical_bound_scripts": _convert_script_usages(spell.get("criticalHitBoundScriptUsageData")),
            }

            self._assign_localized_fields(entry, "name", spell.get("nameId"))
            self._assign_localized_fields(entry, "description", spell.get("descriptionId"))

            type_id = spell.get("typeId")
            if type_id is not None:
                entry.update(self._type_names(int(type_id)))

            variant_block = self._variant_block(int(spell_id))
            if variant_block:
                entry["variant_group"] = variant_block

            levels = self._spell_levels(spell)
            entry["levels"] = levels
            entry["level_count"] = len(levels)
            entry["max_grade"] = max((lvl.get("grade") or 0 for lvl in levels), default=0)
            breed_ids = {lvl.get("spell_breed") for lvl in levels if lvl.get("spell_breed")}
            # Recent classes (Forgelance = breed 20) carry the player breed only in
            # spell_variants (breedId); their levels' spell_breed is an unrelated id.
            variant_link = self.variant_lookup.get(int(spell_id))
            if variant_link and variant_link.breed_id:
                breed_ids.add(variant_link.breed_id)
            breed_ids = sorted(breed_ids)
            if breed_ids:
                entry["breed_ids"] = breed_ids
            entry["level_requirements"] = [lvl.get("min_player_level") for lvl in levels]
            stack_cap_hint = self._infer_stack_cap(entry)
            damage_templates = self._build_damage_templates(levels, stack_cap_override=stack_cap_hint)
            if damage_templates:
                entry["damage_templates"] = damage_templates

            payload.append(entry)
            entries_by_id[int(spell_id)] = entry

        self.spell_entries_by_id = entries_by_id
        self._attach_variant_links(entries_by_id)
        return payload

    def write(self, payload: List[Dict[str, Any]]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {len(payload)} spells -> {self.output_path}")
        if self.missing_levels:
            missing = len(self.missing_levels)
            print(f"Warning: {missing} spell level IDs were referenced but missing from spell_levels.json", file=sys.stderr)
        if self.missing_effects:
            missing = len(self.missing_effects)
            print(f"Warning: metadata missing for {missing} effect IDs", file=sys.stderr)

    def write_spell_names(self, payload: Sequence[Mapping[str, Any]], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        names: Dict[str, Dict[str, str]] = {}
        for spell in payload:
            name_en = (spell.get("name_en") or "").strip()
            if not name_en:
                continue

            localized: Dict[str, str] = {}
            for lang in self.languages:
                value = spell.get(f"name_{lang}")
                if isinstance(value, str) and value.strip():
                    localized[lang] = value.strip()

            if localized:
                names.setdefault(name_en, localized)

        # Dofus 3 and the beta share this file with different spell lists.
        merged: Dict[str, Dict[str, str]] = {}
        if output_path.exists():
            try:
                existing = json.loads(output_path.read_text(encoding="utf-8"))
            except ValueError:
                existing = None
            if isinstance(existing, dict):
                merged.update(existing)
        merged.update(names)

        output_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        print(f"Wrote {len(merged)} spell names -> {output_path}")

    def _ensure_breeds(self) -> None:
        if self._breeds is not None:
            return
        breed_path = self.dataset_dir / "breeds.json"
        if not breed_path.exists():
            raise FileNotFoundError(
                f"Class output requested but breeds.json is missing under {self.dataset_dir}"
            )
        self._breeds = _load_datacenter_table(breed_path)
        self._breed_names = {}
        for breed_id, record in self._breeds.items():
            localized = self._localized_map(record.get("shortNameId")) or {}
            self._breed_names[breed_id] = localized

    def _class_key(self, breed_id: int) -> str:
        assert self._breed_names is not None
        name = self._breed_names.get(breed_id, {}).get("en")
        return name or f"breed_{breed_id}"

    def _spell_for_class(self, entry: Mapping[str, Any]) -> Dict[str, Any]:
        keep_keys = {
            "ankama_id",
            "order",
            "icon_id",
            "script_id",
            "script_id_critical",
            "script_params",
            "script_params_critical",
            "base_preview_zone",
            "bound_scripts",
            "critical_bound_scripts",
            "type_id",
            "level_count",
            "max_grade",
            "variant_group",
            "levels",
            "flags",
            "breed_ids",
            "level_requirements",
            "damage_templates",
            "variant_link",
        }
        spell: Dict[str, Any] = {}
        for key in keep_keys:
            if key in entry:
                spell[key] = copy.deepcopy(entry[key])

        for lang in self.languages:
            for prefix in ("name", "description", "type_name", "type_short_name"):
                key = f"{prefix}_{lang}"
                if key in entry:
                    spell[key] = entry[key]
        return spell

    def build_class_map(self, payload: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        self._ensure_breeds()
        assert self._breed_names is not None
        grouped: Dict[str, Dict[str, Any]] = {}
        for entry in payload:
            breed_ids = [bid for bid in entry.get("breed_ids", []) if bid in self._breed_names]
            if not breed_ids:
                continue
            class_spell = self._spell_for_class(entry)
            for breed_id in breed_ids:
                key = self._class_key(breed_id)
                container = grouped.setdefault(
                    key,
                    {
                        "breed_id": breed_id,
                        "names": self._breed_names[breed_id],
                        "spells": [],
                    },
                )
                container["spells"].append(copy.deepcopy(class_spell))

        for class_data in grouped.values():
            class_data["spells"].sort(
                key=lambda spell: (spell.get("order") or 0, spell.get("ankama_id") or 0)
            )

        default_spells = self._build_default_spells(payload)
        if default_spells:
            grouped["default"] = {
                "breed_id": None,
                "names": {"en": "default"},
                "spells": default_spells,
            }
        return grouped

    def _build_default_spells(self, payload: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        lookup: Dict[str, Mapping[str, Any]] = {}
        for entry in payload:
            name = (entry.get("name_en") or "").strip()
            if not name:
                continue
            lookup.setdefault(name.lower(), entry)

        spells: List[Dict[str, Any]] = []
        missing: List[str] = []
        for name in DEFAULT_DAMAGE_SPELL_NAMES:
            entry = lookup.get(name.lower())
            if not entry:
                missing.append(name)
                continue
            spells.append(self._spell_for_class(entry))

        if missing:
            print(
                "Warning: the following default spells were not found in the payload: "
                + ", ".join(missing),
                file=sys.stderr,
            )
        return spells

    def write_class_map(self, class_map: Mapping[str, Any], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(class_map, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {sum(len(data['spells']) for data in class_map.values())} class spells -> {output_path}")


def _detect_latest_tag(raw_root: Path) -> Path:
    if not raw_root.exists():
        raise FileNotFoundError(f"Raw directory not found: {raw_root}")
    dirs = [path for path in raw_root.iterdir() if path.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"No datacenter dumps found under {raw_root}")
    return sorted(dirs)[-1]


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT, help="Root folder that contains datacenter dumps")
    parser.add_argument("--tag", help="Specific datacenter tag (sub-folder inside --raw-root). Defaults to the latest one.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Destination JSON file")
    parser.add_argument("--names-output", type=Path, default=DEFAULT_NAMES_OUTPUT, help="Destination compact JSON file for localized spell names")
    parser.add_argument("--languages", nargs="+", default=list(LANGUAGES), help="Language files to merge (default: en fr es pt de)")
    parser.add_argument(
        "--class-output",
        type=Path,
        help="Optional path to write class-only spells grouped similarly to DAMAGE_SPELLS",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    dataset_dir = (args.raw_root / args.tag) if args.tag else _detect_latest_tag(args.raw_root)
    try:
        transformer = SpellTransformer(dataset_dir=dataset_dir, output_path=args.output, languages=args.languages)
        payload = transformer.build()
        transformer.write(payload)
        transformer.write_spell_names(payload, args.names_output)
        if args.class_output:
            class_map = transformer.build_class_map(payload)
            transformer.write_class_map(class_map, args.class_output)
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
