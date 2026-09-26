"""Interactive data updates: py update_all.py [--list | --dry-run | --restore FOLDER | --clean-reports]."""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'itemscraper'))
import update_audit as audit  # noqa: E402

REPORTS = ROOT / '.update-reports'
VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu')
NAMES = dict(zip(VERSIONS, ('Dofus 3', 'Dofus 3 Beta', 'Dofus 2', 'Dofus Touch', 'Dofus Retro', 'Wakfu')))
PIPELINES = dict(zip(VERSIONS, ('update_data', 'update_data_beta',
                              'update_data_dofus2', 'update_data_touch',
                              'update_data_retro', 'update_data_wakfu')))
METADATA = dict(zip(VERSIONS[:5], ('FASHIONISTA_VERSION',
                    'FASHIONISTA_BETA_VERSION', 'FASHIONISTA_DOFUS2_VERSION',
                    'FASHIONISTA_TOUCH_VERSION', 'FASHIONISTA_RETRO_VERSION')))
WATCHED = {'touch': ('WATCHED_TOUCH_ASSETS',),
           'retro': ('WATCHED_RETRO_BUILD', 'WATCHED_RETRO_LANG',
                     'WATCHED_RETRO_ASSET_DIGEST', 'WATCHED_RETRO_ASSET_COUNT')}
APIS = {'dofus3': 'https://api.dofusdu.de/dofus3/v1/',
        'beta': 'https://api.dofusdu.de/dofus3beta/v1/',
        'dofus2': 'https://api.dofusdu.de/dofus2/'}
REPOS = {'dofus3': 'dofus3-main', 'beta': 'dofus3-beta', 'dofus2': 'dofus2-main'}
CYTRUS = 'https://cytrus.cdn.ankama.com/cytrus.json'
TOUCH = 'https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr'
TOUCH_CLIENT = 'https://dt-proxy-production-login.ankama-games.com/build/script.js'
WAKFU = 'https://wakfu.cdn.ankama.com/gamedata/config.json'
IMAGE_STEPS = {'item-images', 'resource-icons', 'monster-images',
               'monsters/artworks', 'spell-images', 'spell-icons', 'resize'}
LOCAL_TABLES = {'mount-looks': 'mount_looks', 'monster-grades': 'monster_grades',
                'monster-subareas': 'monster_subareas'}
NETWORK_STEP = re.compile(r'download|mirror|scrape|data/sets|data/spells|data/mounts|images|icons|artworks')
RETRY_DELAY = 20
PIPELINE_TIMEOUT = 4 * 3600
IMPORTED = 'IMPORTED'
PARTLY_IMPORTED = 'PARTLY IMPORTED'
FAILED = 'FAILED'
RESTORED = 'FAILED, RESTORED'
RESTORE_INCOMPLETE = 'RESTORE INCOMPLETE'
LEGACY_RESTORE_INCOMPLETE = 'RESTAURATION INCOMPL'
NOT_STARTED = 'NOT STARTED'
INTERRUPTED = 'INTERRUPTED'
RUNNING = 'RUNNING'
REVIEW = 'TESTS TO REVIEW'
ERRORS = 'ERRORS'
HOLDERS = 'the dev server, DB Browser or the image viewer (or wait for the antivirus scan to finish)'
CHECK_TITLES = {'generation': 'Build generation', 'weapons': 'Weapon check',
                'django': 'Full Django suite'}
PROGRESS_PREFIX = '[progress] '
HEARTBEAT_SECONDS = 30
IMAGE_SECONDS_PER_FILE = .005
DISK_MARGIN = 1.2
KEPT_IMAGE_BACKUPS = 3
MARKER = re.compile(r'update_all pid=(\d+) (\S+)(?: (?:run|restore)=(.+))?')
STEP_TITLES = {
    'items/download': 'Downloading items', 'data/download': 'Downloading data',
    'data/mirror': 'Copying the Wakfu data', 'data/sets': 'Set names',
    'data/spells': 'Downloading spells', 'data/mounts': 'Downloading mounts',
    'lang/download': 'Downloading languages',
    'items/transform': 'Transforming items', 'items/dump': 'Creating the SQL dump',
    'items/load-db': 'Loading the database', 'items/build-db': 'Building the database',
    'items/obtainment': 'Ways to obtain items', 'items/corrections': 'Item corrections',
    'items/recipes': 'Saving recipes', 'items/special-spells': 'Special item spells',
    'items/spells': 'Saving spells', 'item-skins': 'Item appearances',
    'item-images': 'Equipment images', 'resource-icons': 'Resource images',
    'monster-images': 'Monster images', 'monsters/artworks': 'Monster artwork',
    'spell-images': 'Spell images', 'spell-icons': 'Spell icons', 'resize': 'Resizing images',
    'mount-looks': 'Mount appearances', 'monster-grades': 'Monster grades',
    'monster-subareas': 'Monster subareas', 'monster-spells': 'Monster spells',
    'monsters/grades': 'Monster grades', 'monsters/subareas': 'Monster subareas',
    'monsters/subarea-langs': 'Subarea names',
    'spells/download': 'Downloading spells', 'spells/transform': 'Transforming spells',
    'spells/duplicates': 'Duplicate damage rows', 'spells/build': 'Building spells',
    'spells/reference': 'Spell reference', 'spells/states': 'Spell states',
    'spells/constants': 'Spell statistics', 'spells/tooltips': 'Spell effects on items',
    'spells/modifiers': 'Spell modifiers on items',
    'spells/decode': 'Decoding spells', 'spells/d2o-tables': 'Client spell tables',
    'drops/transform': 'Transforming drops', 'drops/store': 'Saving drops',
    'craftjobs/transform': 'Transforming professions', 'craftjobs/store': 'Saving professions',
    'craftjobs/jobs-table': 'Profession table', 'recipes/store': 'Saving recipes',
    'pets/scrape': 'Reading pets', 'pets/store': 'Saving pets',
    'pets/scrape-bonuses': 'Reading pet bonuses',
    'pets/store-bonuses': 'Saving pet bonuses',
    'sets/bonuses': 'Set bonuses', 'descriptions/store': 'Item descriptions',
    'stats/starting': 'Starting stats',
    'dynamic-translations': 'Data translations', 'verify/rebuild': 'Rebuild check',
}


def step_title(label):
    match = re.fullmatch(r'(data/spells) (\w+)|(lang/download)-(\w+)', label)
    if match:
        base, language = (match[1], match[2]) if match[1] else (match[3], match[4])
        return '%s (%s)' % (STEP_TITLES[base], language)
    return STEP_TITLES.get(label, label)


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def fetch_json(url):
    headers = {'User-Agent': 'DofusFashionista data updater', 'Accept': 'application/json'}
    if url.startswith('https://api.github.com/') and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def read_metadata():
    tree = ast.parse((ROOT / 'fashionista_version.py').read_text(encoding='utf-8'))
    return {node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)}


def touch_build_version():
    request = urllib.request.Request(TOUCH_CLIENT, headers={
        'User-Agent': 'DofusFashionista data updater',
        'Range': 'bytes=0-65535', 'Cache-Control': 'no-cache',
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        script = response.read(65536).decode('utf-8', errors='replace')
    builds = set(re.findall(r'\bwindow\.buildVersion\s*=\s*[\'"](\d+\.\d+\.\d+)[\'"]', script))
    if len(builds) != 1:
        raise ValueError('Touch build missing or ambiguous in the production client: ' + TOUCH_CLIENT)
    return builds.pop()


def retro_game_version(build):
    raw = build.split('_')[-1]
    match = re.fullmatch(r'(\d+\.\d+\.\d+)(?:\.\d+)*(?:-[a-zA-Z0-9]+)?', raw)
    if not match:
        raise ValueError('Invalid Retro build: ' + build)
    return match.group(1)


def set_game_versions(rows):
    from update_data import set_patch_started
    path = ROOT / 'fashionista_version.py'
    content = path.read_text(encoding='utf-8')
    ours = read_metadata()
    for row in rows:
        key = row['key']
        if key not in METADATA:
            continue
        version = row['available']
        pattern = r'\d+(?:\.\d+){2,4}' if key in APIS else r'\d+\.\d+\.\d+'
        if not re.fullmatch(pattern, version):
            raise ValueError('Invalid game version: ' + version)
        name = METADATA[key]
        old = ours[name]
        content, count = re.subn(r'(?m)^(' + name + r'[ \t]*=[ \t]*)[\'"][^\'"\r\n]+[\'"]',
                                lambda m: m[1] + json.dumps(version), content)
        if count != 1:
            raise ValueError('Version constant missing or ambiguous: ' + name)
        if old.split('.')[:2] != version.split('.')[:2]:
            patch = '.'.join(version.split('.')[:2])
            updated = set_patch_started(content, key, patch, quiet=True)
            if updated == content:
                progress('%s: no PATCH_TIMELINE entry, add it by hand' % NAMES[key])
            else:
                progress('%s: start of patch %s noted in PATCH_TIMELINE' % (NAMES[key], patch))
            content = updated
        content = set_watched_sources(content, row)
    if content != path.read_text(encoding='utf-8'):
        path.write_text(content, encoding='utf-8')


def constant_pattern(name):
    """A NAME = value line, or a NAME = {...} block closed at column 0."""
    return r'(?ms)^(%s[ \t]*=[ \t]*)(\{.*?^\}|[^\r\n]+)' % name


def replace_constant(content, name, literal):
    return re.sub(constant_pattern(name), lambda m: m[1] + literal, content, count=1)


def transplant_constant(content, saved, name):
    value = re.search(constant_pattern(name), saved)
    if value and re.search(constant_pattern(name), content):
        content = replace_constant(content, name, value[2])
    return content


def set_watched_sources(content, row):
    """The version watch compares against these: they name the source just imported."""
    source = row.get('source') or {}
    if row['key'] == 'touch' and source.get('assets'):
        content = replace_constant(content, 'WATCHED_TOUCH_ASSETS', json.dumps(source['assets']))
    if row['key'] == 'retro':
        if source.get('build'):
            content = replace_constant(content, 'WATCHED_RETRO_BUILD', json.dumps(source['build']))
        served = (source.get('languages') or {}).get('fr') or {}
        watched = read_metadata().get('WATCHED_RETRO_LANG') or {}
        if served and all(name in served for name in watched):
            lines = ["    '%s': '%s'," % (name, served[name]) for name in watched]
            content = replace_constant(content, 'WATCHED_RETRO_LANG', '{\n' + '\n'.join(lines) + '\n}')
        if row.get('images') and source.get('image_digest'):
            content = replace_constant(content, 'WATCHED_RETRO_ASSET_DIGEST', json.dumps(source['image_digest']))
            content = replace_constant(content, 'WATCHED_RETRO_ASSET_COUNT', str(source['image_count']))
    return content


def transplant_label(content, saved, key):
    name = METADATA.get(key)
    if not name:
        return content
    for constant in [name] + list(WATCHED.get(key, ())):
        content = transplant_constant(content, saved, constant)
    block = r"(PATCH_TIMELINE\s*=\s*\{.*?'%s'\s*:\s*\[)(.*?)(\n[ \t]*\],)" % key
    old_block = re.search(block, saved, re.S)
    if old_block:
        content = re.sub(block, lambda m: m[1] + old_block[2] + m[3], content, count=1, flags=re.S)
    return content


def restore_label(key, backup):
    saved = backup / 'fashionista_version.py'
    path = ROOT / 'fashionista_version.py'
    if key not in METADATA or not saved.is_file() or not path.is_file():
        return []
    content = path.read_text(encoding='utf-8')
    updated = transplant_label(content, saved.read_text(encoding='utf-8'), key)
    if updated != content:
        try:
            path.write_text(updated, encoding='utf-8')
        except OSError:
            return ['fashionista_version.py']
    return []


def probe(version, catalog=None):
    ours = read_metadata()
    state = read_json(REPORTS / 'state.json', {})
    result = {'key': version, 'current': ours.get(METADATA.get(version), '?'),
              'available': None, 'official': None, 'source': {}, 'warnings': [],
              'error': None, 'changed': False}
    if version in APIS:
        api = fetch_json(APIS[version] + 'meta/version')
        tag = api['version']
        if not re.fullmatch(r'\d+(?:\.\d+){2,4}', tag):
            raise ValueError('Invalid data version: %r' % tag)
        current = result['current']
        if re.fullmatch(r'\d+(?:\.\d+){2,4}', current) and tuple(map(int, tag.split('.'))) < tuple(map(int, current.split('.'))):
            raise ValueError('Source older than the local version: %s < %s; downgrade refused.' % (tag, current))
        release = fetch_json('https://api.github.com/repos/dofusdude/%s/releases/tags/%s'
                             % (REPOS[version], tag))
        assets = {a['name'] for a in release['assets']}
        needed = {'spells.json', 'effects.json', 'breeds.json', 'monsters.json',
                  'recipes.json', 'en.json', 'fr.json', 'es.json', 'pt.json', 'de.json'}
        if release.get('draft') or needed - assets:
            raise ValueError('Incomplete archive: ' + ', '.join(sorted(needed - assets)))
        result['available'] = tag
        result['source'] = {'version': tag, 'update_stamp': api.get('update_stamp'),
                            'archive': release['tag_name']}
        channel = {'dofus3': 'dofus3', 'beta': 'beta', 'dofus2': 'main'}[version]
        catalog = catalog or fetch_json(CYTRUS)
        result['official'] = catalog['games']['dofus']['platforms']['windows'][channel].split('_')[-1]
        if result['official'] != tag:
            result['warnings'].append('The Ankama client and the importable data differ.')
        result['changed'] = result['current'] != tag
    elif version == 'touch':
        config = fetch_json(TOUCH)
        assets = config['assetsUrl'].rstrip('/').rsplit('/', 1)[-1]
        build = touch_build_version()
        result['available'] = result['official'] = build
        result['source'] = {'build': build, 'assets': assets, 'languages': sorted(config['serverLanguages']),
                            'data_url': config['dataUrl']}
        previous = state.get(version, {}).get('source', {})
        result['current_data'] = previous.get('assets', ours['WATCHED_TOUCH_ASSETS'])
        result['changed'] = (result['current'] != build or assets != result['current_data']
                             or any(previous.get(field) != result['source'][field]
                                    for field in ('build', 'languages', 'data_url')))
    elif version == 'retro':
        from download_retro_langs import fetch_manifest
        from check_game_versions import retro_asset_entries, retro_asset_digest
        catalog = catalog or fetch_json(CYTRUS)
        build = catalog['games']['retro']['platforms']['windows']['main']
        languages = {lang: fetch_manifest(lang) for lang in ('fr', 'en', 'es', 'pt', 'de')}
        for lang, entries in languages.items():
            if not {'items', 'itemstats', 'itemsets', 'crafts', 'classes', 'effects', 'spells'} <= entries.keys():
                raise ValueError('Incomplete Retro manifest: ' + lang)
        entries = retro_asset_entries(version=build)
        if not entries:
            raise ValueError('Retro manifest without any known image')
        result['available'] = retro_game_version(build)
        result['official'] = result['available']
        result['source'] = {'build': build.split('_')[-1], 'languages': languages,
                            'image_digest': retro_asset_digest(entries), 'image_count': len(entries)}
        previous = state.get(version, {}).get('source')
        result['current_data'] = (previous or {}).get('build', ours['WATCHED_RETRO_BUILD'])
        result['changed'] = result['current'] != result['available'] or (previous != result['source'] if previous else
            any(languages['fr'].get(k) != str(v) for k, v in ours['WATCHED_RETRO_LANG'].items())
            or result['source']['image_digest'] != ours['WATCHED_RETRO_ASSET_DIGEST'])
    else:
        tag = fetch_json(WAKFU)['version']
        local = read_json(ROOT / 'itemscraper/transformed_wakfu.json', {})
        result.update(current=local.get('version', 'absent'), available=tag,
                      official=tag, source={'version': tag})
        result['changed'] = result['current'] != tag
    if version in ('touch', 'retro'):
        if tuple(map(int, result['available'].split('.'))) < tuple(map(int, result['current'].split('.'))):
            raise ValueError('Source older than the local version: downgrade refused.')
    return result


def discover():
    rows = []
    try:
        catalog = fetch_json(CYTRUS)
    except Exception:
        catalog = None
    for key in VERSIONS:
        print('Checking for updates: ' + NAMES[key], flush=True)
        try:
            row = probe(key, catalog)
        except Exception as exc:
            row = {'key': key, 'current': read_metadata().get(METADATA.get(key), '?'),
                   'available': None, 'official': None, 'source': {}, 'changed': False,
                   'warnings': [], 'error': str(exc)}
        rows.append(row)
    return rows


def show_versions(rows):
    for row in rows:
        number = VERSIONS.index(row['key']) + 1
        print('\n%d. %s (local version: %s)' % (number, NAMES[row['key']], row['current']))
        for line in version_details(row, console=True):
            print('   ' + line)
        print('   ' + (row['error'] or ('Update found' if row['changed'] else 'No change found')))
        for warning in row['warnings']:
            print('   To check: ' + warning)


def version_details(row, console=False):
    source = row.get('source', {})
    if row['key'] == 'touch':
        lines = ['Game build available: ' + (row['available'] or 'unavailable'),
                 'CDN assets: %s -> %s' % (row.get('current_data', '?'), source.get('assets', '?'))]
        if console:
            lines.append("The installed app's version number is not the game build.")
        return lines
    if row['key'] == 'retro':
        return ['Game version available: ' + (row['available'] or 'unavailable'),
                'Cytrus technical id: %s -> %s' % (row.get('current_data', '?'), source.get('build', '?'))]
    return ['Importable data: %s | Ankama client: %s' % (row['available'] or 'unavailable', row['official'] or '?')]


def selection(text, rows):
    tokens = text.lower().replace(',', ' ').split()
    keys = []
    for token in tokens:
        if token in ('all', 'tout'):
            keys.extend(row['key'] for row in rows if not row['error'] and row['key'] != 'wakfu')
        elif token in ('changed', 'nouveau'):
            keys.extend(row['key'] for row in rows if row['changed'] and not row['error'] and row['key'] != 'wakfu')
        elif token.isdigit() and 1 <= int(token) <= len(VERSIONS):
            keys.append(VERSIONS[int(token) - 1])
        elif token in VERSIONS:
            keys.append(token)
        else:
            raise ValueError('Unknown choice: ' + token)
    by_key = {r['key']: r for r in rows}
    for key in keys:
        if by_key[key]['error']:
            raise ValueError('%s: source unavailable, cannot update' % NAMES[key])
    return [key for key in VERSIONS if key in keys]


def restore_keys(text):
    keys = []
    for token in text.lower().replace(',', ' ').split():
        if token.isdigit() and 1 <= int(token) <= len(VERSIONS):
            keys.append(VERSIONS[int(token) - 1])
        elif token in VERSIONS:
            keys.append(token)
        else:
            raise ValueError('Unknown choice: ' + token)
    return [key for key in VERSIONS if key in keys]


def environment(django=False):
    env = os.environ.copy()
    paths = (ROOT, ROOT / 'fashionistapulp', ROOT / 'fashionsite') if django else (ROOT,)
    env['PYTHONPATH'] = os.pathsep.join(map(str, paths))
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    flash = Path.home() / 'Documents/fashionista-loop/tools/flash'
    candidates = {'JAVA_EXE': sorted(flash.glob('jdk-*-jre/bin/java.exe')),
                  'FFDEC_JAR': [flash / 'ffdec/ffdec.jar'],
                  'RESVG_EXE': [flash / 'resvg/resvg.exe']}
    for name, paths in candidates.items():
        if not env.get(name):
            available = next((path for path in paths if path.is_file()), None)
            if available:
                env[name] = str(available)
    return env


def progress(message):
    print(PROGRESS_PREFIX + message, flush=True)


@contextlib.contextmanager
def phase(title):
    started = time.monotonic()
    stopped = threading.Event()
    def heartbeat():
        while not stopped.wait(HEARTBEAT_SECONDS):
            progress('%s: running (%.0f s)' % (title, time.monotonic() - started))
    progress(title + '...')
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    completed = False
    try:
        yield
        completed = True
    finally:
        stopped.set()
        thread.join()
        progress('%s: %s (%.1f s)' % (title, 'done' if completed else 'interrupted', time.monotonic() - started))


def failure_detail(log):
    with log.open('rb') as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - 8192))
        lines = handle.read().decode('utf-8', errors='replace').splitlines()
    useful = [line.strip() for line in lines if line.strip()]
    return useful[-1][:500] if useful else 'No detail in the log.'


def run_command(command, log, cwd=ROOT, timeout=3600, *, django=False, title=None, relay_progress=False):
    started = time.monotonic()
    title = title or log.stem
    progress(title + '...')
    with log.open('w', encoding='utf-8') as output, log.open('r', encoding='utf-8', errors='replace') as reader:
        output.write('Command: ' + subprocess.list2cmdline(list(map(str, command))) + '\n')
        output.flush()
        process = subprocess.Popen(command, cwd=cwd, env=environment(django), stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
        pending = ''
        last_progress = started
        def relay(final=False):
            nonlocal pending, last_progress
            if not relay_progress:
                return
            while chunk := reader.read(65536):
                lines = (pending + chunk).split('\n')
                pending = lines.pop()
                for line in lines:
                    if line.startswith(PROGRESS_PREFIX):
                        print(line.rstrip(), flush=True)
                        last_progress = time.monotonic()
            if final and pending.startswith(PROGRESS_PREFIX):
                print(pending.rstrip(), flush=True)
                pending = ''
        try:
            while process.poll() is None:
                relay()
                now = time.monotonic()
                if now - started > timeout:
                    raise TimeoutError('Timed out (%d s): %s' % (timeout, title))
                if now - last_progress >= HEARTBEAT_SECONDS + (2 if relay_progress else 0):
                    progress('%s: running (%.0f s)' % (title, now - started))
                    last_progress = now
                try:
                    process.wait(timeout=.25 if relay_progress else min(HEARTBEAT_SECONDS, 1))
                except subprocess.TimeoutExpired:
                    pass
        except BaseException:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            else:
                import signal
                os.killpg(process.pid, signal.SIGTERM)
            process.wait()
            raise
        finally:
            relay(final=True)
    result = {'command': list(map(str, command)), 'exit_code': process.returncode,
              'seconds': round(time.monotonic() - started, 1), 'log': str(log)}
    if process.returncode:
        result['error'] = failure_detail(log)
    return result


@contextlib.contextmanager
def update_guard():
    with (ROOT / '.update-data.guard').open('a+b') as handle:
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise FileExistsError('Another update holds the lock; wait for it to finish.') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def process_snapshot():
    if os.name == 'nt':
        command = ['$ErrorActionPreference="Stop";',
                   '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;',
                   'Get-CimInstance Win32_Process |',
                   'Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress']
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ' '.join(command)],
                                capture_output=True, encoding='utf-8-sig', check=True, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        rows = json.loads(result.stdout)
        return [{'pid': row['ProcessId'], 'parent': row['ParentProcessId'],
                 'name': row['Name'], 'command': row['CommandLine'] or ''}
                for row in (rows if isinstance(rows, list) else [rows])]
    result = subprocess.run(['ps', '-eo', 'pid=,ppid=,comm=,args='], capture_output=True,
                            encoding='utf-8', check=True, timeout=30)
    return [{'pid': int(pid), 'parent': int(parent), 'name': name, 'command': command}
            for line in result.stdout.splitlines() for pid, parent, name, command in [line.strip().split(None, 3)]]


def abandoned_marker(marker):
    match = MARKER.fullmatch(marker.strip())
    if not match:
        raise RuntimeError('Unrecognized lock, kept for checking: ' + marker.strip())
    rows = process_snapshot()
    if not rows or not any(row['pid'] == os.getpid() for row in rows):
        raise RuntimeError('Incomplete process list; lock kept.')
    ancestors = {os.getpid()}
    parents = {row['pid']: row['parent'] for row in rows}
    current = os.getpid()
    while parents.get(current) and parents[current] not in ancestors:
        current = parents[current]
        ancestors.add(current)
    scripts = {p.name.lower() for p in (ROOT / 'itemscraper').glob('*.py')}
    scripts.update(name + '.py' for name in PIPELINES.values())
    scripts.update(('update_all.py', 'manage.py', 'check_version_weapon_data.py'))
    for row in rows:
        if row['pid'] in ancestors:
            continue
        name, command = row['name'].lower(), row['command'].lower()
        shown = (row['command'] or row['name'])[:160]
        if 'python' in name or name in ('py.exe', 'py'):
            tokens = re.split(r'[\s"\'/\\]+', command)
            # A worker of the dead launcher names one of these; an unreadable command line is another user's
            if (scripts.intersection(tokens) or 'multiprocessing.spawn' in command
                    or 'itemscraper.' in command):
                raise RuntimeError('A Python program from the repository is still running (pid %d: %s). Close it '
                                   '(the dev server included), then run update_all.py again; '
                                   'lock kept.' % (row['pid'], shown))
        if 'cbc' in name or ('java' in name and str(ROOT).lower().replace('\\', '/') in command.replace('\\', '/')):
            raise RuntimeError('A solver or an image job is still running (pid %d: %s). Wait for it to finish '
                               'or close it, then run update_all.py again; lock kept.'
                               % (row['pid'], shown))
    return match[3]


def remove_running_marker(running_file, marker):
    if running_file.exists():
        lines = running_file.read_text(encoding='utf-8').splitlines()
        running_file.write_text('\n'.join(line for line in lines if line.strip() != marker.strip()).rstrip() + '\n', encoding='utf-8')


def running_section(text, running_file):
    heading = re.search(r'(?m)^## En cours[ \t]*$', text)
    if not heading:
        raise RuntimeError('No "## En cours" section in ' + str(running_file))
    start = heading.end()
    following = re.search(r'(?m)^## ', text[start:])
    return start, start + following.start() if following else len(text)


@contextlib.contextmanager
def exclusive(running_file, tag=None):
    with update_guard():
        with exclusive_marker(running_file, tag):
            yield


@contextlib.contextmanager
def exclusive_marker(running_file, tag=None):
    lock = ROOT / '.update-data.lock'
    if lock.exists():
        previous = lock.read_text(encoding='utf-8')
        directory = abandoned_marker(previous)
        remove_running_marker(running_file, previous)
        lock.unlink()
        print('Recovered an abandoned lock: ' + previous.strip(), flush=True)
        if directory:
            print('The previous run stopped before the end, backups kept: ' + directory, flush=True)
    marker = 'update_all pid=%d %s' % (os.getpid(), datetime.now().astimezone().isoformat())
    if tag:
        marker += ' ' + tag
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(marker)
    registered = False
    try:
        if running_file.exists():
            text = running_file.read_text(encoding='utf-8')
            start, end = running_section(text, running_file)
            active = [line.strip() for line in text[start:end].splitlines()
                      if line.strip() and line.strip() != '(rien)']
            for line in list(active):
                if line.startswith('update_all pid='):
                    abandoned_marker(line)
                    remove_running_marker(running_file, line)
                    active.remove(line)
                    print('Recovered an abandoned marker: ' + line, flush=True)
            if active:
                raise RuntimeError('Exclusive work already running: ' + '; '.join(active))
            text = running_file.read_text(encoding='utf-8')
            start, end = running_section(text, running_file)
            rest = text[end:]
            text = text[:end].rstrip('\n') + '\n' + marker + '\n' + ('\n' + rest if rest else '')
            running_file.write_text(text, encoding='utf-8')
            registered = True
        yield
    finally:
        try:
            if registered:
                remove_running_marker(running_file, marker)
        finally:
            lock.unlink()


def job_command(key, label, command, job):
    command = list(command)
    if label == 'spells/build' and key == 'touch' and not job['images']:
        command.append('--skip-images')
    if label == 'spells/download':
        command.append('--no-skip-existing')
    if key == 'wakfu' and label.startswith('data/spells') and '--version' not in command:
        command += ['--version', job['available']]
    return command


def attempt_step(label, command, cwd, log, timeout, title):
    started = time.monotonic()
    try:
        result = run_command(command, log, cwd, timeout, title=title)
    except Exception as exc:
        result = {'exit_code': 1, 'log': str(log), 'seconds': round(time.monotonic() - started, 1),
                  'error': str(exc), 'command': list(map(str, command)),
                  'timed_out': isinstance(exc, TimeoutError)}
    result['step'] = label
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines() if log.exists() else []
    silent_errors = [line for line in lines if re.search(
        r'Failed to retrieve|parse skipped|\bFAILED\b|Traceback \(most recent call last\)', line)]
    if silent_errors:
        result['exit_code'] = result['exit_code'] or 1
        result['silent_errors'] = silent_errors[:30]
        result.setdefault('error', failure_detail(log) if any('Traceback (' in line for line in silent_errors)
                          else silent_errors[-1].strip())
    if result['exit_code']:
        result.setdefault('error', failure_detail(log) if log.exists() else 'Command not started.')
    result['notices'] = log_notices(lines)
    return result, lines


def run_pipeline_step(label, command, cwd, log, timeout, title):
    result, lines = attempt_step(label, command, cwd, log, timeout, title)
    if not result['exit_code'] or not NETWORK_STEP.search(label) or result.get('timed_out'):
        return result, lines
    first = log.with_name(log.stem + '.attempt-1.log')
    if log.exists():
        os.replace(log, first)
    progress('%s: failed (%s), trying again in %d s' % (title, result['error'], RETRY_DELAY))
    time.sleep(RETRY_DELAY)
    retry, lines = attempt_step(label, command, cwd, log, timeout, title)
    retry['retried'] = {'error': result['error'], 'log': str(first)}
    with log.open('a', encoding='utf-8') as handle:
        handle.write('\nSecond attempt. The first one failed: %s (log %s)\n' % (result['error'], first.name))
    return retry, lines


def worker(job_path):
    job = read_json(job_path)
    key = job['key']
    module = importlib.import_module(PIPELINES[key])
    setter = {'dofus3': 'set_version', 'beta': 'set_beta_version', 'dofus2': 'set_dofus2_version'}.get(key)
    if setter:
        setattr(module, setter, lambda version: version)
    report_dir = job_path.parent
    sequence = []

    def record(entry):
        sequence.append(entry)
        write_json(report_dir / (key + '-steps.json'), sequence)

    def kept_locally(label, message):
        record({'step': label, 'exit_code': 0, 'warning': message, 'kept': True})
        return True, [message]

    def step(label, command, cwd=None):
        number = len(sequence) + 1
        title = '%s | %02d | %s' % (NAMES[key], number, step_title(label))
        if not job['images'] and label in IMAGE_STEPS:
            return True, []
        if label == 'monster-images' and key in ('dofus3', 'beta'):
            progress(title + ': kept, not refreshed')
            return kept_locally(label, 'Monster artwork kept, not refreshed (DofusDB API disabled).')
        if label in LOCAL_TABLES and key in ('dofus3', 'beta'):
            table = LOCAL_TABLES[label]
            database = audit.database_path(key)
            with phase(title):
                audit.preserve_table(report_dir / key / audit.relative_name(database), database, table)
            return kept_locally(label, '%s: kept from the local database, not refreshed (DofusDB disabled).' % table)
        if any('dofusdb' in str(part).lower() for part in command):
            raise RuntimeError('DofusDB step not allowed: ' + label)
        if label == 'verify/rebuild':
            return True, []
        command = job_command(key, label, command, job)
        log = report_dir / ('%s-%02d-%s.log' % (key, number, label.replace('/', '-')))
        result, lines = run_pipeline_step(label, command, cwd or ROOT, log, job['timeout'], title)
        record(result)
        if result['exit_code']:
            progress(title + ': ' + FAILED + ': ' + result['error'])
            raise RuntimeError('Step failed: %s: %s; log %s' % (step_title(label), result['error'], log))
        progress('%s: OK (%.1f s)' % (title, result.get('seconds', 0)))
        return True, lines

    module.run_step = step
    args = [module.__file__]
    if key in APIS:
        args += ['--version', job['available']]
    if not job['images']:
        args += ['--skip-images']
    sys.argv = args
    if module.main():
        raise RuntimeError('Import of %s failed' % NAMES[key])


def log_notices(lines):
    return list(dict.fromkeys(line.strip() for line in lines
        if re.search(r'warning|attention|unknown|unmapped|unresolved|missing translation|unsupported|not found', line, re.I)
        and not re.search(r'\b(?:0|no) (?:unresolved|missing|unknown|unmapped|warnings?)\b|Spaces are not permitted', line, re.I)))


def held_open_on_windows(path):
    import ctypes
    generic_read, open_existing, sharing_violation = 0x80000000, 3, 32
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateFileW.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                     ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    # An idle sqlite connection holds no lock but its open handle still makes os.replace fail.
    handle = kernel32.CreateFileW(str(path), generic_read, 0, None, open_existing, 0, None)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        return ctypes.get_last_error() == sharing_violation
    kernel32.CloseHandle(handle)
    return False


def database_in_use(path):
    if os.name == 'nt' and held_open_on_windows(path):
        return True
    connection = sqlite3.connect(path, timeout=0, isolation_level=None)
    try:
        connection.execute('BEGIN EXCLUSIVE')
        connection.execute('ROLLBACK')
    except sqlite3.OperationalError:
        return True
    finally:
        connection.close()
    return False


def busy_databases(keys):
    paths = [audit.database_path(key) for key in keys]
    return [path for path in paths if path.exists() and database_in_use(path)]


def refuse_busy_databases(keys):
    busy = busy_databases(keys)
    if busy:
        raise RuntimeError('Database open in another program: %s. Close %s, then run again.'
                           % (', '.join(map(str, busy)), HOLDERS))


def importing_path(directory, key):
    return Path(directory) / (key + '.importing')


def pending_imports():
    pending = {}
    for marker in sorted(REPORTS.glob('*/*.importing')):
        if marker.stem in VERSIONS:
            pending.setdefault(marker.parent, set()).add(marker.stem)
    return {directory: [key for key in VERSIONS if key in keys] for directory, keys in pending.items()}


def pending_import_lines(pending):
    return ['%s: import stopped halfway (%s), data half written. Run this first: %s'
            % (', '.join(NAMES[key] for key in keys), directory, restore_command(directory, keys))
            for directory, keys in pending.items()]


def refuse_pending_imports():
    lines = pending_import_lines(pending_imports())
    if lines:
        raise RuntimeError('; '.join(lines))


def size_text(size):
    for unit, factor in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if size >= factor:
            return '%.1f %s' % (size / factor, unit)
    return '%d bytes' % size


def count_text(number):
    return '{:,}'.format(number)


def files_text(number):
    return '1 file' if number == 1 else count_text(number) + ' files'


def image_estimate():
    files, size = audit.image_backup_size()
    minutes = max(1, math.ceil(files * IMAGE_SECONDS_PER_FILE / 60))
    return files, size, minutes


def refuse_small_disk(size, directory):
    needed = int(size * DISK_MARGIN)
    free = shutil.disk_usage(directory).free
    if free < needed:
        raise RuntimeError('Not enough disk space for the image backup: %s needed, %s free. '
                           'Free some space (py update_all.py --clean-reports) or choose no images.'
                           % (size_text(needed), size_text(free)))


def folder_size(path):
    files, total, stack = 0, 0, [path]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    files += 1
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return files, total


def pipeline_timeout(args):
    return max(PIPELINE_TIMEOUT, args.step_timeout)


def imported_rows(report):
    return [row for row in report.get('versions', []) if row.get('status') == IMPORTED]


def digest_or_none(path):
    return audit.file_digest(path) if path.is_file() else None


def shared_digests():
    return {audit.relative_name(path): audit.file_digest(path) for path in audit.shared_files() if path.is_file()}


def save_state(row, directory):
    state = read_json(REPORTS / 'state.json', {})
    applied = dict(row['source'])
    if row['key'] == 'retro' and not row['images']:
        previous = state.get('retro', {}).get('source', {})
        metadata = read_metadata()
        applied['image_digest'] = previous.get('image_digest', metadata['WATCHED_RETRO_ASSET_DIGEST'])
        applied['image_count'] = previous.get('image_count', metadata['WATCHED_RETRO_ASSET_COUNT'])
    state[row['key']] = {'source': applied, 'images': row['images'], 'report': str(directory)}
    write_json(REPORTS / 'state.json', state)


def revert_state(run, key):
    previous = read_json(run['directory'] / 'state-before.json', {})
    state = read_json(REPORTS / 'state.json', {})
    if key in previous:
        state[key] = previous[key]
    else:
        state.pop(key, None)
    write_json(REPORTS / 'state.json', state)


def prepare_version(run, row):
    key, directory = row['key'], run['directory']
    name = NAMES[key]
    with phase(name + ': checking the source'):
        fresh = probe(key)
    if fresh['source'] != row['source']:
        raise RuntimeError('the source changed since it was chosen; run update_all.py again.')
    with phase(name + ': inventory before the import (data, dumps and images)'):
        before = audit.snapshot(key)
    write_json(directory / (key + '-before.json'), before)
    with phase(name + ': backing up the data'):
        manifest = audit.backup_runtime([key], False, directory / key)
        tracked = audit.record_tracked(directory / key, exclude=audit.manifest_names(manifest))
    if tracked is None and (ROOT / '.git').exists():
        row['warnings'].append('intermediate files tracked by git not backed up: git unavailable.')
    row['backup'] = str(directory / key)
    return before


def inspect_version(run, row, before):
    key = row['key']
    try:
        with phase(NAMES[key] + ': inventory after the import (data, dumps and images)'):
            after = audit.snapshot(key)
        write_json(run['directory'] / (key + '-after.json'), after)
        row['diff'] = audit.compare(before, after)
    except Exception as exc:
        return 'inventory after the import failed: %s' % exc
    for change in row['diff'].get('changes', []):
        if change.startswith(('Items:', 'Spells:', 'Missing or unreadable images:')):
            progress(NAMES[key] + ': ' + change)
    return None


def check_source_after(row):
    key = row['key']
    try:
        with phase(NAMES[key] + ': final source check'):
            source = probe(key)['source']
    except Exception as exc:
        row['warnings'].append('final source check failed: %s' % exc)
        return None
    if source != row['source']:
        return 'the source changed during the download, the data may be mixed.'
    return None


def run_version(run, row, before):
    key, directory = row['key'], run['directory']
    job_path = directory / (key + '-job.json')
    write_json(job_path, dict(row, timeout=run['args'].step_timeout))
    log = directory / (key + '-pipeline.log')
    try:
        result = run_command([sys.executable, str(Path(__file__)), '--worker', str(job_path)], log,
                             timeout=pipeline_timeout(run['args']), title=NAMES[key] + ': import',
                             relay_progress=True)
    except Exception as exc:
        result = {'exit_code': 1, 'log': str(log), 'error': str(exc)}
    row['steps'] = read_json(directory / (key + '-steps.json'), [])
    if result['exit_code']:
        failed = next((step for step in row['steps'] if step['exit_code']), result)
        title = step_title(failed['step']) if failed.get('step') else 'Import'
        return '%s: %s; log %s' % (title, failed.get('error', 'command failed'),
                                        failed.get('log', result['log']))
    cause = inspect_version(run, row, before) or check_source_after(row)
    if cause:
        return cause
    errors = row['diff']['errors']
    if errors:
        return 'data checks failed (%d): %s' % (len(errors), errors[0])
    return None


def publish_version(row, directory):
    try:
        set_game_versions([row])
        save_state(row, directory)
    except Exception as exc:
        return 'could not write the version: %s' % exc
    return None


def repair_images(run, row, before):
    manifest = run['image_manifest']
    if not manifest or not before:
        return []
    names = audit.backed_up_images(audit.lost_images(before), manifest)
    row['images_restored'] = names
    if not names:
        return []
    return audit.restore_runtime(manifest, run['directory'] / 'images', only=names)


def restore_version(run, row, before):
    key = row['key']
    backup = run['directory'] / key
    row['unrestored'] = []
    row['status'] = RESTORE_INCOMPLETE
    try:
        with phase(NAMES[key] + ': restoring the version'):
            row['unrestored'] += audit.restore_runtime(read_json(backup / 'manifest.json'), backup)
            row['unrestored'] += audit.restore_tracked(backup)[0]
            row['unrestored'] += repair_images(run, row, before)
    except KeyboardInterrupt:
        row['restore_error'] = 'restore interrupted by Ctrl+C'
        raise
    except Exception as exc:
        row['restore_error'] = str(exc)
        return
    if not row['unrestored']:
        row['status'] = RESTORED


def import_version(run, key):
    chosen = next(row for row in run['rows'] if row['key'] == key)
    row = dict(chosen, images=run['images'][key], steps=[], warnings=list(chosen.get('warnings', [])),
               status=NOT_STARTED)
    run['report']['versions'].append(row)
    try:
        before = prepare_version(run, row)
    except Exception as exc:
        row['cause'] = str(exc)
        progress('%s: %s' % (NAMES[key], row['cause']))
        return row
    marker = importing_path(run['directory'], key)
    marker.write_text('update_all pid=%d\n' % os.getpid(), encoding='utf-8')
    try:
        try:
            cause = run_version(run, row, before) or publish_version(row, run['directory'])
        except KeyboardInterrupt:
            row['cause'] = 'interrupted by Ctrl+C during the import.'
            restore_version(run, row, before)
            raise
        except Exception as exc:
            cause = 'launcher error: %s' % exc
        if cause:
            row['cause'] = cause
            progress('%s: failed, restoring (%s)' % (NAMES[key], cause))
            restore_version(run, row, before)
            progress('%s: %s' % (NAMES[key], row['status']))
            return row
        row['status'] = IMPORTED
        row['shared_after'] = shared_digests()
        audit.record_tracked_after(run['directory'] / key)
        progress(NAMES[key] + ': imported')
        return row
    finally:
        if row['status'] in (IMPORTED, RESTORED):
            marker.unlink(missing_ok=True)


def stop_after(run, remaining, key):
    for rest in remaining:
        chosen = next(row for row in run['rows'] if row['key'] == rest)
        run['report']['versions'].append(dict(
            chosen, images=run['images'][rest], steps=[], warnings=list(chosen.get('warnings', [])),
            status=NOT_STARTED, cause='the restore of %s is incomplete: finish it before any other import.'
            % NAMES[key]))
        progress('%s: not started, the restore of %s is incomplete' % (NAMES[rest], NAMES[key]))


def restore_under_later(directory, key, shared_after):
    backup = directory / key
    manifest = read_json(backup / 'manifest.json')
    own = {audit.relative_name(path) for path in audit.version_files(key)}
    shared = audit.manifest_names(manifest) - own - {'fashionista_version.py'}
    unrestored = audit.restore_runtime(manifest, backup, only=own)
    kept = []
    for name in sorted(shared):
        before, after = manifest['files'].get(name), shared_after.get(name, 'unknown')
        current = digest_or_none(ROOT / name)
        if before == after or current == before:
            continue
        if current == after:
            unrestored += audit.restore_runtime(manifest, backup, only=[name])
        else:
            kept.append(name)
    unrestored += restore_label(key, backup)
    tracked_unrestored, tracked_kept = audit.restore_tracked(backup)
    return unrestored + tracked_unrestored, kept + tracked_kept


def restore_late(run, row):
    key = row['key']
    marker = importing_path(run['directory'], key)
    marker.write_text('update_all pid=%d\n' % os.getpid(), encoding='utf-8')
    row['status'] = RESTORE_INCOMPLETE
    row['unrestored'], row['kept_shared'] = restore_under_later(run['directory'], key, row.get('shared_after', {}))
    revert_state(run, key)
    row['unrestored'] += repair_images(run, row, read_json(run['directory'] / (key + '-before.json')))
    if not row['unrestored']:
        row['status'] = RESTORED
        marker.unlink(missing_ok=True)


def failing_tests(log):
    if not log.exists():
        return []
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    return list(dict.fromkeys(line.strip() for line in lines if line.startswith(('FAIL: ', 'ERROR: '))))


def failing_version(test):
    match = re.search(r"\(version='(\w+)'\)", test)
    if match:
        return match[1]
    if 'TheWakfuSolverObeysTheGameTests' in test:
        return 'wakfu'
    return None


def short_test_name(line):
    match = re.match(r'(?:FAIL|ERROR): (\w+) \(([\w.]+)\)(.*)', line)
    if not match:
        return line
    parts = match[2].split('.')
    owner = parts[-2] if len(parts) > 1 and parts[-1] == match[1] else parts[-1]
    return '%s.%s%s' % (owner, match[1], match[3])


def restore_unbuildable(run, check):
    broken = {failing_version(test) for test in check['failures']}
    restored = []
    for row in reversed(imported_rows(run['report'])):
        if row['key'] not in broken:
            continue
        row['cause'] = ('build generation fails with this data: the site can no longer generate a build;'
                        ' log ' + check['log'])
        progress('%s: cannot generate builds, restoring the version' % NAMES[row['key']])
        try:
            with phase(NAMES[row['key']] + ': restoring the version'):
                restore_late(run, row)
        except Exception as exc:
            row['status'] = RESTORE_INCOMPLETE
            row['restore_error'] = str(exc)
        restored.append(row['key'])
    return restored


def run_check(run, name, command, log, title):
    try:
        result = run_command(command, log, timeout=run['args'].step_timeout,
                             django=name in ('generation', 'django'), title=title)
    except Exception as exc:
        result = {'exit_code': 1, 'log': str(log), 'seconds': 0, 'error': str(exc)}
    result['name'] = name
    result['failures'] = failing_tests(log) if result['exit_code'] else []
    progress('%s: %s (%.1f s)' % (title, FAILED if result['exit_code'] else 'OK', result.get('seconds', 0)))
    return result


def validate(run, keys):
    for name, command in validation_commands(keys):
        title = CHECK_TITLES[name]
        result = run_check(run, name, command, run['directory'] / (name + '.log'), title)
        run['report']['checks'].append(result)
        if name == 'generation' and result['exit_code']:
            result['restored'] = restore_unbuildable(run, result)
            if result['restored']:
                again = run_check(run, name, command, run['directory'] / 'generation-after-restore.log',
                                  title + ' after the restore')
                result['after_restore'] = {field: again[field] for field in
                                           ('exit_code', 'log', 'seconds', 'failures', 'error') if field in again}


def remaining_failures(check):
    again = check.get('after_restore')
    if again is not None:
        return again['failures']
    restored = set(check.get('restored', []))
    return [test for test in check['failures'] if failing_version(test) not in restored]


def needs_review(check):
    if not check['exit_code']:
        return False
    again = check.get('after_restore')
    if again is not None:
        return bool(again['exit_code'])
    return not check['failures'] or bool(remaining_failures(check))


def checks_to_review(report):
    return [check for check in report['checks'] if needs_review(check)]


def inventory_other_versions(keys, directory):
    inventories = {}
    for key in VERSIONS:
        if key in keys or not audit.database_path(key).exists():
            continue
        try:
            with phase('Inventory of shared images: ' + NAMES[key]):
                inventories[key] = audit.snapshot(key)
        except Exception as exc:
            progress('%s: image inventory failed (%s)' % (NAMES[key], exc))
            continue
        write_json(directory / (key + '-before.json'), inventories[key])
    return inventories


def repair_other_versions(run, inventories):
    for key, before in inventories.items():
        try:
            with phase('Checking shared images: ' + NAMES[key]):
                lost = audit.lost_images(before)
                names = audit.backed_up_images(lost, run['image_manifest'])
                unrestored = audit.restore_runtime(run['image_manifest'], run['directory'] / 'images', only=names)
        except Exception as exc:
            run['report']['warnings'].append('shared images of %s not checked: %s' % (NAMES[key], exc))
            continue
        run['report']['shared_images'][key] = {'lost': lost, 'restored': sorted(set(names) - set(unrestored)),
                                               'unrestored': unrestored}


def record_changed_images(run):
    if not run['image_manifest']:
        return
    try:
        with phase('Listing changed images'):
            names = audit.changed_files(run['image_manifest'], run['directory'] / 'images')
    except Exception as exc:
        run['report']['warnings'].append('could not list the changed images: %s' % exc)
        return
    write_json(run['directory'] / 'images-changed.json', names)
    run['report']['images_changed'] = len(names)


def all_unrestored(report):
    names = []
    for row in report['versions']:
        names += row.get('unrestored', [])
    for images in report.get('shared_images', {}).values():
        names += images['unrestored']
    return sorted(set(names))


def restore_incomplete(report):
    return bool(all_unrestored(report)) or any(row.get('status') == RESTORE_INCOMPLETE for row in report['versions'])


def keys_to_finish(report):
    keys = {row['key'] for row in report['versions'] if row.get('status') == RESTORE_INCOMPLETE or row.get('unrestored')}
    keys.update(key for key, images in report.get('shared_images', {}).items() if images['unrestored'])
    return [key for key in VERSIONS if key in keys]


def overall_status(report):
    rows = report['versions']
    imported = imported_rows(report)
    if report.get('interrupted'):
        status = INTERRUPTED
    elif not imported:
        status = FAILED
    elif len(imported) < len(rows):
        status = PARTLY_IMPORTED
    else:
        status = IMPORTED
    if imported and checks_to_review(report):
        status += ', ' + REVIEW
    if imported and report['errors'] and not report.get('interrupted'):
        status += ', ' + ERRORS
    if restore_incomplete(report):
        status += ', ' + RESTORE_INCOMPLETE
    return status


def exit_code(report):
    if report.get('interrupted'):
        return 130
    rows = report['versions']
    if report['errors'] or not rows or len(imported_rows(report)) < len(rows) or restore_incomplete(report):
        return 1
    return 2 if checks_to_review(report) else 0


def restore_command(directory, keys=None):
    command = 'py update_all.py --restore "%s"' % directory
    if keys:
        command += ' --versions ' + ','.join(keys)
    return command


def warned_steps(steps):
    names = []
    for step in steps:
        if step.get('kept'):
            continue
        count = len(step.get('notices', [])) + (1 if step.get('warning') else 0)
        if count:
            names.append(step_title(step['step']) + (' (%d)' % count if count > 1 else ''))
    return names


def kept_steps(steps):
    return list(dict.fromkeys(step_title(step['step']) for step in steps if step.get('kept')))


def diff_lines(diff):
    spells = diff.get('spell_changes', {})
    problems = diff.get('new_image_problems', {})
    items = (len(diff.get('items_added', [])), len(diff.get('items_removed', [])), len(diff.get('items_changed', [])))
    spell_counts = (len(spells.get('added', [])), len(spells.get('removed', [])), len(spells.get('changed', [])))
    lines, unchanged = [], []
    if any(items):
        lines.append('- Items: +%d, -%d, %d changed' % items)
    else:
        unchanged.append('items')
    if diff.get('items_hidden'):
        lines.append('- Items removed by Ankama, kept hidden for saved builds: %d'
                     % len(diff['items_hidden']))
    if any(spell_counts):
        lines.append('- Spells: +%d, -%d, %d changed' % spell_counts)
    else:
        unchanged.append('spells')
    if diff.get('new_stats'):
        lines.append('- New stats: ' + ', '.join(diff['new_stats']))
    else:
        unchanged.append('stats')
    if problems:
        lines.append('- New image problems: %d' % len(problems))
        lines += ['  - %s: `%s`' % (key, image['path']) for key, image in list(problems.items())[:10]]
    else:
        unchanged.append('images')
    if unchanged:
        lines.append('- No change: ' + ', '.join(unchanged))
    lines += ['- Blocking: ' + error for error in diff.get('errors', [])[:10]]
    review = [warning for warning in diff.get('warnings', [])
              if not warning.startswith('NEW STAT') and 'missing or unreadable images' not in warning]
    lines += ['- To check: ' + warning for warning in review[:10]]
    return lines


def version_block(row):
    lines = ['## %s: %s' % (NAMES[row['key']], row.get('status', NOT_STARTED)), '',
             '- Version: %s -> %s, images: %s' % (row.get('current', '?'), row.get('available', '?'),
                                                  'yes' if row.get('images') else 'no')]
    if row['key'] in ('touch', 'retro'):
        lines += ['- ' + detail for detail in version_details(row)]
    if row.get('cause'):
        lines.append('- Cause: ' + row['cause'])
    if row.get('restore_error'):
        lines.append('- Restore stopped: ' + row['restore_error'])
    if row.get('diff') and row.get('status') == IMPORTED:
        lines += diff_lines(row['diff'])
    elif row.get('diff'):
        lines += ['- Blocking: ' + error for error in row['diff'].get('errors', [])[:10]]
    lines += ['- To check: ' + warning for warning in row.get('warnings', [])]
    kept = kept_steps(row.get('steps', []))
    if kept:
        lines.append('- Kept from local data, not refreshed (DofusDB disabled): ' + ', '.join(kept))
    warned = warned_steps(row.get('steps', []))
    if warned:
        lines.append('- Steps with warnings: ' + ', '.join(warned))
    retried = [step_title(step['step']) for step in row.get('steps', [])
               if step.get('retried') and not step.get('exit_code')]
    if retried:
        lines.append('- Steps that passed on the second attempt: ' + ', '.join(retried))
    if row.get('images_restored'):
        lines.append('- Lost images put back from the backup: %d' % len(row['images_restored']))
    if row.get('kept_shared'):
        lines.append('- Files kept, also changed by a later version: ' + ', '.join(row['kept_shared']))
    return lines


def tests_block(report):
    lines = ['## Tests', '']
    if not report.get('checks'):
        if not imported_rows(report):
            reason = ': no version imported.'
        elif restore_incomplete(report):
            reason = ': a restore is incomplete, finish it first.'
        else:
            reason = '.'
        return lines + ['Tests not run' + reason]
    for check in report['checks']:
        title = CHECK_TITLES[check['name']]
        if not check['exit_code']:
            lines.append('- %s: OK (%.0f s)' % (title, check.get('seconds', 0)))
            continue
        lines.append('- %s: %s, log `%s`' % (title, FAILED, check['log']))
        if check.get('restored'):
            lines.append('  - Restored versions: ' + ', '.join(NAMES[key] for key in check['restored']))
        again = check.get('after_restore')
        if again is not None and again['exit_code']:
            lines.append('  - New check after the restore: %s, log `%s`' % (FAILED, again['log']))
            lines += ['    - `%s`' % test for test in again['failures'][:50]]
            if not again['failures']:
                lines.append('    - Cause: ' + again.get('error', 'see the log'))
        elif again is not None:
            lines.append('  - New check after the restore: OK')
        lines += ['  - `%s`' % test for test in check['failures'][:50]]
        if not check['failures']:
            lines.append('  - Cause: ' + check.get('error', 'see the log'))
    return lines


def report_markdown(report):
    lines = ['# ' + report['status'], '', 'Folder: `%s`' % report['directory'], '']
    if report.get('images_changed') is not None:
        lines += ['New, changed or deleted images: %d' % report['images_changed'], '']
    for row in report.get('versions', []):
        lines += version_block(row) + ['']
    lines += tests_block(report) + ['']
    for key, images in report.get('shared_images', {}).items():
        if images['lost']:
            lines.append('Shared images of %s lost: %d, put back: %d' % (NAMES[key], len(images['lost']),
                                                                         len(images['restored'])))
    if report.get('errors'):
        lines += ['## Errors', ''] + ['- ' + error for error in report['errors']] + ['']
    if report.get('warnings'):
        lines += ['## To check', ''] + ['- ' + warning for warning in report['warnings']] + ['']
    if restore_incomplete(report):
        lines += ['## Restore to finish', '']
        unrestored = all_unrestored(report)
        if unrestored:
            lines += ['Files not restored:', ''] + ['- `%s`' % name for name in unrestored] + ['']
        lines += ['Close %s, then run: `%s`' % (HOLDERS, restore_command(report['directory'],
                                                                         keys_to_finish(report))), '']
    if imported_rows(report):
        lines.append('To undo this update: `%s`' % restore_command(report['directory']))
    return '\n'.join(lines) + '\n'


def check_summary(check):
    title = CHECK_TITLES[check['name']]
    again = check.get('after_restore')
    failures = remaining_failures(check)
    log = again['log'] if again is not None else check['log']
    if not failures:
        error = (again or check).get('error', 'see the log')
        return '%s: %s, %s; log %s' % (title, FAILED, error, log)
    shown = ', '.join(short_test_name(test) for test in failures[:3])
    more = ' and %d more' % (len(failures) - 3) if len(failures) > 3 else ''
    count = '1 failing test' if len(failures) == 1 else '%d failing tests' % len(failures)
    return '%s: %s (%s%s); log %s' % (title, count, shown, more, log)


def print_summary(report, directory):
    print('\n%s\nSummary: %s' % (report['status'], directory / 'RECAP.md'), flush=True)
    for row in report['versions']:
        if row.get('status') != IMPORTED:
            print('%s: %s' % (NAMES[row['key']], row.get('status', NOT_STARTED)))
            print('  Cause: %s' % row.get('cause', '?'))
            if row.get('restore_error'):
                print('  Restore stopped: ' + row['restore_error'])
    for error in report['errors']:
        print('Cause: ' + error)
    for check in checks_to_review(report):
        print(check_summary(check))
    if restore_incomplete(report):
        unrestored = all_unrestored(report)
        if unrestored:
            print('Files not restored: ' + ', '.join(unrestored))
        print('Close %s, then run: %s' % (HOLDERS, restore_command(directory, keys_to_finish(report))), flush=True)


def interrupt(report, message='Interrupted by Ctrl+C.'):
    report['interrupted'] = True
    if message not in report['errors']:
        report['errors'].append(message)


def write_report(report, directory):
    report['status'] = overall_status(report)
    try:
        write_json(directory / 'report.json', report)
    finally:
        try:
            (directory / 'RECAP.md').write_text(report_markdown(report), encoding='utf-8')
        finally:
            print_summary(report, directory)


def finish(run, locks):
    report = run['report']
    try:
        if not report.get('interrupted'):
            record_changed_images(run)
    except KeyboardInterrupt:
        interrupt(report)
    finally:
        try:
            try:
                locks.close()
            except KeyboardInterrupt:
                interrupt(report, 'Interrupted while releasing the lock.')
            except Exception as exc:
                report['errors'].append('Lock cleanup: ' + str(exc))
        finally:
            write_report(report, run['directory'])


def execute(rows, keys, images, args):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '-%d' % os.getpid()
    directory = REPORTS / stamp
    directory.mkdir(parents=True)
    report = {'status': RUNNING, 'directory': str(directory), 'versions': [], 'checks': [],
              'errors': [], 'warnings': [], 'shared_images': {}}
    run = {'directory': directory, 'report': report, 'rows': rows, 'images': images, 'args': args,
           'image_manifest': None}
    locks = contextlib.ExitStack()
    try:
        locks.enter_context(exclusive(args.running_file, 'run=%s' % directory))
        check_configuration()
        if not (ROOT / 'fashionsite/fashionsite/settings_test.py').exists():
            raise RuntimeError('settings_test.py is missing: set up SQLite for the tests, see the README.')
        refuse_pending_imports()
        refuse_busy_databases(keys)
        print('Logs and backups: ' + str(directory), flush=True)
        write_json(directory / 'state-before.json', read_json(REPORTS / 'state.json', {}))
        others = {}
        if any(images.values()):
            files, size, minutes = image_estimate()
            refuse_small_disk(size, directory)
            with phase('Backing up images (%s, %s, about %d min)'
                       % (files_text(files), size_text(size), minutes)):
                run['image_manifest'] = audit.backup_runtime([], True, directory / 'images', shared=False)
            others = inventory_other_versions(keys, directory)
        for position, key in enumerate(keys, 1):
            progress('Version %d/%d: %s' % (position, len(keys), NAMES[key]))
            row = import_version(run, key)
            if row['status'] == RESTORE_INCOMPLETE:
                stop_after(run, keys[position:], key)
                break
        repair_other_versions(run, others)
        if imported_rows(report) and not restore_incomplete(report):
            validate(run, keys)
    except KeyboardInterrupt:
        interrupt(report)
    except Exception as exc:
        report['errors'].append(str(exc))
    finally:
        finish(run, locks)
    return exit_code(report)


def restore_run_images(directory):
    manifest = read_json(directory / 'images/manifest.json')
    names = read_json(directory / 'images-changed.json')
    if names is None:
        with phase('Finding changed images'):
            names = audit.changed_files(manifest, directory / 'images')
    with phase('Restoring %d images' % len(names)):
        return audit.restore_runtime(manifest, directory / 'images', only=names)


def written_by(entry, directory):
    source = (entry or {}).get('report')
    return bool(source) and Path(source).resolve() == directory


def restore_run_state(directory, keys, force=False):
    previous = read_json(directory / 'state-before.json')
    if previous is None or not keys:
        return
    state = read_json(REPORTS / 'state.json', {})
    for key in keys:
        if not force and not written_by(state.get(key), directory):
            continue
        if key in previous:
            state[key] = previous[key]
        else:
            state.pop(key, None)
    write_json(REPORTS / 'state.json', state)


def run_is_newer(other, directory):
    stamp = re.compile(r'\d{8}T\d{6}')
    if stamp.match(other.name) and stamp.match(directory.name):
        return other.name > directory.name
    if not other.exists():
        return True
    return other.stat().st_mtime > directory.stat().st_mtime


def newer_imports(directory, keys):
    state = read_json(REPORTS / 'state.json', {})
    found = []
    for key in keys:
        source = (state.get(key) or {}).get('report')
        if source and not written_by(state[key], directory) and run_is_newer(Path(source).resolve(), directory):
            found.append((key, source))
    return found


def imported_in_run(directory):
    state = read_json(REPORTS / 'state.json', {})
    return [key for key in VERSIONS if written_by(state.get(key), directory)]


def restore_key(directory, key, scoped):
    backup = directory / key
    manifest = read_json(backup / 'manifest.json')
    unrestored, kept = [], []
    if manifest is not None:
        later = [other for other in imported_in_run(directory)
                 if scoped and other not in scoped and VERSIONS.index(other) > VERSIONS.index(key)]
        if later:
            rows = {row['key']: row for row in (read_json(directory / 'report.json') or {}).get('versions', [])}
            unrestored, kept = restore_under_later(directory, key, rows.get(key, {}).get('shared_after', {}))
        else:
            unrestored = audit.restore_runtime(manifest, backup)
            unrestored += audit.restore_tracked(backup)[0]
    before = read_json(directory / (key + '-before.json'))
    image_manifest = read_json(directory / 'images/manifest.json')
    if scoped and before and image_manifest:
        names = audit.backed_up_images(audit.lost_images(before), image_manifest)
        unrestored += audit.restore_runtime(image_manifest, directory / 'images', only=names)
    return unrestored, kept


def restore_run(directory, running_file, versions=None, force=False):
    directory = Path(directory).resolve()
    available = [key for key in VERSIONS if (directory / key / 'manifest.json').exists()]
    legacy = directory / 'backup/manifest.json'
    images = directory / 'images/manifest.json'
    if versions:
        missing = [key for key in versions
                   if key not in available and not (directory / (key + '-before.json')).exists()]
        if missing:
            print('No backup of %s in %s' % (', '.join(NAMES[key] for key in missing), directory))
            return 1
        keys = list(versions)
    else:
        keys = available
        if not keys and not legacy.exists() and not images.exists():
            print('No backup in ' + str(directory))
            return 1
    # Shared files and images span every version, so any newer import counts
    newer = newer_imports(directory, VERSIONS)
    if newer and not force:
        for key, other in newer:
            print('%s: a newer run imported this version: %s' % (NAMES[key], other))
        print('Undo the newest run first, or add --force to overwrite its data.')
        return 1
    by_key, kept, restored, whole = {}, [], [], []
    with exclusive(running_file, 'restore=%s' % directory):
        try:
            for key in reversed(keys):
                with phase('Restoring: ' + NAMES[key]):
                    by_key[key], more = restore_key(directory, key, versions)
                if key in available:
                    restored.append(key)
                kept += more
                if not by_key[key]:
                    importing_path(directory, key).unlink(missing_ok=True)
            if not versions and legacy.exists():
                with phase('Restoring the full backup'):
                    whole += audit.restore_runtime(read_json(legacy), legacy.parent)
            if not versions and images.exists():
                whole += restore_run_images(directory)
        finally:
            restore_run_state(directory, restored, force)
    unrestored = sorted(set(whole + [name for names in by_key.values() for name in names]))
    if kept:
        print('Files kept, also changed by a newer version: ' + ', '.join(sorted(set(kept))))
    if unrestored:
        print('Files not restored:')
        for name in unrestored:
            print('  ' + name)
        unfinished = None if whole else [key for key in VERSIONS if by_key.get(key)]
        print('Close %s, then run again: %s' % (HOLDERS, restore_command(directory, unfinished)))
        return 1
    print('Restore finished: ' + str(directory))
    return 0


def image_backup_paths(directory):
    candidates = [directory / 'images', directory / 'backup/fashionsite/chardata/static',
                  directory / 'backup/fashionsite/staticfiles']
    return [path for path in candidates if path.is_dir()]


def image_backups():
    found = []
    for directory in REPORTS.iterdir() if REPORTS.is_dir() else []:
        paths = image_backup_paths(directory)
        manifests = [path for path in (directory / 'images/manifest.json', directory / 'backup/manifest.json')
                     if path.is_file()]
        if paths and manifests:
            found.append((max(path.stat().st_mtime for path in manifests), directory, paths))
    return [(directory, paths) for _, directory, paths in sorted(found, key=lambda entry: entry[0], reverse=True)]


def restore_pending(directory):
    if any(directory.glob('*.importing')):
        return True
    try:
        report = read_json(directory / 'report.json') or {}
    except (OSError, ValueError):
        return True
    status = str(report.get('status', ''))
    return RESTORE_INCOMPLETE in status or LEGACY_RESTORE_INCOMPLETE in status


def clean_reports():
    backups = image_backups()
    old = [(directory, paths) for directory, paths in backups[KEPT_IMAGE_BACKUPS:] if not restore_pending(directory)]
    pending = [directory for directory, _ in backups[KEPT_IMAGE_BACKUPS:] if restore_pending(directory)]
    for directory in pending:
        print('Kept, restore unfinished: ' + str(directory))
    if not old:
        print('No image backup to delete: the %d most recent are kept.' % KEPT_IMAGE_BACKUPS)
        return 0
    total = 0
    print('Image backups older than the last %d:' % KEPT_IMAGE_BACKUPS)
    for directory, paths in old:
        files, size = map(sum, zip(*(folder_size(path) for path in paths)))
        total += size
        print('  %s: %s, %s' % (directory, files_text(files), size_text(size)))
    try:
        answer = input('Delete these %d image backups (%s)? Type yes to confirm: '
                       % (len(old), size_text(total)))
    except EOFError:
        answer = ''
    if answer.strip().lower() not in ('yes', 'oui'):
        print('Nothing deleted.')
        return 0
    with update_guard():
        for directory, paths in old:
            for path in paths:
                shutil.rmtree(path)
            print('Deleted: images of ' + str(directory))
    return 0


def validation_commands(keys):
    base = [sys.executable, 'fashionsite/manage.py', 'test']
    flags = ['--settings=fashionsite.settings_test', '--noinput']
    smoke = ['chardata.tests_update_generation.UpdateGenerationTests']
    if 'wakfu' in keys:
        smoke += ['chardata.tests.TheWakfuSolverObeysTheGameTests']
    return [('generation', base + smoke + flags),
            ('weapons', [sys.executable, 'check_version_weapon_data.py']),
            ('django', base + ['chardata'] + flags)]


def check_configuration():
    if os.name == 'nt':
        config = Path(os.environ.get('APPDATA', '')) / 'fashionista/config'
    else:
        config = Path('/etc/fashionista/config')
    if config.exists() and Path(config.read_text().strip()).resolve() != ROOT:
        raise RuntimeError('The path in %s points to another repository; fix it before updating.' % config)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Guided data update, backed up and checked.')
    parser.add_argument('--list', action='store_true', help='show the versions without writing anything')
    parser.add_argument('--dry-run', action='store_true', help='show the choices and checks without changing any data')
    parser.add_argument('--versions', help='names or numbers separated by commas; all, changed; Wakfu only when named')
    parser.add_argument('--images', choices=('yes', 'no'), help='download the images or keep the local ones')
    parser.add_argument('--yes', action='store_true', help='run the explicit choices without asking')
    parser.add_argument('--step-timeout', type=int, default=3600, help='longest time for one step, in seconds')
    parser.add_argument('--restore', type=Path, metavar='FOLDER',
                        help='undo a run, or only the versions given with --versions')
    parser.add_argument('--force', action='store_true',
                        help='with --restore: restore even if a newer run imported these versions')
    parser.add_argument('--clean-reports', action='store_true',
                        help='delete the image backups of old runs, after confirmation')
    parser.add_argument('--running-file', type=Path, default=Path.home() / 'Documents/fashionista-loop/RUNNING.md')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        worker(args.worker)
        return 0
    if args.clean_reports:
        return clean_reports()
    if args.restore:
        try:
            versions = restore_keys(args.versions) if args.versions else None
            return restore_run(args.restore, args.running_file, versions, args.force)
        except Exception as exc:
            print('Restore failed: %s' % exc)
            return 1
    if args.yes and (not args.versions or not args.images):
        parser.error('--yes needs --versions and --images')
    if args.step_timeout <= 0:
        parser.error('--step-timeout must be positive')
    rows = discover()
    show_versions(rows)
    if args.list:
        files, size = folder_size(REPORTS) if REPORTS.is_dir() else (0, 0)
        print('\nBackups and logs in %s: %s (%s)' % (REPORTS, size_text(size), files_text(files)))
        return 1 if any(row['error'] for row in rows) else 0
    while True:
        choice = args.versions if args.versions is not None else input(
            '\nWhich versions? (1,4; all; changed; Enter to quit): ')
        try:
            keys = selection(choice, rows)
            break
        except ValueError as exc:
            if args.versions is not None:
                parser.error(str(exc))
            print(exc)
    if not keys:
        return 0
    images = {}
    for key in keys:
        answer = args.images
        while answer is None:
            raw = input('%s: download the images? [Y/n]: ' % NAMES[key]).strip().lower()
            answer = 'yes' if raw in ('', 'o', 'oui', 'y', 'yes') else 'no' if raw in ('n', 'non', 'no') else None
        images[key] = answer == 'yes'
    print('\nChoice: ' + ', '.join('%s (%s images)' % (NAMES[key], 'with' if images[key] else 'without') for key in keys))
    print('For each version: backup, import, inventory. A failure restores that version and moves on to the next.')
    print('Then: build generation, weapon check, Django suite. If build generation fails for a version,'
          ' that version is restored; other failing tests keep the data.')
    if args.dry_run:
        for line in pending_import_lines(pending_imports()):
            print('Refusing to start until this is done: ' + line)
        for path in busy_databases(keys):
            print('Database open in another program, the launch will be refused: %s' % path)
        if any(images.values()):
            files, size, minutes = image_estimate()
            free = shutil.disk_usage(REPORTS if REPORTS.is_dir() else ROOT).free
            print('Image backup: %s, %s, about %d min; %s free on the disk.'
                  % (files_text(files), size_text(size), minutes, size_text(free)))
            if free < size * DISK_MARGIN:
                print('Not enough disk space: a launch with images will be refused.')
        for name, command in validation_commands(keys):
            print('%s: %s' % (CHECK_TITLES[name], subprocess.list2cmdline(command)))
        return 0
    if not args.yes and input('Start? [y/N]: ').strip().lower() not in ('y', 'yes', 'o', 'oui'):
        return 0
    return execute(rows, keys, images, args)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.')
        raise SystemExit(130)
