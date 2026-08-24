"""What share of readers reaches for the donation link, and from where.

SupportClick has been counting since the support block went up, and nothing
reads it. A measurement nobody can read without writing a query by hand is a
measurement that does not get read, which is the same as not having it.

The comparison that matters is by source, not the total. The whole question
the block was built to answer is whether asking at the moment the tool has
just done its work beats asking on a page almost nobody opens:

    solution  the block under a finished set
    footer    the link in the footer, on every page
    support   the /support/ page itself
    other     anything that did not match the closed list

    manage.py report_support_clicks
    manage.py report_support_clicks --days 7
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from chardata.models import SupportClick


class Command(BaseCommand):
    help = 'Report donation-link clicks by source, language and day.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=30,
            help='how many days back to look, 30 by default')

    def handle(self, *args, **options):
        jours = max(1, options['days'])
        depuis = timezone.localdate() - timedelta(days=jours - 1)
        lignes = SupportClick.objects.filter(day__gte=depuis)

        total = lignes.aggregate(n=Sum('count'))['n'] or 0
        if not total:
            # Dire qu'il n'y a rien, plutot que d'afficher des tableaux vides
            # qu'on lirait comme un resultat.
            self.stdout.write(
                'no click recorded since %s. Either nobody reached for the '
                'link, or the block is not on the pages you think it is.'
                % depuis)
            return

        self.stdout.write('%d clicks since %s, over %d day(s)'
                          % (total, depuis, jours))

        self.stdout.write('')
        self.stdout.write('by source')
        par_source = (lignes.values('source')
                      .annotate(n=Sum('count')).order_by('-n'))
        for ligne in par_source:
            part = 100.0 * ligne['n'] / total
            self.stdout.write('  %-10s %6d  %5.1f %%  %6.2f/day'
                              % (ligne['source'], ligne['n'], part,
                                 ligne['n'] / float(jours)))

        self.stdout.write('')
        self.stdout.write('by language')
        for ligne in (lignes.values('language')
                      .annotate(n=Sum('count')).order_by('-n')):
            self.stdout.write('  %-10s %6d  %5.1f %%'
                              % (ligne['language'] or '(none)', ligne['n'],
                                 100.0 * ligne['n'] / total))

        self.stdout.write('')
        self.stdout.write('by day')
        for ligne in (lignes.values('day')
                      .annotate(n=Sum('count')).order_by('day')):
            self.stdout.write('  %s %6d' % (ligne['day'], ligne['n']))

        # Un clic n'est pas un don, et la difference est tout le sujet : le
        # rappeler ici evite de lire ce tableau comme une recette.
        self.stdout.write('')
        self.stdout.write(
            'These are clicks, not donations. The page they lead to takes the '
            'money, so only Ko-fi knows how many of them gave.')
