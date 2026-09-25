# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Builds other sites send here, the page that tells them how, and ours written in the same format."""

import ipaddress
import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.http import (HttpResponse, HttpResponseNotAllowed,
                         HttpResponseRedirect, JsonResponse, QueryDict)
from django.http.multipartparser import MultiPartParserError
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.translation import get_language
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters

from chardata import export_count, fashionista_build, text_build_view
from chardata.api_view import _api_endpoint, _absent, _json
from chardata.fashionista_build import FormatError
from chardata.util import get_char_or_raise, set_response, version_free_canonical
from fashionistapulp.game_versions import version_keys

VALIDATE_WINDOW = 600
VALIDATE_PER_ADDRESS = 120
VALIDATE_NEW_ADDRESSES = 200
VALIDATE_ALL = 1200

# A body this long is refused before it is read
MAX_BODY = fashionista_build.MAX_JSON * 4

EXAMPLE_GAMES = ('dofus3', 'retro')


def _import_url(game):
    try:
        return reverse('import_build' if game == 'dofus3'
                       else '%s:import_build' % game)
    except NoReverseMatch:
        return '%s/import/build/' % ('' if game == 'dofus3' else '/' + game)


def _game_of(text):
    try:
        game = fashionista_build.parse_json(text).get('game')
    except FormatError:
        return None
    return game if game in version_keys() else None


def _body_too_large(request):
    try:
        return int(request.META.get('CONTENT_LENGTH') or 0) > MAX_BODY
    except ValueError:
        return True


def _from_another_site(request):
    """A POST another site sent, which carries none of the reader's SameSite=Lax cookies."""
    return (request.POST.get('hop') != '1'
            and request.META.get('HTTP_SEC_FETCH_SITE') != 'same-origin')


def _hop(request, text, refused):
    """A bare page that posts the build again from our own origin, where the reader's cookies go along."""
    response = HttpResponse(render_to_string('chardata/send_a_build_hop.html', {
        'action': request.path, 'data': text, 'refused': refused,
        'language': get_language() or 'en',
    }))
    response['Cache-Control'] = 'no-store'
    response['X-Robots-Tag'] = 'noindex'
    return response


@csrf_exempt
@sensitive_post_parameters('data')
def import_build(request):
    """A build sent by link (?data=) or form (data): our import page shows it, the player confirms there."""
    if request.method not in ('GET', 'HEAD', 'POST'):
        return HttpResponseNotAllowed(['GET', 'HEAD', 'POST'])
    page_version = text_build_view._version(request)
    refused = None
    if request.method == 'POST':
        if _body_too_large(request):
            # Rendering the page reads request.POST, which would parse the body
            request.POST = QueryDict()
            text, refused = '', 'too_large'
        else:
            text = request.POST.get('data') or ''
            # Only the hop page sends it, for a body too large to pass on
            if request.POST.get('refused') == 'too_large':
                refused = 'too_large'
            if len(text) > fashionista_build.MAX_JSON:
                text, refused = '', 'too_large'
    else:
        data = request.GET.get('data')
        if data is None:
            return HttpResponseRedirect(text_build_view._url_pour_version(page_version))
        try:
            text = fashionista_build.decode_link_data(data)
        except FormatError as error:
            return text_build_view.sent_build_refused(request, error.reason)
    text = text.strip()

    game = _game_of(text)
    if game is not None and game != page_version:
        target = _import_url(game)
        if request.method == 'POST':
            moved = HttpResponseRedirect(target)
            # 307 keeps the method and the form
            moved.status_code = 307
            return moved
        return HttpResponseRedirect('%s?%s' % (target, request.META.get('QUERY_STRING', '')))
    if request.method == 'POST' and _from_another_site(request):
        return _hop(request, text, refused)
    if refused:
        return text_build_view.sent_build_refused(request, refused)
    if not text:
        return text_build_view.sent_build_refused(request, 'not_json')
    if not fashionista_build.looks_sent(text):
        try:
            fashionista_build.parse_json(text)
            code = 'not_json'
        except FormatError as error:
            code = error.reason
        return text_build_view.sent_build_refused(request, code)
    return text_build_view.sent_build(request, text)


def _stat_keys(game):
    from chardata.translation_util import localized_stat_name
    from fashionistapulp.structure import get_structure
    structure = get_structure(game)
    return sorted(((stat.key, localized_stat_name(stat.name, game))
                   for stat in structure.get_stats_list()),
                  key=lambda pair: pair[0])


def _classes():
    from chardata.character_look import CLASS_TO_BREED
    from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
    return [(key, CLASS_TO_BREED.get(key), str(LOCALIZED_CHARACTER_CLASSES.get(key, key)))
            for key in sorted(CLASS_TO_BREED, key=CLASS_TO_BREED.get)]


def send_a_build(request):
    """The developer page: the format, the two ways in, the codes and a checker."""
    from chardata.url_language import SITE_URL
    page_version = text_build_view._version(request)
    examples = []
    for game in EXAMPLE_GAMES:
        payload = fashionista_build.example_payload(game)
        data = fashionista_build.encode_link_data(payload)
        path = _import_url(game).split('/import/build/')[0]
        examples.append({
            'game': game,
            'label': 'Dofus Retro' if game == 'retro' else 'Dofus 3',
            'json': json.dumps(payload, indent=2, ensure_ascii=False),
            'link': '%s%s/import/build/?data=%s' % (
                SITE_URL, '' if game == 'dofus3' else '/' + game, data),
            'open': '%s/import/build/?data=%s' % (path, data),
        })
    language = get_language() or 'en'
    checker_language = language if language in dict(settings.LANGUAGES) else 'en'
    answer = fashionista_build.report(fashionista_build.example_payload('dofus3'),
                                      checker_language)
    return set_response(request, 'chardata/send_a_build.html', {
        'canonical_path': version_free_canonical('send_a_build'),
        'examples': examples,
        'item_example': json.dumps(
            fashionista_build.example_payload('dofus3')['items'][0],
            ensure_ascii=False),
        'site_url': SITE_URL,
        'schema_path': fashionista_build.SCHEMA_PATH,
        'validate_path': fashionista_build.VALIDATE_PATH,
        'validate_example': '%s?lang=%s' % (fashionista_build.VALIDATE_PATH,
                                            checker_language),
        'answer_example': json.dumps(answer, indent=2, ensure_ascii=False),
        'import_path': _import_url(page_version),
        'games': list(version_keys()),
        'errors': [(code, str(text)) for code, text in fashionista_build.ERRORS],
        'warnings': [(code, str(text)) for code, text in fashionista_build.WARNINGS],
        'stat_keys': _stat_keys(page_version),
        'classes': _classes(),
        'limits': {
            'link': fashionista_build.MAX_LINK_DATA,
            'json': fashionista_build.MAX_JSON,
            'items': fashionista_build.MAX_ITEMS,
            'lines': fashionista_build.MAX_STAT_LINES,
            'name': fashionista_build.NAME_LENGTH,
            'checks': VALIDATE_PER_ADDRESS,
            'minutes': VALIDATE_WINDOW // 60,
            'per_code': fashionista_build.ISSUES_PER_CODE,
        },
        'checker_language': checker_language,
    })


def export_fashionista(request, char_id):
    """The build as fashionista-build JSON, for its owner."""
    char = get_char_or_raise(request, char_id)
    payload = fashionista_build.export_build(char)
    if payload is None:
        return JsonResponse({'error': 'no gear'}, status=404)
    response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False,
                                                        'indent': 2})
    response['Content-Disposition'] = 'inline; filename="build-%d.json"' % char.id
    response['X-Robots-Tag'] = 'noindex'
    export_count.count(request, export_count.JSON, char.id, char.game_version)
    return response


def _cors(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Access-Control-Max-Age'] = '86400'
    return response


def _answer(data, status):
    return _cors(JsonResponse(data, status=status,
                              json_dumps_params={'ensure_ascii': False}))


def _language(request):
    wanted = (request.GET.get('lang') or '').strip().lower()
    return wanted if wanted in dict(settings.LANGUAGES) else 'en'


def _caller(request):
    """The caller's address as our proxies saw it, an IPv6 one as its /64."""
    # Cloudflare sets CF-Connecting-IP and nginx X-Real-IP, each over what the client sent
    for header in ('HTTP_CF_CONNECTING_IP', 'HTTP_X_REAL_IP', 'REMOTE_ADDR'):
        try:
            address = ipaddress.ip_address((request.META.get(header) or '').strip())
        except ValueError:
            continue
        if address.version == 6:
            return str(ipaddress.ip_network('%s/64' % address, strict=False))
        return str(address)
    return 'unknown'


def _over_the_limit(request):
    """Per address, then a ceiling on new addresses and on every check, all per window."""
    from chardata.rate_limit import hits, note_hit
    key = 'build-validate:%s' % _caller(request)
    seen = hits(key, VALIDATE_WINDOW)
    if seen >= VALIDATE_PER_ADDRESS:
        return True
    if not seen and (note_hit('build-validate-new', VALIDATE_WINDOW)
                     > VALIDATE_NEW_ADDRESSES):
        return True
    if note_hit('build-validate-all', VALIDATE_WINDOW) > VALIDATE_ALL:
        return True
    note_hit(key, VALIDATE_WINDOW)
    return False


def _usage():
    from chardata.url_language import SITE_URL
    return {
        'endpoint': 'POST %s?lang=en' % fashionista_build.VALIDATE_PATH,
        'body': 'one %s JSON object, version %d'
                % (fashionista_build.FORMAT, fashionista_build.FORMAT_VERSION),
        'schema': SITE_URL + fashionista_build.SCHEMA_PATH,
        'docs': SITE_URL + '/developers/send-a-build/',
        'limits': {'json_characters': fashionista_build.MAX_JSON,
                   'requests': VALIDATE_PER_ADDRESS,
                   'window_seconds': VALIDATE_WINDOW},
    }


@csrf_exempt
def api_validate(request):
    """POST a fashionista-build as the JSON body: what we read, with stable error and warning codes. GET says how."""
    if request.method == 'OPTIONS':
        return _cors(HttpResponse(status=204))
    language = _language(request)
    if request.method in ('GET', 'HEAD'):
        return _answer(_usage(), 200)
    if request.method != 'POST':
        refused = _answer(fashionista_build.refusal('method_not_allowed', language), 405)
        refused['Allow'] = 'GET, POST, OPTIONS'
        return refused
    if _over_the_limit(request):
        refused = _answer(fashionista_build.refusal('rate_limited', language), 429)
        refused['Retry-After'] = str(VALIDATE_WINDOW)
        return refused
    if _body_too_large(request):
        return _answer(fashionista_build.refusal('too_large', language), 413)
    try:
        body = request.body
    except Exception:
        return _answer(fashionista_build.refusal('too_large', language), 413)
    if len(body) > MAX_BODY:
        return _answer(fashionista_build.refusal('too_large', language), 413)
    try:
        if request.content_type in ('application/x-www-form-urlencoded',
                                    'multipart/form-data'):
            text = request.POST.get('data') or ''
        else:
            text = body.decode('utf-8')
        payload = fashionista_build.parse_json(text)
    except (UnicodeDecodeError, MultiPartParserError, SuspiciousOperation):
        return _answer(fashionista_build.refusal('not_json', language), 400)
    except FormatError as error:
        return _answer(fashionista_build.refusal(error.reason, language),
                       413 if error.reason == 'too_large' else 400)
    answer = fashionista_build.report(payload, language)
    return _answer(answer, 200 if answer['valid'] else 400)


@_api_endpoint
@cache_page(3600)
def api_schema(request, version):
    if int(version) not in fashionista_build.READABLE_VERSIONS:
        return _absent('schema')
    return _json(fashionista_build.json_schema())


def _counted_pull(view):
    """Counts every answered pull, cached answers included."""
    @wraps(view)
    def wrapper(request, encoded_id):
        response = view(request, encoded_id)
        if response.status_code == 200 and export_count.counts_pull(request):
            from chardata.encoded_char_id import decode_char_id
            export_count.count(request, export_count.API,
                               decode_char_id(encoded_id),
                               json.loads(response.content).get('game'),
                               export_count.requesting_site(request),
                               rule=export_count.counts_pull)
        return response
    return wrapper


@_api_endpoint
@_counted_pull
@cache_page(60)
def api_shared_build_export(request, encoded_id):
    from chardata.encoded_char_id import decode_char_id
    from chardata.models import Char
    try:
        char_id = decode_char_id(encoded_id)
    except Exception:
        return _absent('shared build')
    char = Char.objects.filter(id=char_id, link_shared=True, deleted=False).first()
    if char is None or char.game_version not in version_keys():
        return _absent('shared build')
    payload = fashionista_build.export_build(char)
    if payload is None:
        return _absent('shared build')
    return _json(payload)
