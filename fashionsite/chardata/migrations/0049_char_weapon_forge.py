from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0048_exporthit'),
    ]

    operations = [
        migrations.AddField(
            model_name='char',
            name='weapon_forge',
            field=models.CharField(blank=True, db_default='', default='', max_length=255),
        ),
    ]
