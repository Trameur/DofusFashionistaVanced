import re

from django.db import migrations

ADDRESS = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def handle(user_id):
    return 'Player%d' % user_id


def hide_the_addresses(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserAlias = apps.get_model('chardata', 'UserAlias')
    to_update = []
    for row in UserAlias.objects.filter(alias__contains='@'):
        if ADDRESS.match(row.alias):
            row.alias = handle(row.user_id)
            to_update.append(row)
    address_ids = [user.pk for user in User.objects.filter(username__contains='@')
                   if ADDRESS.match(user.username)]
    rows = {row.user_id: row for row in UserAlias.objects.filter(user_id__in=address_ids)}
    to_create = []
    for user_id in address_ids:
        row = rows.get(user_id)
        if row is None:
            to_create.append(UserAlias(user_id=user_id, alias=handle(user_id)))
        elif not (row.alias or '').strip():
            row.alias = handle(user_id)
            to_update.append(row)
    UserAlias.objects.bulk_create(to_create, batch_size=500)
    UserAlias.objects.bulk_update(to_update, ['alias'], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0051_google_accounts_get_a_public_name'),
    ]

    operations = [
        migrations.RunPython(hide_the_addresses, migrations.RunPython.noop),
    ]
