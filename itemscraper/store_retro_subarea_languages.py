#!/usr/bin/env python3
"""Add the languages Solomonk cannot serve to the Retro subarea names.

store_retro_monster_subareas.py fills monster_subareas from the Solomonk
bestiary, which answers fr, en and es. The monster page falls back to French
when a language has no row, so a Portuguese reader of a Retro monster page
reads French place names.

That fallback was invisible while Retro had no Portuguese monster names at all:
the pages did not exist. They do now, and 281 of them carry a subarea list.

Ankama's own `maps` lang file carries the subarea names in all five languages,
keyed by subarea id. The table stores names and not ids, so the French name is
the join.

  Usage (from itemscraper/):
      python store_retro_subarea_languages.py [--languages pt de]

WHY EVERY ROW IS WRITTEN, translated or not: the page falls back to French only
when a language has NO row at all. Inserting only the names Ankama translates
would leave the rest out of the list entirely -- the reader would lose subareas
rather than read them in French. Losing information is worse than showing it in
the wrong language, so an untranslated subarea is written with its French name.
"""

import argparse
import collections
import os
import sqlite3
import sys
import urllib.request
import zlib

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)

DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                       'items_retro.db')
CDN_BASE = 'https://dofusretro.cdn.ankama.com/lang'
SOURCE_LANGUAGE = 'fr'
DEFAULT_LANGUAGES = ('pt', 'de')
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

# The table holds about a thousand rows. Far below means the subarea scraper
# left it empty or the schema moved -- and an empty read would otherwise write
# nothing and report success, which reads as "there was nothing to do".
MIN_SOURCE_ROWS = 500
# Ankama publishes a couple of hundred subareas. A handful means the payload
# key moved, not that Retro lost its map.
MIN_SUBAREAS = 100


def _fetch(url, timeout=120):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _manifest(language):
    body = _fetch('%s/versions_%s.txt' % (CDN_BASE, language),
                  timeout=60).decode('utf-8', 'replace')
    versions = {}
    for entry in body.split('=', 1)[-1].split('|'):
        parts = entry.split(',')
        if len(parts) == 3:
            versions[parts[0].strip()] = parts[2].strip()
    return versions


def subarea_names(language):
    """{subarea_id: name} from Ankama's own map file for one language."""
    try:
        from retro_swf_parser import parse_lang_swf
    except ImportError:  # when run as a module
        from itemscraper.retro_swf_parser import parse_lang_swf

    version = _manifest(language).get('maps')
    if not version:
        raise SystemExit(
            'no `maps` category in the %s manifest: the CDN layout moved, the '
            'subarea names did not disappear' % language)
    data = _fetch('%s/swf/maps_%s_%s.swf' % (CDN_BASE, language, version))
    if data[:3] == b'CWS':
        zlib.decompress(data[8:])  # fail loudly here rather than in the parser
    payload = (parse_lang_swf(data) or {}).get('MA') or {}
    found = {}
    for subarea_id, entry in (payload.get('sa') or {}).items():
        if isinstance(entry, dict) and entry.get('n'):
            found[str(subarea_id)] = entry['n']
    # An assertion on the question and not on the answer: a moved key gives an
    # empty dict, and an empty dict reads as "this language has no subareas".
    if len(found) < MIN_SUBAREAS:
        raise SystemExit(
            'only %d %s subareas parsed, expected at least %d: the payload key '
            'moved' % (len(found), language, MIN_SUBAREAS))
    print('  ankama %s: %d subareas' % (language, len(found)))
    return found


def store(languages, db_path=DB_PATH, refresh_dump=True):
    connexion = sqlite3.connect(db_path)
    try:
        curseur = connexion.cursor()
        source = curseur.execute(
            'SELECT monster_ankama_id, position, name FROM monster_subareas '
            'WHERE language = ? ORDER BY monster_ankama_id, position',
            (SOURCE_LANGUAGE,)).fetchall()
        if len(source) < MIN_SOURCE_ROWS:
            raise SystemExit(
                'only %d %s rows in monster_subareas, expected at least %d; '
                'run store_retro_monster_subareas.py first and nothing is '
                'written' % (len(source), SOURCE_LANGUAGE, MIN_SOURCE_ROWS))

        par_nom = {nom: identifiant
                   for identifiant, nom in subarea_names(SOURCE_LANGUAGE).items()}
        resume = collections.OrderedDict()
        for language in languages:
            localises = subarea_names(language)
            traduits = 0
            lignes = []
            for monstre, position, nom in source:
                identifiant = par_nom.get(nom)
                localise = localises.get(identifiant) if identifiant else None
                if localise:
                    traduits += 1
                lignes.append((monstre, language, position, localise or nom))
            curseur.execute('DELETE FROM monster_subareas WHERE language = ?',
                            (language,))
            curseur.executemany(
                'INSERT INTO monster_subareas '
                '(monster_ankama_id, language, position, name) '
                'VALUES (?, ?, ?, ?)', lignes)
            resume[language] = (len(lignes), traduits)

        connexion.commit()
        for language, (total, traduits) in resume.items():
            print('  %s: %d rows, %d translated, %d kept in %s'
                  % (language, total, traduits, total - traduits,
                     SOURCE_LANGUAGE))
        # Compte par langue et pas en tout : un total qui monte peut cacher une
        # langue restee vide.
        for language, (total, _traduits) in resume.items():
            if total != len(source):
                raise SystemExit(
                    '%s ended with %d rows against %d in %s; refusing a '
                    'partial list' % (language, total, len(source),
                                      SOURCE_LANGUAGE))
    finally:
        connexion.close()

    if not refresh_dump:
        print('dump left alone (--no-dump)')
        return
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(db_path, 'retro')
    print('retro dump refreshed')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--languages', nargs='*',
                        default=list(DEFAULT_LANGUAGES))
    parser.add_argument('--db', default=DB_PATH)
    # Pour eprouver le script sur une copie sans toucher au dump partage.
    parser.add_argument('--no-dump', action='store_true')
    args = parser.parse_args()
    store(args.languages, args.db, refresh_dump=not args.no_dump)
    return 0


if __name__ == '__main__':
    sys.exit(main())
