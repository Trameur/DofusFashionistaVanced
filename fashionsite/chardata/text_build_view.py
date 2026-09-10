# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page qui reconstitue un build a partir de texte colle.

Meme forme que l'import DofusBook, et pour la meme raison: l'equipement est
montre AVANT que quoi que ce soit soit cree, donc le joueur voit ce qui va
arriver et peut s'en aller. Le solveur ne tourne pas.

Ce que cette page couvre et que le lien DofusBook ne couvre pas: un build prive,
un build lu sur une image, un build recopie d'un forum ou d'un Discord, et un
build qu'on a simplement sous les yeux dans le jeu. Il n'y a rien a publier
ailleurs pour l'amener ici.

Le niveau et la classe sont DEMANDES et non devines. Le texte d'une infobulle
porte le niveau de l'OBJET, jamais celui du personnage, et rien dans une liste
de noms ne nomme une classe. Les deviner reviendrait a inventer les deux
champs dont depend toute la suite.
"""

import logging

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata.dofusbook_view import (_classes_for, _place_items,
                                     _solution_path)
from chardata.lock_forbid import set_stat_overrides
from chardata.text_build_import import MAX_LIGNES, read_items
from chardata.util import set_response, safe_int
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.structure import get_current_game_version
from fashionistapulp.translation import get_supported_language

logger = logging.getLogger(__name__)

#: Le texte colle. Trois cents lignes d'infobulles tiennent tres large
#: dedans, et au dela on lit un presse-papiers entier.
MAX_CARACTERES = 40000

NIVEAU_PAR_DEFAUT = 200


def _version(request):
    return getattr(request, 'game_version', None) or get_current_game_version()


def text_build(request):
    """GET montre la zone de texte, POST la lit, confirmer cree le build."""
    texte = (request.POST.get('text') or '')[:MAX_CARACTERES]
    version = _version(request)

    if request.method != 'POST' or not texte.strip():
        return set_response(request, 'chardata/text_build.html', {
            'text': '',
            'version_label': get_game_version(version).label,
            'login_problem': is_anon_cant_create(request),
        })

    lu = read_items(texte, version, get_supported_language())

    if not lu['item_ids']:
        return set_response(request, 'chardata/text_build.html', {
            'text': texte,
            'version_label': get_game_version(version).label,
            'error': _('No item in that text matched our catalogue for this '
                       'version. Check the game version at the top, and that '
                       'the item names are on their own lines.'),
            'ignored': lu['ignored'][:12],
            'login_problem': is_anon_cant_create(request),
        })

    char_class = request.POST.get('char_class') or ''
    niveau = safe_int(request.POST.get('level'), NIVEAU_PAR_DEFAUT)

    if not request.POST.get('confirm') or char_class not in CHARACTER_CLASSES:
        return set_response(request, 'chardata/text_build.html', {
            'text': texte,
            'confirm': True,
            'version_label': get_game_version(version).label,
            'matched': lu['matched'],
            'ignored': lu['ignored'][:12],
            'ignored_total': len(lu['ignored']),
            'truncated': lu['truncated'],
            'max_lines': MAX_LIGNES,
            'refused_rolls': lu['refused_rolls'][:12],
            'level': niveau,
            'classes': _classes_for(version),
            'login_problem': is_anon_cant_create(request),
        })

    char = create_build(request, char_class, niveau, set(), version,
                        name=_('Imported build'))
    _place_items(char, lu['item_ids'], origin='pasted_text')
    # Les jets APRES la pose des objets: `_place_items` appelle set_minimal_
    # solution, qui ecrit sur le char, et ecrire les overrides avant se
    # ferait ecraser. Un seul save pour tout le lot, la ou
    # set_item_stat_override en fait un par caracteristique.
    if lu['overrides']:
        set_stat_overrides(char, lu['overrides'])
    logger.info('imported %d items and %d rolled stats from pasted text '
                'into char %s', len(lu['item_ids']),
                sum(len(v) for v in lu['overrides'].values()), char.id)
    return HttpResponseRedirect(_solution_path(char))
