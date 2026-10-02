# -*- coding: utf-8 -*-
"""sync_db.py must copy every base table of the source, in any order, through the real PyMySQL cursors."""
import importlib.util
import json
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

import pymysql

from chardata.tests_the_backup_can_reach_s3 import REPO

SYNC_DB_PATH = os.path.join(REPO, 'sync_db.py')


def load_sync_module():
    if not os.path.exists(SYNC_DB_PATH):
        return None
    spec = importlib.util.spec_from_file_location('sync_db_under_test', SYNC_DB_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AField(object):

    def __init__(self, name, table_name=''):
        self.name = name
        self.table_name = table_name


class AResult(object):
    """What a PyMySQL cursor reads from its connection after a query."""

    def __init__(self, names=(), rows=(), unbuffered=False, affected_rows=0):
        self.affected_rows = affected_rows
        self.warning_count = 0
        self.insert_id = 0
        self.has_next = False
        self.fields = [AField(name) for name in names]
        self.description = tuple((name,) for name in names) or None
        self._pending = iter(list(rows))
        self.rows = None if unbuffered else tuple(rows)

    def _read_rowdata_packet_unbuffered(self):
        return next(self._pending, None)

    def _finish_unbuffered_query(self):
        self._pending = iter(())


class AServer(object):
    """A MySQL database small enough to read: tables, rows and foreign keys."""

    def __init__(self, tables, foreign_keys=()):
        self.tables = {name: (list(columns), [tuple(row) for row in rows])
                       for name, (columns, rows) in tables.items()}
        self.foreign_keys = list(foreign_keys)

    def rows(self, table):
        return sorted(self.tables[table][1])


class AConnection(object):
    """The surface pymysql.connections.Connection offers its cursors."""

    encoding = 'utf8'

    def __init__(self, server, cursorclass=pymysql.cursors.Cursor, init_command=None, **kwargs):
        self.server = server
        self.cursorclass = cursorclass
        self.foreign_key_checks = True
        self._result = None
        self._values = []
        if init_command is not None:
            with self.cursor() as cursor:
                cursor.execute(init_command)

    def cursor(self, cursor=None):
        return (cursor or self.cursorclass)(self)

    def escape(self, value, mapping=None):
        self._values.append(value)
        return '@@%d' % (len(self._values) - 1)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def next_result(self, unbuffered=False):
        raise AssertionError('no query here returns more than one result set')

    def query(self, sql, unbuffered=False):
        if isinstance(sql, (bytes, bytearray)):
            sql = sql.decode(self.encoding)
        self._result = self._run(sql.strip(), unbuffered)
        return self._result.affected_rows

    def _run(self, sql, unbuffered):
        tables = self.server.tables
        match = re.fullmatch(r'SET FOREIGN_KEY_CHECKS\s*=\s*(\d)', sql)
        if match:
            self.foreign_key_checks = match.group(1) == '1'
            return AResult()
        if sql == "SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'":
            return AResult(['Tables_in_fashionista', 'Table_type'],
                           [(name, 'BASE TABLE') for name in tables], unbuffered)
        if sql == 'SHOW TABLES':
            return AResult(['Tables_in_fashionista'], [(name,) for name in tables], unbuffered)
        match = re.fullmatch(r'SHOW COLUMNS FROM `?(\w+)`?', sql)
        if match:
            return AResult(['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'],
                           [(column, 'int', 'NO', '', None, '')
                            for column in self._table(match.group(1))[0]], unbuffered)
        match = re.fullmatch(r'SELECT COUNT\(\*\) as cnt FROM `?(\w+)`?', sql)
        if match:
            return AResult(['cnt'], [(len(self._table(match.group(1))[1]),)], unbuffered)
        match = re.fullmatch(r'SELECT (.+) FROM `?(\w+)`?', sql)
        if match:
            columns, rows = self._table(match.group(2))
            wanted = [name.strip(' `') for name in match.group(1).split(',')]
            picked = [tuple(row[columns.index(name)] for name in wanted) for row in rows]
            return AResult(wanted, picked, unbuffered)
        match = re.fullmatch(r'(DELETE FROM|TRUNCATE TABLE) `?(\w+)`?', sql)
        if match:
            return self._empty(match.group(2), truncate=match.group(1) == 'TRUNCATE TABLE')
        match = re.fullmatch(r'INSERT INTO `?(\w+)`? \((.+?)\) VALUES (.+)', sql, re.S)
        if match:
            return self._insert(match.group(1), match.group(2), match.group(3))
        raise AssertionError('this fake does not know the query: %s' % sql)

    def _table(self, name):
        if name not in self.server.tables:
            raise pymysql.err.ProgrammingError(1146, "Table 'fashionista.%s' doesn't exist" % name)
        return self.server.tables[name]

    def _empty(self, table, truncate):
        columns, rows = self._table(table)
        for child, child_column, parent, parent_column in self.server.foreign_keys:
            if parent != table or not self.foreign_key_checks:
                continue
            if truncate:
                raise pymysql.err.OperationalError(
                    1701, 'Cannot truncate a table referenced in a foreign key constraint')
            child_columns, child_rows = self.server.tables[child]
            used = {row[child_columns.index(child_column)] for row in child_rows}
            if used & {row[columns.index(parent_column)] for row in rows}:
                raise pymysql.err.IntegrityError(
                    1451, 'Cannot delete or update a parent row: a foreign key constraint fails')
        deleted = len(rows)
        del rows[:]
        return AResult(affected_rows=deleted)

    def _insert(self, table, column_list, values):
        columns, rows = self._table(table)
        names = [name.strip(' `') for name in column_list.split(',')]
        added = []
        for group in re.findall(r'\(([^()]*)\)', values):
            given = dict(zip(names, [self._values[int(token)]
                                     for token in re.findall(r'@@(\d+)', group)]))
            added.append(tuple(given[name] for name in columns))
        for row in added:
            for child, child_column, parent, parent_column in self.server.foreign_keys:
                if child != table or not self.foreign_key_checks:
                    continue
                parent_columns, parent_rows = self.server.tables[parent]
                keys = {parent_row[parent_columns.index(parent_column)] for parent_row in parent_rows}
                if row[columns.index(child_column)] not in keys:
                    raise pymysql.err.IntegrityError(
                        1452, 'Cannot add or update a child row: a foreign key constraint fails')
            rows.append(row)
        self._values = []
        return AResult(affected_rows=len(added))


def a_source():
    return AServer({
        'a_child': (['id', 'parent_id'], [(n, n % 3 + 1) for n in range(1, 8)]),
        'b_parent': (['id', 'name'], [(1, 'one'), (2, 'two'), (3, 'three')]),
        'c_alone': (['id'], [(n,) for n in range(1, 6)]),
        'd_empty': (['id'], []),
    }, foreign_keys=[('a_child', 'parent_id', 'b_parent', 'id')])


def a_stale_destination():
    return AServer({
        'a_child': (['id', 'parent_id'], [(50, 9)]),
        'b_parent': (['id', 'name'], [(9, 'stale')]),
        'c_alone': (['id'], [(99,)]),
        'd_empty': (['id'], [(42,)]),
    }, foreign_keys=[('a_child', 'parent_id', 'b_parent', 'id')])


class TheDatabaseSyncCopiesEveryTable(unittest.TestCase):

    def setUp(self):
        self.sync_db = load_sync_module()
        if self.sync_db is None:
            self.skipTest('sync_db.py is not in this checkout')
        self.source = a_source()
        self.destination = a_stale_destination()

    def _run(self, dry_run=False, exits=False):
        servers = {'source.example': self.source, 'destination.example': self.destination}

        def connect(host, **kwargs):
            return AConnection(servers[host], **kwargs)

        config = {'port': 3306, 'db': 'fashionista', 'user': 'fashionista', 'password': 'p'}
        manager = self.sync_db.DatabaseSyncManager(dict(config, host='source.example'),
                                                   dict(config, host='destination.example'),
                                                   dry_run=dry_run)
        manager.BATCH_SIZE = 2
        manager.COMMIT_INTERVAL = 2
        with mock.patch.object(self.sync_db.pymysql, 'connect', connect), \
                self.assertLogs(self.sync_db.logger, 'INFO') as logs:
            if exits:
                with self.assertRaises(SystemExit) as raised:
                    manager.run_sync()
                self.assertEqual(1, raised.exception.code)
            else:
                manager.run_sync()
        return manager, '\n'.join(logs.output)

    def test_every_table_of_the_source_reaches_the_destination(self):
        manager, _ = self._run()
        for table in self.source.tables:
            self.assertEqual(self.source.rows(table), self.destination.rows(table), table)

    def test_every_row_is_counted_once(self):
        manager, _ = self._run()
        self.assertEqual({'a_child': 7, 'b_parent': 3, 'c_alone': 5, 'd_empty': 0}, manager.stats)
        self.assertEqual(15, manager.total_rows_synced)

    def test_the_destination_does_not_check_foreign_keys_while_it_loads(self):
        _, output = self._run()
        self.assertNotIn('Cannot add or update a child row', output)
        self.assertNotIn('Cannot delete or update a parent row', output)

    def test_the_log_says_no_backup_was_written(self):
        _, output = self._run()
        self.assertIn('writes no backup', output)
        self.assertNotIn('Backup created', output)

    def test_a_dry_run_reads_everything_and_writes_nothing(self):
        before = {table: self.destination.rows(table) for table in self.destination.tables}
        manager, _ = self._run(dry_run=True)
        self.assertEqual(before, {table: self.destination.rows(table)
                                  for table in self.destination.tables})
        self.assertEqual(15, manager.total_rows_synced)

    def test_a_table_missing_on_the_destination_fails_the_run(self):
        del self.destination.tables['c_alone']
        _, output = self._run(exits=True)
        self.assertIn('Tables not copied or not matching: c_alone', output)
        self.assertNotIn('sync successful', output)

    def test_a_dry_run_fails_when_the_destination_lacks_a_table(self):
        del self.destination.tables['c_alone']
        _, output = self._run(dry_run=True, exits=True)
        self.assertIn('Tables not copied or not matching: c_alone', output)
        self.assertNotIn('dry run, nothing written', output)


class TheSyncReadsItsConfigFile(unittest.TestCase):

    def setUp(self):
        self.sync_db = load_sync_module()
        if self.sync_db is None:
            self.skipTest('sync_db.py is not in this checkout')

    def _configs_for(self, argv):
        seen = {}

        class AManager(object):
            def __init__(self, source_config, dest_config, dry_run=False):
                seen['source'], seen['destination'] = source_config, dest_config

            def run_sync(self):
                pass

        with mock.patch.object(self.sync_db, 'DatabaseSyncManager', AManager), \
                mock.patch.object(self.sync_db.logging, 'basicConfig'), \
                mock.patch.object(self.sync_db.logging, 'FileHandler'), \
                mock.patch.object(self.sync_db.sys, 'argv', ['sync_db.py'] + argv):
            self.sync_db.main()
        return seen

    def _a_config_file(self, content):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, 'sync.json'), 'w') as handle:
            json.dump(content, handle)
        return folder

    def test_the_file_gives_both_ends_their_password(self):
        folder = self._a_config_file({
            'source': {'host': 'source.example', 'password': 'from-the-file'},
            'destination': {'host': 'rds.example', 'port': 3306, 'password': 'rds-from-the-file'}})
        seen = self._configs_for(['--config', os.path.join(folder, 'sync.json'),
                                  '--dest-db', 'fashionista'])
        self.assertEqual(('source.example', 'from-the-file'),
                         (seen['source']['host'], seen['source']['password']))
        self.assertEqual(('rds.example', 'rds-from-the-file', 'fashionista'),
                         (seen['destination']['host'], seen['destination']['password'],
                          seen['destination']['db']))

    def test_a_path_under_the_home_folder_is_found(self):
        folder = self._a_config_file({'destination': {'host': 'rds.example'}})
        with mock.patch.dict(os.environ, {'HOME': folder, 'USERPROFILE': folder}):
            seen = self._configs_for(['--config', '~/sync.json'])
        self.assertEqual('rds.example', seen['destination']['host'])
