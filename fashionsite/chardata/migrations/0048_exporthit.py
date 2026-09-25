from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0047_importsourcehit'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportHit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(db_index=True)),
                ('destination', models.CharField(max_length=20)),
                ('host', models.CharField(blank=True, max_length=190)),
                ('game_version', models.CharField(default='dofus3', max_length=20)),
                ('count', models.BigIntegerField(default=0)),
            ],
            options={
                'unique_together': {('day', 'destination', 'host', 'game_version')},
            },
        ),
    ]
