from django.conf import settings
from django.db import migrations

PLACEHOLDER_ADDRESS = 'admin@localhost'


def flag_the_listed_accounts(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    for address in settings.GEN_CONFIGS.get('SUPER_USERS_EMAILS') or []:
        if address == PLACEHOLDER_ADDRESS:
            continue
        # MySQL's collation also matches accent and case variants of the address
        for user in User.objects.filter(email=address):
            if user.email == address and not user.is_superuser:
                user.is_superuser = True
                user.save(update_fields=['is_superuser'])


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('chardata', '0049_char_weapon_forge'),
    ]

    operations = [
        migrations.RunPython(flag_the_listed_accounts, migrations.RunPython.noop),
    ]
