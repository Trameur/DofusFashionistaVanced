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
    deleted = models.BooleanField(default=False)
    allow_points_distribution = models.BooleanField(default=True)

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
    
class ContactForm(forms.Form):
    name = forms.CharField()
    email = forms.EmailField()
    topic = forms.CharField()
    message = forms.CharField(widget=Textarea())

class SolutionCounter(models.Model):
    input_hash = models.BigIntegerField(unique=True)
    get_count = models.IntegerField(default=0)
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