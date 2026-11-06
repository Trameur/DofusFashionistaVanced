from django.db import migrations


def handle(user_id):
    return 'Player%d' % user_id


def name_the_google_accounts(apps, schema_editor):
    UserAlias = apps.get_model('chardata', 'UserAlias')
    UserSocialAuth = apps.get_model('social_django', 'UserSocialAuth')
    google_ids = set(UserSocialAuth.objects.values_list('user_id', flat=True))
    rows = {row.user_id: row for row in UserAlias.objects.all()
            if row.user_id in google_ids}
    to_create = []
    to_update = []
    for user_id in google_ids:
        row = rows.get(user_id)
        if row is None:
            to_create.append(UserAlias(user_id=user_id, alias=handle(user_id)))
        elif not (row.alias or '').strip():
            row.alias = handle(user_id)
            to_update.append(row)
    UserAlias.objects.bulk_create(to_create, batch_size=500)
    UserAlias.objects.bulk_update(to_update, ['alias'], batch_size=500)


def clear_the_handles(apps, schema_editor):
    UserAlias = apps.get_model('chardata', 'UserAlias')
    for row in UserAlias.objects.filter(alias__startswith='Player'):
        if row.alias == handle(row.user_id):
            row.alias = None
            row.save(update_fields=['alias'])


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0050_superusers_by_flag'),
        ('social_django', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(name_the_google_accounts, clear_the_handles),
    ]
