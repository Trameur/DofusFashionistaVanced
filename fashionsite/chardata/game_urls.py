from django.urls import re_path
from django.conf import settings
from chardata import (
    home_view, views, projects_view, base_stats_view, create_project_view,
    stats_weights_view, min_stats_view, options_view, inclusions_view,
    exclusions_view, wizard_view, fashion_action, solution_view, spells_view,
    compare_sets_view, item_exchange, util_views, shared_builds_view,
    encyclopedia_view, login_view, manage_account_view, contact_view,
    comment_view, coaching_view, workshop_view, profile_view,
    tag_view, nl_build_view, forgemagie_view, inventory_view,
)

urlpatterns = [
    re_path(r'^$', home_view.home, name='home'),
    re_path(r'^random/$', home_view.random_build, name='random_build'),

    re_path(r'^login_page/', login_view.login_page, name='login_page'),
    re_path(r'^local_login/', login_view.local_login, name='local_login'),
    re_path(r'^register/', login_view.register, name='register'),
    re_path(r'^check_your_email/', login_view.check_your_email, name='check_your_email'),

    re_path(r'^manageaccount/', manage_account_view.manage_account, name='manage_account'),
    re_path(r'^saveaccount/', manage_account_view.save_account, name='save_account'),

    re_path(r'^loadprojects/', views.load_projects, name='load_projects'),
    re_path(r'^loadprojectserror/(?P<error>.+)/', views.load_projects_error, name='load_projects_error'),
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
    re_path(r'^hidesharinglink/(?P<char_id>\d+)/', solution_view.hide_sharing_link, name='hide_sharing_link'),
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
    re_path(r'^faq/', views.faq, name='faq'),
    re_path(r'^support/', views.support, name='support'),
    re_path(r'^license/', views.license_page, name='license_page'),
    re_path(r'^contact/thankyou/', contact_view.thankyou, name='thankyou'),
    re_path(r'^contact/nomessage/', contact_view.nomessage, name='nomessage'),
    re_path(r'^contact/', contact_view.contact, name='contact'),
    re_path(r'^send/', contact_view.send_email, name='send_email'),

    re_path(r'^encyclopedia/$', encyclopedia_view.encyclopedia, name='encyclopedia'),
    re_path(r'^encyclopedia/item/(?P<ankama_type>[^/]+)/(?P<ankama_id>\d+)-(?P<slug>.*)/$',
            encyclopedia_view.encyclopedia_item, name='encyclopedia_item'),
    re_path(r'^forgemagie/$', forgemagie_view.forgemagie, name='forgemagie'),
    re_path(r'^forgemagie/items/$', forgemagie_view.forgemagie_items, name='forgemagie_items'),
    re_path(r'^inventory/$', inventory_view.inventory, name='inventory'),
    re_path(r'^inventory/folders/$', inventory_view.inventory_folders, name='inventory_folders'),
    re_path(r'^inventory/folder/add/$', inventory_view.inventory_folder_add, name='inventory_folder_add'),
    re_path(r'^inventory/folder/delete/$', inventory_view.inventory_folder_delete, name='inventory_folder_delete'),
    re_path(r'^inventory/add/$', inventory_view.inventory_add, name='inventory_add'),
    re_path(r'^inventory/update/$', inventory_view.inventory_update, name='inventory_update'),
    re_path(r'^inventory/remove/$', inventory_view.inventory_remove, name='inventory_remove'),

    re_path(r'^spells/(?P<char_id>\d+)/', spells_view.spells, name='spells'),
    re_path(r'^spells_linked/(?P<char_name>.*)/(?P<encoded_char_id>.+)/', spells_view.spells_linked, name='spells_linked'),
]

if settings.EXPERIMENTS.get('COMPARE_SETS'):
    urlpatterns += [
        re_path(r'^compare_sets/(?P<sets_params>.+)', compare_sets_view.compare_sets, name='compare_sets'),
        re_path(r'^choose_compare_sets/$', compare_sets_view.choose_compare_sets, name='choose_compare_sets'),
        re_path(r'^choose_compare_sets_post/$', compare_sets_view.choose_compare_sets_post, name='choose_compare_sets_post'),
        re_path(r'^get_compare_sharing_link/(?P<sets_params>.+)', compare_sets_view.get_sharing_link, name='get_compare_sharing_link'),
        re_path(r'^get_item_stats_compare/$', compare_sets_view.get_item_stats, name='get_item_stats'),
        re_path(r'^compare_set_search_proj_name/$', compare_sets_view.compare_set_search_proj_name, name='compare_set_search_proj_name'),
    ]
