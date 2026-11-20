"""The stat a "Max." effect caps, by the characteristic id the game writes in it."""

CHARACTERISTIC_ID_TO_STAT_NAME = {
    1: 'AP',
    19: 'Range',
    23: 'MP',
    26: 'Summon',
}


def max_caps(effects):
    """[(stat name, max value)] of the "Max." rows among transformed [first, second, name] effects."""
    caps = []
    for char_id, max_value, stat_name in effects:
        if stat_name != 'Max.' or max_value is None:
            continue
        mapped = CHARACTERISTIC_ID_TO_STAT_NAME.get(char_id)
        if mapped is not None:
            caps.append((mapped, max_value))
    return caps
