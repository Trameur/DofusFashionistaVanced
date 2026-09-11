# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le nom sous lequel un build se presente, quand son auteur n'en a pas donne.

La page de creation remplit le champ <<Nom du projet>> toute seule, avec le
nom du personnage suivi du niveau. Le nom du personnage, lui, n'est pas
obligatoire. Un joueur qui pose seulement son niveau part donc avec un projet
nomme <<espace, 199>>, et le champ etant obligatoire le formulaire passe sans
rien dire.

Mesure du 11 septembre 2026 sur la copie de production: **404 des 1980 builds
partages qui ont une solution n'ont pas de nom lisible**, soit un sur cinq, et
39 784 des 152 862 builds au total. Les plus frequents sont
<<espace 199>> (46 fois parmi les partages), <<espace 160>>, <<espace 60>>, et
<<NoName>>, qui est le defaut du serveur quand le champ manque.

Depuis que les builds neufs sont publics des qu'ils portent un stuff
(section 37), cette part n'est plus un detail de la liste personnelle: c'est
une carte de galerie sur cinq qui n'annonce rien.

Rien n'est reecrit dans la base. Les builds existants gardent leur nom, comme
toujours: c'est l'AFFICHAGE qui se rattrape, et la creation qui cesse de
fabriquer ces noms-la.
"""

import re

#: Un nom vide, ou qui n'est que des blancs.
_VIDE = re.compile(r'^\s*$')

#: Exactement ce que le script de la page ecrit quand le nom du personnage est
#: vide: une ou des espaces, le niveau, puis autant de <<copy>> que le build a
#: ete duplique. Le niveau tient sur trois chiffres au plus, donc <<espace
#: 1999>> est un nom tape par quelqu'un et reste tel quel.
_ARTEFACT = re.compile(r'^\s+\d{1,3}(\s+copy)*\s*$')

#: Ce que le serveur ecrit quand le formulaire n'a pas porte le champ.
_DEFAUT_DU_SERVEUR = 'NoName'


def is_placeholder(name):
    """Si ce nom ne dit rien de ce build.

    Mesure sur les vrais noms: la regle laisse passer <<200 sadi 200>>,
    <<117>>, <<espace 110cha int handmade>> et <<espace Travitas 130>>, qui
    sont des noms que quelqu'un a tapes, et ne prend que ce que la page a
    fabrique toute seule.
    """
    name = name or ''
    return bool(_VIDE.match(name)
                or name.strip() == _DEFAUT_DU_SERVEUR
                or _ARTEFACT.match(name))


def fallback_name(char_class, level):
    """Deux faits que le build porte toujours, dans la langue du lecteur.

    Pas de phrase inventee et rien de traduisible en plus: la classe est
    deja traduite ailleurs sur le site, et le niveau est un nombre.
    """
    from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
    classe = LOCALIZED_CHARACTER_CLASSES.get(char_class, char_class or '')
    niveau = '' if level is None else str(level)
    return ('%s %s' % (classe, niveau)).strip()


def display_name(char):
    """Le nom du build tel qu'on doit l'ecrire, jamais vide."""
    if char is None:
        return ''
    name = getattr(char, 'name', '') or ''
    if not is_placeholder(name):
        return name
    return fallback_name(getattr(char, 'char_class', ''),
                         getattr(char, 'level', None)) or name.strip()


def cleaned_at_creation(name, char_class, level):
    """Le nom a ecrire dans la base pour un build qui se cree.

    La reparation de l'affichage vaut pour les 39 784 builds deja ecrits; ici
    on cesse simplement d'en fabriquer d'autres.
    """
    if is_placeholder(name):
        return fallback_name(char_class, level)
    return name
