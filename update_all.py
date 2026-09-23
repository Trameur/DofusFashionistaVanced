"""Interactive data updates: python update_all.py [--list | --dry-run]."""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'itemscraper'))
REPORTS = ROOT / '.update-reports'
VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu')
LABELS = ('Dofus 3', 'Beta', 'Dofus 2', 'Touch', 'Retro', 'Wakfu (expérimental)')
PIPELINES = dict(zip(VERSIONS, ('update_data', 'update_data_beta',
                              'update_data_dofus2', 'update_data_touch',
                              'update_data_retro', 'update_data_wakfu')))
METADATA = dict(zip(VERSIONS[:5], ('FASHIONISTA_VERSION',
                    'FASHIONISTA_BETA_VERSION', 'FASHIONISTA_DOFUS2_VERSION',
                    'FASHIONISTA_TOUCH_VERSION', 'FASHIONISTA_RETRO_VERSION')))
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
PROGRESS_PREFIX = '[suivi] '
HEARTBEAT_SECONDS = 30
STEP_TITLES = {
    'items/download': 'Téléchargement des objets', 'data/download': 'Téléchargement des données',
    'items/transform': 'Transformation des objets', 'items/dump': 'Création du dump SQL',
    'items/load-db': 'Chargement de la base', 'items/build-db': 'Construction de la base',
    'items/obtainment': "Moyens d'obtention", 'items/corrections': 'Corrections des objets',
    'item-images': 'Images des équipements', 'resource-icons': 'Images des ressources',
    'monster-images': 'Images des monstres', 'monsters/artworks': 'Images des monstres',
    'spell-images': 'Images des sorts', 'spell-icons': 'Images des sorts', 'resize': 'Redimensionnement des images',
    'spells/download': 'Téléchargement des sorts', 'spells/transform': 'Transformation des sorts',
    'spells/build': 'Construction des sorts', 'spells/reference': 'Référentiel des sorts',
    'spells/constants': 'Statistiques des sorts', 'spells/tooltips': 'Effets des sorts sur les objets',
    'drops/transform': 'Transformation des butins', 'drops/store': 'Enregistrement des butins',
    'dynamic-translations': 'Traductions des données', 'data/mounts': 'Téléchargement des montures',
}


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
        raise ValueError('Build Touch absent ou ambigu dans le client de production : ' + TOUCH_CLIENT)
    return builds.pop()


def retro_game_version(build):
    raw = build.split('_')[-1]
    match = re.fullmatch(r'(\d+\.\d+\.\d+)(?:\.\d+)*(?:-[a-zA-Z0-9]+)?', raw)
    if not match:
        raise ValueError('Build Retro invalide : ' + build)
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
            raise ValueError('Version de jeu invalide : ' + version)
        name = METADATA[key]
        old = ours[name]
        content, count = re.subn(r'(?m)^(' + name + r'[ \t]*=[ \t]*)[\'"][^\'"\r\n]+[\'"]',
                                lambda m: m[1] + json.dumps(version), content)
        if count != 1:
            raise ValueError('Constante de version absente ou ambiguë : ' + name)
        if old.split('.')[:2] != version.split('.')[:2]:
            content = set_patch_started(content, key, '.'.join(version.split('.')[:2]))
    if content != path.read_text(encoding='utf-8'):
        path.write_text(content, encoding='utf-8')


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
            raise ValueError('Version de données invalide : %r' % tag)
        current = result['current']
        if re.fullmatch(r'\d+(?:\.\d+){2,4}', current) and tuple(map(int, tag.split('.'))) < tuple(map(int, current.split('.'))):
            raise ValueError('Source plus ancienne que la version locale : %s < %s ; rétrogradation refusée.' % (tag, current))
        release = fetch_json('https://api.github.com/repos/dofusdude/%s/releases/tags/%s'
                             % (REPOS[version], tag))
        assets = {a['name'] for a in release['assets']}
        needed = {'spells.json', 'effects.json', 'breeds.json', 'monsters.json',
                  'recipes.json', 'en.json', 'fr.json', 'es.json', 'pt.json', 'de.json'}
        if release.get('draft') or needed - assets:
            raise ValueError('Archive incomplète : ' + ', '.join(sorted(needed - assets)))
        result['available'] = tag
        result['source'] = {'version': tag, 'update_stamp': api.get('update_stamp'),
                            'archive': release['tag_name']}
        channel = {'dofus3': 'dofus3', 'beta': 'beta', 'dofus2': 'main'}[version]
        catalog = catalog or fetch_json(CYTRUS)
        result['official'] = catalog['games']['dofus']['platforms']['windows'][channel].split('_')[-1]
        if result['official'] != tag:
            result['warnings'].append('Le client Ankama et les données importables diffèrent.')
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
                raise ValueError('Manifeste Retro incomplet : ' + lang)
        entries = retro_asset_entries(version=build)
        if not entries:
            raise ValueError('Manifeste Retro sans images reconnues')
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
            raise ValueError('Source plus ancienne que la version locale : rétrogradation refusée.')
    return result


def discover():
    rows = []
    try:
        catalog = fetch_json(CYTRUS)
    except Exception:
        catalog = None
    for key, label in zip(VERSIONS, LABELS):
        print('Consultation : ' + label, flush=True)
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
        label = LABELS[number - 1]
        print('\n%d. %s — locale : %s' % (number, label, row['current']))
        for line in version_details(row):
            print('   ' + line)
        print('   ' + (row['error'] or ('Mise à jour détectée' if row['changed'] else 'Pas de changement détecté')))
        for warning in row['warnings']:
            print('   À vérifier : ' + warning)


def version_details(row):
    source = row.get('source', {})
    if row['key'] == 'touch':
        return ['Build du jeu disponible : ' + (row['available'] or 'indisponible'),
                'Ressources CDN : %s → %s' % (row.get('current_data', '?'), source.get('assets', '?')),
                'Le numéro du client mobile installé est distinct du build du jeu.']
    if row['key'] == 'retro':
        return ['Version du jeu disponible : ' + (row['available'] or 'indisponible'),
                'Identifiant technique Cytrus : %s → %s' % (row.get('current_data', '?'), source.get('build', '?'))]
    return ['Importable : %s | Ankama : %s' % (row['available'] or 'indisponible', row['official'] or '?')]


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
            raise ValueError('Choix inconnu : ' + token)
    by_key = {r['key']: r for r in rows}
    for key in keys:
        if by_key[key]['error']:
            raise ValueError('%s : source indisponible, mise à jour impossible' % key)
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
            progress('%s — en cours (%.0f s)' % (title, time.monotonic() - started))
    progress(title + '…')
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    completed = False
    try:
        yield
        completed = True
    finally:
        stopped.set()
        thread.join()
        progress('%s — %s (%.1f s)' % (title, 'terminé' if completed else 'interrompu', time.monotonic() - started))


def failure_detail(log):
    with log.open('rb') as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - 8192))
        lines = handle.read().decode('utf-8', errors='replace').splitlines()
    useful = [line.strip() for line in lines if line.strip()]
    return useful[-1][:500] if useful else 'Aucun détail dans le journal.'


def run_command(command, log, cwd=ROOT, timeout=3600, *, django=False, title=None, relay_progress=False):
    started = time.monotonic()
    title = title or log.stem
    progress(title + '…')
    with log.open('w', encoding='utf-8') as output, log.open('r', encoding='utf-8', errors='replace') as reader:
        output.write('Commande : ' + subprocess.list2cmdline(list(map(str, command))) + '\n')
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
                    raise TimeoutError('Délai dépassé pour ' + str(log))
                if now - last_progress >= HEARTBEAT_SECONDS + (2 if relay_progress else 0):
                    progress('%s — en cours (%.0f s)' % (title, now - started))
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
            raise FileExistsError('Une autre mise à jour détient le verrou ; attendre sa fin.') from exc
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
    match = re.fullmatch(r'update_all pid=(\d+) (\S+)', marker.strip())
    if not match:
        raise RuntimeError('Verrou non reconnu ; conservé pour vérification : ' + marker.strip())
    pid = int(match[1])
    rows = process_snapshot()
    if not rows or not any(row['pid'] == os.getpid() for row in rows):
        raise RuntimeError('Liste des processus incomplète ; verrou conservé.')
    if any(row['pid'] == pid or row['parent'] == pid for row in rows):
        raise RuntimeError('Mise à jour encore active (processus ou enfant du pid %d).' % pid)
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
        if 'python' in name or name in ('py.exe', 'py'):
            tokens = re.split(r'[\s"\'/\\]+', command)
            if not command or scripts.intersection(tokens) or 'multiprocessing.spawn' in command or 'itemscraper.' in command:
                raise RuntimeError('Un import ou test Python peut encore tourner (pid %d) ; verrou conservé.' % row['pid'])
        if 'cbc' in name or ('java' in name and str(ROOT).lower().replace('\\', '/') in command.replace('\\', '/')):
            raise RuntimeError('Un calcul ou traitement des images peut encore tourner (pid %d) ; verrou conservé.' % row['pid'])


def remove_running_marker(running_file, marker):
    if running_file.exists():
        lines = running_file.read_text(encoding='utf-8').splitlines()
        running_file.write_text('\n'.join(line for line in lines if line.strip() != marker.strip()).rstrip() + '\n', encoding='utf-8')


@contextlib.contextmanager
def exclusive(running_file):
    with update_guard():
        with exclusive_marker(running_file):
            yield


@contextlib.contextmanager
def exclusive_marker(running_file):
    lock = ROOT / '.update-data.lock'
    if lock.exists():
        previous = lock.read_text(encoding='utf-8')
        abandoned_marker(previous)
        remove_running_marker(running_file, previous)
        lock.unlink()
        print('Verrou abandonné récupéré : ' + previous.strip(), flush=True)
        print('Exécution précédente interrompue : relancer les versions concernées ; sauvegardes conservées.', flush=True)
    marker = 'update_all pid=%d %s' % (os.getpid(), datetime.now().astimezone().isoformat())
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(marker)
    registered = False
    try:
        if running_file.exists():
            text = running_file.read_text(encoding='utf-8')
            if '## En cours' not in text:
                raise RuntimeError('Section En cours absente de ' + str(running_file))
            active = [line.strip() for line in text.split('## En cours', 1)[1].splitlines()
                      if line.strip() and line.strip() != '(rien)']
            for line in list(active):
                if line.startswith('update_all pid='):
                    abandoned_marker(line)
                    remove_running_marker(running_file, line)
                    active.remove(line)
                    print('Marqueur abandonné récupéré : ' + line, flush=True)
            if active:
                raise RuntimeError('Travail exclusif déjà en cours : ' + '; '.join(active))
            with running_file.open('a', encoding='utf-8') as handle:
                handle.write('\n' + marker + '\n')
            registered = True
        yield
    finally:
        try:
            if registered:
                remove_running_marker(running_file, marker)
        finally:
            lock.unlink()


def worker(job_path):
    from update_audit import preserve_table, database_path
    job = read_json(job_path)
    key = job['key']
    module = importlib.import_module(PIPELINES[key])
    setter = {'dofus3': 'set_version', 'beta': 'set_beta_version', 'dofus2': 'set_dofus2_version'}.get(key)
    if setter:
        setattr(module, setter, lambda version: version)
    report_dir = job_path.parent
    sequence = []

    def step(label, command, cwd=None):
        title = '%s | %02d | %s' % (key, len(sequence) + 1, STEP_TITLES.get(label, label))
        if not job['images'] and label in IMAGE_STEPS:
            return True, []
        if not job['images'] and label == 'spells/build' and key == 'touch':
            command = list(command) + ['--skip-images']
        if label == 'monster-images' and key in ('dofus3', 'beta'):
            message = 'Illustrations de monstres conservées, non actualisées (API DofusDB désactivée).'
            progress(title + ' — ' + message)
            sequence.append({'step': label, 'exit_code': 0, 'warning': message})
            write_json(report_dir / (key + '-steps.json'), sequence)
            return True, [message]
        if label in LOCAL_TABLES and key in ('dofus3', 'beta'):
            table = LOCAL_TABLES[label]
            with phase(title):
                preserve_table(report_dir / 'backup' / database_path(key).relative_to(ROOT), database_path(key), table)
            message = '%s : conservé depuis la base locale, non actualisé (DofusDB désactivé).' % table
            sequence.append({'step': label, 'exit_code': 0, 'warning': message})
            write_json(report_dir / (key + '-steps.json'), sequence)
            return True, [message]
        if any('dofusdb' in str(part).lower() for part in command):
            raise RuntimeError('Étape DofusDB non autorisée : ' + label)
        if label == 'verify/rebuild':
            return True, []
        if label == 'spells/download':
            command = list(command) + ['--no-skip-existing']
        log = report_dir / ('%s-%02d-%s.log' % (key, len(sequence), label.replace('/', '-')))
        started = time.monotonic()
        try:
            result = run_command(command, log, cwd or ROOT, job['timeout'], title=title)
        except Exception as exc:
            result = {'exit_code': 1, 'log': str(log), 'seconds': round(time.monotonic() - started, 1),
                      'error': str(exc), 'command': list(map(str, command))}
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
            result.setdefault('error', failure_detail(log) if log.exists() else 'Commande non démarrée.')
        result['notices'] = log_notices(lines)
        sequence.append(result)
        write_json(report_dir / (key + '-steps.json'), sequence)
        if result['exit_code']:
            progress(title + ' — ÉCHEC : ' + result['error'])
            raise RuntimeError('Étape échouée : %s : %s ; voir %s' % (label, result['error'], log))
        progress('%s — OK (%.1f s)' % (title, result.get('seconds', 0)))
        return True, lines

    module.run_step = step
    args = [module.__file__]
    if key in APIS:
        args += ['--version', job['available']]
    if not job['images']:
        args += ['--skip-images']
    sys.argv = args
    result = module.main()
    if result:
        raise RuntimeError('Pipeline échoué : ' + key)


def log_notices(lines):
    return list(dict.fromkeys(line.strip() for line in lines
        if re.search(r'warning|attention|unknown|unmapped|unresolved|missing translation|unsupported|not found', line, re.I)
        and not re.search(r'\b(?:0|no) (?:unresolved|missing|unknown|unmapped|warnings?)\b|Spaces are not permitted', line, re.I)))


def report_markdown(report):
    lines = ['# Mise à jour des données', '', 'État : **%s**' % report['status'],
             '', 'Dossier : `%s`' % report['directory'], '']
    for entry in report.get('versions', []):
        lines += ['## ' + entry['key'], '', 'Locale : %s → demandée : %s' % (entry['current'], entry['available']),
                  'Images : ' + ('oui' if entry['images'] else 'non'), '']
        if entry['key'] in ('touch', 'retro'):
            lines.extend('- ' + detail for detail in version_details(entry))
        diff = entry.get('diff', {})
        for category in ('errors', 'warnings', 'changes'):
            for message in diff.get(category, []):
                lines.append('- %s : %s' % (category, message))
        for step in entry.get('steps', []):
            if step.get('warning'):
                lines.append('- ' + step['warning'])
            if step['exit_code']:
                lines.append('- ÉCHEC %s : `%s`' % (step['step'], step.get('log', '')))
                if step.get('error'):
                    lines.append('- Cause : ' + step['error'])
            for notice in step.get('notices', [])[:20]:
                lines.append('- À vérifier (%s) : %s' % (step['step'], notice))
        for key, image in list(diff.get('new_image_problems', {}).items())[:20]:
            lines.append('- Image : %s — `%s`' % (key, image['path']))
        for item in diff.get('items_added', [])[:10]:
            lines.append('- Nouvel objet : %s (id %s, niveau %s)' % (item['name'], item['id'], item['level']))
        lines += ['']
    lines += ['## Contrôles', '']
    for version, diff in report.get('shared_images', {}).items():
        lines.append('- Images partagées, %s : %d nouveaux défauts' % (version, len(diff['new_image_problems'])))
        lines.extend('- ' + error for error in diff['errors'])
    if not report.get('checks'):
        lines.append('Tests non exécutés : arrêt avant la phase de validation.')
    for check in report.get('checks', []):
        lines.append('- %s : code %s, %.1f s — `%s`' % (check['name'], check['exit_code'], check['seconds'], check['log']))
    for error in report.get('errors', []):
        lines.append('- ' + error)
    lines += ['', '## Suite à donner', '',
              'Les inventaires avant/après et les journaux complets sont conservés dans ce dossier.',
              'Pertes de données : consulter `<version>-after.json`, les différences de tables et les identifiants signalés.',
              'Stats Dofus 3/Beta/Dofus 2 : `itemscraper/get_equipments2.py` puis `itemscraper/get_equipments3.py`.',
              'Stats Touch/Retro/Wakfu : `itemscraper/get_equipments_touch.py`, `get_equipments_retro.py` ou `get_items_wakfu.py`.',
              'Échec de génération : lire `generation.log` ; autres régressions : `django.log`.',
              'Une nouvelle stat peut nécessiter une règle dans le solveur et des traductions.',
              'Les caches bruts téléchargés restent disponibles pour une nouvelle tentative.',
              'Aucun commit, push ou déploiement effectué.', '']
    return '\n'.join(lines)


def execute(rows, keys, images, args):
    from update_audit import snapshot, compare, backup_runtime, restore_runtime, database_path
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '-%d' % os.getpid()
    directory = REPORTS / stamp
    directory.mkdir(parents=True)
    report = {'status': 'EN COURS', 'directory': str(directory), 'versions': [], 'checks': [], 'errors': []}
    backup = None
    locks = contextlib.ExitStack()
    try:
        locks.enter_context(exclusive(args.running_file))
        check_configuration()
        if not (ROOT / 'fashionsite/fashionsite/settings_test.py').exists():
            raise RuntimeError('settings_test.py absent : configurer SQLite pour les tests, voir README.')
        print('Journaux et sauvegarde : ' + str(directory), flush=True)
        with phase('Sauvegarde des données' + (' et des images' if any(images.values()) else '')):
            backup = backup_runtime(keys, any(images.values()), directory / 'backup')
        shared_before = {}
        if any(images.values()):
            for key in VERSIONS:
                if key not in keys and database_path(key).exists():
                    with phase('Inventaire des images partagées : ' + key):
                        shared_before[key] = snapshot(key)
                    write_json(directory / (key + '-before.json'), shared_before[key])
        for position, key in enumerate(keys, 1):
            progress('Version %d/%d : %s' % (position, len(keys), LABELS[VERSIONS.index(key)]))
            row = dict(next(row for row in rows if row['key'] == key), images=images[key])
            report['versions'].append(row)
            with phase(key + ' : inventaire avant import (données, dumps et images)'):
                before = snapshot(key)
            write_json(directory / (key + '-before.json'), before)
            with phase(key + ' : vérification de la source'):
                fresh = probe(key)
            if fresh['source'] != row['source']:
                raise RuntimeError(key + ' : la source a changé depuis le choix, relancer le lanceur.')
            job_path = directory / (key + '-job.json')
            write_json(job_path, dict(row, timeout=args.step_timeout))
            result = run_command([sys.executable, str(Path(__file__)), '--worker', str(job_path)],
                                 directory / (key + '-pipeline.log'), timeout=args.step_timeout * 60,
                                 title=key + ' : import', relay_progress=True)
            row['steps'] = read_json(directory / (key + '-steps.json'), [])
            with phase(key + ' : inventaire après import (données, dumps et images)'):
                after = snapshot(key)
            write_json(directory / (key + '-after.json'), after)
            row['diff'] = compare(before, after)
            if result['exit_code']:
                failed = next((step for step in row['steps'] if step['exit_code']), result)
                raise RuntimeError('%s : %s : %s ; voir %s' % (key, failed.get('step', 'pipeline'),
                                   failed.get('error', 'Commande échouée'), failed['log']))
            with phase(key + ' : vérification finale de la source'):
                source_after = probe(key)['source']
            if source_after != row['source']:
                raise RuntimeError(key + ' : la source a changé pendant le téléchargement, données mélangées possibles.')
            if row['diff']['errors']:
                raise RuntimeError(key + ' : contrôles de données échoués.')
            for change in row['diff'].get('changes', []):
                if change.startswith(('Objets :', 'Sorts :', 'Images absentes/illisibles :')):
                    progress(key + ' : ' + change)
        report['shared_images'] = {}
        for key, before in shared_before.items():
            with phase('Contrôle des images partagées : ' + key):
                after = snapshot(key)
            write_json(directory / (key + '-after.json'), after)
            diff = compare(before, after)
            report['shared_images'][key] = diff
            if diff['errors']:
                raise RuntimeError(key + ' : une version non sélectionnée a subi une régression.')
        for name, command in validation_commands(keys):
            title = {'generation': 'Test de génération des builds', 'weapons': 'Contrôle des armes',
                     'django': 'Suite Django complète'}[name]
            result = run_command(command, directory / (name + '.log'), timeout=args.step_timeout,
                                 django=name in ('generation', 'django'), title=title)
            report['checks'].append(dict(result, name=name))
            progress('%s — %s (%.1f s)' % (title, 'ÉCHEC' if result['exit_code'] else 'OK', result['seconds']))
            if result['exit_code']:
                report['errors'].append(name + ' : ' + result.get('error', 'échec') + ' ; voir ' + result['log'])
        if report['errors']:
            raise RuntimeError('Au moins un contrôle a échoué.')
        set_game_versions(report['versions'])
        state = read_json(REPORTS / 'state.json', {})
        for row in report['versions']:
            applied = dict(row['source'])
            if row['key'] == 'retro' and not row['images']:
                previous = state.get('retro', {}).get('source', {})
                applied['image_digest'] = previous.get('image_digest', read_metadata()['WATCHED_RETRO_ASSET_DIGEST'])
                applied['image_count'] = previous.get('image_count', read_metadata()['WATCHED_RETRO_ASSET_COUNT'])
            state[row['key']] = {'source': applied, 'images': row['images'], 'report': str(directory)}
        write_json(REPORTS / 'state.json', state)
        review = (any(row['diff']['warnings'] or any(step.get('warning') or step.get('notices') for step in row['steps'])
                      for row in report['versions']) or any(diff['new_image_problems'] for diff in report['shared_images'].values()))
        report['status'] = 'APPLIQUÉ — POINTS À VÉRIFIER' if review else 'VALIDÉ'
    except (Exception, KeyboardInterrupt) as exc:
        report['errors'].append(str(exc) or 'Interrompu au clavier')
        report['status'] = 'ÉCHEC'
        if backup is not None:
            try:
                with phase('Restauration des données et fichiers sauvegardés'):
                    restore_runtime(backup, directory / 'backup')
                report['status'] = 'ÉCHEC — DONNÉES ET FICHIERS RESTAURÉS'
            except Exception as restore_error:
                report['errors'].append('RESTAURATION INCOMPLÈTE : ' + str(restore_error))
    finally:
        try:
            locks.close()
        except Exception as exc:
            report['errors'].append('Nettoyage du verrou : ' + str(exc))
        write_json(directory / 'report.json', report)
        (directory / 'RECAP.md').write_text(report_markdown(report), encoding='utf-8')
        print('\n%s\nRécapitulatif : %s' % (report['status'], directory / 'RECAP.md'))
        for error in report['errors']:
            print('Cause : ' + error)
    return 1 if report['errors'] else (2 if report['status'].startswith('APPLIQUÉ') else 0)


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
        raise RuntimeError('Le chemin dans %s pointe vers un autre dépôt ; le corriger avant la mise à jour.' % config)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Mise à jour guidée, sauvegardée et contrôlée des données.')
    parser.add_argument('--list', action='store_true', help='consulter les versions, sans écrire')
    parser.add_argument('--dry-run', action='store_true', help='afficher les choix et contrôles sans modifier les données')
    parser.add_argument('--versions', help='noms ou numéros séparés par des virgules ; all, changed ; Wakfu explicite')
    parser.add_argument('--images', choices=('yes', 'no'), help='télécharger les images ou garder les images locales')
    parser.add_argument('--yes', action='store_true', help='exécuter les choix explicites sans dialogue')
    parser.add_argument('--step-timeout', type=int, default=3600, help='délai maximum par étape en secondes')
    parser.add_argument('--running-file', type=Path, default=Path.home() / 'Documents/fashionista-loop/RUNNING.md')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        worker(args.worker)
        return 0
    if args.yes and (not args.versions or not args.images):
        parser.error('--yes exige --versions et --images')
    if args.step_timeout <= 0:
        parser.error('--step-timeout doit être positif')
    rows = discover()
    show_versions(rows)
    if args.list:
        return 1 if any(row['error'] for row in rows) else 0
    while True:
        choice = args.versions if args.versions is not None else input(
            '\nQuelles versions ? (1,4 ; all ; changed ; Entrée pour quitter) : ')
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
            raw = input('%s : télécharger les images ? [O/n] : ' % key).strip().lower()
            answer = 'yes' if raw in ('', 'o', 'oui', 'y', 'yes') else 'no' if raw in ('n', 'non', 'no') else None
        images[key] = answer == 'yes'
    print('\nChoix : ' + ', '.join('%s (%s images)' % (key, 'avec' if images[key] else 'sans') for key in keys))
    print('Sauvegarde → mises à jour successives → inventaires → génération → suite complète → récapitulatif.')
    print('En cas d’échec : restauration des fichiers de données, constantes et images sauvegardés.')
    if args.dry_run:
        for name, command in validation_commands(keys):
            print(name + ' : ' + subprocess.list2cmdline(command))
        return 0
    if not args.yes and input('Lancer ? [o/N] : ').strip().lower() not in ('o', 'oui', 'yes', 'y'):
        return 0
    return execute(rows, keys, images, args)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nAnnulé.')
        raise SystemExit(130)
