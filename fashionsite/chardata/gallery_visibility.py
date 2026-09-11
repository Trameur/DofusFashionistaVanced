# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Pourquoi un build publie n'apparait pas dans la galerie.

La galerie ecarte les builds qu'elle ne peut pas montrer honnetement. Compte
du 11 septembre 2026 sur la copie de production: **1476 des 1980 builds
partages qui ont une solution sont ecartes, soit 74,5 %**. Les raisons se
cumulent: emplacements perimes 1382, objets absents du catalogue 1083,
conditions non tenues 1050.

Ce module ne change pas cette regle, il la rend VISIBLE. Jusqu'ici l'auteur
publiait, ne voyait son build nulle part, et rien sur sa propre page ne le
lui disait. Depuis que les builds sont publics par defaut (section 37), la
page allait meme jusqu'a lui affirmer <<Dans la galerie>>, ce qui etait faux
trois fois sur quatre.

Les raisons tiennent a l'age du build. Un objet retire du jeu disparait du
catalogue: 368 des 3519 objets que la migration de novembre 2025 connaissait
n'y sont plus. Un emplacement peut cesser d'etre valide pour un type. Une
condition peut cesser d'etre tenue quand les stats de base ou les objets
changent. Aucune de ces trois n'est la faute de l'auteur, et c'est
precisement pour cela qu'il faut la lui dire plutot que de le laisser
chercher.
"""

#: L'ordre dans lequel on nomme la raison quand plusieurs se cumulent: la
#: plus concrete d'abord. Un objet qui n'existe plus se comprend tout de
#: suite; <<une condition n'est plus tenue>> demande d'ouvrir le build.
_ORDRE = ('missing_items', 'outdated_slots', 'conditions')


def refusal_reason(char):
    """La cle de la raison pour laquelle la galerie n'affiche pas ce build,
    ou None quand elle l'affiche.

    Rend None aussi pour un build qui n'est pas publie: la question ne se
    pose pas, et la page dit deja qu'il est prive.
    """
    if not getattr(char, 'link_shared', False) or getattr(char, 'deleted', False):
        return None
    if not getattr(char, 'minimal_solution', None):
        # La galerie et le sitemap ecartent deja un build sans solution
        # stockee, et sa page /s/ repond 404.
        return 'no_solution'
    from chardata.shared_builds_view import _get_shared_build_meta
    meta = _get_shared_build_meta(char)
    if not meta.get('is_invalid') and not meta.get('cannot_render'):
        return None
    drapeaux = {
        'missing_items': meta.get('has_missing_items'),
        'outdated_slots': meta.get('has_outdated_slots'),
        'conditions': meta.get('has_condition_issues'),
    }
    for cle in _ORDRE:
        if drapeaux.get(cle):
            return cle
    return 'no_solution' if meta.get('cannot_render') else None


def refusal_sentence(reason):
    """La phrase a montrer, traduite, ou une chaine vide.

    Les quatre disent ce qui se passe ET ce que l'auteur peut y faire. Une
    raison sans suite laisserait le lecteur devant un fait accompli.
    """
    from django.utils.translation import gettext as _
    if reason == 'missing_items':
        return _('Not shown in the gallery: some of its items are no longer '
                 'in the game. Replace them and it comes back.')
    if reason == 'outdated_slots':
        return _('Not shown in the gallery: some pieces sit in a slot that no '
                 'longer takes them. Open the build and place them again.')
    if reason == 'conditions':
        return _('Not shown in the gallery: the build does not meet its own '
                 'conditions. Open it to see which ones.')
    if reason == 'no_solution':
        return _('Not shown in the gallery: this build has no saved gear yet.')
    return ''
