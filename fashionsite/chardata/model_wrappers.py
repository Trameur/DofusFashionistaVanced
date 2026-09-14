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

from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from chardata.smart_build import ASPECT_TO_NAME, ASPECT_TO_SHORT_NAME

SHORT_NAME_TO_KEY = {v: k for k, v in ASPECT_TO_SHORT_NAME.items()}

def translate_build_name(build_name):
    """Translate a build name that may contain multiple aspects separated by / or spaces"""
    if not build_name:
        return ''
    
    lookup_key = SHORT_NAME_TO_KEY.get(build_name, build_name.lower())
    if lookup_key in ASPECT_TO_NAME:
        return str(ASPECT_TO_NAME[lookup_key])
    
    if '/' in build_name:
        parts = build_name.split('/')
        translated_parts = []
        for part in parts:
            part = part.strip()
            if part:
                translated_parts.append(translate_build_name(part))
        return '/'.join(translated_parts)
    
    # Handle space-separated parts (e.g., "Int Crit Glass Cannon")
    # But we need to be smart about multi-word build types like "Glass Cannon"
    if ' ' in build_name:
        words = build_name.split(' ')
        translated_parts = []
        i = 0
        while i < len(words):
            matched = False
            if i + 1 < len(words):
                two_word = f"{words[i]} {words[i+1]}"
                lookup_key = SHORT_NAME_TO_KEY.get(two_word, two_word.lower())
                if lookup_key in ASPECT_TO_NAME:
                    translated_parts.append(str(ASPECT_TO_NAME[lookup_key]))
                    i += 2
                    matched = True
            
            if not matched:
                lookup_key = SHORT_NAME_TO_KEY.get(words[i], words[i].lower())
                translated_parts.append(str(ASPECT_TO_NAME.get(lookup_key, words[i])))
                i += 1
        
        return ' '.join(translated_parts)

    return build_name


#: Les aspects qui viennent APRES l'element: un build qui en porte un n'est
#: pas equilibre, et son nom se suffit.
FOCUS_ASPECTS = ('Vit', 'Glass Cannon', 'Dam', 'Heals', 'AP Red', 'MP Red',
                 'Crit', 'Res', 'Leecher', 'PP', 'Pods', 'Traps', 'Summons',
                 'Pushback', 'Non-Crit')


def build_label(char_build):
    """Le nom du build, tel que le lecteur doit le lire, dans sa langue.

    Une seule reponse pour toutes les pages. Elle etait ecrite trois fois et
    les trois ne disaient pas la meme chose. Mesure du 14 septembre 2026, en
    francais:

    | char_build         | en-tete, projets, galerie | profil et feed     | choix a comparer   |
    |--------------------|---------------------------|--------------------|--------------------|
    | `Str`              | Force Equilibre           | Force              | **Str**            |
    | `''`               | Equilibre                 | (rien)             | **(rien)**         |
    | `Str Glass Cannon` | Force Canon de verre      | Force Canon de ... | **Str Glass Cannon** |
    | `Cha/Agi`          | Chance/Agilite Equilibre  | Chance/Agilite     | **Cha/Agi**        |

    La page qui sert a **choisir** entre deux builds rendait donc la chaine
    interne, dans les cinq langues, l'anglais compris ou <<Str>> se lit
    <<Strength>>. C'est la meme faute que le lot 76 a corrigee sur l'en-tete
    de projet, sur les lecteurs qu'il n'avait pas parcourus.

    `char_build` vide veut dire <<aucun aspect choisi>>, et le site appelle
    cela <<Equilibre>> depuis toujours: c'est sa convention, pas une mesure du
    stuff. Elle etait deja sur trois pages; elle est maintenant sur les
    quatre, au lieu d'un vide et d'un separateur pendant.
    """
    if not char_build:
        return str(ASPECT_TO_NAME['balanced'])
    has_focus = any(focus in char_build for focus in FOCUS_ASPECTS)
    translated = translate_build_name(char_build)
    if has_focus:
        return translated
    return '%s %s' % (translated, ASPECT_TO_NAME['balanced'])


class WrappedChar(object):

    def __init__(self, char):
        self.char = char

    def gallery_refusal(self):
        """Pourquoi la galerie n'affiche pas ce build, ou une chaine vide.

        Compte du 11 septembre 2026: elle en ecarte 74,5 %, et jusqu'ici leur
        auteur n'en savait rien. La colonne lui disait meme <<Dans la
        galerie>>, ce qui etait faux trois fois sur quatre.
        """
        from chardata.gallery_visibility import sentence_for
        return sentence_for(self.char)

    def class_string(self):
        return LOCALIZED_CHARACTER_CLASSES.get(self.char.char_class, '')

    def class_avatar(self):
        from chardata.solution_view import get_class_avatar
        return get_class_avatar(self.char)
    
    def build_string(self):
        """Return translated build type name(s)"""
        return build_label(self.char.char_build)
