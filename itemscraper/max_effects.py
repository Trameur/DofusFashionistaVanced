"""The stat a "Max." effect caps, by the characteristic id the game writes in it."""
import json
import os

STAT_NAME_BY_KEYWORD = {
    'actionPoints': 'AP',
    'range': 'Range',
    'movementPoints': 'MP',
    'maxSummonedCreaturesBoost': 'Summon',
}

FALLBACK_STAT_NAME_BY_ID = {
    1: 'AP',
    19: 'Range',
    23: 'MP',
    26: 'Summon',
}

CHARACTERISTICS_FILE = 'characteristics.json'

_warned = set()


def read_keywords(raw_dir):
    """{characteristic id: keyword} of the client's characteristics.json, or None without that file."""
    path = os.path.join(raw_dir, CHARACTERISTICS_FILE)
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as handle:
        document = json.load(handle)
    keywords = {}
    for reference in document['references']['RefIds']:
        data = reference.get('data') or {}
        if 'id' in data and 'keyword' in data:
            keywords[int(data['id'])] = data['keyword']
    return keywords


def load_cap_stats(raw_dir):
    """(stat name by characteristic id, keyword by id) from raw_dir's characteristics.json, else the fallback table."""
    keywords = read_keywords(raw_dir) if raw_dir else None
    if keywords is None:
        if raw_dir:
            print('warning: no %s in %s, the "Max." caps use the fallback characteristic ids'
                  % (CHARACTERISTICS_FILE, raw_dir))
        return dict(FALLBACK_STAT_NAME_BY_ID), {}
    stats = {char_id: STAT_NAME_BY_KEYWORD[keyword] for char_id, keyword in keywords.items()
             if keyword in STAT_NAME_BY_KEYWORD}
    for keyword in sorted(set(STAT_NAME_BY_KEYWORD) - set(keywords.values())):
        print('warning: no characteristic named %s in %s, its "Max." caps are lost'
              % (keyword, os.path.join(raw_dir, CHARACTERISTICS_FILE)))
    return stats, keywords


def max_caps(effects, stat_by_id=None, keyword_by_id=None):
    """[(stat name, max value)] of the "Max." rows among transformed [first, second, name] effects."""
    if stat_by_id is None:
        stat_by_id = FALLBACK_STAT_NAME_BY_ID
    caps = []
    for char_id, max_value, stat_name in effects:
        if stat_name != 'Max.' or max_value is None:
            continue
        mapped = stat_by_id.get(char_id)
        if mapped is not None:
            caps.append((mapped, max_value))
        elif char_id not in _warned:
            _warned.add(char_id)
            print('warning: a "Max." row names characteristic %s (%s) with no mapping, its cap is dropped'
                  % (char_id, (keyword_by_id or {}).get(char_id, 'unknown')))
    return caps
