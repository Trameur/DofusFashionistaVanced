# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Tune the default weights of a version on the sets the site's doors give, into a run folder.

    py fashionsite/manage.py tune_weights --version dofus3 --out <folder outside the repository> [--scenarios plain]
    py fashionsite/manage.py tune_weights --version dofus3 --out <folder> --dry-run --processes 1
    py fashionsite/manage.py tune_weights --version dofus3 --out <folder> --ship <run folder>

A run only writes into --out. --ship is the one option that writes the version's weight_tables file.
"""
import json
import multiprocessing
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chardata import weight_tuning as tuning
from chardata.weight_table import DIRECTORY, VERSIONS, engine_digest, grid_element_sets

PROGRESS_FILE = 'rounds_%d.jsonl'
STOP_FILE = 'stop_%s'
PROBE_FILE = 'probe_%d.json'

_RUNNER = None


def make_runner(game_version):
    return tuning.DoorRunner(game_version)


def _runner(game_version):
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = make_runner(game_version)
    return _RUNNER


def _logger(out):
    path = os.path.join(out, PROGRESS_FILE % os.getpid())

    def log(record):
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, sort_keys=True, default=tuning._plain) + '\n')
        print(tuning.format_round(record), flush=True)
    return log


def _work(job):
    """The records of one group of cells, or None when its scenario has been stopped."""
    game_version, cells, max_rounds, time_limit, out = job
    if os.path.exists(os.path.join(out, STOP_FILE % cells[0].scenario)):
        return None
    return tuning.tune_group(_runner(game_version), cells, max_rounds, time_limit, _logger(out))


def _probe_work(job):
    game_version, instance, time_limit, out = job
    runner = _runner(game_version)
    walls = []
    for _ in range(tuning.PROBE_RUNS):
        walls.append(runner.run(instance, None, (), time_limit).wall)
    return {'instance': tuning.instance_key(instance), 'walls': walls, 'pid': os.getpid()}


def _close_runner():
    global _RUNNER
    close = getattr(_RUNNER, 'close', None)
    _RUNNER = None
    if close:
        close()


def _pool_map(function, jobs, processes):
    """Results of the jobs as they finish, on this process alone or on a pool of spawned ones."""
    if processes <= 1:
        try:
            for job in jobs:
                yield function(job)
        finally:
            _close_runner()
        return
    context = multiprocessing.get_context('spawn')
    with context.Pool(processes) as pool:
        for result in pool.imap_unordered(function, jobs, chunksize=1):
            yield result


class Command(BaseCommand):
    help = __doc__

    def create_parser(self, prog_name, subcommand, **kwargs):
        # --version names the game here, in place of Django's own
        return super().create_parser(prog_name, subcommand, conflict_handler='resolve', **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('--version', default=VERSIONS[0], choices=VERSIONS)
        parser.add_argument('--scenarios', help='comma separated: plain, glasscannon, tank')
        parser.add_argument('--classes', help='comma separated class names')
        parser.add_argument('--elements', help='comma separated element keys, such as str or str+int')
        parser.add_argument('--cells', help='comma separated Class/elements/scenario')
        parser.add_argument('--processes', type=int, default=5)
        parser.add_argument('--max-rounds', type=int, default=tuning.MAX_ROUNDS)
        parser.add_argument('--time-limit', type=int, default=tuning.TIME_LIMIT)
        parser.add_argument('--warm', action='store_true',
                            help='solve one door before the first cell so imports and caches stay out of the times')
        parser.add_argument('--out', required=True, help='run folder, outside the repository')
        parser.add_argument('--resume', action='store_true', help='skip the groups the folder already holds')
        parser.add_argument('--plan', action='store_true', help='print the projected compute and stop')
        parser.add_argument('--probe', type=int, metavar='N', help='time N instances at --processes and stop')
        parser.add_argument('--dry-run', action='store_true', help='tune the two smoke instances, write no cell')
        parser.add_argument('--ship', metavar='RUN', help='write the weight table of the run folder RUN')

    def handle(self, *args, **options):
        out = os.path.abspath(options['out'])
        if tuning.path_is_inside(out, tuning.repository_root()):
            raise CommandError('--out must be outside the repository: %s' % out)
        game_version = options['version']
        if options['ship']:
            return self._ship(os.path.abspath(options['ship']), game_version)
        cells = self._cells(options)
        if options['plan']:
            return self._plan(cells, options['processes'], out)
        if not tuning.database_is_in_memory(settings.DATABASES['default']):
            raise CommandError('tune_weights runs on an in-memory sqlite database only: use '
                               '--settings=fashionsite.settings_test')
        os.makedirs(out, exist_ok=True)
        if options['dry_run']:
            return self._dry_run(game_version, out, options)
        if options['probe']:
            return self._probe(game_version, cells, out, options)
        return self._run(game_version, cells, out, options)

    def _cells(self, options):
        if options['cells']:
            try:
                return [tuning.parse_cell(text) for text in options['cells'].split(',')]
            except ValueError as error:
                raise CommandError(str(error))
        split = lambda text: [part.strip() for part in text.split(',')] if text else None
        elements = split(options['elements'])
        known = {tuning.element_key(played) for played in grid_element_sets()}
        for key in elements or ():
            if key not in known:
                raise CommandError('not an element set of the grid: %s' % key)
        for name in split(options['scenarios']) or ():
            if name not in tuning.SCENARIOS:
                raise CommandError('not a scenario: %s' % name)
        for name in split(options['classes']) or ():
            if name not in tuning.CHARACTER_CLASSES:
                raise CommandError('not a class: %s' % name)
        return tuning.lot1_cells(split(options['classes']), elements, split(options['scenarios']))

    def _plan(self, cells, processes, out):
        call_seconds = self._measured_call_seconds(out)
        projected = tuning.projection(cells, processes, call_seconds or tuning.CALL_SECONDS)
        self.stdout.write('%d cells, %.1f process hours, %.1f hours on %d processes (call %.1f s, %s)' % (
            projected['cells'], projected['process_hours'], projected['wall_hours'], processes,
            call_seconds or tuning.CALL_SECONDS, 'measured' if call_seconds else 'default'))

    @staticmethod
    def _measured_call_seconds(out):
        walls = []
        for name in sorted(os.listdir(out)) if os.path.isdir(out) else []:
            if name.startswith('rounds_') and name.endswith('.jsonl'):
                with open(os.path.join(out, name), encoding='utf-8') as handle:
                    walls.extend(json.loads(line)['wall'] for line in handle if line.strip())
        walls = [wall for wall in walls if wall]
        return sum(walls) / len(walls) if walls else None

    def _ship(self, run_path, game_version):
        if not os.path.isdir(os.path.join(run_path, 'cells')):
            raise CommandError('not a run folder: %s' % run_path)
        table = tuning.ship_table(run_path, game_version)
        path = os.path.join(DIRECTORY, '%s.json' % game_version)
        os.makedirs(DIRECTORY, exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(table, handle, sort_keys=True, indent=1)
            handle.write('\n')
        shipped = sum(1 for by_class in table['cells'].values() for by_key in by_class.values()
                      for by_scenario in by_key.values() for cell in by_scenario.values()
                      if cell['status'] == 'shipped')
        self.stdout.write('%s: %d cells shipped' % (path, shipped))

    def _dry_run(self, game_version, out, options):
        runner = make_runner(game_version)
        log = _logger(out)
        report = []
        try:
            if options['warm']:
                self._warm(runner, options['time_limit'])
            for char_class, played, scenario, minimums, tier in tuning.SMOKE_INSTANCES:
                instance = tuning.Instance(char_class, played, scenario, tuning.BANDS[0], minimums, tier, 'dry')
                started = time.monotonic()
                run = tuning.tune_instance(runner, instance, max_rounds=min(options['max_rounds'], tuning.DRY_ROUNDS),
                                           time_limit=options['time_limit'],
                                           on_round=lambda item, key=tuning.instance_key(instance): log(
                                               dict(item.record(), instance=key)))
                report.append(dict(run.record(), seconds=time.monotonic() - started))
        finally:
            close = getattr(runner, 'close', None)
            if close:
                close()
        with open(os.path.join(out, 'dry.json'), 'w', encoding='utf-8') as handle:
            json.dump(report, handle, sort_keys=True, default=tuning._plain)
        self.stdout.write('dry run: %d instances, no table written' % len(report))

    @staticmethod
    def _warm(runner, time_limit):
        char_class, played, scenario, minimums, tier = tuning.SMOKE_INSTANCES[0]
        runner.run(tuning.Instance(char_class, played, scenario, tuning.BANDS[0], minimums, tier, 'warm'), None, (),
                   time_limit)

    def _probe(self, game_version, cells, out, options):
        instances = [tuning.instances_for(cell)[0] for cell in cells][:options['probe']]
        jobs = [(game_version, instance, options['time_limit'], out) for instance in instances]
        results = list(_pool_map(_probe_work, jobs, options['processes']))
        walls = sorted(wall for result in results for wall in result['walls'])
        if walls:
            summary = {'processes': options['processes'], 'calls': len(walls), 'mean': sum(walls) / len(walls),
                       'p90': walls[min(len(walls) - 1, int(0.9 * len(walls)))], 'max': walls[-1],
                       'results': results}
            with open(os.path.join(out, PROBE_FILE % options['processes']), 'w', encoding='utf-8') as handle:
                json.dump(summary, handle, sort_keys=True)
            self.stdout.write('probe on %d processes: %d calls, mean %.1f s, p90 %.1f s, max %.1f s' % (
                summary['processes'], summary['calls'], summary['mean'], summary['p90'], summary['max']))

    def _run(self, game_version, cells, out, options):
        folder = os.path.join(out, 'cells')
        held = set(os.listdir(folder)) if os.path.isdir(folder) else set()
        if held and not options['resume']:
            raise CommandError('%s already holds a run: pass --resume or choose another folder' % out)
        groups = [group for group in tuning.groups_of(cells)
                  if not all(os.path.basename(tuning.cell_path(out, tuning.cell_key(cell))) in held
                             for cell in group)]
        self._write_meta(game_version, out, options)
        jobs = [(game_version, group, options['max_rounds'], options['time_limit'], out) for group in groups]
        by_scenario = {}
        finished = 0
        for records in _pool_map(_work, jobs, options['processes']):
            if records is None:
                continue
            finished += 1
            for record in records:
                tuning.write_record(out, record)
            scenario = records[0]['cell'].split('/')[2]
            by_scenario.setdefault(scenario, []).extend(records)
            if tuning.shard_stopped(by_scenario[scenario]):
                open(os.path.join(out, STOP_FILE % scenario), 'w').close()
                self.stdout.write('shard %s stopped: too many cells kept the engine weights' % scenario)
        self.stdout.write('%d of %d groups finished' % (finished, len(groups)))

    @staticmethod
    def _write_meta(game_version, out, options):
        meta = {'version': game_version, 'generator_version': tuning.GENERATOR_VERSION,
                'engine_digest': engine_digest(game_version), 'repository_head': tuning.repository_head(),
                'solver': tuning.solver_facts(options['time_limit']),
                'options': {name: value for name, value in options.items()
                            if name in ('scenarios', 'classes', 'elements', 'cells', 'processes', 'max_rounds',
                                        'time_limit')}}
        with open(os.path.join(out, 'run.json'), 'w', encoding='utf-8') as handle:
            json.dump(meta, handle, sort_keys=True)
