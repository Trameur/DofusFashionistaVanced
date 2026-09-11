# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le nom d'un build dans un gabarit, jamais vide.

Un filtre plutot qu'une propriete de modele: les cartes de la galerie
travaillent sur des objets legers tires d'un `.only()`, et un filtre les
accepte comme il accepte un Char entier.
"""

from django import template

from chardata.build_name import display_name

register = template.Library()


@register.filter(name='build_display_name')
def build_display_name(char):
    return display_name(char)
