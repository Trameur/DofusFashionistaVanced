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
        if ADDRESS.match(row.alias.strip()):
            row.alias = handle(row.user_id)
            to_update.append(row)
    address_ids = [user.pk for user in User.objects.filter(username__contains='@')
                   if ADDRESS.match(user.username.strip())]
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


def name_the_nameless(apps, schema_editor):
    # The gallery searches public names only, and these accounts showed their username
    User = apps.get_model('auth', 'User')
    UserAlias = apps.get_model('chardata', 'UserAlias')
    UserSocialAuth = apps.get_model('social_django', 'UserSocialAuth')
    social = set(UserSocialAuth.objects.values_list('user_id', flat=True))
    rows = {row.user_id: row for row in UserAlias.objects.all()}
    for user in User.objects.only('pk', 'username'):
        row = rows.get(user.pk)
        if user.pk in social or (row is not None and (row.alias or '').strip()):
            continue
        if row is None:
            UserAlias.objects.create(user_id=user.pk, alias=user.username[:50])
        else:
            row.alias = user.username[:50]
            row.save(update_fields=['alias'])


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0051_google_accounts_get_a_public_name'),
    ]

    operations = [
        migrations.RunPython(hide_the_addresses, migrations.RunPython.noop),
        migrations.RunPython(name_the_nameless, migrations.RunPython.noop),
    ]
