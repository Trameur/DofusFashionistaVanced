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

from django import forms
from django.contrib.auth.models import User
from django.db import models
from django.forms.widgets import Textarea

from chardata.data_versions import current_data_version


class Char(models.Model):
    owner = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modified_time = models.DateTimeField(auto_now=True, blank=True, null=True)
    name = models.CharField(max_length=50)
    char_name = models.CharField(max_length=50)
    char_class = models.CharField(max_length=20)
    char_build = models.CharField(max_length=50)
    level = models.IntegerField()
    minimum_stats = models.BinaryField()
    minimum_crits = models.BinaryField()
    stats_weight = models.BinaryField()
    minimal_solution = models.BinaryField(default=b'')
    link_shared = models.BooleanField()
    # Publish at the first solution; cleared once the owner touches the switch
    auto_publish = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)
    options = models.BinaryField()
    inclusions = models.BinaryField()
    exclusions = models.BinaryField()
    aspects = models.BinaryField(default=b'')
    empty_slots = models.BinaryField(default=b'')
    stat_overrides = models.BinaryField(default=b'')
    deleted = models.BooleanField(default=False)
    allow_points_distribution = models.BooleanField(default=True)
    # 0 male, 1 female, for the preview
    gender = models.IntegerField(default=0)
    # Six comma separated hex colors for the preview, empty for the default
    colors = models.CharField(max_length=48, blank=True, default='')
    # Slots the preview leaves off, e.g. "hat,cloak"
    hidden_parts = models.CharField(max_length=60, blank=True, default='')
    game_version = models.CharField(
        max_length=20,
        default='dofus3',
        db_index=True,
    )
    # Item data version (SITE_VERSIONS) at creation and at the last solve
    created_version = models.CharField(max_length=20, blank=True, default='')
    solved_version = models.CharField(max_length=20, blank=True, default='')
    solved_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Shared-builds page filter, newest first
        indexes = [
            models.Index(fields=['game_version', 'link_shared', 'deleted',
                                 '-created_time'],
                         name='char_shared_browse'),
        ]

    def save(self, *args, **kwargs):
        # MySQL strict mode rejects over-long values
        for field_name in ('name', 'char_name', 'char_build'):
            value = getattr(self, field_name, None)
            if value:
                limit = self._meta.get_field(field_name).max_length
                if len(value) > limit:
                    setattr(self, field_name, value[:limit])
        if self.pk is None:
            self.created_version = current_data_version(self.game_version)
        super().save(*args, **kwargs)

    def __unicode__(self):
        return self.name

class CharBaseStats(models.Model):
    char = models.ForeignKey(Char, on_delete=models.CASCADE)
    stat = models.CharField(max_length=30)
    total_value = models.IntegerField(default=0)
    scrolled_value = models.IntegerField(default=0)

class UserAlias(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    alias = models.CharField(max_length=50, null=True, blank=True)
    notify_comments = models.BooleanField(default=True)
    # Last language the user picked, for notification emails
    language = models.CharField(max_length=10, null=True, blank=True)
    # Character preview size in percent
    preview_size = models.IntegerField(default=100)

class BuildVote(models.Model):
    """Track user votes (likes/favorites) for shared builds"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    build = models.ForeignKey(Char, on_delete=models.CASCADE)
    vote_type = models.CharField(max_length=10, choices=[('like', 'Like'), ('favorite', 'Favorite')])
    created_time = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'build', 'vote_type')
        indexes = [
            models.Index(fields=['build', 'vote_type']),
            models.Index(fields=['user', 'vote_type']),
        ]

class BuildView(models.Model):
    """Track build views with IP-based rate limiting (1 view per IP per 24h)"""
    build = models.ForeignKey(Char, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['build', 'ip_address', 'viewed_at']),
        ]

class BuildComment(models.Model):
    """Comments on shared builds, soft-deleted via `deleted`."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    build = models.ForeignKey(Char, on_delete=models.CASCADE)
    content = models.TextField(max_length=2000)
    created_time = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['build', 'deleted', 'created_time']),
        ]

class BuildTag(models.Model):
    """Owner tags on a build; `name` is lowercased, `display_name` as typed."""
    char = models.ForeignKey(Char, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=40, db_index=True)
    display_name = models.CharField(max_length=40)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('char', 'name')
        indexes = [
            models.Index(fields=['name', 'char']),
        ]


class SolutionGeneration(models.Model):
    """Recent solutions of a character, per game version."""
    char = models.ForeignKey(Char, on_delete=models.CASCADE,
                             related_name='solution_generations')
    game_version = models.CharField(max_length=20, default='dofus3', db_index=True)
    minimal_solution = models.BinaryField()
    created_time = models.DateTimeField(auto_now_add=True)
    data_version = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        ordering = ['-created_time', '-id']
        indexes = [
            models.Index(fields=['char', 'created_time']),
            models.Index(fields=['char', 'game_version', 'created_time']),
        ]


class UserFollow(models.Model):
    """One-way follow relationship, A follows B."""
    follower = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='following_set')
    followed = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='follower_set')
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'followed')
        indexes = [
            models.Index(fields=['followed', 'created_time']),
            models.Index(fields=['follower', 'created_time']),
        ]


class WorkshopItem(models.Model):
    """Item the user wants to craft, per game version."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_id = models.IntegerField()  # internal id from structure.items_dict
    game_version = models.CharField(max_length=20, default='dofus3')
    quantity = models.IntegerField(default=1)
    added_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'item_id', 'game_version')
        indexes = [
            models.Index(fields=['user', 'game_version', 'added_time']),
        ]


class InventoryFolder(models.Model):
    """Named group of owned items, per game version."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    game_version = models.CharField(max_length=20, default='dofus3')
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name', 'game_version')
        indexes = [
            models.Index(fields=['user', 'game_version', 'name']),
        ]


class InventoryItem(models.Model):
    """Owned item; custom_stats is JSON {stat_key: value}, empty for defaults."""
    folder = models.ForeignKey(InventoryFolder, on_delete=models.CASCADE,
                               related_name='items')
    item_id = models.IntegerField()  # internal id from structure.items_dict
    custom_stats = models.TextField(default='', blank=True)
    added_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['folder', 'added_time']),
        ]


class CommentReport(models.Model):
    """Report on a comment; three reporters auto-delete it."""

    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('harassment', 'Harassment / insult'),
        ('off_topic', 'Off-topic'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.ForeignKey(BuildComment, on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='other')
    created_time = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'comment')
        indexes = [
            models.Index(fields=['comment', 'processed']),
            models.Index(fields=['processed', 'created_time']),
        ]
    
class ContactForm(forms.Form):
    name = forms.CharField()
    email = forms.EmailField()
    topic = forms.CharField()
    message = forms.CharField(widget=Textarea())

class SolutionCounter(models.Model):
    input_hash = models.BigIntegerField(unique=True)
    get_count = models.IntegerField(default=0)
    # Game version the solve ran under
    game_version = models.CharField(max_length=20, default='dofus3', db_index=True)
    created_time = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modified_time = models.DateTimeField(auto_now=True, blank=True, null=True)

class SolutionMemory(models.Model):
    input_hash = models.BigIntegerField(unique=True)
    input = models.BinaryField()
    stored = models.BinaryField()

class ItemDbVersion(models.Model):
    dump_hash = models.CharField(max_length=255)
    created_time = models.DateField(auto_now_add=True, blank=True, null=True)

class SolutionMemoryHits(models.Model):
    count_hit = models.BigIntegerField(default=0)
    count_miss = models.BigIntegerField(default=0)
    day = models.DateField(unique=True)


class PageHit(models.Model):
    """One row per page and day, ids in the path folded into a placeholder."""
    day = models.DateField(db_index=True)
    path = models.CharField(max_length=200)
    game_version = models.CharField(max_length=20, default='dofus3')
    count = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('day', 'path', 'game_version')


class SiteSetting(models.Model):
    """Settings changed from the admin page; gen_config.json is read at boot."""
    key = models.CharField(max_length=60, unique=True)
    value = models.TextField(blank=True)


class RateCounter(models.Model):
    """Count per key and time window, shared by every worker."""
    key = models.CharField(max_length=190, unique=True)
    window_start = models.DateTimeField()
    count = models.IntegerField(default=0)

    def __str__(self):
        return '%s x%d' % (self.key, self.count)

# Signals live here, Django always imports models.py
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import translation as _translation


class VisitSource(models.Model):
    """Arrivals from another host per day and referrer, no visitor stored."""
    day = models.DateField(db_index=True)
    # 'google', 'youtube.com', 'discord', or utm_source
    source = models.CharField(max_length=100)
    # 'organic', 'referral', 'none' for a bare arrival, or utm_medium
    medium = models.CharField(max_length=40)
    campaign = models.CharField(max_length=60, blank=True)
    language = models.CharField(max_length=10, blank=True)
    # Cloudflare's CF-IPCountry, blank without Cloudflare
    country = models.CharField(max_length=2, blank=True)
    count = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('day', 'source', 'medium', 'campaign', 'language',
                           'country')

    def __str__(self):
        return '%s %s/%s %s' % (self.day, self.source, self.medium, self.count)


class SupportClick(models.Model):
    """Clicks on the support link per day, language and page."""
    day = models.DateField(db_index=True)
    language = models.CharField(max_length=10, blank=True)
    # Page the click came from
    source = models.CharField(max_length=20, default='support')
    count = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('day', 'language', 'source')

    def __str__(self):
        return '%s %s %s' % (self.day, self.language, self.count)


class ItemPopularity(models.Model):
    """Builds wearing an item; `eligible` counts builds at or above its level."""
    ankama_id = models.IntegerField()
    game_version = models.CharField(max_length=20, default='dofus3')
    builds = models.IntegerField(default=0)
    eligible = models.IntegerField(default=0)

    class Meta:
        unique_together = ('ankama_id', 'game_version')

    # Below this many wearers the share is noise
    ENOUGH_WEARERS = 30

    @property
    def share(self):
        """Percent of eligible builds wearing it, None if too few or 0.0."""
        if not self.eligible or self.builds < self.ENOUGH_WEARERS:
            return None
        part = 100.0 * self.builds / self.eligible
        return None if round(part, 1) < 0.1 else part

    def __str__(self):
        return '%s %s: %s/%s' % (self.game_version, self.ankama_id,
                                 self.builds, self.eligible)


class ItemInSharedBuild(models.Model):
    """Shared builds wearing an item, rebuilt by reindex_builds_by_item."""
    ankama_id = models.IntegerField()
    game_version = models.CharField(max_length=20, default='dofus3')
    char = models.ForeignKey(Char, on_delete=models.CASCADE)

    class Meta:
        # Also the index for (ankama_id, game_version) lookups
        unique_together = ('ankama_id', 'game_version', 'char')

    def __str__(self):
        return '%s %s -> %s' % (self.game_version, self.ankama_id, self.char_id)


@receiver(user_logged_in)
def _remember_language_on_login(sender, request, user, **kwargs):
    """Backfill the notification language, never over an explicit choice."""
    try:
        alias, _created = UserAlias.objects.get_or_create(user=user)
        if not alias.language:
            alias.language = _translation.get_language() or 'en'
            alias.save(update_fields=['language'])
    except Exception:
        pass
