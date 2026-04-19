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

# Create reverse mapping from short names to keys (e.g., "Int" -> "int", "Glass Cannon" -> "glasscannon")
SHORT_NAME_TO_KEY = {v: k for k, v in ASPECT_TO_SHORT_NAME.items()}

def translate_build_name(build_name):
    """Translate a build name that may contain multiple aspects separated by / or spaces"""
    if not build_name:
        return ''
    
    # First, try to match the entire string (e.g., "Glass Cannon" as a whole)
    lookup_key = SHORT_NAME_TO_KEY.get(build_name, build_name.lower())
    if lookup_key in ASPECT_TO_NAME:
        return str(ASPECT_TO_NAME[lookup_key])
    
    # Handle slash-separated parts first (e.g., "Agi Glass Cannon/Pushback")
    if '/' in build_name:
        parts = build_name.split('/')
        translated_parts = []
        for part in parts:
            part = part.strip()
            if part:
                # Recursively translate each part (which may contain spaces)
                translated_parts.append(translate_build_name(part))
        return '/'.join(translated_parts)
    
    # Handle space-separated parts (e.g., "Int Crit Glass Cannon")
    # But we need to be smart about multi-word build types like "Glass Cannon"
    if ' ' in build_name:
        # Try to find multi-word matches first (longer matches first)
        words = build_name.split(' ')
        translated_parts = []
        i = 0
        while i < len(words):
            # Try matching 2 words first (for "Glass Cannon", etc.)
            matched = False
            if i + 1 < len(words):
                two_word = f"{words[i]} {words[i+1]}"
                lookup_key = SHORT_NAME_TO_KEY.get(two_word, two_word.lower())
                if lookup_key in ASPECT_TO_NAME:
                    translated_parts.append(str(ASPECT_TO_NAME[lookup_key]))
                    i += 2
                    matched = True
            
            # If no 2-word match, try single word
            if not matched:
                lookup_key = SHORT_NAME_TO_KEY.get(words[i], words[i].lower())
                translated_parts.append(str(ASPECT_TO_NAME.get(lookup_key, words[i])))
                i += 1
        
        return ' '.join(translated_parts)
    
    # Single word that wasn't found
    return build_name

class WrappedChar(object):

    def __init__(self, char):
        self.char = char

    def class_string(self):
        return LOCALIZED_CHARACTER_CLASSES.get(self.char.char_class, '')
    
    def build_string(self):
        """Return translated build type name(s)"""
        build_name = self.char.char_build
        
        # Check if build has no focus aspects (which means it's balanced)
        # Focus aspects are those that appear after the element (like Vit, Dam, Crit, etc.)
        focus_aspects = ['Vit', 'Glass Cannon', 'Dam', 'Heals', 'AP Red', 'MP Red', 
                        'Crit', 'Res', 'Leecher', 'PP', 'Pods', 'Traps', 'Summons', 
                        'Pushback', 'Non-Crit']
        
        has_focus = any(focus in build_name for focus in focus_aspects if build_name)
        
        if build_name and not has_focus:
            # Build has elements but no focus = balanced
            translated = translate_build_name(build_name)
            return f"{translated} {ASPECT_TO_NAME['balanced']}"
        elif not build_name:
            # No build type at all = balanced
            return str(ASPECT_TO_NAME['balanced'])
        else:
            return translate_build_name(build_name)
