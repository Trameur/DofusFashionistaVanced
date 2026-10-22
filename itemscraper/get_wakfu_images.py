#!/usr/bin/env python3
"""Extract the Wakfu pictures the database refers to from the client's picture archive.

    python itemscraper/get_wakfu_images.py [--client itemscraper/wakfu_client] [--force]

get_wakfu_client.py keeps gui.jar and config.properties in the newest client folder and
build_wakfu_db.py writes client_pictures, the file number or key the client draws for each
item, spell, state, ability, monster, monster family and class. This reads those rows
(never writing the database), takes the matching .tga from gui.jar at the path the
client's own config.properties gives, and stores it as webp:

    items/wakfu/64/<gfx>.webp            spells/wakfu/<icon>.webp
    states/wakfu/<key>.webp              abilities/wakfu/<icon>.webp
    classes/wakfu/icons/<breed>.webp     classes/wakfu/portrait80/<breed><sex>.webp
    monsters/wakfu/<picture>.webp        monsters/wakfu/families/<family>.webp

Every folder also gets a default.webp, the client's own placeholder, for a row whose file
the archive does not hold. A picture shared by several rows is one file. A file already on
disk is kept unless --force, and nothing is ever deleted. The items are the ones the
database refers to: its items, pets, mounts, the containers of its effects, recipes,
monster drops and loot lists.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import get_wakfu_client  # noqa: E402
import wakfu_client  # noqa: E402

CLIENT = HERE / 'itemscraper' / 'wakfu_client'
WAKFU_DB = HERE / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'
STATIC = HERE / 'fashionsite' / 'chardata' / 'static' / 'chardata'
ARCHIVE_PREFIX = 'gui.jar!/'
SAFE_STEM = re.compile(r'[A-Za-z0-9_.-]+')
SEXES = (0, 1)
PREVIEW_LIMIT = 10

ITEM_IDS = """
    SELECT id FROM items UNION SELECT item FROM pets UNION SELECT item FROM mounts
    UNION SELECT container FROM effects WHERE container_type IN ('ITEM_EQUIP', 'ITEM_USE')
    UNION SELECT item FROM item_recipes UNION SELECT ingredient_ankama_id FROM item_recipes
    UNION SELECT item FROM monster_drops UNION SELECT item FROM loot_list_rows"""

# name, client_pictures family (None: derived), config key, folder, longest edge kept
# (None: the file's own size), config key of the placeholder
TARGETS = (
    ('items', 'item', 'itemsIconsPath', 'items/wakfu/64', 64, 'defaultIconPath'),
    ('spells', 'spell', 'spellsIconsPath', 'spells/wakfu', 64, 'defaultIconPath'),
    ('states', 'state', 'statesIconsPath', 'states/wakfu', 64, 'defaultIconPath'),
    ('abilities', 'ability', 'aptitudeIconsPath', 'abilities/wakfu', None, 'defaultIconPath'),
    ('class icons', 'class', 'breedSmallIconPath', 'classes/wakfu/icons', 64,
     'defaultIconPath'),
    ('class portraits', None, 'breedCharacterPortrait80Path', 'classes/wakfu/portrait80',
     None, 'defaultIconPath'),
    ('monsters', 'monster', 'monsterIllustrationPath', 'monsters/wakfu', None,
     'defaultMonsterIllustrationPath'),
    ('monster families', 'monster_family', 'monstersFamily', 'monsters/wakfu/families', None,
     'defaultIconPath'),
)
CONFIG_KEYS = sorted({row[2] for row in TARGETS} | {row[5] for row in TARGETS})


def newest_client(root):
    """The newest client folder that holds a picture archive, or None."""
    folders = [path for path in Path(root).iterdir() if (path / 'gui.jar').is_file()] \
        if Path(root).is_dir() else []
    return max(folders, key=lambda path: get_wakfu_client.version_key(path.name), default=None)


def read_members(folder):
    """{config key: template of the archive member}, read from the client's config.properties."""
    properties = wakfu_client.read_properties(folder / 'config.properties')
    members = {}
    for key in CONFIG_KEYS:
        value = properties.get(key)
        if value is None or ARCHIVE_PREFIX not in value:
            raise wakfu_client.TableError('config.properties has no archive path for %s' % key)
        members[key] = value.split(ARCHIVE_PREFIX, 1)[1]
    return members


def member_of(template, picture):
    return re.sub(r'%[ds]', lambda _match: str(picture), template, count=1)


def wanted(conn, name, family):
    """{file stem: first id} of the pictures a target stores."""
    if name == 'class portraits':
        rows = [(breed, '%d%d' % (breed, sex)) for (breed,) in conn.execute(
            "SELECT id FROM client_pictures WHERE family = 'class' ORDER BY id")
            for sex in SEXES]
    elif name == 'items':
        rows = conn.execute(
            "SELECT id, picture FROM client_pictures WHERE family = 'item' AND id IN (%s)"
            ' ORDER BY id' % ITEM_IDS).fetchall()
    else:
        rows = conn.execute(
            'SELECT id, picture FROM client_pictures WHERE family = ? ORDER BY id',
            (family,)).fetchall()
    stems = {}
    for ident, picture in rows:
        stems.setdefault(str(picture), ident)
    return stems


def convert(blob, edge, path):
    """Write one picture as webp at its own size, or at `edge` when it is larger."""
    from PIL import Image
    with Image.open(io.BytesIO(blob)) as picture:
        picture.load()
        if picture.mode != 'RGBA':
            picture = picture.convert('RGBA')
        if edge and max(picture.size) > edge:
            picture.thumbnail((edge, edge), Image.LANCZOS)
        part = path.with_name(path.name + '.part')
        try:
            picture.save(str(part), 'WEBP', quality=90, method=6)
            os.replace(part, path)
        finally:
            if part.exists():
                part.unlink()
    return path.stat().st_size


def extract(archive, names, member, edge, path, force):
    """'kept', 'written' or 'missing'; the size written is returned beside it."""
    if path.exists() and not force:
        return 'kept', 0
    if member not in names:
        return 'missing', 0
    path.parent.mkdir(parents=True, exist_ok=True)
    return 'written', convert(archive.read(member), edge, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', default=str(CLIENT))
    parser.add_argument('--db', default=str(WAKFU_DB))
    parser.add_argument('--static', default=str(STATIC))
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)

    folder = newest_client(args.client)
    if folder is None or not (folder / 'config.properties').is_file():
        print('no client folder with gui.jar and config.properties under %s' % args.client)
        return 1
    try:
        members = read_members(folder)
    except wakfu_client.TableError as error:
        print(error)
        return 1
    db_path = Path(args.db)
    if not db_path.is_file():
        print('%s is missing' % db_path)
        return 1
    static = Path(args.static)
    conn = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
    failed = False
    try:
        with zipfile.ZipFile(folder / 'gui.jar') as archive:
            names = set(archive.namelist())
            print('client %s' % folder.name)
            for name, family, key, target, edge, default_key in TARGETS:
                stems = wanted(conn, name, family)
                counts = {'written': 0, 'kept': 0, 'missing': 0}
                lost, size, first = [], 0, None
                for stem, ident in stems.items():
                    member = member_of(members[key], stem)
                    path = static / target / (stem + '.webp')
                    if not SAFE_STEM.fullmatch(stem):
                        counts['missing'] += 1
                        lost.append(ident)
                        continue
                    outcome, written = extract(archive, names, member, edge, path, args.force)
                    counts[outcome] += 1
                    size += written
                    if outcome == 'missing':
                        lost.append(ident)
                    elif first is None:
                        first = (ident, stem, member, path)
                default = extract(archive, names, members[default_key], edge,
                                  static / target / 'default.webp', args.force)
                size += default[1]
                if first:
                    print('%-16s id %s picture %s member %s -> %s' % ((name,) + first))
                print('%-16s wanted %d written %d kept %d missing %d, %.2f MB, default %s'
                      % (name, len(stems), counts['written'], counts['kept'],
                         counts['missing'], size / 1e6, default[0]))
                if lost:
                    print('   missing ids %s%s' % (
                        ', '.join(str(one) for one in lost[:PREVIEW_LIMIT]),
                        ' ...' if len(lost) > PREVIEW_LIMIT else ''))
                if counts['written'] + counts['kept'] == 0:
                    print('   no file at all for %s' % name)
                    failed = True
    except (OSError, zipfile.BadZipFile) as error:
        print('the picture archive could not be read: %s' % error)
        return 1
    finally:
        conn.close()
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
