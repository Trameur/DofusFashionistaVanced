# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Ce que la politique aurait bloque, ecrit dans le journal.

Sans cet endpoint, une politique en mode rapport ne sert a rien: le navigateur
la verifie, ne bloque rien, et n'a personne a qui le dire. C'est ici que se
constitue la liste des origines reelles, celle qui manque pour decider un jour
de bloquer pour de bon.

Trois precautions, parce que l'adresse est ouverte a tout le monde:

**On ne journalise pas le corps.** Un rapport porte `document-uri`, qui est la
page que le lecteur regardait, et `source-file`. Seuls trois champs sortent, et
`document-uri` est reduit a son chemin: la page suffit a corriger la politique,
la chaine de requete ne sert a rien et peut porter ce que le lecteur cherchait.

**On plafonne la taille.** Un corps plus gros que quelques kilo-octets n'est
pas un rapport de navigateur.

**On plafonne le debit.** Une page qui viole dix directives envoie dix
rapports, et une page populaire multiplie par ses lecteurs. Le compteur est
par minute et par type de violation, donc le journal garde le premier exemple
de chaque probleme sans se faire noyer par le millieme.
"""

import json
import logging

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

#: Un rapport de navigateur pese quelques centaines d'octets.
MAX_CORPS = 8192

#: Combien de fois par minute on journalise UNE violation donnee.
MAX_PAR_MINUTE = 5

#: Combien de temps la fenetre de comptage dure.
FENETRE = 60


def _resume(rapport):
    """(directive, origine bloquee, chemin de la page), tronques."""
    directive = (rapport.get('effective-directive')
                 or rapport.get('violated-directive') or '')[:60]
    bloquee = (rapport.get('blocked-uri') or '')[:200]
    page = (rapport.get('document-uri') or '')
    # Le chemin seul: la chaine de requete peut porter ce que le lecteur
    # cherchait, et elle n'aide en rien a corriger une directive.
    if '://' in page:
        reste = page.split('://', 1)[1]
        page = '/' + reste.split('/', 1)[1] if '/' in reste else '/'
    page = page.split('?')[0][:120]
    return directive, bloquee, page


@csrf_exempt
@require_POST
def csp_report(request):
    """Le navigateur poste ici ce que la politique aurait refuse."""
    corps = request.body[:MAX_CORPS + 1]
    if len(corps) > MAX_CORPS:
        return HttpResponseBadRequest('too large')
    try:
        charge = json.loads(corps.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest('unreadable')

    rapport = charge.get('csp-report') if isinstance(charge, dict) else None
    if not isinstance(rapport, dict):
        return HttpResponseBadRequest('not a report')

    directive, bloquee, page = _resume(rapport)
    if not directive and not bloquee:
        return HttpResponseBadRequest('empty report')

    cle = 'csp:%s:%s' % (directive, bloquee)
    try:
        vus = cache.get_or_set(cle, 0, FENETRE)
        cache.set(cle, vus + 1, FENETRE)
    except Exception:
        vus = 0
    if vus < MAX_PAR_MINUTE:
        logger.warning('csp would have blocked %s on %s (page %s)',
                       bloquee or '(inline)', directive or '(unknown)', page)

    # 204: le navigateur n'attend rien et une page d'erreur ne servirait a
    # personne.
    return HttpResponse(status=204)
