import pickle

from django.db import migrations

# The GM-only items added to DEFAULT_EXCLUSION_ANKAMA_IDS in July 2026. Default
# exclusions are only seeded when a char is created, so chars created before the
# addition could still equip them (the GM combat pets carry +300/+600 Strength
# and distort solves). These items were never forbidden for those chars, so
# forbidding them here overrides no deliberate user choice; they stay removable
# on the exclusions page like any other default.
GM_ANKAMA_IDS = [6894, 6895, 7913, 7920]

GAME_VERSIONS = ['dofus3', 'beta', 'dofus2', 'touch', 'retro']


def forbid_gm_items_on_existing_chars(apps, schema_editor):
    from fashionistapulp.structure import get_structure
    Char = apps.get_model('chardata', 'Char')
    for version in GAME_VERSIONS:
        try:
            structure = get_structure(version)
        except Exception:
            continue
        item_ids = []
        for ankama_id in GM_ANKAMA_IDS:
            item = structure.get_item_by_ankama_id(ankama_id)
            if item is not None:
                item_ids.append(item.id)
        if not item_ids:
            continue
        for char in Char.objects.filter(game_version=version).iterator():
            try:
                exclusions = pickle.loads(char.exclusions) if char.exclusions else []
            except Exception:
                continue
            if not isinstance(exclusions, list):
                continue
            missing = [i for i in item_ids if i not in exclusions]
            if not missing:
                continue
            update_fields = ['exclusions']
            char.exclusions = pickle.dumps(exclusions + missing)
            # Mirror set_exclusions_list_and_check_inclusions: an excluded item
            # cannot stay pinned, or the solve becomes infeasible.
            try:
                inclusions = pickle.loads(char.inclusions) if char.inclusions else {}
            except Exception:
                inclusions = {}
            if isinstance(inclusions, dict):
                dirty = False
                for slot, pinned in list(inclusions.items()):
                    if pinned in missing:
                        inclusions[slot] = ''
                        dirty = True
                if dirty:
                    char.inclusions = pickle.dumps(inclusions)
                    update_fields.append('inclusions')
            char.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('chardata', '0025_solutiongeneration'),
    ]

    operations = [
        migrations.RunPython(forbid_gm_items_on_existing_chars,
                             migrations.RunPython.noop),
    ]
