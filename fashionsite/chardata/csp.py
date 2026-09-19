# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Content-Security-Policy in report-only mode, blocks nothing."""

from django.conf import settings

# Browser reports land here
REPORT_PATH = '/csp-report/'

# 'unsafe-inline' scripts: templates use onclick attributes, a nonce doesn't cover them
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
        # AdSense loads sodar2.js from a numbered subdomain
        'https://*.adtrafficquality.google',
    ],
    'style-src': ["'self'", "'unsafe-inline'", 'https://ajax.googleapis.com'],
    'img-src': ["'self'", 'data:', 'blob:', 'https:'],
    'font-src': ["'self'", 'data:'],
    # Analytics subdomain is the account region (region1, region5...)
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
    # CSP wildcards only go left: reCAPTCHA's www.google.fr etc. can't be listed
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

_ORDRE = ('default-src', 'script-src', 'style-src', 'img-src', 'font-src',
          'connect-src', 'frame-src', 'worker-src', 'base-uri',
          'form-action', 'frame-ancestors')


def build_policy(report_path=REPORT_PATH):
    """The policy as one header line."""
    morceaux = ['%s %s' % (directive, ' '.join(_SOURCES[directive]))
                for directive in _ORDRE]
    morceaux.append('report-uri %s' % report_path)
    return '; '.join(morceaux)


def policy_is_enabled():
    """On unless CSP_REPORT_ONLY_ENABLED is False."""
    return getattr(settings, 'CSP_REPORT_ONLY_ENABLED', True)


class ContentSecurityPolicyReportOnlyMiddleware:
    """Sets the header on HTML pages only."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = build_policy()

    def __call__(self, request):
        response = self.get_response(request)
        if not policy_is_enabled():
            return response
        if request.path == REPORT_PATH:
            return response
        type_contenu = (response.get('Content-Type') or '').lower()
        if not type_contenu.startswith('text/html'):
            return response
        if response.has_header('Content-Security-Policy-Report-Only'):
            return response
        response['Content-Security-Policy-Report-Only'] = self.policy
        return response
