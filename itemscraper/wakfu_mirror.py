"""The Wakfu build the mirror holds, read from transformed_wakfu.json, so every step reads one folder."""

from __future__ import annotations

import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MIRROR = HERE / 'itemscraper' / 'wakfu_raw'
DUMP = HERE / 'itemscraper' / 'transformed_wakfu.json'


def _as_numbers(build):
    return [int(part) if part.isdigit() else -1 for part in build.split('.')]


def current_build(dump_path=DUMP, mirror=MIRROR):
    """The build get_items_wakfu.py mirrored last, else the highest build folder, else None."""
    if Path(dump_path).exists():
        with io.open(dump_path, encoding='utf-8') as handle:
            version = json.load(handle).get('version')
        if version:
            return version
    builds = [path.name for path in Path(mirror).glob('*') if path.is_dir()]
    return max(builds, key=_as_numbers) if builds else None


def current_build_dir(dump_path=DUMP, mirror=MIRROR):
    build = current_build(dump_path, mirror)
    return Path(mirror) / build if build else None
