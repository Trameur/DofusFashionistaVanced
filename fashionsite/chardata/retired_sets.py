"""Sets the game removed from a version, read from the record next to its transformed sets."""
import json
from pathlib import Path

ITEMSCRAPER = Path(__file__).resolve().parents[2] / 'itemscraper'
_retired_by_version = {}


def retired_sets_file(game_version):
    """Where the pipeline records a version's removed sets."""
    folder = ITEMSCRAPER if game_version == 'dofus3' else ITEMSCRAPER / game_version
    return folder / 'retired_sets.json'


def retired_sets(game_version):
    """{set id: names by language} of the sets the game removed from this version, read once per process."""
    cached = _retired_by_version.get(game_version)
    if cached is None:
        path = retired_sets_file(game_version)
        rows = json.loads(path.read_text(encoding='utf-8'))['sets'] if path.is_file() else []
        cached = {row['ankama_id']: row['names'] for row in rows}
        _retired_by_version[game_version] = cached
    return cached


def retired_set_name(game_version, set_id, language):
    """The removed set's name in language, else English, else any; None when the set was not removed."""
    names = retired_sets(game_version).get(set_id)
    if names is None:
        return None
    return names.get(language) or names.get('en') or next((n for n in names.values() if n), '#%s' % set_id)
