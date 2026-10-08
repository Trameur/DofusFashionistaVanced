# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A resource icon is fetched again when the source it was written from changed."""

import contextlib
import io
import os
import sys
import tempfile
from unittest import mock

from django.test import SimpleTestCase
from PIL import Image, PngImagePlugin

from chardata.tests import itemscraper_module

_MULDO_AMBER = 17864
_OLD_URL = 'https://api.dofusdu.de/dofus3/v1/img/item/164094-64.png'
_NEW_URL = 'https://api.dofusdu.de/dofus3/v1/img/item/50005-64.png'
_OLD_COLOUR = (30, 200, 30, 255)
_NEW_COLOUR = (200, 30, 30, 255)


def _png(colour):
    buffer = io.BytesIO()
    Image.new('RGBA', (64, 64), colour).save(buffer, 'PNG')
    return buffer.getvalue()


class _Source:
    """A fetch that answers from a table and remembers what it was asked."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def __call__(self, url):
        self.asked.append(url)
        return self.answers.get(url, (404, b''))


class AChangedIconIsDownloadedAgainTests(SimpleTestCase):

    def setUp(self):
        self.module = itemscraper_module('download_resource_icons')
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = folder.name
        self.targets = [os.path.join(self.root, 'static'), os.path.join(self.root, 'staticfiles')]
        for target in self.targets:
            os.makedirs(target)
        self.record = os.path.join(self.root, 'record', 'resource_icon_sources.json')

    def _paths(self):
        return [os.path.join(target, '%d-60-60.png' % _MULDO_AMBER) for target in self.targets]

    def _store(self, colour, pnginfo=None):
        picture = self.module.icon_picture(_png(colour))
        for path in self._paths():
            picture.save(path, pnginfo=pnginfo)

    def _colours(self):
        out = []
        for path in self._paths():
            with Image.open(path) as picture:
                out.append(picture.convert('RGBA').getpixel((30, 30)))
        return out

    def _sync(self, url, recorded, source, keys=None):
        return self.module.sync_icons({_MULDO_AMBER}, {_MULDO_AMBER: url}, self.targets,
                                      recorded, source, keys=keys)

    def _command(self, source, version='dofus3', **found):
        argv = ['download_resource_icons.py', '--game-version', version]
        with contextlib.ExitStack() as stack:
            for name, value in dict(found, target_dirs=self.targets, http_fetch=source).items():
                stack.enter_context(mock.patch.object(self.module, name, return_value=value))
            stack.enter_context(mock.patch.dict(self.module.SOURCE_RECORDS, {version: self.record}))
            stack.enter_context(mock.patch.object(sys, 'argv', argv))
            stack.enter_context(mock.patch('builtins.print'))
            self.module.main()

    def test_a_changed_icon_is_downloaded_again(self):
        self._store(_OLD_COLOUR)
        self.module.write_sources(self.record, {_MULDO_AMBER: _OLD_URL})
        source = _Source({_NEW_URL: (200, _png(_NEW_COLOUR))})
        counts, record = self._sync(_NEW_URL, self.module.read_sources(self.record), source)
        self.assertEqual([_NEW_URL], source.asked)
        self.assertEqual(1, counts['written'])
        self.assertEqual([_NEW_COLOUR, _NEW_COLOUR], self._colours())
        self.module.write_sources(self.record, record)
        self.assertEqual({_MULDO_AMBER: _NEW_URL}, self.module.read_sources(self.record))

    def test_an_icon_from_the_recorded_source_is_not_fetched(self):
        self._store(_OLD_COLOUR)
        source = _Source({})
        counts, record = self._sync(_OLD_URL, {_MULDO_AMBER: _OLD_URL}, source)
        self.assertEqual([], source.asked)
        self.assertEqual(1, counts['kept'])
        self.assertEqual({_MULDO_AMBER: _OLD_URL}, record)

    def test_a_missing_copy_is_fetched_even_from_the_recorded_source(self):
        self._store(_NEW_COLOUR)
        os.remove(self._paths()[1])
        source = _Source({_NEW_URL: (200, _png(_NEW_COLOUR))})
        counts, _ = self._sync(_NEW_URL, {_MULDO_AMBER: _NEW_URL}, source)
        self.assertEqual([_NEW_URL], source.asked)
        self.assertEqual([_NEW_COLOUR, _NEW_COLOUR], self._colours())

    def test_an_unrecorded_icon_with_the_same_picture_is_left_as_it_was(self):
        note = PngImagePlugin.PngInfo()
        note.add_text('Comment', 'saved another way')
        self._store(_NEW_COLOUR, pnginfo=note)
        before = [open(path, 'rb').read() for path in self._paths()]
        source = _Source({_NEW_URL: (200, _png(_NEW_COLOUR))})
        counts, record = self._sync(_NEW_URL, {}, source)
        self.assertEqual(1, counts['same'])
        self.assertEqual(before, [open(path, 'rb').read() for path in self._paths()])
        self.assertEqual({_MULDO_AMBER: _NEW_URL}, record)

    def test_an_icon_absent_at_its_new_source_keeps_its_file_and_its_record(self):
        self._store(_OLD_COLOUR)
        source = _Source({})
        counts, record = self._sync(_NEW_URL, {_MULDO_AMBER: _OLD_URL}, source)
        self.assertEqual(1, counts['absent'])
        self.assertEqual([_OLD_COLOUR, _OLD_COLOUR], self._colours())
        self.assertEqual({_MULDO_AMBER: _OLD_URL}, record)

    def test_a_new_touch_assets_version_alone_does_not_fetch_again(self):
        self._store(_OLD_COLOUR)
        path = self.module.TOUCH_ICON_PATH % 50005
        source = _Source({})
        counts, record = self._sync('https://cdn.test/assets/next/' + path, {_MULDO_AMBER: path},
                                    source, keys={_MULDO_AMBER: path})
        self.assertEqual([], source.asked)
        self.assertEqual({_MULDO_AMBER: path}, record)

    def test_the_command_replaces_the_stale_icon_and_records_its_source(self):
        self._store(_OLD_COLOUR)
        self.module.write_sources(self.record, {_MULDO_AMBER: _OLD_URL})
        source = _Source({_NEW_URL: (200, _png(_NEW_COLOUR))})
        self._command(source, ingredient_ids={_MULDO_AMBER}, icon_urls={_MULDO_AMBER: _NEW_URL})
        self.assertEqual([_NEW_URL], source.asked)
        self.assertEqual([_NEW_COLOUR, _NEW_COLOUR], self._colours())
        self.assertEqual({_MULDO_AMBER: _NEW_URL}, self.module.read_sources(self.record))

    def test_the_touch_command_keeps_an_icon_whose_path_did_not_change(self):
        self._store(_OLD_COLOUR)
        path = self.module.TOUCH_ICON_PATH % 50005
        self.module.write_sources(self.record, {_MULDO_AMBER: path})
        source = _Source({})
        self._command(source, 'touch', ingredient_ids={_MULDO_AMBER},
                      touch_icon_paths={_MULDO_AMBER: path},
                      touch_assets_url='https://cdn.test/assets/next')
        self.assertEqual([], source.asked)
        self.assertEqual({_MULDO_AMBER: path}, self.module.read_sources(self.record))

    def test_an_icon_left_out_of_a_run_keeps_its_recorded_source(self):
        source = _Source({})
        _counts, record = self.module.sync_icons(set(), {}, self.targets,
                                                 {_MULDO_AMBER: _OLD_URL}, source)
        self.assertEqual([], source.asked)
        self.assertEqual({_MULDO_AMBER: _OLD_URL}, record)

    def test_a_run_without_any_icon_url_keeps_the_recorded_sources(self):
        self._store(_OLD_COLOUR)
        self.module.write_sources(self.record, {_MULDO_AMBER: _OLD_URL})
        source = _Source({})
        self._command(source, ingredient_ids={_MULDO_AMBER}, icon_urls={})
        self.assertEqual([], source.asked)
        self.assertEqual({_MULDO_AMBER: _OLD_URL}, self.module.read_sources(self.record))
