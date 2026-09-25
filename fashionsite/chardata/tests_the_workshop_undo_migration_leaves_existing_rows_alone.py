# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Migration 0046 only adds a table; existing WorkshopItem/WorkshopStock rows are untouched."""

import importlib
import io
import os

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

_BEFORE = '0045_workshopstock'
_AFTER = '0046_workshopundo'


def _source(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'migrations', name)
    with io.open(path, encoding='utf-8') as source_file:
        return source_file.read()


class TheMigrationFileOnlyCreatesATableTests(TransactionTestCase):

    def test_0046_holds_a_single_create_model(self):
        migration_module = importlib.import_module(
            'chardata.migrations.0046_workshopundo')
        operations = migration_module.Migration.operations
        self.assertEqual(1, len(operations))
        self.assertEqual('CreateModel', operations[0].__class__.__name__)
        self.assertEqual('WorkshopUndo', operations[0].name)

    def test_the_migration_text_touches_no_other_model(self):
        source = _source('0046_workshopundo.py')
        for banned in ('AlterField', 'RemoveField', 'RunPython', 'RunSQL',
                      'DeleteModel', 'AlterModelTable'):
            self.assertNotIn(banned, source)


class ExistingRowsSurviveTheMigrationTests(TransactionTestCase):

    def setUp(self):
        self._migrate_to(_BEFORE)

    def tearDown(self):
        self._migrate_to_latest()

    def _executor(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        return executor

    def _migrate_to(self, target):
        self._executor().migrate([('chardata', target)])

    def _migrate_to_latest(self):
        executor = self._executor()
        leaves = [node for node in executor.loader.graph.leaf_nodes()
                 if node[0] == 'chardata']
        executor.migrate(leaves)

    def test_row_count_and_checksum_are_identical_before_and_after(self):
        old_apps = self._executor().loader.project_state(
            ('chardata', _BEFORE)).apps
        OldWorkshopItem = old_apps.get_model('chardata', 'WorkshopItem')
        OldWorkshopStock = old_apps.get_model('chardata', 'WorkshopStock')
        OldUser = old_apps.get_model('auth', 'User')

        user_a = OldUser.objects.create(username='mig-undo-a')
        user_b = OldUser.objects.create(username='mig-undo-b')
        OldWorkshopItem.objects.create(
            user=user_a, item_id=111, game_version='dofus3', quantity=2)
        OldWorkshopStock.objects.create(
            user=user_b, game_version='touch', ingredient_ankama_id=222,
            ingredient_subtype='resources', owned=7)

        items_before = sorted(
            (row.id, row.user_id, row.item_id, row.game_version, row.quantity)
            for row in OldWorkshopItem.objects.all())
        stock_before = sorted(
            (row.id, row.user_id, row.ingredient_ankama_id,
             row.ingredient_subtype, row.owned)
            for row in OldWorkshopStock.objects.all())
        self.assertEqual(1, len(items_before))
        self.assertEqual(1, len(stock_before))

        self._migrate_to(_AFTER)

        from chardata.models import WorkshopItem, WorkshopStock, WorkshopUndo
        items_after = sorted(
            (row.id, row.user_id, row.item_id, row.game_version, row.quantity)
            for row in WorkshopItem.objects.all())
        stock_after = sorted(
            (row.id, row.user_id, row.ingredient_ankama_id,
             row.ingredient_subtype, row.owned)
            for row in WorkshopStock.objects.all())
        self.assertEqual(items_before, items_after)
        self.assertEqual(stock_before, stock_after)
        self.assertEqual(0, WorkshopUndo.objects.count())
