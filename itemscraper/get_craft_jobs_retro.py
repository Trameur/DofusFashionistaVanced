#!/usr/bin/env python3
"""get_craft_jobs_retro.py - build the crafted-item -> profession index for
Dofus Retro from Ankama's official lang files.

The 1.29 skills lang carries, for every craft skill, the explicit list of
craftable item ids (`cl`) plus the owning job (`j`); the jobs lang localizes
the job names (the pre-merge professions: "Forgeur d'Epees", "Sculpteur
d'Arcs", ...). 1.29 has no per-recipe level in the lang data, so the level is
0 and the encyclopedia shows the profession alone. Emits the same index shape
as get_craft_jobs.py, consumed unchanged by store_craft_jobs.py.

Inputs (download_retro_langs.py --categories jobs skills):
    retro_raw/skills_fr.json   SK = {skillId: {j: jobId, cl: [itemId...], ...}}
    retro_raw/jobs_<lang>.json J  = {jobId: {n: localized name, ...}}

Usage (from repo root):
    python itemscraper/get_craft_jobs_retro.py --raw-dir itemscraper/retro_raw \
        --output itemscraper/transformed_craft_jobs_retro.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Sequence

LANGUAGES: Sequence[str] = ("en", "fr", "es", "pt", "de")
DEFAULT_OUTPUT = Path("itemscraper/transformed_craft_jobs_retro.json")


def _load_global(path: Path, key: str):
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    table = data.get(key)
    if not isinstance(table, dict):
        raise ValueError("%s has no %r global" % (path, key))
    return table


def build_craft_jobs_index(raw_dir: Path,
                           languages: Sequence[str] = LANGUAGES) -> Dict[str, Any]:
    skills = _load_global(raw_dir / "skills_fr.json", "SK")

    job_names: Dict[int, Dict[str, str]] = {}
    for lang in languages:
        path = raw_dir / f"jobs_{lang}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing localized jobs: {path}")
        for job_id, job in _load_global(path, "J").items():
            name = (job or {}).get("n")
            if name:
                job_names.setdefault(int(job_id), {})[lang] = name

    index: Dict[str, Any] = {}
    for skill in skills.values():
        if not isinstance(skill, dict):
            continue
        craft_list = skill.get("cl")
        job_id = skill.get("j")
        if not craft_list or job_id is None:
            continue
        names = job_names.get(int(job_id))
        if not names:
            continue
        for item_id in craft_list:
            index[str(int(item_id))] = {
                "job_ankama_id": int(job_id),
                # 1.29 langs carry no per-recipe level: the page then shows the
                # profession without a level instead of inventing one.
                "level": 0,
                "names": {lang: names.get(lang) for lang in languages},
            }
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Retro crafted-item -> profession index")
    parser.add_argument("--raw-dir", type=Path,
                        default=Path("itemscraper/retro_raw"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    index = build_craft_jobs_index(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    print("crafted items with a job: %d -> %s" % (len(index), args.output))


if __name__ == "__main__":
    main()
