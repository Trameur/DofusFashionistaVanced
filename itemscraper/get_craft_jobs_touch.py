#!/usr/bin/env python3
"""get_craft_jobs_touch.py - build the crafted-item -> profession index for
Dofus Touch, so the encyclopedia can show "Crafted by <job> (lvl N)".

The Touch backend Recipes table carries jobId + resultLevel and, unlike the
other versions, a jobName that is already localized per language file
(Recipes_<lang>.json from download_touch_data.py --all-langs). Emits the same
index shape as get_craft_jobs.py, consumed unchanged by store_craft_jobs.py.

Usage (from repo root):
    python itemscraper/get_craft_jobs_touch.py --raw-dir itemscraper/touch_raw \
        --output itemscraper/transformed_craft_jobs_touch.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Sequence

LANGUAGES: Sequence[str] = ("en", "fr", "es", "pt", "de")
DEFAULT_OUTPUT = Path("itemscraper/transformed_craft_jobs_touch.json")


def _load_recipes(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    values = data.values() if isinstance(data, dict) else data
    return [r for r in values if isinstance(r, dict)]


def build_craft_jobs_index(raw_dir: Path,
                           languages: Sequence[str] = LANGUAGES) -> Dict[str, Any]:
    # jobName per (resultId, lang); the fr file drives the record list.
    names_by_result: Dict[int, Dict[str, str]] = {}
    base: Dict[int, Dict[str, Any]] = {}
    for lang in languages:
        path = raw_dir / f"Recipes_{lang}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing localized recipes: {path}")
        for recipe in _load_recipes(path):
            result_id = recipe.get("resultId")
            job_id = recipe.get("jobId")
            job_name = recipe.get("jobName")
            if result_id is None or job_id is None or not job_name:
                continue
            result_id = int(result_id)
            names_by_result.setdefault(result_id, {})[lang] = job_name
            base.setdefault(result_id, {
                "job_ankama_id": int(job_id),
                "level": int(recipe.get("resultLevel") or 0),
            })

    index: Dict[str, Any] = {}
    for result_id, info in base.items():
        index[str(result_id)] = {
            "job_ankama_id": info["job_ankama_id"],
            "level": info["level"],
            "names": {lang: names_by_result.get(result_id, {}).get(lang)
                      for lang in languages},
        }
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Touch crafted-item -> profession index")
    parser.add_argument("--raw-dir", type=Path,
                        default=Path("itemscraper/touch_raw"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    index = build_craft_jobs_index(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    print("crafted items with a job: %d -> %s" % (len(index), args.output))


if __name__ == "__main__":
    main()
