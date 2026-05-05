from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0012_alter_char_created_time_alter_char_modified_time_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='char',
            index=models.Index(fields=['link_shared', 'deleted'], name='chardata_char_shared_deleted_idx'),
        ),
        migrations.AddIndex(
            model_name='char',
            index=models.Index(fields=['link_shared', 'deleted', 'view_count'], name='chardata_char_shared_views_idx'),
        ),
        migrations.AddIndex(
            model_name='char',
            index=models.Index(fields=['link_shared', 'deleted', 'created_time'], name='chardata_char_shared_created_idx'),
        ),
        migrations.AddIndex(
            model_name='char',
            index=models.Index(fields=['link_shared', 'deleted', 'modified_time'], name='chardata_char_shared_modified_idx'),
        ),
    ]
