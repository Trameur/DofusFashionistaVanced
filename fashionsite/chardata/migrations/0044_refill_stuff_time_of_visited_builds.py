from django.db import migrations

from chardata.stuff_time_backfill import backfill_stuff_time


def refill(apps, schema_editor):
    backfill_stuff_time(apps.get_model('chardata', 'Char'),
                        apps.get_model('chardata', 'SolutionGeneration'),
                        cases=('view_saved',))


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('chardata', '0043_backfill_stuff_time'),
    ]

    operations = [
        migrations.RunPython(refill, migrations.RunPython.noop),
    ]
