# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Fills Char.stuff_time from what each build already records; the migration calls it."""
from collections import Counter
from datetime import datetime, timezone

from django.db.models import Count, F, Max, Min, OuterRef, Subquery
from django.db.models.functions import TruncMinute

# A minute in which this many builds were saved is a batch, not players
BATCH_MINUTE_ROWS = 30
# Opening a shared build saved its row between these two deploys
VIEW_SAVED_WINDOW = (datetime(2025, 11, 3, tzinfo=timezone.utc),
                     datetime(2026, 7, 3, tzinfo=timezone.utc))
RANGE_SIZE = 4000

# The column each case copies; a generation is read through a subquery
SOURCE_FIELDS = {
    'solved_time': 'solved_time',
    'modified_time': 'modified_time',
    'batch_minute': 'created_time',
    'view_saved': 'created_time',
    'no_modified_time': 'created_time',
}


def to_minute(moment):
    return moment.astimezone(timezone.utc).replace(second=0, microsecond=0)


def batch_minutes(char_model, threshold=BATCH_MINUTE_ROWS):
    """UTC minutes in which at least `threshold` builds were saved."""
    rows = (char_model.objects.order_by()
            .filter(modified_time__isnull=False)
            .annotate(minute=TruncMinute('modified_time', tzinfo=timezone.utc))
            .values('minute')
            .annotate(n=Count('id'))
            .filter(n__gte=threshold))
    return {to_minute(row['minute']) for row in rows}


def classify(char_model, generation_model, minutes, low, high):
    """Ids per case for the builds with a stored set whose id is in [low, high)."""
    stored = (char_model.objects.order_by()
              .filter(id__gte=low, id__lt=high)
              .exclude(minimal_solution=b''))
    with_generation = set(generation_model.objects.order_by()
                          .filter(char_id__gte=low, char_id__lt=high)
                          .values_list('char_id', flat=True)
                          .distinct())
    ids_by_case = {case: [] for case in ('generation',) + tuple(SOURCE_FIELDS)}
    for pk, solved, modified, shared in stored.values_list(
            'id', 'solved_time', 'modified_time', 'link_shared'):
        if pk in with_generation:
            case = 'generation'
        elif solved is not None:
            case = 'solved_time'
        elif modified is None:
            case = 'no_modified_time'
        elif to_minute(modified) in minutes:
            case = 'batch_minute'
        elif shared and VIEW_SAVED_WINDOW[0] <= modified < VIEW_SAVED_WINDOW[1]:
            case = 'view_saved'
        else:
            case = 'modified_time'
        ids_by_case[case].append(pk)
    return ids_by_case


def _source(case, generation_model):
    if case == 'generation':
        return Subquery(generation_model.objects
                        .filter(char_id=OuterRef('pk'))
                        .order_by('-created_time', '-id')
                        .values('created_time')[:1])
    return F(SOURCE_FIELDS[case])


def backfill_stuff_time(char_model, generation_model, apply=True, range_size=RANGE_SIZE,
                        cases=None):
    """Counts per case and the batch minutes found; writes `cases` only, nothing when apply is False."""
    minutes = batch_minutes(char_model)
    counts = Counter()
    bounds = char_model.objects.aggregate(low=Min('id'), high=Max('id'))
    if bounds['low'] is None:
        return counts, minutes
    for low in range(bounds['low'], bounds['high'] + 1, range_size):
        high = low + range_size
        counts['no_set'] += (char_model.objects.order_by()
                             .filter(id__gte=low, id__lt=high, minimal_solution=b'')
                             .count())
        for case, ids in classify(char_model, generation_model, minutes, low, high).items():
            counts[case] += len(ids)
            if apply and ids and (cases is None or case in cases):
                (char_model.objects.filter(id__in=ids)
                 .update(stuff_time=_source(case, generation_model)))
    return counts, minutes
