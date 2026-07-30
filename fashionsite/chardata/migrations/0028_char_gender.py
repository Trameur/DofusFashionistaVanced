# Which body and head the character preview draws.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0027_pagehit'),
    ]

    operations = [
        migrations.AddField(
            model_name='char',
            name='gender',
            field=models.IntegerField(default=0),
        ),
    ]
