"""Throw away the arrivals counted before crawlers were filtered out.

The first day of VisitSource recorded 62 130 arrivals for a site with about
3 000 monthly readers, 61 539 of them from the United States, all filed as
"direct". They were crawlers: a crawler sends no referrer, so every one landed
in that bucket and drowned the six real rows underneath.

The user agent was never stored -- deliberately, it is one more thing that can
describe a person -- so those rows cannot be sorted after the fact. They can
only be dropped, and the count restarted with the filter in place.

    manage.py purge_bot_arrivals --before 2026-08-24
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from chardata.models import VisitSource


class Command(BaseCommand):
    help = 'Delete VisitSource rows recorded before crawlers were filtered.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--before', required=True,
            help='delete rows strictly before this day, as YYYY-MM-DD')
        parser.add_argument(
            '--apply', action='store_true',
            help='actually delete; without it the command only reports')

    def handle(self, *args, **options):
        try:
            limite = date.fromisoformat(options['before'])
        except ValueError:
            raise CommandError('--before wants a date like 2026-08-24')

        vises = VisitSource.objects.filter(day__lt=limite)
        lignes = vises.count()
        arrivees = vises.aggregate(n=Sum('count'))['n'] or 0
        restant = VisitSource.objects.filter(day__gte=limite).aggregate(
            n=Sum('count'))['n'] or 0

        self.stdout.write('before %s : %d rows, %d arrivals'
                          % (limite, lignes, arrivees))
        self.stdout.write('kept    : %d arrivals from %s onwards'
                          % (restant, limite))

        if not options['apply']:
            self.stdout.write('dry run. Re-run with --apply to delete.')
            return

        vises.delete()
        self.stdout.write(self.style.SUCCESS(
            'deleted %d rows. The count starts again, crawlers excluded.'
            % lignes))
