# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from itertools import product

import re
import unicodedata


def _fold(text):
    # Lowercase + strip accents so localized markers (e.g. "degats", "piege")
    # match however the user typed them ("dégâts", "piège").
    folded = unicodedata.normalize('NFKD', text or '')
    return ''.join(c for c in folded if not unicodedata.combining(c)).lower()


def parse_aspects(build):
    words = re.findall(r"\w+", _fold(build))
    phrase = ' '.join(words)

    aspects = set()   

    if _words_contain_marker(words, ['str', 'stre', 'strength', 'earth',
                                     'terre', 'force', 'tierra', 'fuerza',
                                     'terra', 'forca', 'erde', 'starke']):
        aspects.add('str')

    if _words_contain_marker(words, ['int', 'intel', 'intelligence', 'fire',
                                     'feu', 'fuego', 'fogo', 'feuer', 'intelligenz']):
        aspects.add('int')

    if _words_contain_marker(words, ['agi', 'agility', 'air', 'agilite', 'aire',
                                     'ar', 'agilidad', 'agilidade', 'luft',
                                     'beweglichkeit']):
        aspects.add('agi')

    if _words_contain_marker(words, ['cha', 'chance', 'water', 'eau', 'agua',
                                     'wasser', 'suerte', 'sorte']):
        aspects.add('cha')

    if _words_contain_marker(words, ['wis', 'wisdom', 'leech', 'leecher', 'leeching',
                                     'leveling', 'training', 'xp', 'xping', 'exp',
                                     'exping', 'wiswhore', 'sagesse', 'sabiduria',
                                     'sabedoria', 'weisheit']):
        aspects.add('wis')

    if _words_contain_marker(words, ['vit', 'vita', 'vital', 'vitality', 'vitalite',
                                     'vitalidad', 'vitalidade', 'vitalitat']):
        aspects.add('vit')

    if _words_contain_marker(words, ['res', 'resist', 'resists', 'resistance',
                                     'resistances', 'resistencia', 'resistencias',
                                     'resistenz']):
        aspects.add('res')

    if _words_contain_marker(words, ['tank', 'tanker']):
        aspects.add('vit')
        aspects.add('res')

    if _words_contain_marker(words, ['dam', 'damage', 'degats', 'dano', 'danos',
                                     'schaden']):
        aspects.add('dam')

    #if _words_contain_marker(words, ['attack', 'attacker', 'dealer', 'dps', 'dpt', 'hitter']):
    #    aspects.add('damdealer')

    crit_words = [''.join(t) for t in product(
            ['non', 'no'],
            ['', '-'],
            ['cri', 'crit', 'crits', 'critical', 'ch'])]
    crit_phrases = [''.join(t) for t in product(
            ['non ', 'no '],
            ['cri', 'crit', 'crits', 'critical', 'ch'])]
    if (_words_contain_marker(words, ['cri', 'crit', 'crits', 'ch', 'critical'])
        and not(_words_contain_marker(words, crit_words)
                or _phrase_contains_marker(phrase, crit_phrases))):
        aspects.add('crit')

    if _words_contain_marker(words, ['omni', 'omnielement', 'omnielemental', 'allelement',
                                'allelements', 'pow', 'power', 'multi', 'multielement',
                                'multielemento', 'polyvalent', 'puissance']):
        aspects.add('omni')

    ap_rape_phrases = [''.join(t) for t in product(
            ['ap ', 'ap'],
            ['rape', 'raper', 'removal', 'reduction', 'red'])]
    if _phrase_contains_marker(phrase, ap_rape_phrases):
        aspects.add('aprape')

    mp_rape_phrases = [''.join(t) for t in product(
            ['mp ', 'mp'],
            ['rape', 'raper', 'removal', 'reduction', 'red'])]
    if _phrase_contains_marker(phrase, mp_rape_phrases):
        aspects.add('mprape')

    if ('aprape' not in aspects and 'mprape' not in aspects
        and _words_contain_marker(words, ['rape', 'raper', 'disabler', 'disable'])):
        aspects.add('aprape')
        aspects.add('mprape')
    
    if _words_contain_marker(words, ['heal', 'heals', 'healer', 'healing', 'healbot',
                                     'soin', 'soins', 'soigneur', 'sanador', 'cura',
                                     'curandeiro', 'heilung', 'heiler']):
        aspects.add('heal')

    if _words_contain_marker(words, ['trap', 'traps', 'trapper', 'trapdam', 'piege',
                                     'pieges', 'trampa', 'trampas', 'armadilha',
                                     'armadilhas', 'falle', 'fallen']):
        aspects.add('trap')

    if _words_contain_marker(words, ['pp', 'prosp', 'prospecting', 'prospe', 'drop',
                                     'dropwhore', 'prospection', 'prospeccion',
                                     'prospeccao', 'prospektion']):
        aspects.add('pp')

    if (_words_contain_marker(words, ['pod', 'pods', 'prof', 'profession',
                                      'mine', 'miner', 'mining',
                                      'alch', 'alchemist',
                                      'harvest', 'harvesting', 'harvester',
                                      'craft', 'crafter', 'crafting'])
        or ('pp' not in aspects
            and _words_contain_marker(words, ['farm', 'farmer', 'farming']))):
        aspects.add('pods')

    if _words_contain_marker(words, ['fish', 'fisher', 'fishing']):
        aspects.add('pp')
        aspects.add('pods')

    if _words_contain_marker(words, ['psh', 'pushback', 'push', 'pushbackdam',
                                     'poussee', 'repousse', 'empuje', 'empurrao']):
        aspects.add('pushback')

    if _words_contain_marker(words, ['summon', 'summons', 'summoning', 'summo',
                                     'summoner', 'invocation', 'invocations', 'invoc',
                                     'invocateur', 'invocador', 'invocacao',
                                     'beschworung', 'beschworer']):
        aspects.add('summon')

    if _words_contain_marker(words, ['pvp', 'pvper', 'pvping', 'duel',
                                     'kolo', 'kolossium', 'perc', 'perceptor',
                                     'kolizeum', 'kolosseum', 'arene', 'arena']):
        aspects.add('pvp')
        
    if (_words_contain_marker(words, ['duel', 'dueler', 'dueling', '1v1', '1vs1', '1x1', 'x1'])
        or _phrase_contains_marker(phrase, ['1 v 1', '1 vs 1', '1 x 1'])):
        aspects.add('pvp')        
        aspects.add('duel')

    return aspects

def _words_contain_marker(words, markers):
    return any(marker in words for marker in markers)
    
def _phrase_contains_marker(phrase, markers):
    return any(marker in phrase for marker in markers)
    