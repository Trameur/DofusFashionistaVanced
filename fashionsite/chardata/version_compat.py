"""Per-game-version compatibility data.

What's listed here is whatever exists in Dofus 3 but is absent (or different)
in older versions. Default behavior assumes Dofus 3 (the live current version).
"""

# Classes that don't exist in a given game version.
# Forgelance was introduced in Dofus 3.
CLASSES_NOT_IN_VERSION = {
    'dofus2': {'Forgelance'},
    # Retro is Dofus 1.29: only the original 12 classes exist.
    'retro': {'Forgelance', 'Eliotrope', 'Huppermage', 'Ouginak',
              'Masqueraider', 'Foggernaut', 'Rogue'},
    # 'touch': set(),  # TODO once a Touch data source is identified
}


def filter_classes_for_version(classes, game_version):
    """Return only the classes available in this game version."""
    excluded = CLASSES_NOT_IN_VERSION.get(game_version, set())
    if not excluded:
        return list(classes)
    return [c for c in classes if c not in excluded]


def class_exists_in_version(char_class, game_version):
    return char_class not in CLASSES_NOT_IN_VERSION.get(game_version, set())
