"""Rebuild what the encyclopedia knows about how items are actually worn.

    manage.py reindex_builds_by_item

Two things come out of one pass, because the public builds are a subset of all
of them and reading a solution twice would double the only expensive part:

  ItemInSharedBuild   the public builds an item page may name and link to.
                      1 980 of them, and only those: a build nobody chose to
                      share is nobody's business to display.

  ItemPopularity      how many builds wear the item, out of those that could.
                      Counted over all 142 043 calculated builds, shared or
                      not, since a count is anonymous where a link is not.

Both are derived data, emptied and rebuilt every time, so they can never drift
from the builds and losing them costs nothing but the run. Reading every build
takes on the order of a quarter of an hour, which is why this is a command and
not something a page does while somebody waits.

HOW OFTEN: monthly is plenty, and there is no reason to automate it. Measured
on the live site, about 180 builds are calculated a day against an index of
161 476, so a share of 14.0 % reads 13.98 % after a day, 13.89 % after a
week and 13.54 % after a month. Putting this in the entrypoint would cost a
quarter of an hour of downtime on every deploy to correct a second decimal.

A build whose solution cannot be read is skipped and counted, never dropped in
silence: a rebuild that quietly indexed half the site would leave item pages
looking as though nobody wears the item.
"""
import collections

from django.core.management.base import BaseCommand
from django.db import transaction

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
            # A build can wear the same item twice, two rings for instance, and
            # both questions here are "does this build wear it", not how often.
            for ankama_id in {getattr(item, 'ankama_id', None)
                              for item in (solution.item_list or [])}:
                if not ankama_id:
                    continue
                portes[(version, ankama_id)] += 1
                if build.link_shared:
                    lignes.append(ItemInSharedBuild(
                        ankama_id=ankama_id, game_version=version, char=build))

        # Une passe partielle ne peut pas produire une part honnete : sur les
        # seuls builds partages, un objet niveau 200 se compare a 625 builds
        # au lieu de 48 522, ce qui reste au-dessus du seuil et affiche donc un
        # pourcentage credible calcule sur un pour cent des donnees. Un chiffre
        # faux indiscernable d'un vrai est pire que pas de chiffre.
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
        """How many builds could have worn each item, meaning those at or
        above its level. Computed once per version from a level histogram
        rather than per item, which would be one scan of every build each."""
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
            # The first recorded level at or above the item's own: everything
            # from there up could wear it.
            i = bisect.bisect_left(cles, niveau_objet)
            eligibles = suffixe[cles[i]] if i < len(cles) else 0
            comptes.append(ItemPopularity(
                ankama_id=ankama_id, game_version=version,
                builds=n, eligible=eligibles))
        return comptes
