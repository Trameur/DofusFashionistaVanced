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
    # 0 male, 1 female, only used to pick the body and head of the preview.
    gender = models.IntegerField(default=0)
    # Six hex triplets for the preview, comma separated (41 chars). Empty means
    # the default palette.
    colors = models.CharField(max_length=48, blank=True, default='')
    # Slots the preview leaves off, comma separated, e.g. "hat,cloak".
    hidden_parts = models.CharField(max_length=60, blank=True, default='')
    game_version = models.CharField(
        max_length=20,
        default='dofus3',
        db_index=True,
    )

    class Meta:
        # The shared-builds page filters on these three and orders by date.
        # game_version alone is not selective: nearly every row is dofus3.
        indexes = [
            models.Index(fields=['game_version', 'link_shared', 'deleted',
                                 '-created_time'],
                         name='char_shared_browse'),
        ]

    def save(self, *args, **kwargs):
        # MySQL strict mode rejects over-long values.
        for field_name in ('name', 'char_name', 'char_build'):
            value = getattr(self, field_name, None)
            if value:
                limit = self._meta.get_field(field_name).max_length
                if len(value) > limit:
                    setattr(self, field_name, value[:limit])
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
    # Last language the user explicitly picked; notification emails use it.
    language = models.CharField(max_length=10, null=True, blank=True)
    # How big the character preview is drawn, in percent of the normal size.
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
    """Comments left by users on shared builds, soft-deleted via `deleted`."""
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
    """Free-form tags the build owner attaches to a Char ("Klime", "PvP arena").
    `name` is lowercased and trimmed, `display_name` keeps the original."""
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
    """Recent generated solutions for a character, per game version: item ids
    and calculations are not shared across versions."""
    char = models.ForeignKey(Char, on_delete=models.CASCADE,
                             related_name='solution_generations')
    game_version = models.CharField(max_length=20, default='dofus3', db_index=True)
    minimal_solution = models.BinaryField()
    created_time = models.DateTimeField(auto_now_add=True)

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
    """A single item the user wants to craft, per game version. Adding the same
    item again bumps quantity."""
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
    """A named group of items the user owns ("Imagiro", "Bank alt"), per game
    version. The solver can be restricted to one folder."""
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
    """One physical item the user owns, in a folder; the same item can appear
    several times with different rolls. custom_stats is a JSON
    {stat_key: value} map, empty meaning the stats the encyclopedia lists."""
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
    """Player-submitted report on a comment. Three distinct reporters auto-mark
    the comment deleted (chardata.comment_view.report_comment)."""

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
    # Game version the solve ran under, for per-version stats.
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
    """One row per page and per day; ids in the path are folded into a
    placeholder."""
    day = models.DateField(db_index=True)
    path = models.CharField(max_length=200)
    game_version = models.CharField(max_length=20, default='dofus3')
    count = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('day', 'path', 'game_version')


class SiteSetting(models.Model):
    """Settings the owner changes from the admin page; gen_config.json is only
    read at boot."""
    key = models.CharField(max_length=60, unique=True)
    value = models.TextField(blank=True)


class RateCounter(models.Model):
    """How many times something happened inside a window, shared by every worker.

    The failed-login and reset-mail limits used to count in the cache, which is
    local memory here: a pool of four workers held four separate counters, so the
    real ceiling was four times what the code says, and a restart forgot the lot.
    A row per key is small, exact and survives a reload.
    """
    key = models.CharField(max_length=190, unique=True)
    window_start = models.DateTimeField()
    count = models.IntegerField(default=0)

    def __str__(self):
        return '%s x%d' % (self.key, self.count)

# Signal wiring (models.py is the one chardata module Django always imports).
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import translation as _translation


class VisitSource(models.Model):
    """Where a reader came from, counted per day. No ip, no cookie, no id.

    The site knows how many people come and not one thing about how they got
    here: 77% of its search clicks are people typing its own name, which means
    the growth question is not "does Google rank us" but "who ever hears of
    us". Answering that needs the referrer, and nothing else -- so nothing else
    is stored.

    Rows are aggregated by day the way PageHit is, so the table stays small and
    holds no trace of an individual. Storing no identifier and no address is
    also what keeps this out of consent-banner territory: these are anonymous
    statistics kept for the site's own operator alone.

    Only ARRIVALS are counted -- a request whose referrer is absent or on
    another host. Clicking from one page of the site to the next is not a
    provenance, and counting it would drown the signal.
    """
    day = models.DateField(db_index=True)
    #: 'google', 'youtube.com', 'discord', or whatever utm_source was given.
    source = models.CharField(max_length=100)
    #: 'organic', 'referral', 'none' for a bare arrival, or utm_medium.
    medium = models.CharField(max_length=40)
    campaign = models.CharField(max_length=60, blank=True)
    language = models.CharField(max_length=10, blank=True)
    #: Cloudflare's CF-IPCountry when it is in front; blank otherwise.
    country = models.CharField(max_length=2, blank=True)
    count = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('day', 'source', 'medium', 'campaign', 'language',
                           'country')

    def __str__(self):
        return '%s %s/%s %s' % (self.day, self.source, self.medium, self.count)


class SupportClick(models.Model):
    """How many readers asked how to support the site, per day and language.

    The one number nobody has: what share of an audience would pay. Traffic is
    already known and worth less than half a cent a visit, so measuring more of
    it teaches nothing. This measures intent instead, and it is what decides
    whether the hours it would take to court content creators are worth
    spending at all.

    A click, not a payment: the page it leads to takes no money and promises no
    price. Counted per day like everything else here, with no visitor attached.
    """
    day = models.DateField(db_index=True)
    language = models.CharField(max_length=10, blank=True)
    #: Which page the reader was on. The whole question is whether asking at
    #: the moment the tool just did its work beats asking on a page nobody
    #: visits, and that cannot be answered by one undifferentiated total.
    source = models.CharField(max_length=20, default='support')
    count = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('day', 'language', 'source')

    def __str__(self):
        return '%s %s %s' % (self.day, self.language, self.count)


class ItemPopularity(models.Model):
    """How often an item is actually worn, across every build ever calculated.

    The named builds on an item page can only ever be the public ones, 1 980
    of them. This counts all 142 043, which is what makes the number worth
    printing: it is the one thing this site knows and Ankama, DofusDB and the
    wikis do not, since they all publish the same numbers from the same game
    files and none of them sees what people put on.

    Nothing identifying is stored, not the owner, not the build: only how many
    wore it. `eligible` is the number of builds that could have worn it at all,
    meaning those at or above its level. Dividing by every build instead would
    make a level 20 item look unpopular for the sole reason that most builds
    are level 200.
    """
    ankama_id = models.IntegerField()
    game_version = models.CharField(max_length=20, default='dofus3')
    builds = models.IntegerField(default=0)
    eligible = models.IntegerField(default=0)

    class Meta:
        unique_together = ('ankama_id', 'game_version')

    @property
    def share(self):
        """Percentage of the builds that could wear it and did, or None.

        None rather than zero when nothing is comparable: a share computed on
        a handful of builds says nothing, and printing 0 percent would read as
        a fact rather than as an absence of one.
        """
        if not self.eligible or self.eligible < 30:
            return None
        return 100.0 * self.builds / self.eligible

    def __str__(self):
        return '%s %s: %s/%s' % (self.game_version, self.ankama_id,
                                 self.builds, self.eligible)


class ItemInSharedBuild(models.Model):
    """Which shared builds wear a given item.

    The encyclopedia has promised "Discover builds using X" in its meta
    description on every item page since it existed, and no page has ever
    carried a single one. This is the index that makes the promise true.

    It also answers the one thing the encyclopedia could never answer better
    than Ankama or a wiki: they all publish the same numbers, taken from the
    same game files, and none of them knows what people actually wear. That
    knowledge exists here and nowhere else.

    Derived data, rebuilt from the builds themselves by reindex_builds_by_item,
    so it is never the source of truth and can be thrown away at any time. The
    whole rebuild reads 3 361 shared builds in about 12 seconds.
    """
    ankama_id = models.IntegerField()
    game_version = models.CharField(max_length=20, default='dofus3')
    char = models.ForeignKey(Char, on_delete=models.CASCADE)

    class Meta:
        # The lookup is always (ankama_id, game_version), which this covers as
        # a prefix, so it needs no index of its own.
        unique_together = ('ankama_id', 'game_version', 'char')

    def __str__(self):
        return '%s %s -> %s' % (self.game_version, self.ankama_id, self.char_id)


@receiver(user_logged_in)
def _remember_language_on_login(sender, request, user, **kwargs):
    """Backfill the notification-email language; an explicit choice is never
    overwritten."""
    try:
        alias, _created = UserAlias.objects.get_or_create(user=user)
        if not alias.language:
            alias.language = _translation.get_language() or 'en'
            alias.save(update_fields=['language'])
    except Exception:
        pass
