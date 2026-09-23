"""Local inventories and recovery for update_all.py."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import shutil
import sqlite3
from data_file_ops import replace_file

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'fashionistapulp/fashionistapulp'
STATIC = ROOT / 'fashionsite/chardata/static'


def database_path(version):
    return DATA / ('items.db' if version == 'dofus3' else 'items_%s.db' % version)


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


def runtime_files(versions, images):
    files = {ROOT / 'fashionista_version.py', ROOT / 'fashionsite/chardata/dynamic_translations.py'}
    files.update(DATA.glob('dofus_constants*.py'))
    for version in versions:
        files.add(database_path(version))
        files.add(DATA / ('item_db_dumped.dump' if version == 'dofus3' else 'item_db_dumped_%s.dump' % version))
        for directory in ('spell_reference', 'spell_states'):
            files.add(ROOT / 'fashionsite/chardata' / directory / (version + '.json'))
    if 'wakfu' in versions:
        files.add(ROOT / 'itemscraper/transformed_wakfu.json')
    if images:
        for static in (STATIC, ROOT / 'fashionsite/staticfiles'):
            for directory in ('items', 'pets', 'resources', 'monsters', 'spells'):
                files.update(path for path in (static / 'chardata' / directory).rglob('*') if path.is_file())
    return files


def backup_runtime(versions, images, destination):
    manifest = {'versions': versions, 'images': images, 'files': {}}
    for path in sorted(runtime_files(versions, images)):
        relative = path.relative_to(ROOT).as_posix()
        manifest['files'][relative] = None
        if not path.exists():
            continue
        saved = destination / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == '.db':
            with readonly(path) as source, writable(saved) as target:
                source.backup(target)
        else:
            shutil.copy2(path, saved)
        manifest['files'][relative] = hashlib.sha256(saved.read_bytes()).hexdigest()
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def restore_runtime(manifest, source):
    for name, digest in manifest['files'].items():
        if digest and hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Sauvegarde altérée : ' + name)
    current = runtime_files(manifest['versions'], manifest['images'])
    for path in sorted(current, key=lambda path: (path.suffix not in ('.db', '.dump', '.py'), str(path))):
        relative = path.relative_to(ROOT).as_posix()
        digest = manifest['files'].get(relative)
        if digest is None:
            path.unlink(missing_ok=True)
        else:
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                continue
            temp = path.with_name(path.name + '.restore-tmp')
            shutil.copy2(source / relative, temp)
            replace_file(temp, path)
    for relative, digest in manifest['files'].items():
        path = ROOT / relative
        if digest and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, path)


def preserve_table(before, after, table):
    with readonly(before) as old, writable(after) as new:
        schema = old.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not schema:
            raise ValueError('Complément local absent : ' + table)
        rows = old.execute('SELECT * FROM ' + quoted(table)).fetchall()
        if table == 'mount_looks':
            current = {(ankama, name): item for item, ankama, name in new.execute('SELECT id, ankama_id, name FROM items')}
            old_items = {item: (ankama, name) for item, ankama, name in old.execute('SELECT id, ankama_id, name FROM items')}
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


def image_inventory(version, items, connection, tables):
    from fashionistapulp.fashionistapulp.fashion_util import normalize_name, safe_icon_name
    import re
    from PIL import Image

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
            try:
                with Image.open(STATIC / relative) as image:
                    image.verify()
                checked[relative] = None
            except (OSError, ValueError, SyntaxError) as exc:
                checked[relative] = str(exc)
        if checked[relative] is not None:
            problems[key] = {'path': relative, 'reason': checked[relative]}
    return {'references': len(expected), 'paths': expected, 'unique_files': len(checked), 'problems': problems}


def snapshot(version):
    path = database_path(version)
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
        dump = DATA / ('item_db_dumped.dump' if version == 'dofus3' else 'item_db_dumped_%s.dump' % version)
        dump_errors = []
        if not dump.exists():
            dump_errors.append('Dump absent : ' + str(dump))
        else:
            try:
                with writable(':memory:') as restored:
                    restored.executescript(dump.read_text(encoding='utf-8'))
                    for table in tables:
                        rows = restored.execute('SELECT COUNT(*) FROM ' + quoted(table)).fetchone()[0]
                        if rows != counts[table]:
                            dump_errors.append('%s : %d lignes en base, %d dans le dump' % (table, counts[table], rows))
            except (sqlite3.Error, UnicodeError) as exc:
                dump_errors.append(str(exc))
        return {'version': version, 'tables': counts, 'schema': tables, 'items': items,
                'stats': stats, 'spells': spells, 'legacy_ids': {str(k): str(v) for k, v in aliases.items()},
                'integrity': [row[0] for row in connection.execute('PRAGMA integrity_check')],
                'source_stats': vocabulary, 'dump_errors': dump_errors,
                'orphaned': orphaned, 'images': image_inventory(version, items, connection, tables)}


def compare(before, after):
    result = {'errors': [], 'warnings': [], 'changes': [], 'items_added': [], 'items_removed': [], 'items_changed': []}
    if after['integrity'] != ['ok']:
        result['errors'].append('SQLite : ' + '; '.join(after['integrity']))
    result['errors'].extend('Dump incohérent : ' + error for error in after.get('dump_errors', []))
    for name in sorted(after.get('source_stats', {}).keys() - before.get('source_stats', {}).keys()):
        result['warnings'].append('NOUVEL EFFET SOURCE : %s (%d objets), vérifier sa prise en compte' % (name, after['source_stats'][name]))
    for table in sorted(before['tables'].keys() | after['tables'].keys()):
        old, new = before['tables'].get(table, 0), after['tables'].get(table, 0)
        if new != old:
            result['changes'].append('%s : %d → %d lignes (%+d)' % (table, old, new, new - old))
        if table in before['tables'] and (table not in after['tables'] or (old and new < old * .97)):
            result['errors'].append('%s : perte de plus de 3 %% ou table supprimée (%d → %d)' % (table, old, new))
        elif new < old:
            result['warnings'].append('%s : %d lignes en moins' % (table, old - new))
    required = ('items', 'stats', 'stats_of_item', 'sets')
    if after['version'] != 'wakfu':
        required += ('weapon_hits', 'weapon_ap')
    for table in required:
        if not after['tables'].get(table):
            result['errors'].append('Table essentielle vide : ' + table)
    for table, ids in after['orphaned'].items():
        new_ids = set(ids) - set(before['orphaned'].get(table, []))
        if new_ids:
            result['errors'].append('%s : %d nouvelles références sans objet' % (table, len(new_ids)))
    for key in sorted(after['stats'].keys() - before['stats'].keys()):
        result['warnings'].append('NOUVELLE STAT : %s (%s) ; vérifier calcul, poids et traductions' % (key, after['stats'][key]['name']))
    for key in sorted(before['stats'].keys() - after['stats'].keys()):
        result['errors'].append('STAT DISPARUE : ' + key)
    for key in sorted(after['stats'].keys() & before['stats'].keys()):
        if after['stats'][key] != before['stats'][key]:
            result['warnings'].append('Stat modifiée : %s : %s → %s' % (key, before['stats'][key], after['stats'][key]))
    for item_id, old in before['items'].items():
        target = after['legacy_ids'].get(item_id, item_id)
        new = after['items'].get(target)
        if new is None or (old.get('ankama_id'), old.get('ankama_type')) != (new.get('ankama_id'), new.get('ankama_type')):
            result['errors'].append('Identifiant perdu ou réaffecté : %s (%s)' % (item_id, old['name']))
            result['items_removed'].append(old)
        elif old != new:
            result['items_changed'].append({'id': item_id, 'name': new['name'], 'before': old, 'after': new})
    result['items_added'] = [item for key, item in after['items'].items() if key not in before['items']]
    result['changes'].append('Objets : +%d, -%d, %d modifiés' % (len(result['items_added']), len(result['items_removed']), len(result['items_changed'])))
    added = after['spells'].keys() - before['spells'].keys()
    removed = before['spells'].keys() - after['spells'].keys()
    changed = [key for key in after['spells'].keys() & before['spells'].keys() if after['spells'][key] != before['spells'][key]]
    result['spell_changes'] = {'added': sorted(added), 'removed': sorted(removed), 'changed': changed}
    result['changes'].append('Sorts : +%d, -%d, %d modifiés' % (len(added), len(removed), len(changed)))
    if removed:
        result['warnings'].append('Sorts retirés : ' + ', '.join(sorted(removed)))
    old_images, new_images = before['images']['problems'], after['images']['problems']
    result['new_image_problems'] = {key: value for key, value in new_images.items() if key not in old_images or value['path'] != old_images[key]['path']}
    for key, image in result['new_image_problems'].items():
        if key not in old_images and before['images'].get('paths', {}).get(key) == image['path']:
            result['errors'].append('Image existante perdue ou illisible : %s (%s)' % (key, image['path']))
    result['changes'].append('Images absentes/illisibles : %d → %d (%d nouvelles)' % (len(old_images), len(new_images), len(result['new_image_problems'])))
    if new_images:
        result['warnings'].append('%d images absentes ou illisibles ; liste exacte dans l’inventaire après mise à jour' % len(new_images))
    return result
