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

from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib import admin
from django.views.generic import RedirectView, TemplateView
from django.http import Http404, HttpResponse
from django.views.static import serve
from django.utils.html import escape
from django.utils import translation
from django.utils.translation import get_language, gettext as _
import os
from chardata import home_view, login_view, views, projects_view, base_stats_view, create_project_view, \
    stats_weights_view, min_stats_view, options_view, inclusions_view, exclusions_view, wizard_view, \
    fashion_action, solution_view, spells_view, contact_view, manage_account_view, util, manage_items_view, \
  compare_sets_view, item_exchange, util_views, shared_builds_view, encyclopedia_view, comment_view, \
    coaching_view, workshop_view, profile_view, tag_view, api_view, nl_build_view, forgemagie_view, \
    inventory_view, guides_view, admin_tools_view, character_assets
from chardata.models import Char
from chardata.encoded_char_id import encode_char_id
admin.autodiscover()

def ads_txt_view(request):
    """Fallback ads.txt; in production nginx answers from docker/ads.txt.

    A publisher id that disagrees with the ad code stops the ads being bought.
    """
    from chardata.context_processors import DEFAULT_AD_CLIENT, ad_config
    client = ad_config().get('client') or DEFAULT_AD_CLIENT
    content = 'google.com, %s, DIRECT, f08c47fec0942fa0' % client.replace('ca-', '', 1)
    return HttpResponse(content, content_type='text/plain')

def chrome_devtools_view(request):
    """Chrome DevTools probes this path on localhost."""
    return HttpResponse(status=204)

def manifest_view(request):
    """PWA web app manifest (served from root so scope covers the whole site)."""
    from django.templatetags.static import static as dj_static
    try:
        from static_s3.templatetags.static_s3 import static as s3_static
        icon192 = s3_static('chardata/icon-192.png')
        icon512 = s3_static('chardata/icon-512.png')
    except Exception:
        icon192 = dj_static('chardata/icon-192.png')
        icon512 = dj_static('chardata/icon-512.png')
    import json as _json
    manifest = {
        "name": "Dofus Fashionista",
        "short_name": "Fashionista",
        "description": "Automatic Dofus equipment set optimizer.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#1b1b1b",
        "theme_color": "#1b1b1b",
        # Square PNG icons (>=192px) so the "add to home screen" install prompt works.
        "icons": [
            {"src": icon192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icon512, "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ],
    }
    return HttpResponse(_json.dumps(manifest), content_type='application/manifest+json')

def service_worker_view(request):
    """Offline-first service worker; served at root so its scope covers the site."""
    sw = """
const CACHE = 'fashionista-v2';
const OFFLINE_URL = '/offline/';
self.addEventListener('install', function(e) {
    e.waitUntil(caches.open(CACHE).then(function(c) { return c.add(OFFLINE_URL); }));
    self.skipWaiting();
});
self.addEventListener('activate', function(e) {
    e.waitUntil(caches.keys().then(function(keys) {
        return Promise.all(keys.filter(function(k){return k!==CACHE;}).map(function(k){return caches.delete(k);}));
    }));
    self.clients.claim();
});
self.addEventListener('fetch', function(e) {
    var req = e.request;
    if (req.method !== 'GET') return;
    var url = new URL(req.url);
    if (url.origin !== self.location.origin) return;
    if (req.mode === 'navigate') {
        e.respondWith(fetch(req).catch(function() { return caches.match(OFFLINE_URL); }));
        return;
    }
    // CSS/JS: network-first so style/script updates always apply (cache = offline fallback)
    if (/\\.(css|js)$/.test(url.pathname)) {
        e.respondWith(fetch(req).then(function(resp) {
            var copy = resp.clone();
            caches.open(CACHE).then(function(c){ c.put(req, copy); });
            return resp;
        }).catch(function(){ return caches.match(req); }));
        return;
    }
    // images/fonts: cache-first (rarely change)
    if (/\\.(png|jpg|jpeg|gif|svg|ico|woff2?)$/.test(url.pathname)) {
        e.respondWith(caches.match(req).then(function(cached) {
            return cached || fetch(req).then(function(resp) {
                var copy = resp.clone();
                caches.open(CACHE).then(function(c){ c.put(req, copy); });
                return resp;
            });
        }));
    }
});
"""
    return HttpResponse(sw, content_type='application/javascript')

def offline_view(request):
    # The service worker caches this page at install time, so it is served in
    # the language the visitor had then.
    return HttpResponse(
        "<!doctype html><html lang='%s'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>%s</title></head>"
        "<body style='font-family:sans-serif;text-align:center;padding:40px;'>"
        "<h1>%s</h1><p>%s</p></body></html>"
        % (escape(get_language() or 'en'),
           escape(_('Offline - Dofus Fashionista')),
           escape(_('You are offline')),
           escape(_('Dofus Fashionista needs a connection to optimize builds. '
                    'Reconnect and try again.'))),
        content_type='text/html')

# --- Sitemap ---------------------------------------------------------------
import time as _sitemap_time

# One cache entry per (section, language): the same builder now produces a
# different document per language, so a single slot would serve French XML
# for a Spanish request.
_SITEMAP_CACHES = {}


def _sitemap_cache(section, language):
    return _SITEMAP_CACHES.setdefault((section, language),
                                      {'ts': 0.0, 'xml': ''})


_SITEMAP_ITEM_CACHE = {'ts': 0.0, 'xml': ''}
_SITEMAP_ITEM_TTL = 6 * 3600


def _sitemap_url(loc, changefreq, priority):
    return ('  <url>\n    <loc>%s</loc>\n    <changefreq>%s</changefreq>\n'
            '    <priority>%s</priority>\n  </url>') % (loc, changefreq, priority)


def _sitemap_encyclopedia_items(base_url, language='en'):
    """<url> block for encyclopedia item pages in every game version."""
    now = _sitemap_time.time()
    cached = _sitemap_cache('items', language)
    if cached['xml'] and (now - cached['ts'] < _SITEMAP_ITEM_TTL):
        return cached['xml']
    try:
        import sqlite3
        from chardata.official_site import get_item_link
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.game_versions import dofus_versions
        seen = set()
        rows = []
        for game_version in dofus_versions():
            conn = sqlite3.connect(get_items_db_path(game_version))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'items'")
                if cursor.fetchone() is None:
                    continue
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_names'")
                has_item_names = cursor.fetchone() is not None
                name_join_sql = (
                    "LEFT JOIN item_names en ON en.item = i.id AND en.language = ?"
                    if has_item_names else '')
                localized_name_sql = 'COALESCE(en.name, i.name)' if has_item_names else 'i.name'
                cursor.execute(
                    """
                    WITH representative_items AS (
                        SELECT MIN(id) AS item_id
                        FROM items
                        WHERE ankama_id IS NOT NULL AND ankama_type IS NOT NULL
                        GROUP BY ankama_type, ankama_id
                    )
                    SELECT i.ankama_type, i.ankama_id, %s AS localized_name, i.name
                    FROM representative_items ri
                    JOIN items i ON i.id = ri.item_id
                    %s
                    ORDER BY i.ankama_type, i.ankama_id
                    """ % (localized_name_sql, name_join_sql),
                    (language,) if has_item_names else ())
                for ankama_type, ankama_id, name, english in cursor.fetchall():
                    with translation.override(language):
                        link = get_item_link(ankama_type, ankama_id, name or '',
                                             game_version=game_version)
                    if language != 'en':
                        # An untranslated name gives the English URL, which
                        # answers in English. Filing it under another language
                        # would promise Google a page that is not there.
                        with translation.override('en'):
                            english_link = get_item_link(
                                ankama_type, ankama_id, english or '',
                                game_version=game_version)
                        if link == english_link:
                            continue
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    rows.append(_sitemap_url(base_url + link, 'monthly', '0.6'))
            finally:
                conn.close()
        xml = '\n'.join(rows)
    except Exception:
        return cached['xml'] or ''
    cached['ts'] = now
    cached['xml'] = xml
    return xml


_SITEMAP_SET_CACHE = {'ts': 0.0, 'xml': ''}


def _sitemap_encyclopedia_sets(base_url, language='en'):
    """<url> block for encyclopedia set pages in every game version."""
    now = _sitemap_time.time()
    cached = _sitemap_cache('sets', language)
    if cached['xml'] and (now - cached['ts'] < _SITEMAP_ITEM_TTL):
        return cached['xml']
    try:
        from chardata import encyclopedia_view
        from chardata.official_site import get_set_link
        from fashionistapulp.game_versions import dofus_versions
        rows = []
        seen = set()
        for game_version in dofus_versions():
            structure = encyclopedia_view.get_structure(game_version)
            for set_id, item_set in structure.sets_dict.items():
                if not getattr(item_set, 'items', None):
                    continue
                set_name = (item_set.localized_names.get(language)
                            or item_set.localized_names.get('en')
                            or item_set.name)
                if not set_name:
                    continue
                link = get_set_link(set_id, set_name, game_version=game_version)
                if not link:
                    continue
                if language != 'en':
                    english_name = (item_set.localized_names.get('en')
                                    or item_set.name)
                    if link == get_set_link(set_id, english_name,
                                            game_version=game_version):
                        continue
                if link in seen:
                    continue
                seen.add(link)
                rows.append(_sitemap_url('%s%s' % (base_url, link),
                                         'monthly', '0.6'))
        xml = '\n'.join(rows)
    except Exception:
        return cached['xml'] or ''
    cached['ts'] = now
    cached['xml'] = xml
    return xml


_SITEMAP_RESOURCE_CACHE = {'ts': 0.0, 'xml': ''}


def _sitemap_encyclopedia_resources(base_url, language='en'):
    """<url> block for encyclopedia ingredient pages in every game version."""
    now = _sitemap_time.time()
    cached = _sitemap_cache('resources', language)
    if cached['xml'] and (now - cached['ts'] < _SITEMAP_ITEM_TTL):
        return cached['xml']
    try:
        import sqlite3
        from chardata.official_site import get_resource_link
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.game_versions import dofus_versions
        rows = []
        seen = set()
        for game_version in dofus_versions():
            conn = sqlite3.connect(get_items_db_path(game_version))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'item_recipe_ingredient_names'")
                if cursor.fetchone() is None:
                    continue

                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_recipes'")
                if cursor.fetchone() is None:
                    continue
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'resource_drops'")
                has_drops = cursor.fetchone() is not None

                drop_join = ''
                drop_criterion = ''
                if has_drops:
                    drop_join = (
                        " LEFT JOIN (SELECT resource_ankama_id AS ankama_id,"
                        " COUNT(*) AS drops FROM resource_drops GROUP BY 1) d"
                        " ON d.ankama_id = n.ingredient_ankama_id"
                        " AND n.ingredient_subtype = 'resources'")
                    drop_criterion = ' OR COALESCE(d.drops, 0) >= 1'
                cursor.execute(
                    """
                    WITH usage_counts AS (
                        SELECT ingredient_ankama_id AS ankama_id,
                               ingredient_subtype AS subtype,
                               COUNT(*) AS uses
                        FROM item_recipes
                        GROUP BY 1, 2
                    )
                    SELECT DISTINCT n.ingredient_ankama_id, n.ingredient_subtype, n.name,
                           (SELECT name FROM item_recipe_ingredient_names e
                             WHERE e.ingredient_ankama_id = n.ingredient_ankama_id
                               AND e.ingredient_subtype = n.ingredient_subtype
                               AND e.language = 'en'
                             LIMIT 1)
                    FROM item_recipe_ingredient_names n
                    JOIN usage_counts u
                      ON u.ankama_id = n.ingredient_ankama_id
                     AND u.subtype = n.ingredient_subtype
                    %s
                    WHERE n.language = '%s' AND (u.uses >= 2%s)
                    ORDER BY n.ingredient_subtype, n.ingredient_ankama_id
                    """ % (drop_join, language, drop_criterion))
                for ankama_id, subtype, name, english in cursor.fetchall():
                    link = get_resource_link(subtype, ankama_id, name or '',
                                             game_version=game_version)
                    if language != 'en' and link == get_resource_link(
                            subtype, ankama_id, english or '',
                            game_version=game_version):
                        # Untranslated name, so the English URL -- which
                        # answers in English. Filing it under another language
                        # would promise a page that is not there.
                        continue
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    rows.append(_sitemap_url(base_url + link, 'monthly', '0.5'))
            finally:
                conn.close()
        xml = '\n'.join(rows)
    except Exception:
        return cached['xml'] or ''
    cached['ts'] = now
    cached['xml'] = xml
    return xml


_SITEMAP_MONSTER_CACHE = {'ts': 0.0, 'xml': ''}


def _sitemap_encyclopedia_monsters(base_url, language='en'):
    """<url> block for monster encyclopedia pages in every game version."""
    now = _sitemap_time.time()
    cached = _sitemap_cache('monsters', language)
    if cached['xml'] and (now - cached['ts'] < _SITEMAP_ITEM_TTL):
        return cached['xml']
    try:
        import sqlite3
        from chardata.encyclopedia_view import has_display_name
        from chardata.official_site import get_monster_link
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.game_versions import dofus_versions
        rows = []
        seen = set()
        for game_version in dofus_versions():
            version_prefix = '' if game_version == 'dofus3' else '/%s' % game_version
            list_link = '%s/encyclopedia/monsters/' % version_prefix
            if list_link not in seen:
                seen.add(list_link)
                rows.append(_sitemap_url(base_url + list_link, 'weekly', '0.7'))

            conn = sqlite3.connect(get_items_db_path(game_version))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'monster_names'")
                if cursor.fetchone() is None:
                    continue

                drop_sources = []
                for table_name in ('resource_drops', 'item_drops'):
                    cursor.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table_name,))
                    if cursor.fetchone() is not None:
                        drop_sources.append('SELECT monster_ankama_id FROM %s' % table_name)
                if not drop_sources:
                    continue

                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'monster_spells'")
                substantial = ('OR ((SELECT COUNT(DISTINCT spell_ankama_id) '
                               'FROM monster_spells s '
                               'WHERE s.monster_ankama_id = n.monster_ankama_id) >= 2 '
                               'AND (SELECT COUNT(*) FROM monster_grades g '
                               'WHERE g.monster_ankama_id = n.monster_ankama_id) >= 2)'
                               if cursor.fetchone() is not None else '')
                cursor.execute(
                    """
                    WITH dropped_monsters AS (
                        SELECT monster_ankama_id, COUNT(*) AS drops FROM (%s)
                        GROUP BY monster_ankama_id
                    )
                    SELECT n.monster_ankama_id,
                           COALESCE(
                               (SELECT name FROM monster_names
                                WHERE monster_ankama_id = n.monster_ankama_id
                                  AND language = '%s'
                                LIMIT 1),
                               (SELECT name FROM monster_names
                                WHERE monster_ankama_id = n.monster_ankama_id
                                LIMIT 1)
                           ),
                           (SELECT name FROM monster_names
                             WHERE monster_ankama_id = n.monster_ankama_id
                               AND language = 'en'
                             LIMIT 1)
                    FROM dropped_monsters n
                    WHERE n.drops >= 2 %s
                    ORDER BY n.monster_ankama_id
                    """ % (' UNION ALL '.join(drop_sources), language,
                           substantial))
                for monster_id, name, english in cursor.fetchall():
                    if not has_display_name({'en': name}):
                        continue
                    if language != 'en' and english and name == english:
                        # Untranslated name, so the English URL. See above.
                        continue
                    link = get_monster_link(monster_id, name or '', game_version=game_version)
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    rows.append(_sitemap_url(base_url + link, 'monthly', '0.5'))
            finally:
                conn.close()
        xml = '\n'.join(rows)
    except Exception:
        return cached['xml'] or ''
    cached['ts'] = now
    cached['xml'] = xml
    return xml


def _sitemap_pages(base_url):
    """Static pages, feature pages, guides, per-version entry points and a
    sample of recently shared builds."""
    blocks = []

    static_paths = [
        ('/', 'daily', '1.0'),
        ('/about/', 'monthly', '0.8'),
        ('/faq/', 'monthly', '0.8'),
        ('/privacy/', 'yearly', '0.5'),
        ('/license/', 'yearly', '0.4'),
        ('/contact/', 'monthly', '0.5'),
        ('/support/', 'monthly', '0.5'),
        ('/setup/', 'weekly', '0.9'),
        ('/quickstart/', 'monthly', '0.7'),
        ('/smartbuild/', 'monthly', '0.7'),
        ('/sharedbuilds/', 'daily', '0.9'),
        # /random/ only ever redirects, so it is not sitemap material.
        ('/choose_compare_sets/', 'weekly', '0.7'),
        ('/encyclopedia/', 'daily', '0.9'),
        ('/encyclopedia/sets/', 'weekly', '0.8'),
        ('/forgemagie/', 'weekly', '0.8'),
        # /workshop/ is behind the login: a crawler only gets the /login/ redirect.
        ('/loadprojects/', 'weekly', '0.5'),
    ]
    for path, freq, prio in static_paths:
        blocks.append(_sitemap_url(base_url + path, freq, prio))

    blocks.append(_sitemap_url(base_url + '/guides/', 'monthly', '0.8'))
    try:
        from chardata import guides_content
        for key in guides_content.ordered_slugs():
            published = guides_content.GUIDES[key].get('published')
            lastmod = ('\n    <lastmod>%s</lastmod>' % published) if published else ''
            # One URL per language. The slug names the language, so the
            # French and Spanish guides are pages of their own rather than
            # the same page served twice. Submitting only the English slug
            # is what kept 128 of the 160 written guide pages out of the
            # index: a crawler sends no Accept-Language, so it only ever
            # saw the English text.
            slugs = sorted(set(guides_content.alternate_slugs(key).values())
                           or {key})
            for slug in slugs:
                # A per-version guide is a distinct page per game version.
                for version in guides_content.canonical_versions(key):
                    prefix = '' if version == 'dofus3' else '/%s' % version
                    blocks.append('  <url>\n    <loc>%s%s/guides/%s/</loc>%s\n'
                                  '    <changefreq>monthly</changefreq>\n'
                                  '    <priority>0.7</priority>\n  </url>'
                                  % (base_url, prefix, slug, lastmod))
    except Exception:
        pass

    for version_slug in ('beta', 'dofus2', 'retro', 'touch'):
        vbase = '%s/%s' % (base_url, version_slug)
        for sub, prio in (('/', '0.8'), ('/setup/', '0.7'), ('/sharedbuilds/', '0.7'),
                          ('/forgemagie/', '0.6'), ('/encyclopedia/', '0.8'),
                          ('/encyclopedia/sets/', '0.7')):
            blocks.append(_sitemap_url(vbase + sub, 'weekly', prio))

    try:
        from urllib.parse import quote
        # A /s/ URL whose build has no stored solution 404s.
        shared_chars = (Char.objects
                        .filter(link_shared=True, deleted=False)
                        .exclude(minimal_solution=b'')
                        .order_by('-view_count', '-modified_time')[:5000])
        for char in shared_chars:
            try:
                loc = base_url + solution_view.shared_build_path(char)
                lastmod = ''
                if char.modified_time:
                    lastmod = '\n    <lastmod>%s</lastmod>' % char.modified_time.date().isoformat()
                blocks.append('  <url>\n    <loc>%s</loc>%s\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>' % (loc, lastmod))
            except Exception:
                continue
    except Exception:
        pass

    return '\n'.join(blocks)


# One file per section: Google refuses a sitemap over 50000 urls.
_LOCALISED_BUILDERS = (
    ('items', _sitemap_encyclopedia_items),
    ('sets', _sitemap_encyclopedia_sets),
    ('resources', _sitemap_encyclopedia_resources),
    ('monsters', _sitemap_encyclopedia_monsters),
)

# Languages submitted beyond English. One file each, rather than one big file,
# so Search Console reports coverage per language: whether Spanish indexes is
# the question worth answering, and a merged file cannot answer it.
#
# Chosen from measured audience, not from what is translated. Analytics over 30
# days: Spanish 789 users (Colombia 417, Chile 161, Spain 141, Mexico 70),
# French 438, Portuguese 217 (Brazil). German appears nowhere in the top seven
# countries, so its pages stay served and stay linked by hreflang -- which is
# enough for Google to find them -- but submitting 40 000 more URLs for an
# audience that has not shown up would be asking for crawl budget we have no
# reason to spend. Add 'de' here the day the numbers justify it.
_SITEMAP_LANGUAGES = ('fr', 'es', 'pt')


def _localised_section(builder, language):
    def build(base_url):
        return builder(base_url, language=language)
    return build


# The English sections keep their names, so the sitemaps already submitted to
# Search Console are untouched.
SITEMAP_SECTIONS = ((
    ('pages', _sitemap_pages),
) + _LOCALISED_BUILDERS + tuple(
    ('%s-%s' % (section, language), _localised_section(builder, language))
    for language in _SITEMAP_LANGUAGES
    for section, builder in _LOCALISED_BUILDERS
))
SITEMAP_BASE = 'https://dofusfashionista.gg'


def sitemap_view(request):
    entries = ['  <sitemap><loc>%s/sitemap-%s.xml</loc></sitemap>' % (SITEMAP_BASE, name)
               for name, _builder in SITEMAP_SECTIONS]
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(entries) + '\n</sitemapindex>',
        content_type='application/xml')


def sitemap_section_view(request, section):
    builder = dict(SITEMAP_SECTIONS).get(section)
    if builder is None:
        raise Http404
    body = builder(SITEMAP_BASE) or ''
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + body + '\n</urlset>',
        content_type='application/xml')


js_info_dict = {
    'packages': 'chardata',
}

urlpatterns = [
    re_path(r'^ads\.txt$', ads_txt_view, name='ads_txt'),
    # Browsers ask the root for the icon even when the page names its own.
    re_path(r'^favicon\.ico$', RedirectView.as_view(
        url=settings.STATIC_URL + 'chardata/favicon.ico', permanent=True),
        name='favicon'),
    re_path(r'^\.well-known/appspecific/com\.chrome\.devtools\.json$', chrome_devtools_view),
    re_path(r'^sitemap\.xml$', sitemap_view, name='sitemap'),
    re_path(r'^sitemap-(?P<section>[a-z-]+)\.xml$', sitemap_section_view,
            name='sitemap_section'),
    # Staff-only dashboard, gated in the view; 404 for everyone else.
    re_path(r'^admin-tools/$', admin_tools_view.admin_tools, name='admin_tools'),
    re_path(r'^admin-comment-action/$', admin_tools_view.admin_comment_action, name='admin_comment_action'),
    re_path(r'^admin-ads-action/$', admin_tools_view.admin_ads_action, name='admin_ads_action'),
    re_path(r'^manifest\.webmanifest$', manifest_view, name='manifest'),
    re_path(r'^sw\.js$', service_worker_view, name='service_worker'),
    re_path(r'^offline/$', offline_view, name='offline'),
    re_path(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog', kwargs=js_info_dict),

    # Character preview art, baked on first request. The -v<n> names match the
    # cache file names, so nginx serves them straight off disk.
    re_path(r'^character/poses/(?P<bone_id>[\w-]+)-v(?P<fmt>\d+)\.json$',
            character_assets.pose_view, name='character_pose_versioned'),
    re_path(r'^character/poses/(?P<bone_id>[\w-]+)\.json$',
            character_assets.pose_view, name='character_pose'),
    re_path(r'^character/mount/(?P<bone_id>\d+)/parts-v(?P<fmt>\d+)\.json$',
            character_assets.mount_manifest_view,
            name='character_mount_versioned'),
    re_path(r'^character/mount/(?P<bone_id>\d+)/parts\.json$',
            character_assets.mount_manifest_view, name='character_mount'),
    re_path(r'^character/mount/(?P<bone_id>\d+)/(?P<part>\d+)\.png$',
            character_assets.mount_part_view, name='character_mount_part'),
    re_path(r'^character/parts/(?P<skin_id>\d+)/parts-v(?P<fmt>\d+)\.json$',
            character_assets.parts_manifest_view,
            name='character_parts_versioned'),
    re_path(r'^character/parts/(?P<skin_id>\d+)/parts\.json$',
            character_assets.parts_manifest_view, name='character_parts'),
    re_path(r'^character/parts/(?P<skin_id>\d+)/atlas\.webp$',
            character_assets.atlas_view, name='character_atlas'),
    re_path(r'^random/$', home_view.random_build, name='random_build'),

    # Public read-only REST API (no auth, CORS open, cached 60s)
    re_path(r'^api/v1/$', api_view.api_meta, name='api_meta'),
    re_path(r'^api/v1/shared-builds/$', api_view.api_shared_builds, name='api_shared_builds'),
    re_path(r'^api/v1/shared-builds/(?P<encoded_id>[^/]+)/$', api_view.api_shared_build_detail, name='api_shared_build_detail'),
    re_path(r'^api/v1/tier-list/$', api_view.api_tier_list, name='api_tier_list'),
    re_path(r'^login_page/', login_view.login_page, name='login_page'),
    re_path(r'^login/$', login_view.login_page, name='login'),
    re_path(r'^local_login/', login_view.local_login, name='local_login'),
    re_path(r'^register/', login_view.register, name='register'),
    re_path(r'^check_your_email/', login_view.check_your_email, name='check_your_email'),
    re_path(r'^confirm_email/(?P<username>.+)/(?P<confirmation_token>.+)/', login_view.confirm_email, name='confirm_email'),
    re_path(r'^check_username/', login_view.check_if_taken, name='check_if_taken'),
    re_path(r'^change_password/', login_view.change_password, name='change_password'),
    re_path(r'^email_confirmed/(?P<username>.+)/(?P<already_confirmed>.+)/', login_view.email_confirmed_page, name='email_confirmed_page'),
    re_path(r'^recover_password/', login_view.recover_password_page, name='recover_password_page'),
    re_path(r'^recover_password_from_register/(?P<email>.+)/', login_view.recover_password_page_from_register, name='recover_password_page_from_register'),
    re_path(r'^do_recover_password/(?P<username>.+)/(?P<recover_token>.+)/', login_view.recover_password, name='recover_password'),
    re_path(r'^recover_password_email/', login_view.recover_password_email_page, name='recover_password_email_page'),

    re_path(r'^loadprojects/', views.load_projects, name='load_projects'),
    re_path(r'^loadprojectserror/(?P<error>.+)/', views.load_projects_error),
    re_path(r'^loadproject/(?P<char_id>\d+)/', views.load_a_project, name='load_a_project'),
    re_path(r'^deleteprojects/', projects_view.delete_projects, name='delete_projects'),
    re_path(r'^duplicateproject/', projects_view.duplicate_project, name='duplicate_project'),
    re_path(r'^duplicatemyproject/(?P<char_id>\d+)/', projects_view.duplicate_my_project, name='duplicate_my_project'),
    re_path(r'^sharedbuilds/', shared_builds_view.shared_builds, name='shared_builds'),
    re_path(r'^user/(?P<alias>[^/]+)/$', profile_view.user_profile, name='user_profile'),
    re_path(r'^follow/(?P<user_id>\d+)/$', profile_view.follow_user, name='follow_user'),
    re_path(r'^unfollow/(?P<user_id>\d+)/$', profile_view.unfollow_user, name='unfollow_user'),
    re_path(r'^feed/$', profile_view.feed, name='feed'),
    re_path(r'^votebuild/(?P<build_id>\d+)/', shared_builds_view.vote_build, name='vote_build'),
    re_path(r'^postcomment/(?P<build_id>\d+)/$', comment_view.post_comment, name='post_comment'),
    re_path(r'^deletecomment/(?P<comment_id>\d+)/$', comment_view.delete_comment, name='delete_comment'),
    re_path(r'^reportcomment/(?P<comment_id>\d+)/$', comment_view.report_comment, name='report_comment'),
    re_path(r'^addtag/(?P<char_id>\d+)/$', tag_view.add_tag, name='add_tag'),
    re_path(r'^removetag/(?P<tag_id>\d+)/$', tag_view.remove_tag, name='remove_tag'),
    re_path(r'^duplicatesomeonesproject/(?P<encoded_char_id>.+)/', projects_view.duplicate_someones_project, name='duplicate_someones_project'),

    re_path(r'^setup/(?P<char_id>\d+)/', base_stats_view.setup_base_stats, name='setup_base_stats'),
    re_path(r'^save_char/(?P<char_id>\d+)/', base_stats_view.save_char, name='save_char'),
    re_path(r'^initbasestats/(?P<char_id>\d+)/', base_stats_view.init_base_stats, name='init_base_stats'),
    re_path(r'^initbasestatspost/(?P<char_id>\d+)/', base_stats_view.init_base_stats_post, name='init_base_stats_post'),

    re_path(r'^setup/$', create_project_view.setup, name='setup'),
    re_path(r'^quickstart/$', coaching_view.coaching, name='quickstart'),
    re_path(r'^smartbuild/$', nl_build_view.smart_build, name='smart_build'),
    re_path(r'^workshop/$', workshop_view.workshop, name='workshop'),
    re_path(r'^workshop/ingredients/$', workshop_view.workshop_ingredients, name='workshop_ingredients'),
    re_path(r'^workshop/add/$', workshop_view.add_to_workshop, name='workshop_add'),
    re_path(r'^workshop/addsolution/(?P<char_id>\d+)/$', workshop_view.add_solution_to_workshop, name='workshop_add_solution'),
    re_path(r'^workshop/solutioningredients/(?P<char_id>\d+)/$', workshop_view.solution_ingredients, name='workshop_solution_ingredients'),
    re_path(r'^workshop/setqty/(?P<workshop_item_id>\d+)/$', workshop_view.set_workshop_quantity, name='workshop_set_qty'),
    re_path(r'^workshop/remove/(?P<workshop_item_id>\d+)/$', workshop_view.remove_from_workshop, name='workshop_remove'),
    re_path(r'^workshop/clear/$', workshop_view.clear_workshop, name='workshop_clear'),
    re_path(r'^createproject/', create_project_view.create_project, name='create_project'),
    re_path(r'^saveprojecttouser/', create_project_view.save_project_to_user, name='save_project_to_user'),
    re_path(r'^project/(?P<char_id>\d+)/', create_project_view.setup, name='project_setup'),
    re_path(r'^saveproject/(?P<char_id>\d+)/', create_project_view.save_project, name='save_project'),
    re_path(r'^understandbuild/', create_project_view.understand_build_post, name='understand_build_post'),

    re_path(r'^stats/(?P<char_id>\d+)/', stats_weights_view.stats, name='stats'),
    re_path(r'^statspost/(?P<char_id>\d+)/', stats_weights_view.stats_post, name='stats_post'),

    re_path(r'^min_stats/(?P<char_id>\d+)/', min_stats_view.min_stats, name='min_stats'),
    re_path(r'^minstatspost/(?P<char_id>\d+)/', min_stats_view.min_stats_post, name='min_stats_post'),

    re_path(r'^options/(?P<char_id>\d+)/', options_view.options, name='options'),
    re_path(r'^optionspost/(?P<char_id>\d+)/', options_view.options_post, name='options_post'),

    re_path(r'^inclusions/(?P<char_id>\d+)/', inclusions_view.inclusions, name='inclusions'),
    re_path(r'^inclusionspost/(?P<char_id>\d+)/', inclusions_view.inclusions_post, name='inclusions_post'),
    re_path(r'^getitemdetails/', inclusions_view.get_item_details, name='get_item_details'),
    re_path(r'^setitemstatoverride/(?P<char_id>\d+)/', inclusions_view.set_item_stat_override_view, name='set_item_stat_override'),

    re_path(r'^exclusions/(?P<char_id>\d+)/', exclusions_view.exclusions, name='exclusions'),
    re_path(r'^exclusionspost/(?P<char_id>\d+)/', exclusions_view.exclusions_post, name='exclusions_post'),

    re_path(r'^wizard/(?P<char_id>\d+)/', wizard_view.wizard, name='wizard'),
    re_path(r'^wizardpost/(?P<char_id>\d+)/', wizard_view.wizard_post, name='wizard_post'),
    re_path(r'^wizardgetsliders/(?P<char_id>\d+)/', wizard_view.get_resetted_sliders, name='wizard_get_sliders'),

    re_path(r'^fashion/(?P<char_id>\d+)/', fashion_action.fashion, name='fashion'),

    re_path(r'^solution/(?P<char_id>\d+)/(?P<empty>.*)/', solution_view.solution, name='solution'),
    re_path(r'^solutiongeneration/(?P<char_id>\d+)/(?P<generation_id>\d+)/',
            solution_view.solution_generation, name='solution_generation'),
    re_path(r'^restoregeneration/(?P<char_id>\d+)/(?P<generation_id>\d+)/',
            solution_view.restore_generation, name='restore_generation'),
    re_path(r'^solution/(?P<char_id>\d+)/', solution_view.solution, name='solution_2'),
    re_path(r'^getsharinglink/(?P<char_id>\d+)/', solution_view.get_sharing_link, name='get_sharing_link'),
    re_path(r'^hidesharinglink/(?P<char_id>\d+)/', solution_view.hide_sharing_link),
    re_path(r'^s/(?P<char_name>.*)/(?P<encoded_char_id>.+)/', solution_view.solution_linked, name='solution_linked'),
    re_path(r'^setchargender/(?P<char_id>\d+)/', solution_view.set_char_gender, name='set_char_gender'),
    re_path(r'^setcharcolors/(?P<char_id>\d+)/', solution_view.set_char_colors, name='set_char_colors'),
    re_path(r'^setcharhidden/(?P<char_id>\d+)/', solution_view.set_char_hidden, name='set_char_hidden'),
    re_path(r'^setitemlocked/(?P<char_id>\d+)/', solution_view.set_item_locked, name='set_item_locked'),
    re_path(r'^setitemforbidden/(?P<char_id>\d+)/', solution_view.set_item_forbidden, name='set_item_forbidden'),
    re_path(r'^setslotlockempty/(?P<char_id>\d+)/', solution_view.set_slot_lock_empty, name='set_slot_lock_empty'),
    re_path(r'^itemexchange/(?P<char_id>\d+)/', item_exchange.get_items_to_exchange, name='item_exchange'),
    re_path(r'^itemadd/(?P<char_id>\d+)/', item_exchange.get_items_of_type, name='item_add'),
    re_path(r'^exchange/(?P<char_id>\d+)/', item_exchange.switch_item, name='exchange'),
    re_path(r'^remove/(?P<char_id>\d+)/', item_exchange.remove_item, name='remove'),

    re_path(r'^infeasible/(?P<char_id>\d+)/', views.infeasible, name='infeasible'),
    re_path(r'^changelog-content/$', util_views.changelog_content,
            name='changelog_content'),
    re_path(r'^guides/(?P<slug>[a-z0-9-]+)/$', guides_view.guide, name='guide'),
    re_path(r'^about/', views.about, name='about'),
    re_path(r'^license/', views.license_page, name='license_page'),
    re_path(r'^faq/', views.faq, name='faq'),
    re_path(r'^privacy/', views.privacy, name='privacy'),
    re_path(r'^support/', views.support, name='support'),
    re_path(r'^encyclopedia/item/(?P<ankama_type>[^/]+)/(?P<ankama_id>\d+)-(?P<slug>[^/]*)/$',
            encyclopedia_view.encyclopedia_item,
            name='encyclopedia_item'),
    re_path(r'^encyclopedia/resource/(?P<subtype>[^/]+)/(?P<ankama_id>\d+)-(?P<slug>[^/]*)/$',
            encyclopedia_view.encyclopedia_resource,
            name='encyclopedia_resource'),
    re_path(r'^encyclopedia/monster/(?P<monster_id>\d+)-(?P<slug>[^/]*)/$',
            encyclopedia_view.encyclopedia_monster,
            name='encyclopedia_monster'),
    re_path(r'^encyclopedia/set/(?P<set_id>\d+)(?:-(?P<slug>[^/]+))?/$', encyclopedia_view.encyclopedia_set,
            name='encyclopedia_set'),
    re_path(r'^forgemagie/$', forgemagie_view.forgemagie, name='forgemagie'),
    re_path(r'^forgemagie/items/$', forgemagie_view.forgemagie_items, name='forgemagie_items'),
    re_path(r'^inventory/$', inventory_view.inventory, name='inventory'),
    re_path(r'^inventory/folders/$', inventory_view.inventory_folders, name='inventory_folders'),
    re_path(r'^inventory/folder/add/$', inventory_view.inventory_folder_add, name='inventory_folder_add'),
    re_path(r'^inventory/folder/delete/$', inventory_view.inventory_folder_delete, name='inventory_folder_delete'),
    re_path(r'^inventory/add/$', inventory_view.inventory_add, name='inventory_add'),
    re_path(r'^inventory/update/$', inventory_view.inventory_update, name='inventory_update'),
    re_path(r'^inventory/remove/$', inventory_view.inventory_remove, name='inventory_remove'),

    re_path(r'^best_combo/(?P<char_id>\d+)/$', spells_view.best_combo_json,
            name='best_combo'),
    re_path(r'^best_combo_linked/(?P<encoded_char_id>.+)/$',
            spells_view.best_combo_linked_json, name='best_combo_linked'),
    re_path(r'^spells/(?P<char_id>\d+)/', spells_view.spells, name='spells'),
    re_path(r'^spells_linked/(?P<char_name>.*)/(?P<encoded_char_id>.+)/', spells_view.spells_linked, name='spells_linked'),

    re_path(r'^403/', views.forbidden, name = 'forbidden'),
    re_path(r'^404/', views.not_found, name = 'not_found'),
    re_path(r'^500/', views.app_error, name = 'app_error'),

    re_path(r'^contact/thankyou/', contact_view.thankyou, name = 'thankyou'),
    re_path(r'^contact/nomessage/', contact_view.nomessage, name = 'nomessage'),
    re_path(r'^contact/', contact_view.contact, name = 'contact'),
    re_path(r'^send/', contact_view.send_email, name = 'send_email'),

    re_path(r'^logout/$', login_view.logout_view, name='logout'),

    re_path(r'^manageaccount/', manage_account_view.manage_account, name = 'manage_account'),
    re_path(r'^saveaccount/', manage_account_view.save_account, name = 'save_account'),
    
    re_path(r'^changetheme/', util.set_theme, name = 'set_theme'),
    re_path(r'^changeautotheme/', util.set_current_auto, name = 'set_current_auto'),

    re_path('', include('social_django.urls', namespace='social')),
    re_path('', include(('django.contrib.auth.urls', 'auth'))),

    re_path(r'^robots\.txt$', TemplateView.as_view(template_name='chardata/robots.txt',
                                               content_type='text/plain')),
                                               
                                               
    
]

if settings.DEBUG:
    urlpatterns += [
        re_path(r'^edit_item/$', manage_items_view.edit_item, name = 'edit_item'),
        re_path(r'^edit_item/(?P<item_id>\d+)/', manage_items_view.edit_item, name = 'edit_item'),
        re_path(r'^edit_item_search_item/', manage_items_view.edit_item_search_item, name = 'edit_item_search_item'),
        re_path(r'^choose_item/', manage_items_view.choose_item, name = 'choose_item'),
        re_path(r'^update_item/', manage_items_view.update_item_post, name = 'update_item'),
        re_path(r'^delete_item/', manage_items_view.delete_item_post, name = 'delete_item'),
        re_path(r'^edit_item_search_sets/', manage_items_view.edit_item_search_sets, name = 'edit_item_search_sets'),
        re_path(r'^edit_set/', manage_items_view.edit_set, name = 'edit_set'),
        re_path(r'^choose_set/', manage_items_view.choose_set, name = 'choose_set'),
        re_path(r'^update_set/', manage_items_view.update_set_post, name = 'update_set'),
        re_path(r'^delete_set/', manage_items_view.delete_set_post, name = 'delete_set'),
        re_path(r'^admin/', admin.site.urls, name = 'admin'),
    ]

if settings.EXPERIMENTS['COMPARE_SETS']:
    urlpatterns += [
                            re_path(r'^compare_sets/(?P<sets_params>.+)', compare_sets_view.compare_sets, name = 'compare_sets'),
                            re_path(r'^choose_compare_sets/$', compare_sets_view.choose_compare_sets, name = 'choose_compare_sets'),
                            re_path(r'^choose_compare_sets_post/$', compare_sets_view.choose_compare_sets_post, name = 'choose_compare_sets_post'),
                            re_path(r'^get_compare_sharing_link/(?P<sets_params>.+)', compare_sets_view.get_sharing_link, name = 'get_compare_sharing_link'),
                            re_path(r'^get_item_stats_compare/$', compare_sets_view.get_item_stats, name = 'get_item_stats'),
                            re_path(r'^compare_set_search_proj_name/$', compare_sets_view.compare_set_search_proj_name, name = 'compare_set_search_proj_name'),]

if settings.EXPERIMENTS['TRANSLATION']:
    urlpatterns += [
                            # Ours first: it also stores the choice on the
                            # profile, for the notification email language.
                            re_path(r'^i18n/setlang/$', views.set_language_and_remember, name='set_language'),
                            re_path(r'^i18n/', include('django.conf.urls.i18n'))]

urlpatterns += staticfiles_urlpatterns()

# Version-specific routes: same views, game_version set by middleware. The URL
# namespace is what makes reverse('beta:setup') give /beta/setup/.
_game_urls = ('chardata.game_urls', 'chardata')

# Pages with no name of their own to localise. Everything else carries its
# language in the entity name -- /encyclopedia/item/equipment/44-espada-de-
# maderucha/ is the Spanish page and says so -- but a hub has no name, so the
# language goes in a prefix instead.
#
# prefix_default_language=False keeps every English URL exactly where it is:
# /encyclopedia/ still answers at /encyclopedia/, and /es/encyclopedia/ is
# added beside it. Nothing already indexed moves.
#
# Only the default version's hubs for now. A version-prefixed hub would stack
# two prefixes (/es/dofus2/encyclopedia/) and needs its own pass.
urlpatterns += i18n_patterns(
    re_path(r'^$', home_view.home, name='home'),
    re_path(r'^guides/$', guides_view.guides, name='guides'),
    re_path(r'^encyclopedia/$', encyclopedia_view.encyclopedia,
            name='encyclopedia'),
    re_path(r'^encyclopedia/monsters/$',
            encyclopedia_view.encyclopedia_monsters,
            name='encyclopedia_monsters'),
    re_path(r'^encyclopedia/sets/$', encyclopedia_view.encyclopedia_sets,
            name='encyclopedia_sets'),

    # The other game versions, inside the same block so the rule holds for all
    # of them: /dofus2/encyclopedia/ in English, /es/dofus2/encyclopedia/ in
    # Spanish. reverse() restores the prefix, so {% game_url %} and
    # version_reverse() need no change.
    #
    # Entity routes come along, which is what we want rather than a problem:
    # /dofus2/encyclopedia/set/123/ carries no name, so today its language
    # comes from Accept-Language -- a header no crawler sends. Prefixed, it is
    # decided by the URL like everything else.
    path('beta/', include(_game_urls, namespace='beta')),
    path('dofus2/', include(_game_urls, namespace='dofus2')),
    path('retro/', include(_game_urls, namespace='retro')),
    path('touch/', include(_game_urls, namespace='touch')),
    prefix_default_language=False,
)

handler403 = views.forbidden
handler404 = views.not_found
handler500 = views.app_error
