STAT_ICON_FILENAME_BY_KEY = {
    'hp': 'Health_Points.png',
    'vit': 'Vitality.png',
    'str': 'Strength.png',
    'int': 'Intelligence.png',
    'cha': 'Chance.png',
    'agi': 'Agility.png',
    'wis': 'Wisdom.png',
    'ap': 'AP.png',
    'mp': 'MP.png',
    'range': 'Range.png',
    'summon': 'Summon.png',
    'init': 'Initiative.png',
    'pp': 'Prospecting.png',
    'pod': 'pod.png',
    'lock': 'Lock.png',
    'dodge': 'Dodge.png',
    'pow': 'puissance.png',
    'dam': 'dommages.png',
    'heals': 'soin.png',
    'ch': 'critique.png',
    'cf': 'critique.png',
    'cridam': 'dmgCritique.png',
    'crires': 'resCrit.png',
    'pshdam': 'dmgPoussee.png',
    'pshres': 'resPoussee.png',
    'apred': 'retraitPA.png',
    'apres': 'esquivePA.png',
    'mpred': 'retraitPM.png',
    'mpres': 'esquivePM.png',
    'neutdam': 'neutre.png',
    'neutres': 'resNeutre.png',
    'neutresper': 'resNeutre.png',
    'earthdam': 'terre.png',
    'earthres': 'resTerre.png',
    'earthresper': 'resTerre.png',
    'firedam': 'feu.png',
    'fireres': 'resFeu.png',
    'fireresper': 'resFeu.png',
    'waterdam': 'eau.png',
    'waterres': 'resEau.png',
    'waterresper': 'resEau.png',
    'airdam': 'air.png',
    'airres': 'resAir.png',
    'airresper': 'resAir.png',
    'pvpneutres': 'resNeutre.png',
    'pvpearthres': 'resTerre.png',
    'pvpfireres': 'resFeu.png',
    'pvpwaterres': 'resEau.png',
    'pvpairres': 'resAir.png',
    'pvpneutresper': 'resNeutre.png',
    'pvpearthresper': 'resTerre.png',
    'pvpfireresper': 'resFeu.png',
    'pvpwaterresper': 'resEau.png',
    'pvpairresper': 'resAir.png',
    'trapdam': 'tx_trap.png',
    'trapdamper': 'tx_trap.png',
    'permedam': 'dmgMelee.png',
    'perrandam': 'dmgDistance.png',
    'perweadam': 'dmgArme.png',
    'perspedam': 'dmgSort.png',
    'respermee': 'resMelee.png',
    'resperran': 'resDistance.png',
    'resperwea': 'resArme.png',
    'ref': 'renvoi.png',
}


def get_stat_icon_filename(stat_key):
    if not stat_key:
        return None
    return STAT_ICON_FILENAME_BY_KEY.get(stat_key)


def get_stat_icon_path(stat_key):
    icon_filename = get_stat_icon_filename(stat_key)
    if icon_filename is None:
        return None
    # Shipped as webp at 120px: these show at 15 to 30px, and the source art
    # was up to 500x500.
    return 'chardata/originals/%s.webp' % icon_filename.rsplit('.', 1)[0]