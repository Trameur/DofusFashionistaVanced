from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0013_char_shared_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='char',
            name='game_version',
            field=models.CharField(db_index=True, default='dofus3', max_length=20),
        ),
    ]
