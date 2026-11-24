"""Per-game-version compatibility data.

What's listed here is whatever exists in Dofus 3 but is absent (or different)
in older versions. Default behavior assumes Dofus 3 (the live current version).
"""

# Classes that don't exist in a given game version.
# Forgelance was introduced in Dofus 3.
CLASSES_NOT_IN_VERSION = {
    'dofus3': {'Bellaphone'},
    'beta': set(),
    'dofus2': {'Forgelance', 'Bellaphone'},
    # Retro is Dofus 1.29: only the original 12 classes exist.
    'retro': {'Forgelance', 'Bellaphone', 'Eliotrope', 'Huppermage', 'Ouginak',
              'Masqueraider', 'Foggernaut', 'Rogue'},
    # Dofus Touch has 15 classes: the original 12 + Rogue (Roublard),
    # Masqueraider (Zobal) and Foggernaut (Steamer). Eliotrope, Huppermage,
    # Ouginak and Forgelance never shipped on Touch.
    'touch': {'Forgelance', 'Bellaphone', 'Eliotrope', 'Huppermage', 'Ouginak'},
    'touchbeta': {'Forgelance', 'Eliotrope', 'Huppermage', 'Ouginak'},
    'retrobeta': {'Forgelance', 'Bellaphone', 'Eliotrope', 'Huppermage', 'Ouginak',
                  'Masqueraider', 'Foggernaut', 'Rogue'},
}


def filter_classes_for_version(classes, game_version):
    """Return only the classes available in this game version."""
    excluded = CLASSES_NOT_IN_VERSION.get(game_version, set())
    if not excluded:
        return list(classes)
    return [c for c in classes if c not in excluded]


def class_exists_in_version(char_class, game_version):
    return char_class not in CLASSES_NOT_IN_VERSION.get(game_version, set())


CLASSES_AWAITING_DATA = {
    'dofus3': set(),
    'beta': set(),
    'dofus2': set(),
    'touch': set(),
    'retro': set(),
}
CLASSES_AWAITING_DATA['touchbeta'] = CLASSES_AWAITING_DATA['touch']
CLASSES_AWAITING_DATA['retrobeta'] = CLASSES_AWAITING_DATA['retro']


def classes_with_data(classes, game_version):
    """The version's classes that already have their game data."""
    waiting = CLASSES_AWAITING_DATA.get(game_version, set())
    return [c for c in filter_classes_for_version(classes, game_version) if c not in waiting]


def first_class_with_data(classes, game_version):
    """The first class the version lists that already has its game data."""
    found = classes_with_data(classes, game_version)
    return found[0] if found else None
