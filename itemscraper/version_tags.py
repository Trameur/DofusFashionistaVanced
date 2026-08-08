#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ordering of the raw datacenter tags under itemscraper/raw.

Sorting the directory names as text picks 3.6.8.8 over 3.6.10.10, because "8"
comes after "1". Nothing went wrong while every build was 3.6.x with x under
ten; the day 3.6.10.10 landed, every script that took sorted(tags)[-1] started
reading the previous build instead.
"""
import os


def version_key(tag):
    parts = []
    for chunk in str(tag).split('.'):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def latest_tag(raw_root):
    tags = [name for name in os.listdir(raw_root)
            if os.path.isdir(os.path.join(raw_root, name))]
    if not tags:
        raise SystemExit('no datacenter dump under %s' % raw_root)
    return max(tags, key=version_key)
