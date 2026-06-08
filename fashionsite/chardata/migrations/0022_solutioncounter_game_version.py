from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0021_buildtag'),
    ]

    operations = [
        migrations.AddField(
            model_name='solutioncounter',
            name='game_version',
            field=models.CharField(default='dofus3', max_length=20),
        ),
    ]
