#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Dict, Iterable, List, Sequence, Set, Tuple

try:
    from fashionista_version import FASHIONISTA_VERSION
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from fashionista_version import FASHIONISTA_VERSION

try:
    from itemscraper.version_tags import version_key
except ModuleNotFoundError:
    from version_tags import version_key


DEFAULT_RAW_ROOT = Path("itemscraper/raw")
DEFAULT_OUTPUT = Path("itemscraper/spell_images")
DEFAULT_METADATA = Path("itemscraper/transformed_spells.json")
DEFAULT_STATIC_SPELLS = Path("fashionsite/chardata/static/chardata/spells")
DEFAULT_STATICFILES_SPELLS = Path("fashionsite/staticfiles/chardata/spells")
DEFAULT_CONSTANTS_PATH = Path("fashionistapulp/fashionistapulp/dofus_constants.py")
AVAILABLE_SIZES = ("48", "96")
AVAILABLE_SCOPES = ("damage", "class", "all")
DEFAULT_SCOPE = "damage"
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class SpellIconRecord:
    ankama_id: int | None
    icon_id: int
    english_name: str
    filename_stem: str


@dataclass
class CopyStats:
    processed: int = 0
    written: int = 0
    skipped_existing: int = 0
    missing_source: int = 0
    pruned: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW_ROOT,
        help="Directory containing Ankama raw dumps (default: itemscraper/raw)",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help=(
            "Specific raw subdirectory to use (e.g. "
            f"{FASHIONISTA_VERSION}). Defaults to the latest available."
        ),
    )
    parser.add_argument(
        "--size",
        choices=AVAILABLE_SIZES,
        default="96",
        help="Icon size archive to extract (48 or 96).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination root for extracted images (default: itemscraper/spell_images)",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA,
        help="Path to transformed_spells.json (used for English names).",
    )
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=DEFAULT_STATIC_SPELLS,
        help="Static directory that should receive the renamed spell icons.",
    )
    parser.add_argument(
        "--extra-static-dirs",
        type=Path,
        nargs="*",
        default=[DEFAULT_STATICFILES_SPELLS],
        help=(
            "Additional directories that should mirror the spell icons (default: "
            "fashionsite/staticfiles/chardata/spells). Pass --extra-static-dirs with"
            " no values to disable the default mirror."
        ),
    )
    parser.add_argument(
        "--constants",
        type=Path,
        default=DEFAULT_CONSTANTS_PATH,
        help="Path to fashionistapulp's dofus_constants.py (source of DAMAGE_SPELLS).",
    )
    parser.add_argument(
        "--scope",
        choices=AVAILABLE_SCOPES,
        default=DEFAULT_SCOPE,
        help="Which spells to copy: 'damage' (the DAMAGE_SPELLS), 'class' (every class spell the page lists) or 'all' (every spell in the game, monsters included).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files that already exist (default: skip existing files).",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete *.png files in every destination directory that were not produced during this run.",
    )
    return parser.parse_args()


def resolve_raw_dir(raw_root: Path, version: str | None) -> Path:
    if version:
        candidate = raw_root / version
        if not candidate.is_dir():
            raise FileNotFoundError(f"Raw directory '{candidate}' does not exist")
        return candidate

    candidates = [p for p in raw_root.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No raw directories found under {raw_root}")
    return max(candidates, key=lambda p: version_key(p.name))


def iter_spell_members(tar: tarfile.TarFile) -> Iterable[Tuple[tarfile.TarInfo, str]]:
    for member in tar.getmembers():
        if not member.isfile() or not member.name.lower().endswith(".png"):
            continue
        output_name = normalize_filename(member.name)
        yield member, output_name


def normalize_filename(member_name: str) -> str:
    name = Path(member_name).name  # e.g. sort_14218-96.png
    stem = Path(name).stem         # sort_14218-96
    icon_part, _, _size = stem.rpartition("-")
    if not icon_part:
        icon_part = stem
    # strip prefix like "sort_"
    _, _, icon_id = icon_part.rpartition("_")
    if not icon_id.isdigit():
        icon_id = icon_part
    return f"{icon_id}.png"


def extract_spell_images(raw_dir: Path, size: str, output_dir: Path, overwrite: bool) -> Tuple[int, int]:
    tar_path = raw_dir / f"spell_images_{size}.tar.gz"
    if not tar_path.is_file():
        raise FileNotFoundError(f"Missing archive: {tar_path}")

    destination = output_dir / size
    destination.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    with tarfile.open(tar_path, "r:gz") as archive:
        for member, filename in iter_spell_members(archive):
            target_path = destination / filename
            if target_path.exists() and not overwrite:
                skipped += 1
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                skipped += 1
                continue
            with target_path.open("wb") as fh:
                fh.write(extracted.read())
            written += 1
    return written, skipped


def load_spell_metadata(metadata_path: Path) -> List[SpellIconRecord]:
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata file: {metadata_path}")
    with metadata_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    records: List[SpellIconRecord] = []
    for entry in payload:
        icon_id = entry.get("icon_id")
        name = (entry.get("name_en") or "").strip()
        if not icon_id or not name:
            continue
        try:
            icon_int = int(icon_id)
        except (TypeError, ValueError):
            continue
        ankama_id = entry.get("ankama_id")
        try:
            ankama_int = int(ankama_id) if ankama_id is not None else None
        except (TypeError, ValueError):
            ankama_int = None
        fallback = f"spell_{ankama_int or icon_int}"
        filename_stem = sanitize_spell_name(name, fallback=fallback)
        records.append(
            SpellIconRecord(
                ankama_id=ankama_int,
                icon_id=icon_int,
                english_name=name,
                filename_stem=filename_stem,
            )
        )

    records.sort(key=lambda rec: (rec.filename_stem.casefold(), rec.ankama_id or rec.icon_id))
    if not records:
        raise ValueError(f"No valid spells found inside {metadata_path}")
    return records


def _load_constants_module(constants_path: Path) -> ModuleType:
    if not constants_path.exists():
        raise FileNotFoundError(f"dofus_constants.py not found: {constants_path}")
    spec = importlib.util.spec_from_file_location("fashionista_dofus_constants", constants_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec from {constants_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def load_damage_spell_names(constants_path: Path) -> Set[str]:
    module = _load_constants_module(constants_path)
    damage_spells = getattr(module, "DAMAGE_SPELLS", None)
    if not damage_spells:
        raise ValueError(f"DAMAGE_SPELLS was not found in {constants_path}")

    names: Set[str] = set()
    for spells in damage_spells.values():
        for spell in spells:
            name = getattr(spell, "name", None)
            if not name:
                continue
            names.add(name.strip().casefold())
    if not names:
        raise ValueError("DAMAGE_SPELLS did not provide any spell names")
    return names


def load_class_spell_names(game_version: str) -> Set[str]:
    """Every class spell the version has, from the spell reference the page
    reads: the damage ones plus the spells that only move or protect."""
    path = (Path("fashionsite") / "chardata" / "spell_reference"
            / ("%s.json" % game_version))
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as handle:
        classes = json.load(handle)
    return {(spell.get("name") or {}).get("en", "").casefold()
            for block in classes.values() for spell in block
            if (spell.get("name") or {}).get("en")}


def filter_spell_records(records: Sequence[SpellIconRecord], scope: str,
                         constants_path: Path,
                         game_version: str = "dofus3") -> List[SpellIconRecord]:
    if scope == "all":
        return list(records)
    allowed_names = load_damage_spell_names(constants_path)
    if scope == "class":
        # The whole class book, not only what deals damage. 'all' would drag in
        # every monster spell: 10000 icons and 130 MB.
        allowed_names = allowed_names | load_class_spell_names(game_version)
    filtered = [record for record in records if record.english_name.casefold() in allowed_names]
    if not filtered:
        raise ValueError("No spell images matched the DAMAGE_SPELLS selection")
    return filtered


def dedupe_spell_records(records: Sequence[SpellIconRecord]) -> Tuple[List[SpellIconRecord], List[SpellIconRecord]]:
    unique: List[SpellIconRecord] = []
    dropped: List[SpellIconRecord] = []
    seen: Set[str] = set()
    for record in records:
        key = record.filename_stem.casefold()
        if key in seen:
            dropped.append(record)
            continue
        seen.add(key)
        unique.append(record)
    return unique, dropped


def sanitize_spell_name(name: str, fallback: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub(" ", name)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    if not cleaned:
        cleaned = fallback
    return cleaned


def select_filename(record: SpellIconRecord, seen: Dict[str, int]) -> str:
    base = record.filename_stem
    key = base.casefold()
    count = seen.get(key, 0)
    if count:
        suffix = record.ankama_id if record.ankama_id is not None else count + 1
        base = f"{base} ({suffix})"
        key = base.casefold()
    seen[key] = seen.get(key, 0) + 1
    return f"{base}.png"


def copy_spell_icons(
    source_dir: Path,
    destination_dirs: Sequence[Path],
    records: Sequence[SpellIconRecord],
    overwrite: bool,
) -> Tuple[CopyStats, Set[str]]:
    stats = CopyStats()
    seen_names: Dict[str, int] = {}
    produced: Set[str] = set()
    targets: List[Path] = []
    for dest in destination_dirs:
        path = Path(dest)
        path.mkdir(parents=True, exist_ok=True)
        targets.append(path)

    for record in records:
        stats.processed += 1
        filename = select_filename(record, seen_names)
        produced.add(filename)
        source_path = source_dir / f"{record.icon_id}.png"
        if not source_path.exists():
            stats.missing_source += 1
            continue
        copied = False
        for dest in targets:
            target_path = dest / filename
            if target_path.exists() and not overwrite:
                continue
            shutil.copy2(source_path, target_path)
            copied = True
        if copied or overwrite:
            stats.written += 1
        else:
            stats.skipped_existing += 1

    return stats, produced


#: Every version whose pages read the shared spell directory. dofus3 owns it
#: and the other four fall back to it, so what one run produces is never the
#: whole of what the directory has to hold.
SHARED_ICON_VERSIONS = ("dofus3", "beta", "dofus2", "retro", "touch")

#: The versions whose constants expose DAMAGE_SPELLS under that name. Retro and
#: touch keep theirs under RETRO_DAMAGE_SPELLS / TOUCH_DAMAGE_SPELLS in modules
#: of their own, and their class spells come from the reference below anyway.
CONSTANTS_BY_VERSION = {
    "dofus3": Path("fashionistapulp/fashionistapulp/dofus_constants.py"),
    "beta": Path("fashionistapulp/fashionistapulp/dofus_constants_beta.py"),
    "dofus2": Path("fashionistapulp/fashionistapulp/dofus_constants_dofus2.py"),
}


def names_the_pages_can_ask_for() -> Set[str]:
    """Every spell name any version's pages can put an icon behind.

    The class reference is what a spell page lists, and DAMAGE_SPELLS carries
    a few the reference does not: the Ebony Dofus is a default spell rather
    than a class one, which is how it went missing.
    """
    names: Set[str] = set()
    for version in SHARED_ICON_VERSIONS:
        names |= load_class_spell_names(version)
        path = CONSTANTS_BY_VERSION.get(version)
        if path is None or not path.exists():
            continue
        try:
            names |= load_damage_spell_names(path)
        except ValueError:
            continue
    return {sanitize_spell_name(name, name).casefold() for name in names}


def prune_stale_icons(destination_dir: Path, expected_files: Set[str],
                      protected: Set[str] | None = None) -> int:
    """Delete icons no page can ask for.

    `expected_files` is only what THIS run produced, and one run covers one
    version at one scope. Pruning on that alone emptied the shared directory of
    297 icons on 2026-08-27, every one of them still named by a page: 297 by
    dofus3 itself, 134 by dofus2, 81 by touch, 44 by retro. The run had scope
    'damage', 552 icons, against the 849 the pages list.
    """
    removed = 0
    if not destination_dir.exists():
        return removed
    protected = protected or set()
    for path in destination_dir.glob("*.png"):
        if path.name in expected_files:
            continue
        if path.stem.casefold() in protected:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def main() -> int:
    args = parse_args()
    raw_dir = resolve_raw_dir(args.raw_root, args.version)
    written, skipped = extract_spell_images(raw_dir, args.size, args.output_dir, args.overwrite)
    source_dir = args.output_dir / args.size
    print(f"Extracted {written} spell icons (skipped {skipped}) from {raw_dir.name} -> {source_dir}")

    records = load_spell_metadata(args.metadata)
    scoped_records = filter_spell_records(records, args.scope, args.constants,
                                         getattr(args, "game_version", "dofus3"))
    unique_records, dropped = dedupe_spell_records(scoped_records)
    if dropped:
        print(f"Skipped {len(dropped)} duplicate spell names (keeping the first occurrence).")

    destination_dirs: List[Path] = [args.static_dir]
    if args.extra_static_dirs is not None:
        destination_dirs.extend(args.extra_static_dirs)
    if not destination_dirs:
        raise ValueError("At least one destination directory must be specified")

    ordered_dests: List[Path] = []
    seen_paths: Set[Path] = set()
    for dest in destination_dirs:
        resolved = Path(dest).resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        ordered_dests.append(resolved)

    stats, produced = copy_spell_icons(
        source_dir,
        ordered_dests,
        unique_records,
        overwrite=args.overwrite,
    )
    if args.prune:
        protected = names_the_pages_can_ask_for()
        total_pruned = 0
        for dest in ordered_dests:
            total_pruned += prune_stale_icons(dest, produced, protected)
        stats.pruned = total_pruned
        print(f"Protected {len(protected)} spell names read from the five "
              f"versions' references and constants.")
    dest_summary = ", ".join(str(path) for path in ordered_dests)
    print(
        f"Copied {stats.written}/{stats.processed} spell icons into {dest_summary} "
        f"(missing source: {stats.missing_source}, skipped existing: {stats.skipped_existing}, "
        f"pruned: {stats.pruned})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
