# The five preview colours a build picks. Empty means the default palette.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0028_char_gender'),
    ]

    operations = [
        migrations.AddField(
            model_name='char',
            name='colors',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
    ]
