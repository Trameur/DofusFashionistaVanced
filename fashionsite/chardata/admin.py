# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

from django.contrib import admin

from chardata.models import BuildComment, BuildTag, CommentReport, UserAlias, UserFollow, WorkshopItem


@admin.register(BuildComment)
class BuildCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'build', 'short_content', 'created_time', 'deleted')
    list_filter = ('deleted', 'created_time')
    search_fields = ('content', 'user__username', 'user__useralias__alias',
                     'build__name', 'build__char_name')
    raw_id_fields = ('user', 'build')
    actions = ['mark_as_deleted', 'mark_as_visible']

    def short_content(self, obj):
        return (obj.content[:80] + '…') if len(obj.content) > 80 else obj.content
    short_content.short_description = 'Content'

    @admin.action(description='Mark selected comments as deleted')
    def mark_as_deleted(self, request, queryset):
        queryset.update(deleted=True)

    @admin.action(description='Restore selected comments (un-delete)')
    def mark_as_visible(self, request, queryset):
        queryset.update(deleted=False)


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'comment', 'reason', 'created_time', 'processed')
    list_filter = ('processed', 'reason', 'created_time')
    search_fields = ('user__username', 'comment__content')
    raw_id_fields = ('user', 'comment')
    actions = ['mark_as_processed', 'mark_as_unprocessed']

    @admin.action(description='Mark selected reports as processed')
    def mark_as_processed(self, request, queryset):
        queryset.update(processed=True)

    @admin.action(description='Re-open selected reports')
    def mark_as_unprocessed(self, request, queryset):
        queryset.update(processed=False)


@admin.register(UserAlias)
class UserAliasAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'alias', 'notify_comments')
    list_filter = ('notify_comments',)
    search_fields = ('user__username', 'alias')
    raw_id_fields = ('user',)


@admin.register(WorkshopItem)
class WorkshopItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'item_id', 'game_version', 'quantity', 'added_time')
    list_filter = ('game_version', 'added_time')
    search_fields = ('user__username',)
    raw_id_fields = ('user',)


@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    list_display = ('id', 'follower', 'followed', 'created_time')
    search_fields = ('follower__username', 'followed__username')
    raw_id_fields = ('follower', 'followed')


@admin.register(BuildTag)
class BuildTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'char', 'name', 'display_name', 'created_time')
    search_fields = ('name', 'display_name', 'char__name')
    raw_id_fields = ('char',)
