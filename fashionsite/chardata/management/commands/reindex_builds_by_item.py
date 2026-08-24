"""Rebuild the index of which shared builds wear which item.

    manage.py reindex_builds_by_item

The index is derived data: it is emptied and rebuilt from the builds every
time, so it can never drift from them and losing it costs nothing but the run.
Reading all 3 361 shared builds takes about twelve seconds, which is why this
is a command and not something the encyclopedia does per request.

A build whose solution cannot be read is skipped and counted, never dropped in
silence: a rebuild that quietly indexed half the site would leave item pages
looking as though nobody wears the item.
"""
import collections

from django.core.management.base import BaseCommand
from django.db import transaction

from chardata.models import Char, ItemInSharedBuild
from chardata.solution import get_solution


class Command(BaseCommand):
    help = 'Rebuild the item to shared build index the encyclopedia reads.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=0,
            help='stop after this many builds; 0 reads them all')

    def handle(self, *args, **options):
        builds = (Char.objects.filter(link_shared=True, deleted=False)
                  .exclude(minimal_solution=b'')
                  .only('id', 'minimal_solution', 'game_version'))
        if options['limit']:
            builds = builds[:options['limit']]

        lignes = []
        vus = collections.Counter()
        lus = illisibles = 0

        for build in builds.iterator(chunk_size=200):
            try:
                solution = get_solution(build)
            except Exception:
                illisibles += 1
                continue
            if solution is None:
                illisibles += 1
                continue
            lus += 1
            version = build.game_version or 'dofus3'
            # A build can wear the same item twice, two rings for instance, and
            # the index answers "does this build wear it", not "how often".
            for ankama_id in {getattr(item, 'ankama_id', None)
                              for item in (solution.item_list or [])}:
                if not ankama_id:
                    continue
                vus[version] += 1
                lignes.append(ItemInSharedBuild(
                    ankama_id=ankama_id, game_version=version, char=build))

        with transaction.atomic():
            ItemInSharedBuild.objects.all().delete()
            ItemInSharedBuild.objects.bulk_create(lignes, batch_size=1000,
                                                  ignore_conflicts=True)

        objets = len({(l.game_version, l.ankama_id) for l in lignes})
        self.stdout.write('builds read      : %d' % lus)
        self.stdout.write('unreadable       : %d' % illisibles)
        self.stdout.write('rows written     : %d' % len(lignes))
        self.stdout.write('distinct items   : %d' % objets)
        for version, n in sorted(vus.items(), key=lambda kv: -kv[1]):
            self.stdout.write('  %-8s %6d rows' % (version, n))
        self.stdout.write(self.style.SUCCESS(
            'the encyclopedia can now name the builds that wear an item.'))
