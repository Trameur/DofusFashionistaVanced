"""Rebuild ItemInSharedBuild and ItemPopularity from every calculated build."""
import collections

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chardata.models import Char, ItemInSharedBuild, ItemPopularity
from chardata.solution import get_solution


class Command(BaseCommand):
    help = 'Rebuild the item usage data the encyclopedia reads.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=0,
            help='stop after this many builds; 0 reads them all')
        parser.add_argument(
            '--shared-only', action='store_true',
            help='rebuild only the public builds, leave the counts alone')

    def handle(self, *args, **options):
        from fashionistapulp.structure import get_structure

        builds = (Char.objects.filter(deleted=False)
                  .exclude(minimal_solution=b'')
                  .only('id', 'minimal_solution', 'game_version', 'level',
                        'link_shared'))
        if options['shared_only']:
            builds = builds.filter(link_shared=True)
        if options['limit']:
            builds = builds[:options['limit']]

        lignes = []
        portes = collections.Counter()
        niveaux = collections.Counter()
        lus = illisibles = 0

        for build in builds.iterator(chunk_size=500):
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
            niveaux[(version, build.level or 0)] += 1
            # A build wearing an item twice counts once
            for ankama_id in {getattr(item, 'ankama_id', None)
                              for item in (solution.item_list or [])}:
                if not ankama_id:
                    continue
                portes[(version, ankama_id)] += 1
                if build.link_shared:
                    lignes.append(ItemInSharedBuild(
                        ankama_id=ankama_id, game_version=version, char=build))

        # A partial pass would show a plausible but wrong share
        complet = not options['shared_only'] and not options['limit']
        comptes = (self._eligible_par_objet(get_structure, portes, niveaux)
                   if complet else [])

        with transaction.atomic():
            ItemInSharedBuild.objects.all().delete()
            ItemInSharedBuild.objects.bulk_create(lignes, batch_size=1000,
                                                  ignore_conflicts=True)
            if complet:
                ItemPopularity.objects.all().delete()
                ItemPopularity.objects.bulk_create(comptes, batch_size=1000,
                                                   ignore_conflicts=True)
                # Stored in the key-value table so the page can date its figures
                from chardata.models import SiteSetting
                SiteSetting.objects.update_or_create(
                    key='item_popularity_computed_at',
                    defaults={'value': timezone.now().date().isoformat()})

        self.stdout.write('builds read      : %d' % lus)
        self.stdout.write('unreadable       : %d' % illisibles)
        self.stdout.write('named public     : %d rows' % len(lignes))
        if complet:
            self.stdout.write('counted items    : %d' % len(comptes))
            self.stdout.write(self.style.SUCCESS(
                'the encyclopedia can now say who wears an item, and how many '
                'do.'))
        else:
            self.stdout.write(self.style.WARNING(
                'partial pass: the usage counts were left untouched, since '
                'they would have been computed on a subset.'))

    def _eligible_par_objet(self, get_structure, portes, niveaux):
        """Builds at or above each item's level, per version, from a level histogram."""
        au_dessus = {}
        for version in {v for v, _ in niveaux}:
            par_niveau = sorted(
                ((niveau, n) for (v, niveau), n in niveaux.items()
                 if v == version), reverse=True)
            cumul, suffixe = 0, {}
            for niveau, n in par_niveau:
                cumul += n
                suffixe[niveau] = cumul
            au_dessus[version] = (sorted(suffixe), suffixe, cumul)

        import bisect
        comptes = []
        structures = {}
        for (version, ankama_id), n in portes.items():
            if version not in structures:
                try:
                    structures[version] = get_structure(version)
                except Exception:
                    structures[version] = None
            structure = structures[version]
            item = (structure.get_item_by_ankama_id(ankama_id)
                    if structure is not None else None)
            niveau_objet = getattr(item, 'level', 0) or 0
            cles, suffixe, total = au_dessus.get(version, ([], {}, 0))
            # First recorded level at or above the item's own
            i = bisect.bisect_left(cles, niveau_objet)
            eligibles = suffixe[cles[i]] if i < len(cles) else 0
            comptes.append(ItemPopularity(
                ankama_id=ankama_id, game_version=version,
                builds=n, eligible=eligibles))
        return comptes
