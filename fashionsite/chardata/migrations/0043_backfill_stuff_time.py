from django.db import migrations

from chardata.stuff_time_backfill import backfill_stuff_time


def fill(apps, schema_editor):
    backfill_stuff_time(apps.get_model('chardata', 'Char'),
                        apps.get_model('chardata', 'SolutionGeneration'))


class Migration(migrations.Migration):

    # Each id range commits on its own; the backfill recomputes every row when rerun
    atomic = False

    dependencies = [
        ('chardata', '0042_char_stuff_time'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
