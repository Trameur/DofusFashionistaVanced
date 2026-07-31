# Which pieces the preview leaves off. Empty means it draws them all.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0029_char_colors'),
    ]

    operations = [
        migrations.AddField(
            model_name='char',
            name='hidden_parts',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
    ]
