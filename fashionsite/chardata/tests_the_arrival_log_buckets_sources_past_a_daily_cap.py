"""Past a daily number of distinct sources, new utm_source values are counted in one bucket named other."""
from unittest import mock

from django.test import TestCase

from chardata import middleware
from chardata.models import VisitSource

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


class SourcesPastTheCapAreBucketed(TestCase):

    def arrive(self, source, **extra):
        return self.client.get('/', dict(extra, utm_source=source),
                               HTTP_USER_AGENT=BROWSER)

    def test_new_sources_past_the_cap_share_one_row(self):
        with mock.patch.object(middleware, 'VISIT_SOURCES_PER_DAY', 3):
            for i in range(8):
                self.arrive('src%d' % i)
        names = sorted(VisitSource.objects.values_list('source', flat=True))
        self.assertEqual(['other', 'src0', 'src1', 'src2'], names)
        other = VisitSource.objects.get(source='other')
        self.assertEqual(5, other.count)
        self.assertEqual('other', other.medium)

    def test_a_source_already_open_today_keeps_counting_under_its_name(self):
        with mock.patch.object(middleware, 'VISIT_SOURCES_PER_DAY', 2):
            for source in ('first', 'second', 'third', 'first', 'second'):
                self.arrive(source)
        counts = dict(VisitSource.objects.values_list('source', 'count'))
        self.assertEqual({'first': 2, 'second': 2, 'other': 1}, counts)

    def test_a_new_campaign_of_a_known_source_is_bucketed_too(self):
        with mock.patch.object(middleware, 'VISIT_SOURCES_PER_DAY', 1):
            self.arrive('news', utm_campaign='a')
            self.arrive('news', utm_campaign='b')
        self.assertEqual(['news', 'other'],
                         sorted(VisitSource.objects.values_list('source', flat=True)))

    def test_below_the_cap_nothing_is_bucketed(self):
        for i in range(5):
            self.arrive('plain%d' % i)
        self.assertFalse(VisitSource.objects.filter(source='other').exists())
