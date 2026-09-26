"""Local inventories and recovery for update_all.py."""

from __future__ import annotations

import hashlib
import os
import json
from contextlib import contextmanager
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from data_file_ops import replace_file

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'fashionistapulp/fashionistapulp'
STATIC = ROOT / 'fashionsite/chardata/static'
IMAGE_DIRECTORIES = ('items', 'pets', 'resources', 'monsters', 'spells')
RESTORE_WAIT = 60
SIDECARS = ('-journal', '-wal', '-shm')
TRACKED_DIRECTORY = 'itemscraper'
WAKFU_SOURCES = {'item_recipes': 'recipes.json', 'item_recipe_ingredient_names': 'recipes.json',
                 'item_craft_jobs': 'recipes.json'}
LOSS_TOLERANCE = .03


def database_path(version):
    return DATA / ('items.db' if version == 'dofus3' else 'items_%s.db' % version)


def dump_path(version):
    return DATA / ('item_db_dumped.dump' if version == 'dofus3' else 'item_db_dumped_%s.dump' % version)


@contextmanager
def readonly(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def writable(path):
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_name(path):
    return path.relative_to(ROOT).as_posix()


def shared_files():
    files = {ROOT / 'fashionista_version.py', ROOT / 'fashionsite/chardata/dynamic_translations.py'}
    files.update(DATA.glob('dofus_constants*.py'))
    return files


def version_files(version):
    files = {database_path(version), dump_path(version)}
    for directory in ('spell_reference', 'spell_states', 'spell_modifiers',
                      'starting_stats'):
        files.add(ROOT / 'fashionsite/chardata' / directory / (version + '.json'))
    if version == 'wakfu':
        files.add(ROOT / 'itemscraper/transformed_wakfu.json')
    if version == 'retro':
        files.add(ROOT / 'itemscraper/retro/retro_damage_spells.json')
    return files


def image_files():
    files = set()
    for directory in IMAGE_DIRECTORIES:
        files.update(path for path in (STATIC / 'chardata' / directory).rglob('*') if path.is_file())
    return files


def image_backup_size():
    files = image_files()
    return len(files), sum(path.stat().st_size for path in files)


def runtime_files(versions, images, shared=True):
    files = shared_files() if shared else set()
    for version in versions:
        files.update(version_files(version))
    if images:
        files.update(image_files())
    return files


def backup_runtime(versions, images, destination, shared=True):
    manifest = {'versions': list(versions), 'images': images, 'shared': shared, 'files': {}, 'live': {}}
    for path in sorted(runtime_files(versions, images, shared)):
        relative = relative_name(path)
        manifest['files'][relative] = None
        if not path.exists():
            continue
        saved = destination / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == '.db':
            manifest['live'][relative] = file_digest(path)
            with readonly(path) as source, writable(saved) as target:
                source.backup(target)
        else:
            shutil.copy2(path, saved)
        manifest['files'][relative] = file_digest(saved)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def manifest_names(manifest):
    current = runtime_files(manifest['versions'], manifest['images'], manifest.get('shared', True))
    return set(manifest['files']) | {relative_name(path) for path in current}


def missing_backups(manifest, source, names):
    missing = []
    for name in sorted(names):
        digest = manifest['files'].get(name)
        saved = source / name
        if not digest:
            continue
        if not saved.is_file():
            missing.append(name)
        elif file_digest(saved) != digest:
            raise ValueError('Corrupted backup: ' + name)
    return missing


def restore_order(name):
    return Path(name).suffix not in ('.db', '.dump', '.py'), name


def drop_sidecars(path):
    for suffix in SIDECARS:
        path.with_name(path.name + suffix).unlink(missing_ok=True)


def set_sidecars_aside(path):
    """Move a database's journal files out of the way; [(aside, original)]."""
    moved = []
    try:
        for suffix in SIDECARS:
            original = path.with_name(path.name + suffix)
            if original.exists():
                aside = original.with_name(original.name + '.restore-aside')
                aside.unlink(missing_ok=True)
                os.replace(original, aside)
                moved.append((aside, original))
    except OSError:
        put_sidecars_back(moved)
        raise
    return moved


def put_sidecars_back(moved):
    for aside, original in moved:
        os.replace(aside, original)


def restore_file(name, digest, source, live=None):
    path = ROOT / name
    database = path.suffix == '.db'
    if digest is None or (path.is_file() and file_digest(path) in (digest, live)):
        if database:
            drop_sidecars(path)
        if digest is None:
            path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    moved = set_sidecars_aside(path) if database else []
    temp = path.with_name(path.name + '.restore-tmp')
    try:
        shutil.copy2(source / name, temp)
        replace_file(temp, path, timeout=0)
    except OSError:
        temp.unlink(missing_ok=True)
        put_sidecars_back(moved)
        raise
    for aside, _original in moved:
        aside.unlink(missing_ok=True)


def restore_pass(names, manifest, source):
    locked, failed = [], []
    live = manifest.get('live', {})
    for name in sorted(names, key=restore_order):
        try:
            restore_file(name, manifest['files'].get(name), source, live.get(name))
        except PermissionError:
            locked.append(name)
        except OSError:
            failed.append(name)
    return locked, failed


def restore_runtime(manifest, source, only=None, wait=None):
    """Put the backed up files back; returns the names it could not restore."""
    names = manifest_names(manifest) if only is None else set(only)
    missing = missing_backups(manifest, source, names)
    locked, failed = restore_pass(set(names) - set(missing), manifest, source)
    deadline = time.monotonic() + (RESTORE_WAIT if wait is None else wait)
    while locked and time.monotonic() < deadline:
        time.sleep(1)
        locked, more = restore_pass(locked, manifest, source)
        failed += more
    return sorted(set(failed + locked + missing))


def same_stat(path, saved):
    try:
        current, backup = path.stat(), saved.stat()
    except OSError:
        return False
    return current.st_size == backup.st_size and current.st_mtime_ns == backup.st_mtime_ns


def changed_files(manifest, source):
    changed = []
    for name in sorted(manifest_names(manifest)):
        path = ROOT / name
        digest = manifest['files'].get(name)
        if digest is None:
            if path.exists():
                changed.append(name)
        elif not path.is_file():
            changed.append(name)
        elif not same_stat(path, source / name) and file_digest(path) != digest:
            changed.append(name)
    return changed


def backed_up_images(static_paths, manifest):
    names = {relative_name(STATIC / static_path) for static_path in static_paths}
    return sorted(name for name in names if manifest['files'].get(name))


def git(*args):
    result = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, check=True, timeout=120)
    return result.stdout.decode('utf-8', errors='replace')


def in_work_tree():
    try:
        top = git('rev-parse', '--show-toplevel').strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(top) and Path(top).resolve() == ROOT.resolve()


def tracked_data_files():
    names = git('ls-files', '-z', '--', TRACKED_DIRECTORY).split('\0')
    return sorted(name for name in names if name.endswith('.json'))


def modified_data_files():
    entries = git('status', '--porcelain', '-z', '--untracked-files=no', '--', TRACKED_DIRECTORY).split('\0')
    modified, skip = {}, False
    for entry in entries:
        if skip or len(entry) < 4:
            skip = False
            continue
        state, name = entry[:2], entry[3:]
        skip = 'R' in state or 'C' in state
        if name.endswith('.json'):
            modified[name] = 'D' not in state
    return modified


def file_stat(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return [stat.st_size, stat.st_mtime_ns]


def record_tracked(destination, exclude=()):
    if not in_work_tree():
        return None
    record = {'before': {name: file_stat(ROOT / name) for name in tracked_data_files() if name not in exclude},
              'modified_before': {}}
    for name, present in modified_data_files().items():
        if name in exclude:
            continue
        record['before'].setdefault(name, file_stat(ROOT / name))
        record['modified_before'][name] = None
        if present and (ROOT / name).is_file():
            saved = destination / 'tracked' / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, saved)
            record['modified_before'][name] = file_digest(saved)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'tracked.json').write_text(json.dumps(record, indent=1), encoding='utf-8')
    return record


def record_tracked_after(destination):
    record = read_record(destination / 'tracked.json')
    if record is None:
        return
    after = {name: file_stat(ROOT / name) for name in record['before']}
    (destination / 'tracked-after.json').write_text(json.dumps(after, indent=1), encoding='utf-8')


def read_record(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def restore_tracked(destination):
    """Put back the tracked data files a version changed; returns (unrestored, kept)."""
    record = read_record(destination / 'tracked.json')
    if record is None:
        return [], []
    after = read_record(destination / 'tracked-after.json')
    unrestored, kept, checkout = [], [], []
    for name, before in sorted(record['before'].items()):
        current = file_stat(ROOT / name)
        changed = current != before if after is None else after.get(name) != before
        if not changed or current == before:
            continue
        if after is not None and current != after.get(name):
            kept.append(name)
        elif name not in record['modified_before']:
            checkout.append(name)
        else:
            try:
                put_back_tracked(name, record['modified_before'][name], destination)
            except OSError:
                unrestored.append(name)
    for start in range(0, len(checkout), 50):
        chunk = checkout[start:start + 50]
        try:
            git('checkout', 'HEAD', '--', *chunk)
        except (OSError, subprocess.SubprocessError):
            unrestored += chunk
    return sorted(unrestored), kept


def put_back_tracked(name, digest, destination):
    path = ROOT / name
    if digest is None:
        path.unlink(missing_ok=True)
        return
    saved = destination / 'tracked' / name
    if not saved.is_file() or file_digest(saved) != digest:
        raise FileNotFoundError('Copy missing or corrupted: ' + name)
    temp = path.with_name(path.name + '.restore-tmp')
    shutil.copy2(saved, temp)
    try:
        replace_file(temp, path, timeout=0)
    except OSError:
        temp.unlink(missing_ok=True)
        raise


def lost_images(before):
    images = before.get('images', {})
    problems = images.get('problems', {})
    good = {path for key, path in images.get('paths', {}).items() if key not in problems}
    return sorted(path for path in good if image_problem(STATIC / path))


def preserve_table(before, after, table):
    with readonly(before) as old, writable(after) as new:
        schema = old.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not schema:
            raise ValueError('Local table missing: ' + table)
        rows = old.execute('SELECT * FROM ' + quoted(table)).fetchall()
        if table == 'mount_looks':
            query = 'SELECT id, ankama_id, ankama_type FROM items'
            current = {(ankama, kind): item for item, ankama, kind in new.execute(query)}
            old_items = {item: (ankama, kind) for item, ankama, kind in old.execute(query)}
            rows = [(current[old_items[row[0]]], *row[1:]) for row in rows if old_items[row[0]] in current]
        else:
            known = {row[0] for row in new.execute('SELECT DISTINCT monster_ankama_id FROM monster_names')}
            rows = [row for row in rows if row[0] in known]
        new.execute('DROP TABLE IF EXISTS ' + quoted(table))
        new.execute(schema[0])
        if rows:
            new.executemany('INSERT INTO %s VALUES (%s)' % (quoted(table), ','.join('?' for _ in rows[0])), rows)
    dump = after.with_name(after.name.replace('items', 'item_db_dumped', 1)).with_suffix('.dump')
    temporary = dump.with_name(dump.name + '.tmp')
    with readonly(after) as connection, temporary.open('w', encoding='utf-8') as output:
        for statement in connection.iterdump():
            output.write(statement + '\n')
    replace_file(temporary, dump)


def image_problem(path):
    from PIL import Image
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, ValueError, SyntaxError) as exc:
        return str(exc)
    return None


def image_inventory(version, items, connection, tables):
    from fashionistapulp.fashionistapulp.fashion_util import normalize_name, safe_icon_name
    import re

    types = dict(connection.execute('SELECT id, name FROM item_types'))
    pictures = dict(connection.execute('SELECT item, gfx FROM item_picture')) if 'item_picture' in tables else {}
    expected = {}
    for item_id, item in items.items():
        if item.get('removed'):
            continue
        if version == 'wakfu':
            choices = ['chardata/items/wakfu/64/%s.webp' % pictures.get(int(item_id), 'missing')]
        else:
            directory = 'pets' if types.get(item['type']) == 'Pet' else 'items'
            base = re.sub(r' (?:\d+|\([^)]*\))$', '', item['name'])
            names = list(dict.fromkeys((item['name'], base)))
            folders = [version + '/'] if version != 'dofus3' else ['']
            if version in ('beta', 'dofus2', 'touch'):
                folders.append('')
            choices = ['chardata/%s/%s60x60/%s-60-60.png' % (directory, folder, safe_icon_name(normalize_name(name)))
                       for folder in folders for name in names]
        found = next((path for path in choices if (STATIC / path).is_file()), choices[0])
        expected['item:' + item_id] = found
    reference = ROOT / 'fashionsite/chardata/spell_reference' / (version + '.json')
    if reference.exists():
        spell_data = json.loads(reference.read_text(encoding='utf-8'))
        for spells in spell_data.values():
            for spell in spells:
                names = spell.get('name', {})
                name = names.get('fr' if version in ('touch', 'retro') else 'en')
                if not name:
                    continue
                stem = safe_icon_name(name)
                native = 'chardata/spells/%s/%s.png' % (version, stem)
                common = 'chardata/spells/%s.png' % stem
                path = native if version in ('touch', 'retro') or (STATIC / native).exists() else common
                expected['spell:' + str(spell['id'])] = path
    if 'monster_names' in tables and version in ('dofus3', 'beta', 'touch', 'retro'):
        folder = '' if version in ('dofus3', 'beta') else version + '/'
        for (monster,) in connection.execute('SELECT DISTINCT monster_ankama_id FROM monster_names'):
            expected['monster:' + str(monster)] = 'chardata/monsters/%s96/%s.webp' % (folder, monster)
    if 'item_recipe_ingredient_names' in tables and version != 'wakfu':
        folder = '' if version in ('dofus3', 'beta') else version + '/'
        for (resource,) in connection.execute("SELECT DISTINCT ingredient_ankama_id FROM item_recipe_ingredient_names WHERE ingredient_subtype='resources'"):
            expected['resource:' + str(resource)] = 'chardata/resources/%s60x60/%s-60-60.png' % (folder, resource)
    problems, checked = {}, {}
    for key, relative in expected.items():
        if relative not in checked:
            checked[relative] = image_problem(STATIC / relative)
        if checked[relative] is not None:
            problems[key] = {'path': relative, 'reason': checked[relative]}
    return {'references': len(expected), 'paths': expected, 'unique_files': len(checked), 'problems': problems}


def empty_snapshot(version):
    return {'version': version, 'tables': {}, 'schema': {}, 'items': {}, 'stats': {}, 'spells': {},
            'legacy_ids': {}, 'integrity': ['ok'], 'source_stats': {}, 'dump_errors': [], 'orphaned': {},
            'images': {'references': 0, 'paths': {}, 'unique_files': 0, 'problems': {}},
            'mirror': wakfu_mirror_counts() if version == 'wakfu' else {}}


def wakfu_mirror_counts():
    dump = ROOT / 'itemscraper/transformed_wakfu.json'
    if not dump.is_file():
        return {}
    build = json.loads(dump.read_text(encoding='utf-8')).get('version')
    counts = {'build': build}
    for name in sorted(set(WAKFU_SOURCES.values())):
        source = ROOT / 'itemscraper/wakfu_raw' / str(build) / name
        if source.is_file():
            counts[name] = len(json.loads(source.read_text(encoding='utf-8')))
    return counts


def snapshot(version):
    path = database_path(version)
    if not path.exists():
        return empty_snapshot(version)
    with readonly(path) as connection:
        connection.row_factory = sqlite3.Row
        tables = {row['name']: row['sql'] for row in connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        counts = {name: connection.execute('SELECT COUNT(*) FROM ' + quoted(name)).fetchone()[0] for name in tables}
        stats = {str(row['key']): dict(row) for row in connection.execute('SELECT * FROM stats')}
        items = {str(row['id']): dict(row) for row in connection.execute('SELECT * FROM items')}
        stat_rows = {}
        for row in connection.execute('SELECT s.item, t.key, s.value, s.min_value, s.max_value FROM stats_of_item s JOIN stats t ON t.id=s.stat ORDER BY t.key'):
            stat_rows.setdefault(str(row[0]), []).append(list(row)[1:])
        for key, item in items.items():
            item['stats_hash'] = fingerprint(stat_rows.get(key, []))
        orphaned = {}
        for table in tables:
            columns = {row['name'] for row in connection.execute('PRAGMA table_info(' + quoted(table) + ')')}
            if 'item' in columns:
                ids = [row[0] for row in connection.execute('SELECT DISTINCT item FROM %s WHERE item NOT IN (SELECT id FROM items)' % quoted(table))]
                if ids:
                    orphaned[table] = ids
        aliases = dict(connection.execute('SELECT old_id, item FROM legacy_item_ids')) if 'legacy_item_ids' in tables else {}
        reference = ROOT / 'fashionsite/chardata/spell_reference' / (version + '.json')
        spells = {}
        if reference.exists():
            for class_name, rows in json.loads(reference.read_text(encoding='utf-8')).items():
                for row in rows:
                    spells[class_name + ':' + str(row['id'])] = {'name': row.get('name'), 'hash': fingerprint(row)}
        source_file = ROOT / 'itemscraper' / ('' if version == 'dofus3' else version) / 'transformed_equipment.json'
        vocabulary = {}
        if source_file.exists():
            for item in json.loads(source_file.read_text(encoding='utf-8')):
                for stat in item.get('stats', []):
                    if isinstance(stat, list) and len(stat) >= 3:
                        name = str(stat[2])
                        vocabulary[name] = vocabulary.get(name, 0) + 1
        dump = dump_path(version)
        dump_errors = []
        if not dump.exists():
            dump_errors.append('Dump missing: ' + str(dump))
        else:
            try:
                with writable(':memory:') as restored:
                    restored.executescript(dump.read_text(encoding='utf-8'))
                    for table in tables:
                        rows = restored.execute('SELECT COUNT(*) FROM ' + quoted(table)).fetchone()[0]
                        if rows != counts[table]:
                            dump_errors.append('%s: %d rows in the database, %d in the dump' % (table, counts[table], rows))
            except (sqlite3.Error, UnicodeError) as exc:
                dump_errors.append(str(exc))
        return {'version': version, 'tables': counts, 'schema': tables, 'items': items,
                'stats': stats, 'spells': spells, 'legacy_ids': {str(k): str(v) for k, v in aliases.items()},
                'integrity': [row[0] for row in connection.execute('PRAGMA integrity_check')],
                'source_stats': vocabulary, 'dump_errors': dump_errors,
                'orphaned': orphaned, 'images': image_inventory(version, items, connection, tables),
                'mirror': wakfu_mirror_counts() if version == 'wakfu' else {}}


def source_shrink(before, after, table):
    name = WAKFU_SOURCES.get(table)
    if after.get('version') != 'wakfu' or not name:
        return None
    old, new = before.get('mirror', {}).get(name), after.get('mirror', {}).get(name)
    if not old or new is None or new >= old:
        return None
    return name, old, new


def compare(before, after):
    result = {'errors': [], 'warnings': [], 'changes': [], 'items_added': [], 'items_removed': [], 'items_changed': []}
    if after['integrity'] != ['ok']:
        result['errors'].append('SQLite: ' + '; '.join(after['integrity']))
    result['errors'].extend('Inconsistent dump: ' + error for error in after.get('dump_errors', []))
    for name in sorted(after.get('source_stats', {}).keys() - before.get('source_stats', {}).keys()):
        result['warnings'].append('NEW SOURCE EFFECT: %s (%d items), check that it is handled' % (name, after['source_stats'][name]))
    for table in sorted(before['tables'].keys() | after['tables'].keys()):
        old, new = before['tables'].get(table, 0), after['tables'].get(table, 0)
        if new != old:
            result['changes'].append('%s: %d -> %d rows (%+d)' % (table, old, new, new - old))
        shrink = source_shrink(before, after, table) if table in after['tables'] else None
        explained = bool(shrink) and old > 0 and (old - new) / old <= (shrink[1] - shrink[2]) / shrink[1] + LOSS_TOLERANCE
        if table in before['tables'] and (table not in after['tables'] or (old and new < old * (1 - LOSS_TOLERANCE))):
            if explained:
                result['warnings'].append('%s: %d -> %d rows, the Ankama source %s shrank too (%d -> %d)'
                                          % ((table, old, new) + shrink))
            else:
                result['errors'].append('%s: lost more than 3%% or table deleted (%d -> %d)' % (table, old, new))
        elif new < old:
            result['warnings'].append('%s: %d fewer rows' % (table, old - new))
    required = ('items', 'stats', 'stats_of_item', 'sets')
    if after['version'] != 'wakfu':
        required += ('weapon_hits', 'weapon_ap')
    for table in required:
        if not after['tables'].get(table):
            result['errors'].append('Essential table empty: ' + table)
    for table, ids in after['orphaned'].items():
        new_ids = set(ids) - set(before['orphaned'].get(table, []))
        if new_ids:
            result['errors'].append('%s: %d new references without an item' % (table, len(new_ids)))
    result['new_stats'] = sorted(after['stats'].keys() - before['stats'].keys())
    for key in result['new_stats']:
        result['warnings'].append('NEW STAT: %s (%s); check the calculation, weight and translations' % (key, after['stats'][key]['name']))
    for key in sorted(before['stats'].keys() - after['stats'].keys()):
        result['errors'].append('STAT GONE: ' + key)
    for key in sorted(after['stats'].keys() & before['stats'].keys()):
        if after['stats'][key] != before['stats'][key]:
            result['warnings'].append('Stat changed: %s: %s -> %s' % (key, before['stats'][key], after['stats'][key]))
    for item_id, old in before['items'].items():
        target = after['legacy_ids'].get(item_id, item_id)
        new = after['items'].get(target)
        if new is None or (old.get('ankama_id'), old.get('ankama_type')) != (new.get('ankama_id'), new.get('ankama_type')):
            result['errors'].append('Id lost or reassigned: %s (%s)' % (item_id, old['name']))
            result['items_removed'].append(old)
        elif old != new:
            result['items_changed'].append({'id': item_id, 'name': new['name'], 'before': old, 'after': new})
    result['items_hidden'] = [item_id for item_id, new in after['items'].items()
                              if new.get('removed') and not before['items'].get(item_id, {'removed': 1}).get('removed')]
    if result['items_hidden']:
        result['changes'].append('Items removed by Ankama, kept hidden: %d' % len(result['items_hidden']))
    result['items_added'] = [item for key, item in after['items'].items() if key not in before['items']]
    result['changes'].append('Items: +%d, -%d, %d changed' % (len(result['items_added']), len(result['items_removed']), len(result['items_changed'])))
    added = after['spells'].keys() - before['spells'].keys()
    removed = before['spells'].keys() - after['spells'].keys()
    changed = [key for key in after['spells'].keys() & before['spells'].keys() if after['spells'][key] != before['spells'][key]]
    result['spell_changes'] = {'added': sorted(added), 'removed': sorted(removed), 'changed': changed}
    result['changes'].append('Spells: +%d, -%d, %d changed' % (len(added), len(removed), len(changed)))
    if removed:
        result['warnings'].append('Spells removed: ' + ', '.join(sorted(removed)))
    old_images, new_images = before['images']['problems'], after['images']['problems']
    result['new_image_problems'] = {key: value for key, value in new_images.items() if key not in old_images or value['path'] != old_images[key]['path']}
    for key, image in result['new_image_problems'].items():
        if key not in old_images and before['images'].get('paths', {}).get(key) == image['path']:
            result['errors'].append('Existing image lost or unreadable: %s (%s)' % (key, image['path']))
    result['changes'].append('Missing or unreadable images: %d -> %d (%d new)' % (len(old_images), len(new_images), len(result['new_image_problems'])))
    if new_images:
        result['warnings'].append('%d missing or unreadable images; the exact list is in the inventory after the update' % len(new_images))
    return result
