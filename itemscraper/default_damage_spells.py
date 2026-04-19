from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DefaultSpellSpec:
    name: str
    prefer_variant: bool = False


DEFAULT_DAMAGE_SPELL_SPECS: Sequence[DefaultSpellSpec] = (
    DefaultSpellSpec("Burnt Pie", prefer_variant=True),
    DefaultSpellSpec("Leek Pie", prefer_variant=True),
    DefaultSpellSpec("Grunob's Lightning Strike"),
    DefaultSpellSpec("Grunob's Lesson"),
    DefaultSpellSpec("Kannibubble"),
    DefaultSpellSpec("Kanniboil"),
    DefaultSpellSpec("Mantiscroc"),
    DefaultSpellSpec("Dart Mocles"),
    DefaultSpellSpec("Moon Hammer", prefer_variant=True),
    DefaultSpellSpec("Darkli Moon Hammer"),
    DefaultSpellSpec("Perfidious Boomerang"),
    DefaultSpellSpec("Diamondine Boomerang"),
    DefaultSpellSpec("Weapon Skill"),
    DefaultSpellSpec("Ebony Dofus"),
    DefaultSpellSpec("Crocobur's Appetite"),
    DefaultSpellSpec("Pestilential Fog"),
    DefaultSpellSpec("Scurvion Toxicity"),
)


DEFAULT_DAMAGE_SPELL_NAMES: Sequence[str] = tuple(spec.name for spec in DEFAULT_DAMAGE_SPELL_SPECS)
