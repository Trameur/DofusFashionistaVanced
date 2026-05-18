from django.urls import re_path
from django.conf import settings
from chardata import (
    home_view, views, projects_view, base_stats_view, create_project_view,
    stats_weights_view, min_stats_view, options_view, inclusions_view,
    exclusions_view, wizard_view, fashion_action, solution_view, spells_view,
    compare_sets_view, item_exchange, util_views, shared_builds_view,
    encyclopedia_view,
)

urlpatterns = [
    re_path(r'^$', home_view.home),

    re_path(r'^loadprojects/', views.load_projects),
    re_path(r'^loadprojectserror/(?P<error>.+)/', views.load_projects_error),
    re_path(r'^loadproject/(?P<char_id>\d+)/', views.load_a_project),
    re_path(r'^deleteprojects/', projects_view.delete_projects),
    re_path(r'^duplicateproject/', projects_view.duplicate_project),
    re_path(r'^duplicatemyproject/(?P<char_id>\d+)/', projects_view.duplicate_my_project),
    re_path(r'^sharedbuilds/', shared_builds_view.shared_builds),
    re_path(r'^votebuild/(?P<build_id>\d+)/', shared_builds_view.vote_build),
    re_path(r'^duplicatesomeonesproject/(?P<encoded_char_id>.+)/', projects_view.duplicate_someones_project),

    re_path(r'^setup/(?P<char_id>\d+)/', base_stats_view.setup_base_stats),
    re_path(r'^save_char/(?P<char_id>\d+)/', base_stats_view.save_char),
    re_path(r'^initbasestats/(?P<char_id>\d+)/', base_stats_view.init_base_stats),
    re_path(r'^initbasestatspost/(?P<char_id>\d+)/', base_stats_view.init_base_stats_post),

    re_path(r'^setup/$', create_project_view.setup),
    re_path(r'^createproject/', create_project_view.create_project),
    re_path(r'^saveprojecttouser/', create_project_view.save_project_to_user),
    re_path(r'^project/(?P<char_id>\d+)/', create_project_view.setup),
    re_path(r'^saveproject/(?P<char_id>\d+)/', create_project_view.save_project),
    re_path(r'^understandbuild/', create_project_view.understand_build_post),

    re_path(r'^stats/(?P<char_id>\d+)/', stats_weights_view.stats),
    re_path(r'^statspost/(?P<char_id>\d+)/', stats_weights_view.stats_post),

    re_path(r'^min_stats/(?P<char_id>\d+)/', min_stats_view.min_stats),
    re_path(r'^minstatspost/(?P<char_id>\d+)/', min_stats_view.min_stats_post),

    re_path(r'^options/(?P<char_id>\d+)/', options_view.options),
    re_path(r'^optionspost/(?P<char_id>\d+)/', options_view.options_post),

    re_path(r'^inclusions/(?P<char_id>\d+)/', inclusions_view.inclusions),
    re_path(r'^inclusionspost/(?P<char_id>\d+)/', inclusions_view.inclusions_post),
    re_path(r'^getitemdetails/', inclusions_view.get_item_details),

    re_path(r'^exclusions/(?P<char_id>\d+)/', exclusions_view.exclusions),
    re_path(r'^exclusionspost/(?P<char_id>\d+)/', exclusions_view.exclusions_post),

    re_path(r'^wizard/(?P<char_id>\d+)/', wizard_view.wizard),
    re_path(r'^wizardpost/(?P<char_id>\d+)/', wizard_view.wizard_post),
    re_path(r'^wizardgetsliders/(?P<char_id>\d+)/', wizard_view.get_resetted_sliders),

    re_path(r'^fashion/(?P<char_id>\d+)/', fashion_action.fashion),

    re_path(r'^solution/(?P<char_id>\d+)/(?P<empty>.*)/', solution_view.solution),
    re_path(r'^solution/(?P<char_id>\d+)/', solution_view.solution),
    re_path(r'^getsharinglink/(?P<char_id>\d+)/', solution_view.get_sharing_link),
    re_path(r'^hidesharinglink/(?P<char_id>\d+)/', solution_view.hide_sharing_link),
    re_path(r'^s/(?P<char_name>.*)/(?P<encoded_char_id>.+)/', solution_view.solution_linked),
    re_path(r'^setitemlocked/(?P<char_id>\d+)/', solution_view.set_item_locked),
    re_path(r'^setitemforbidden/(?P<char_id>\d+)/', solution_view.set_item_forbidden),
    re_path(r'^itemexchange/(?P<char_id>\d+)/', item_exchange.get_items_to_exchange),
    re_path(r'^itemadd/(?P<char_id>\d+)/', item_exchange.get_items_of_type),
    re_path(r'^exchange/(?P<char_id>\d+)/', item_exchange.switch_item),
    re_path(r'^remove/(?P<char_id>\d+)/', item_exchange.remove_item),

    re_path(r'^infeasible/(?P<char_id>\d+)/', views.infeasible),
    re_path(r'^error/(?P<char_id>\d+)/', util_views.error),

    re_path(r'^encyclopedia/$', encyclopedia_view.encyclopedia),
    re_path(r'^encyclopedia/item/(?P<ankama_type>[^/]+)/(?P<ankama_id>\d+)-(?P<slug>.*)/$',
            encyclopedia_view.encyclopedia_item),

    re_path(r'^spells/(?P<char_id>\d+)/', spells_view.spells),
    re_path(r'^spells_linked/(?P<char_name>.*)/(?P<encoded_char_id>.+)/', spells_view.spells_linked),
]

if settings.EXPERIMENTS.get('COMPARE_SETS'):
    urlpatterns += [
        re_path(r'^compare_sets/(?P<sets_params>.+)', compare_sets_view.compare_sets),
        re_path(r'^choose_compare_sets/$', compare_sets_view.choose_compare_sets),
        re_path(r'^choose_compare_sets_post/$', compare_sets_view.choose_compare_sets_post),
        re_path(r'^get_compare_sharing_link/(?P<sets_params>.+)', compare_sets_view.get_sharing_link),
        re_path(r'^get_item_stats_compare/$', compare_sets_view.get_item_stats),
        re_path(r'^compare_set_search_proj_name/$', compare_sets_view.compare_set_search_proj_name),
    ]
