# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Read a public DofusCreator project from its link; Retro is not read, and per-item exos are reported, not applied."""

import json
import re
import urllib.error
import urllib.request

from chardata.dofusbook_import import ImportError_, USER_AGENT, TIMEOUT

# Their host to our game version; the Retro subdomain is left out on purpose
HOSTS = {
    'dofuscreator.com': 'dofus3',
    'www.dofuscreator.com': 'dofus3',
}

_CODE = re.compile(r'^/projet/([A-Za-z0-9]{3,12})/?$')

# Their class names (raca) to ours, read off their class selector
CLASSES = {
    'cra': 'Cra', 'ecaflip': 'Ecaflip', 'eliotrope': 'Eliotrope',
    'eniripsa': 'Eniripsa', 'enutrof': 'Enutrof', 'feca': 'Feca',
    'huppermago': 'Huppermage', 'iop': 'Iop', 'kilorf': 'Ouginak',
    'lancedur': 'Forgelance', 'osamodas': 'Osamodas', 'pandawa': 'Pandawa',
    'roublard': 'Rogue', 'sacrier': 'Sacrier', 'sadida': 'Sadida',
    'sram': 'Sram', 'steamer': 'Foggernaut', 'xelor': 'Xelor',
    'zobal': 'Masqueraider',
}

# Their six characteristics to ours, same order as BASE_STATS
STATS = (
    ('vitalidade', 'Vitality'), ('sabedoria', 'Wisdom'), ('forca', 'Strength'),
    ('inteligencia', 'Intelligence'), ('sorte', 'Chance'),
    ('agilidade', 'Agility'),
)


def _host_and_path(url):
    url = (url or '').strip()
    if not url:
        return None, ''
    if '//' not in url:
        url = 'https://' + url
    reste = url.split('//', 1)[1]
    host, _, chemin = reste.partition('/')
    return host.split(':')[0].lower(), '/' + chemin.split('?', 1)[0].split('#', 1)[0]


def parse_link(url):
    """(host, project code) for a link on a host we read, or None."""
    host, chemin = _host_and_path(url)
    if host not in HOSTS:
        return None
    trouve = _CODE.match(chemin)
    if not trouve:
        return None
    return host, trouve.group(1)


def fetch_project(host, code, opener=None):
    """The page of one project, as text. GET, no body, two headers."""
    url = 'https://%s/projet/%s' % (host, code)
    requete = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'text/html',
    })
    ouvreur = opener or urllib.request.urlopen
    try:
        with ouvreur(requete, timeout=TIMEOUT) as reponse:
            octets = reponse.read()
    except urllib.error.HTTPError as erreur:
        raise ImportError_('not_found' if erreur.code == 404 else 'refused')
    except Exception:
        raise ImportError_('unreachable')
    try:
        return octets.decode('utf-8', 'replace')
    except Exception:
        raise ImportError_('unreadable')


def _bloc(texte, cle):
    """The JSON object literal after <cle>: in the inline script, by brace counting"""
    debut = texte.find(cle + ':')
    if debut == -1:
        return None
    ouvre = texte.find('{', debut)
    if ouvre == -1:
        return None
    profondeur = 0
    for i in range(ouvre, len(texte)):
        if texte[i] == '{':
            profondeur += 1
        elif texte[i] == '}':
            profondeur -= 1
            if profondeur == 0:
                try:
                    return json.loads(texte[ouvre:i + 1])
                except ValueError:
                    return None
    return None


def parse_project(html):
    """{name, level, race, items, points, scrolls} from the page, or raise; items is [(slot, ankama id, exos)] in page order"""
    debut = html.find('var projeto')
    if debut == -1:
        raise ImportError_('not_found')
    fin = html.find('</script>', debut)
    script = html[debut:fin if fin != -1 else None]
    itens = _bloc(script, 'itens')
    if not isinstance(itens, dict):
        raise ImportError_('unreadable')
    pieces = []
    for slot, valeur in itens.items():
        if not isinstance(valeur, dict):
            continue
        try:
            ankama = int(valeur.get('id'))
        except (TypeError, ValueError):
            continue
        exos = valeur.get('exos') or []
        pieces.append((slot, ankama, exos if isinstance(exos, list) else []))
    niveau = re.search(r'level:\s*(\d{1,3})', script)
    nom = re.search(r'nome:\s*"([^"\n]*)"', script)
    race = re.search(r'raca:\s*"([a-z]+)"', script)
    return {
        'name': (nom.group(1).strip() if nom else '')[:50],
        'level': int(niveau.group(1)) if niveau else None,
        'race': race.group(1) if race else '',
        'items': pieces,
        'points': _bloc(script, 'distribuidos') or {},
        'scrolls': _bloc(script, 'pergaminhos') or {},
    }


def _stats(leurs):
    notres = {}
    for leur, notre in STATS:
        valeur = leurs.get(leur) if isinstance(leurs, dict) else None
        if isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0:
            notres[notre] = valeur
    return notres


def read_build(url, opener=None):
    """The same shape as dofusbook_import.read_build, plus char_class and fm_not_carried"""
    from fashionistapulp.structure import get_structure
    analyse = parse_link(url)
    if analyse is None:
        raise ImportError_('not_a_link')
    host, code = analyse
    game_version = HOSTS[host]
    projet = parse_project(fetch_project(host, code, opener=opener))
    structure = get_structure(game_version)
    item_ids, manquants, avec_fm = [], [], []
    for slot, ankama, exos in projet['items']:
        item = structure.items_dict_ankama.get(ankama)
        if item is None:
            manquants.append('#%d (%s)' % (ankama, slot))
            continue
        item_ids.append(item.id)
        if exos:
            avec_fm.append(item.id)
    if not item_ids and not manquants:
        raise ImportError_('empty')
    niveau = projet['level']
    return {
        'game_version': game_version,
        'source_host': host,
        'build_id': code,
        'name': projet['name'],
        'level': niveau if isinstance(niveau, int) and 1 <= niveau <= 200 else None,
        'item_ids': item_ids,
        'missing': manquants,
        'base_points': _stats(projet['points']),
        'base_scrolled': _stats(projet['scrolls']),
        'char_class': CLASSES.get(projet['race']),
        'fm_not_carried': avec_fm,
        'class_is_unknown': projet['race'] not in CLASSES,
    }
