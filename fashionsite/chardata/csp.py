# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une politique de securite du contenu, en mode RAPPORT et pas en mode blocage.

Le site n'a aucun `Content-Security-Policy`. En ajouter un est la bonne idee;
en ajouter un qui BLOQUE, ecrit a partir du depot, casserait le site pour une
partie des visiteurs et seulement pour eux.

**La mesure qui tranche.** Le 10 septembre 2026, en chargeant quatre pages et
en lisant `performance.getEntriesByType('resource')` dans le navigateur, le
site va chercher:

    https://ajax.googleapis.com           jQuery,        ecrit dans base.html
    https://www.googletagmanager.com      gtag,          ecrit dans base.html
    https://region1.analytics.google.com  la mesure,     NULLE PART dans le depot
    https://www.google.fr                 reCAPTCHA,     NULLE PART dans le depot

Les deux dernieres n'existent dans aucun gabarit, et leur nom **change selon
le visiteur**: `region1` est la region du compte Analytics, et `www.google.fr`
est le domaine national vers lequel reCAPTCHA bascule (`.de`, `.co.uk`, ...).
Une politique ecrite en lisant le depot aurait donc coupe la mesure d'audience
et le captcha pour une partie des pays, sans que personne ici ne le voie.

S'y ajoute, en production seulement, toute la chaine de diffusion d'AdSense,
que Google ne documente pas de facon exhaustive et qui evolue.

**Donc: `Content-Security-Policy-Report-Only`.** Le navigateur applique la
regle, ne bloque RIEN, et signale ce qu'il aurait bloque. C'est la seule forme
qu'on puisse poser honnetement sans avoir observe le trafic reel, et c'est
exactement ce qui produira la liste qui manque pour, un jour, bloquer.
"""

from django.conf import settings

#: Le chemin qui recoit les rapports du navigateur.
REPORT_PATH = '/csp-report/'

#: Les origines mesurees ou lues dans le depot, par directive.
#:
#: `'unsafe-inline'` sur les scripts n'est pas un renoncement: le site pose des
#: gestionnaires en attribut (`onclick="..."`), qu'un nonce ne couvre PAS. Les
#: retirer est un chantier a part entiere; sans eux la regle bloquerait la
#: moitie des boutons. Ce qu'elle garde malgre tout, et qui est l'essentiel:
#: un script INJECTE depuis une origine etrangere reste refuse.
_SOURCES = {
    'default-src': ["'self'"],
    'script-src': [
        "'self'", "'unsafe-inline'", "'unsafe-eval'",
        'https://ajax.googleapis.com',
        'https://www.googletagmanager.com',
        'https://www.google.com',
        'https://www.gstatic.com',
        'https://cdn.jsdelivr.net',
        'https://pagead2.googlesyndication.com',
        'https://fundingchoicesmessages.google.com',
        'https://googleads.g.doubleclick.net',
        'https://tpc.googlesyndication.com',
        'https://accounts.google.com',
        'https://apis.google.com',
        # Mesure du 10 septembre 2026, dans le navigateur: la regie charge
        # `ep2.adtrafficquality.google/sodar/sodar2.js`. Ce domaine n'existe
        # dans AUCUN gabarit, dans aucune documentation qu'on ait, et son
        # sous-domaine numerote change. On ne l'aurait jamais devine.
        'https://*.adtrafficquality.google',
    ],
    'style-src': ["'self'", "'unsafe-inline'", 'https://ajax.googleapis.com'],
    'img-src': ["'self'", 'data:', 'blob:', 'https:'],
    'font-src': ["'self'", 'data:'],
    # `https://*.analytics.google.com` et `https://*.google-analytics.com`
    # parce que le sous-domaine porte la region du compte: la mesure a vu
    # `region1`, un autre compte verra `region5`.
    'connect-src': [
        "'self'", 'blob:',
        'https://*.analytics.google.com',
        'https://*.google-analytics.com',
        'https://*.googletagmanager.com',
        'https://cdn.jsdelivr.net',
        'https://pagead2.googlesyndication.com',
        'https://fundingchoicesmessages.google.com',
        'https://*.adtrafficquality.google',
    ],
    # reCAPTCHA et la connexion Google dessinent dans une iframe.
    #
    # Le domaine NATIONAL de reCAPTCHA (`www.google.fr`, mesure sur /contact/)
    # n'est pas listable: un joker CSP ne marche qu'a GAUCHE (`*.google.com`),
    # jamais a droite. `https://www.google.*` a ete essaye et le navigateur
    # repond <<invalid source, it will be ignored>>, donc la source entiere
    # disparaissait sans que rien cote serveur ne le dise. Ce sont justement
    # les rapports qui diront quels domaines nationaux apparaissent vraiment.
    'frame-src': [
        "'self'",
        'https://www.google.com',
        'https://recaptcha.google.com',
        'https://accounts.google.com',
        'https://googleads.g.doubleclick.net',
        'https://tpc.googlesyndication.com',
        'https://pagead2.googlesyndication.com',
        'https://*.adtrafficquality.google',
        'https://www.youtube.com',
    ],
    'worker-src': ["'self'", 'blob:'],
    'base-uri': ["'self'"],
    'form-action': ["'self'", 'https://accounts.google.com'],
    'frame-ancestors': ["'self'"],
}

#: L'ordre est fixe pour que l'en-tete soit comparable d'une reponse a
#: l'autre, ce qu'un dictionnaire ne garantissait pas avant Python 3.7 et que
#: personne n'a envie de redecouvrir dans un diff.
_ORDRE = ('default-src', 'script-src', 'style-src', 'img-src', 'font-src',
          'connect-src', 'frame-src', 'worker-src', 'base-uri',
          'form-action', 'frame-ancestors')


def build_policy(report_path=REPORT_PATH):
    """La politique, en une ligne, telle que l'en-tete la porte."""
    morceaux = ['%s %s' % (directive, ' '.join(_SOURCES[directive]))
                for directive in _ORDRE]
    morceaux.append('report-uri %s' % report_path)
    return '; '.join(morceaux)


def policy_is_enabled():
    """Le reglage, avec un defaut explicite.

    L'en-tete ne bloque rien, donc il est actif par defaut. Le reglage existe
    pour pouvoir le couper sans deployer du code, pas pour l'allumer.
    """
    return getattr(settings, 'CSP_REPORT_ONLY_ENABLED', True)


class ContentSecurityPolicyReportOnlyMiddleware:
    """Pose l'en-tete sur les pages HTML, et sur elles seules.

    Une image ou un fichier CSS n'a pas de politique a appliquer, et l'en-tete
    y ajouterait quelques centaines d'octets a chacune des dizaines de
    requetes que porte une page du site.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = build_policy()

    def __call__(self, request):
        response = self.get_response(request)
        if not policy_is_enabled():
            return response
        # Ne pas se signaler a soi-meme: l'endpoint de rapport repond du JSON
        # et n'a pas besoin d'une politique.
        if request.path == REPORT_PATH:
            return response
        type_contenu = (response.get('Content-Type') or '').lower()
        if not type_contenu.startswith('text/html'):
            return response
        if response.has_header('Content-Security-Policy-Report-Only'):
            return response
        response['Content-Security-Policy-Report-Only'] = self.policy
        return response
