# -*- coding: utf-8 -*-
"""Accounts and rows the account deletion tests start from."""
import pickle
import re

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from fashionistapulp.modelresult import ModelResultMinimal
from social_django.models import UserSocialAuth

from chardata.login_view import _prehash_password
from chardata.models import (BuildComment, BuildTag, BuildVote, Char,
                             CharBaseStats, CommentReport, InventoryFolder,
                             InventoryItem, ItemInSharedBuild, SolutionGeneration,
                             UserAlias, UserFollow, WorkshopItem, WorkshopStock,
                             WorkshopUndo)

ADDRESS = 'holder@test.local'
PASSWORD = 'pw-42-solid'


def a_password_account(username='holder', address=ADDRESS, password=PASSWORD):
    user = User.objects.create_user(username, address, _prehash_password(password))
    UserAlias.objects.create(user=user, alias=username.capitalize())
    return user


def a_google_account(username='jean.dupont', address='jean.dupont@gmail.test', uid='42'):
    user = User.objects.create_user(username, address)
    UserSocialAuth.objects.create(user=user, provider='google-oauth2', uid=uid)
    return user


def a_build(owner, name='Mybuild', shared=False, deleted=False, version='dofus3'):
    input_ = {'options': {'ap_exo': False, 'mp_exo': False},
              'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    return Char.objects.create(
        minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
        name=name, char_name=name.lower(), char_class='Iop', char_build='build',
        level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'', owner=owner,
        link_shared=shared, deleted=deleted, game_version=version)


def mailed_link(message=None, route='confirm_account_deletion'):
    body = (message or mail.outbox[-1]).body
    match = re.search(r'https?://[^\s/]+(/%s/[^/\s]+/)' % route, body)
    assert match is not None, body
    return match.group(1)


def outcome_of(response):
    """The outcome word a deletion route redirected to."""
    match = re.search(r'/account_deletion/([a-z_]+)/$', response['Location'])
    assert match is not None, response['Location']
    return match.group(1)


def fill_every_relation(user, other):
    """One row of every kind that points at the user, plus builds with children."""
    shared = a_build(user, 'Shared', shared=True)
    live = a_build(user, 'Private')
    gone = a_build(user, 'Gone', deleted=True)
    for build in (shared, live, gone):
        CharBaseStats.objects.create(char=build, stat='vitality')
        BuildTag.objects.create(char=build, name='tag', display_name='Tag')
        SolutionGeneration.objects.create(char=build, minimal_solution=b'x')
        ItemInSharedBuild.objects.create(ankama_id=1, char=build)
    comment = BuildComment.objects.create(user=user, build=a_build(other, 'Theirs', shared=True),
                                          content='from the leaver')
    CommentReport.objects.create(user=other, comment=comment)
    reply = BuildComment.objects.create(user=other, build=comment.build, content='from the neighbour')
    CommentReport.objects.create(user=user, comment=reply)
    BuildVote.objects.create(user=user, build=comment.build, vote_type='like')
    UserFollow.objects.create(follower=user, followed=other)
    UserFollow.objects.create(follower=other, followed=user)
    WorkshopItem.objects.create(user=user, item_id=1)
    WorkshopStock.objects.create(user=user, ingredient_ankama_id=1, ingredient_subtype='x')
    WorkshopUndo.objects.create(user=user, workshop_item_id=1, item_id=1)
    folder = InventoryFolder.objects.create(user=user, name='Folder')
    InventoryItem.objects.create(folder=folder, item_id=1)
    user_type = ContentType.objects.get_for_model(User)
    LogEntry.objects.create(user=other, content_type=user_type, object_id=str(user.pk),
                            object_repr=user.username, action_flag=ADDITION)
    LogEntry.objects.create(user=user, content_type=user_type, object_id=str(other.pk),
                            object_repr=other.username, action_flag=ADDITION)
    social = UserSocialAuth.objects.create(user=user, provider='google-oauth2',
                                           uid='linked-%d' % user.pk)
    LogEntry.objects.create(user=other,
                            content_type=ContentType.objects.get_for_model(UserSocialAuth),
                            object_id=str(social.pk), object_repr=user.username,
                            action_flag=ADDITION)
    user.groups.add(Group.objects.get_or_create(name='readers')[0])
    user.user_permissions.add(Permission.objects.first())
    return shared, live, gone
