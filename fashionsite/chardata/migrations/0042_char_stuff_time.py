from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0041_char_created_version_char_solved_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='char',
            name='stuff_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
