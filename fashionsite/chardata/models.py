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
    view_count = models.IntegerField(default=0)
    options = models.BinaryField()
    inclusions = models.BinaryField()
    exclusions = models.BinaryField()
    aspects = models.BinaryField(default=b'')
    empty_slots = models.BinaryField(default=b'')
    stat_overrides = models.BinaryField(default=b'')
    deleted = models.BooleanField(default=False)
    allow_points_distribution = models.BooleanField(default=True)
    game_version = models.CharField(
        max_length=20,
        default='dofus3',
        db_index=True,
    )

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
    # Last language the user explicitly picked; notification emails use it.
    language = models.CharField(max_length=10, null=True, blank=True)

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
    """Comments left by users on shared builds. Soft-deleted via `deleted` flag
    (same pattern as Char.deleted) so moderation history stays intact."""
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
    """Free-form tags that the build owner attaches to a Char to help
    classification ("Klime", "PvP arena", "Frigost dungeons"). Stored
    lowercased + trimmed so case-insensitive lookups are cheap; original
    display name is preserved in `display_name`."""
    char = models.ForeignKey(Char, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=40, db_index=True)
    display_name = models.CharField(max_length=40)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('char', 'name')
        indexes = [
            models.Index(fields=['name', 'char']),
        ]


class UserFollow(models.Model):
    """One-way follow relationship — A follows B."""
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
    """A single item the user wants to craft (or remember to acquire).

    Stored per game_version so a Dofus 3 craft list is independent from a
    Dofus 2 one. Quantity defaults to 1 — players who add the same item
    multiple times bump the counter rather than creating duplicates."""
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
    """A named group of items the user owns ("Imagiro", "Bank alt", ...).

    Scoped to a game version so a server folder never mixes items across
    versions. Folders double as the unit the solver can be restricted to
    ("only use items from this folder")."""
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
    """One physical item the user owns, in a folder.

    The same item can appear several times (two Gelanos with different
    rolls). custom_stats holds the real rolls as a JSON {stat_key: value}
    map when known (e.g. saved from the smithmagic page or from a solution's
    stat editor); empty means "stats as listed in the encyclopedia"."""
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
    """Player-submitted report on a comment. unique_together prevents a single
    user from spamming reports on the same comment. When 3 distinct users have
    reported one comment the view will auto-mark it deleted pending admin
    review (see chardata.comment_view.report_comment)."""

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
    # Game version the solve ran under, for per-version stats. Set when the row
    # is first created; rows from before this field existed default to 'dofus3'.
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

# Signal wiring (models.py is the one chardata module Django always imports).
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import translation as _translation


@receiver(user_logged_in)
def _remember_language_on_login(sender, request, user, **kwargs):
    """Backfill the notification-email language for accounts that never used
    the language selector. An explicit choice is never overwritten."""
    try:
        alias, _created = UserAlias.objects.get_or_create(user=user)
        if not alias.language:
            alias.language = _translation.get_language() or 'en'
            alias.save(update_fields=['language'])
    except Exception:
        # A profile hiccup must never break the login itself.
        pass
