# How big the character preview is drawn, per account.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0030_char_hidden_parts'),
    ]

    operations = [
        migrations.AddField(
            model_name='useralias',
            name='preview_size',
            field=models.IntegerField(default=100),
        ),
    ]
