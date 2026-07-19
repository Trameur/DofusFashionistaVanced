# Convert every legacy-charset table to utf8mb4.
#
# Production errors (2026-07-19): a Google login with a Turkish last name
# crashed with DataError 1366 on auth_user.last_name, and a project named
# with an emoji crashed on chardata_char.name. The connection already speaks
# utf8mb4 and the database default is utf8mb4, but tables imported from the
# old server kept their original charset in their CREATE TABLE, so any
# character outside it still fails to store.
#
# The tables are discovered at run time from information_schema (both
# table-level collation and stray per-column charsets), so the migration is
# idempotent and becomes a no-op once everything is converted. On sqlite
# (dev/tests) it is a no-op by construction.

from django.db import migrations


def convert_tables_to_utf8mb4(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE()')
        db_name = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT t.table_name
            FROM information_schema.tables t
            JOIN information_schema.collation_character_set_applicability c
              ON t.table_collation = c.collation_name
            WHERE t.table_schema = %s
              AND t.table_type = 'BASE TABLE'
              AND c.character_set_name <> 'utf8mb4'
            """, [db_name])
        tables = {row[0] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND character_set_name IS NOT NULL
              AND character_set_name <> 'utf8mb4'
            """, [db_name])
        tables.update(row[0] for row in cursor.fetchall())

        for table in sorted(tables):
            cursor.execute(
                'ALTER TABLE `%s` CONVERT TO CHARACTER SET utf8mb4 '
                'COLLATE utf8mb4_unicode_ci' % table)


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0025_solutiongeneration'),
    ]

    operations = [
        migrations.RunPython(convert_tables_to_utf8mb4,
                             migrations.RunPython.noop),
    ]
