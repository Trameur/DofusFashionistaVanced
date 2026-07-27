# Page counters for the staff dashboard.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0026_utf8mb4_tables'),
    ]

    operations = [
        migrations.CreateModel(
            name='PageHit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(db_index=True)),
                ('path', models.CharField(max_length=200)),
                ('game_version', models.CharField(default='dofus3', max_length=20)),
                ('count', models.BigIntegerField(default=0)),
            ],
            options={
                'unique_together': {('day', 'path', 'game_version')},
            },
        ),
    ]
