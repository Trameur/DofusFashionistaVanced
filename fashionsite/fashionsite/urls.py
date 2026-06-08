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

from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib import admin
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views.static import serve
import os
from chardata import home_view, login_view, views, projects_view, base_stats_view, create_project_view, \
    stats_weights_view, min_stats_view, options_view, inclusions_view, exclusions_view, wizard_view, \
    fashion_action, solution_view, spells_view, contact_view, manage_account_view, util, manage_items_view, \
  compare_sets_view, item_exchange, util_views, shared_builds_view, encyclopedia_view, comment_view, \
    coaching_view, workshop_view, profile_view, tag_view, api_view, nl_build_view
from chardata.models import Char
from chardata.encoded_char_id import encode_char_id
admin.autodiscover()

def ads_txt_view(request):
    """Serve the ads.txt file"""
    content = "google.com, pub-3961330018791408, DIRECT, f08c47fec0942fa0"
    return HttpResponse(content, content_type='text/plain')

def manifest_view(request):
    """PWA web app manifest (served from root so scope covers the whole site)."""
    from django.templatetags.static import static as dj_static
    try:
        from static_s3.templatetags.static_s3 import static as s3_static
        icon = s3_static('chardata/favicon.ico')
        banner = s3_static('chardata/fashionista_banner.jpg')
    except Exception:
        icon = dj_static('chardata/favicon.ico')
        banner = dj_static('chardata/fashionista_banner.jpg')
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
        "icons": [
            {"src": icon, "sizes": "64x64", "type": "image/x-icon", "purpose": "any"},
            {"src": banner, "sizes": "512x256", "type": "image/jpeg", "purpose": "any"},
        ],
    }
    return HttpResponse(_json.dumps(manifest), content_type='application/manifest+json')

def service_worker_view(request):
    """Minimal offline-first service worker. Served at root for full scope.

    Network-first for navigation (so users always get fresh builds when online)
    with a tiny cached offline fallback; cache-first for static assets."""
    sw = """
const CACHE = 'fashionista-v1';
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
    if (/\\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?)$/.test(url.pathname)) {
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
    return HttpResponse(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Offline - Dofus Fashionista</title></head>"
        "<body style='font-family:sans-serif;text-align:center;padding:40px;'>"
        "<h1>You are offline</h1>"
        "<p>Dofus Fashionista needs a connection to optimize builds. "
        "Reconnect and try again.</p></body></html>",
        content_type='text/html')

def sitemap_view(request):
    """Generate a comprehensive sitemap.xml for AdSense and SEO
    
    Includes static pages and a sample of popular shared solutions.
    Google will also discover more pages by following links on your site.
    """
    # Always use HTTPS for sitemap URLs to avoid redirect issues
    base_url = 'https://dofusfashionista.gg'
    
    # Build URLs for shared solutions (limit to 50 most recently shared)
    shared_solutions = []
    try:
        shared_chars = Char.objects.filter(link_shared=True, deleted=False).order_by('-modified_time')[:50]
        for char in shared_chars:
            try:
                encoded_id = encode_char_id(int(char.id))
                char_name = char.char_name or 'shared'
                # Escape special characters in char_name for URL safety
                from urllib.parse import quote
                char_name_safe = quote(char_name.encode('utf-8'), safe='')
                shared_url = f"{base_url}/s/{char_name_safe}/{encoded_id}/"
                
                # Use modified_time as lastmod if available
                lastmod = ""
                if char.modified_time:
                    # Convert date to ISO format (YYYY-MM-DD)
                    lastmod = f"<lastmod>{char.modified_time.isoformat()}</lastmod>"
                
                shared_solutions.append(f"""  <url>
    <loc>{shared_url}</loc>{lastmod}
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""")
            except Exception:
                # Skip individual chars that fail
                continue
    except Exception:
        # If there's any error querying shared solutions, continue without them
        pass
    
    shared_solutions_xml = '\n'.join(shared_solutions) if shared_solutions else '  <!-- No shared solutions yet -->'

    # Version-specific landing pages so each game version is indexed as its own
    # entry point (beta, dofus2, retro). dofus3 is the default, covered above.
    version_pages = []
    for version_slug in ('beta', 'dofus2', 'retro'):
        version_base = f"{base_url}/{version_slug}/"
        for sub_path, priority in (('', '1.0'), ('setup/', '0.9'), ('sharedbuilds/', '0.85')):
            version_pages.append(f"""  <url>
    <loc>{version_base}{sub_path}</loc>
    <changefreq>weekly</changefreq>
    <priority>{priority}</priority>
  </url>""")
    version_pages_xml = '\n'.join(version_pages)

    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <!-- Main Pages -->
  <url>
    <loc>{base_url}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  
  <!-- Information Pages -->
  <url>
    <loc>{base_url}/about/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{base_url}/faq/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{base_url}/contact/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{base_url}/license/</loc>
    <changefreq>yearly</changefreq>
    <priority>0.6</priority>
  </url>
  
  <!-- User Authentication -->
  <url>
    <loc>{base_url}/login_page/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>{base_url}/register/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  
  <!-- Main Features -->
  <url>
    <loc>{base_url}/setup/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.95</priority>
  </url>
  <url>
    <loc>{base_url}/loadprojects/</loc>
    <changefreq>daily</changefreq>
    <priority>0.85</priority>
  </url>
  <url>
    <loc>{base_url}/choose_compare_sets/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.85</priority>
  </url>
  
  <!-- Thank You / Confirmation Pages -->
  <url>
    <loc>{base_url}/contact/thankyou/</loc>
    <changefreq>yearly</changefreq>
    <priority>0.4</priority>
  </url>
  
  <!-- Game Version Landing Pages -->
{version_pages_xml}

  <!-- Sample of Popular Shared Solutions -->
{shared_solutions_xml}
</urlset>"""
    
    return HttpResponse(sitemap_content, content_type='application/xml')

js_info_dict = {
    'packages': 'chardata',
}

urlpatterns = [
    re_path(r'^ads\.txt$', ads_txt_view, name='ads_txt'),
    re_path(r'^sitemap\.xml$', sitemap_view, name='sitemap'),
    re_path(r'^manifest\.webmanifest$', manifest_view, name='manifest'),
    re_path(r'^sw\.js$', service_worker_view, name='service_worker'),
    re_path(r'^offline/$', offline_view, name='offline'),
    re_path(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog', kwargs=js_info_dict),
    re_path(r'^$', home_view.home, name='home'),
    re_path(r'^random/$', home_view.random_build, name='random_build'),

    # Public read-only REST API (no auth, CORS open, cached 60s)
    re_path(r'^api/v1/$', api_view.api_meta, name='api_meta'),
    re_path(r'^api/v1/shared-builds/$', api_view.api_shared_builds, name='api_shared_builds'),
    re_path(r'^api/v1/shared-builds/(?P<encoded_id>[^/]+)/$', api_view.api_shared_build_detail, name='api_shared_build_detail'),
    re_path(r'^api/v1/tier-list/$', api_view.api_tier_list, name='api_tier_list'),
    re_path(r'^login_page/', login_view.login_page, name='login_page'),
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
    re_path(r'^solution/(?P<char_id>\d+)/', solution_view.solution, name='solution_2'),
    re_path(r'^getsharinglink/(?P<char_id>\d+)/', solution_view.get_sharing_link, name='get_sharing_link'),
    re_path(r'^hidesharinglink/(?P<char_id>\d+)/', solution_view.hide_sharing_link),
    re_path(r'^s/(?P<char_name>.*)/(?P<encoded_char_id>.+)/', solution_view.solution_linked, name='solution_linked'),
    re_path(r'^setitemlocked/(?P<char_id>\d+)/', solution_view.set_item_locked, name='set_item_locked'),
    re_path(r'^setitemforbidden/(?P<char_id>\d+)/', solution_view.set_item_forbidden, name='set_item_forbidden'),
    re_path(r'^setslotlockempty/(?P<char_id>\d+)/', solution_view.set_slot_lock_empty, name='set_slot_lock_empty'),
    re_path(r'^itemexchange/(?P<char_id>\d+)/', item_exchange.get_items_to_exchange, name='item_exchange'),
    re_path(r'^itemadd/(?P<char_id>\d+)/', item_exchange.get_items_of_type, name='item_add'),
    re_path(r'^exchange/(?P<char_id>\d+)/', item_exchange.switch_item, name='exchange'),
    re_path(r'^remove/(?P<char_id>\d+)/', item_exchange.remove_item, name='remove'),

    re_path(r'^infeasible/(?P<char_id>\d+)/', views.infeasible, name='infeasible'),
    re_path(r'^error/(?P<char_id>\d+)/', util_views.error, name='error'),
    re_path(r'^about/', views.about, name='about'),
    re_path(r'^license/', views.license_page, name='license_page'),
    re_path(r'^faq/', views.faq, name='faq'),
    re_path(r'^support/', views.support, name='support'),
    re_path(r'^encyclopedia/$', encyclopedia_view.encyclopedia, name='encyclopedia'),
    re_path(r'^encyclopedia/item/(?P<ankama_type>[^/]+)/(?P<ankama_id>\d+)-(?P<slug>.*)/$',
            encyclopedia_view.encyclopedia_item,
            name='encyclopedia_item'),

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
                            re_path(r'^i18n/', include('django.conf.urls.i18n'))]

urlpatterns += staticfiles_urlpatterns()

# Version-specific routes: same views, game_version set by middleware.
# Each version gets a Django URL namespace so {% game_url %} can resolve
# version-prefixed URLs (e.g. reverse('beta:setup') → /beta/setup/).
_game_urls = ('chardata.game_urls', 'chardata')
urlpatterns += [
    path('beta/', include(_game_urls, namespace='beta')),
    path('dofus2/', include(_game_urls, namespace='dofus2')),
    path('retro/', include(_game_urls, namespace='retro')),
    path('touch/', include(_game_urls, namespace='touch')),
]

handler403 = views.forbidden
handler404 = views.not_found
handler500 = views.app_error
