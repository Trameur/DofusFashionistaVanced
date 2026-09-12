# -*- coding: utf-8 -*-

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

"""Match an item line to the spell it names."""

import re
from functools import lru_cache


class SpellTip(object):

    def __init__(self, spell, description):
        self.spell = spell
        self.description = description


@lru_cache(maxsize=4096)
def _names_it(spell):
    """Le nom du sort, cherche comme un MOT et non comme une suite de lettres.

    Un nom de sort est parfois aussi un mot courant. En allemand <<Nahkampf>>
    est le nom du sort que l'anglais appelle Punch, et c'est aussi le mot de
    tous les jours pour la melee: il vit a l'interieur de
    <<Nahkampfentfernung>>, <<Nahkampfangriff>>, <<Nahkampfschaden>>. Cherche
    comme une sous-chaine, il collait a la fiche du Dofus Emeraude
    l'explication d'un sort qui n'y a rien a faire: <<Occasionne des dommages
    Neutre.>>

    La cause etait plus haut: `store_spell_tooltips` laissait ce sort entrer
    dans la table, et la corriger la-bas l'en retire pour de bon. Ce garde-ci
    est la seconde ligne de defense, et il corrige en plus un cas que la table
    ne pouvait pas voir: la Ceinture Sanglante de Retro annonce <<Increases
    the range of Cut by 3>> et recevait l'explication de <<Increase>>, pris a
    l'interieur de <<Increases>>, au lieu de celle de <<Cut>>. Deux lignes,
    mesurees le 12 septembre 2026 sur les cinq versions et les cinq langues;
    aucune autre des 13 091 lignes qui recoivent une infobulle ne change.
    """
    return re.compile(r'(?<!\w)%s(?!\w)' % re.escape(spell))


def spell_tip_for(line, tooltips):
    """The spell this line is about, or None.

    Names overlap: Retro has both "Bond" and "Bond Felin", so the longest match
    wins. A name that only lives inside a longer word names nothing.
    """
    if not line or not tooltips:
        return None
    text = str(line)
    best = None
    for spell in tooltips:
        if spell and _names_it(spell).search(text):
            if best is None or len(spell) > len(best):
                best = spell
    if best is None:
        return None
    return SpellTip(best, tooltips[best])
