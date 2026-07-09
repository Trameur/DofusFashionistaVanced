#!/usr/bin/env python3
"""get_craft_jobs.py - build the crafted-item -> profession index from the raw
dofusdude dump, so the encyclopedia can show "Craft: <job> (lvl N)" on item pages.

recipes.json carries jobId + resultLevel per crafted item, jobs.json maps job ids
to nameIds, and the <lang>.json files localize the names. Reuses the datacenter
and translation loaders from get_monsters.py, which already handle both the
dofus3/beta Unity serialization and the Dofus 2 / Touch plain-list format.

Output: {result_ankama_id: {"job_ankama_id", "level", "names": {lang: name}}}

Usage (from repo root):
    python itemscraper/get_craft_jobs.py --dataset-dir itemscraper/raw/<version> \
        --output itemscraper/transformed_craft_jobs.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from get_monsters import (  # noqa: E402
    _load_datacenter_table, _load_json, _load_translations, _unwrap_array)

LANGUAGES: Sequence[str] = ("en", "fr", "es", "pt", "de")
DEFAULT_OUTPUT = Path("itemscraper/transformed_craft_jobs.json")


def _load_recipes(path: Path):
    """recipes.json has no per-recipe id key, so resolve the raw records
    directly (Unity RefIds or a plain list) instead of an {id: record} map."""
    data = _load_json(path)
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    refs = data.get("references", {}).get("RefIds", [])
    return [ref.get("data") for ref in refs if isinstance(ref.get("data"), dict)]


def build_craft_jobs_index(dataset_dir: Path,
                           languages: Sequence[str] = LANGUAGES,
                           jobs_file: Path | None = None) -> Dict[str, Any]:
    # The Dofus 2 release ships no jobs.json, but job ids have been stable since
    # the 2.44 profession merge, so its pipeline borrows the dofus3 id->nameId
    # table while the names still come from the dataset's own language files.
    jobs = _load_datacenter_table(jobs_file or (dataset_dir / "jobs.json"))
    translations = _load_translations(dataset_dir, languages)

    job_names: Dict[int, Dict[str, str]] = {}
    for job_id, job in jobs.items():
        key = str(job.get("nameId"))
        job_names[int(job_id)] = {
            lang: translations.get(lang, {}).get(key) for lang in languages}

    index: Dict[str, Any] = {}
    for recipe in _load_recipes(dataset_dir / "recipes.json"):
        result_id = recipe.get("resultId")
        job_id = recipe.get("jobId")
        if result_id is None or job_id is None:
            continue
        names = job_names.get(int(job_id))
        if not names or not any(names.values()):
            continue
        index[str(int(result_id))] = {
            "job_ankama_id": int(job_id),
            "level": int(recipe.get("resultLevel") or 0),
            "names": names,
        }
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the crafted-item -> profession index from the raw dump")
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--languages", nargs="*", default=list(LANGUAGES))
    parser.add_argument("--jobs-file", type=Path, default=None,
                        help="jobs.json to use when the dataset has none (Dofus 2)")
    args = parser.parse_args()

    index = build_craft_jobs_index(args.dataset_dir, args.languages, args.jobs_file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    print("crafted items with a job: %d -> %s" % (len(index), args.output))


if __name__ == "__main__":
    main()
