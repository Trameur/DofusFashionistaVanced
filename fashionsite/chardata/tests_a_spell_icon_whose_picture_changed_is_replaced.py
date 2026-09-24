# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import importlib.util
import io
import os
import sys
import tarfile
import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from PIL import Image, PngImagePlugin

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'download_spell_images.py')


def _load():
    spec = importlib.util.spec_from_file_location('download_spell_images', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _png(colour, note=None, hidden=(0, 0, 0)):
    image = Image.new('RGBA', (4, 4), colour)
    image.putpixel((0, 0), hidden + (0,))
    info = None
    if note:
        info = PngImagePlugin.PngInfo()
        info.add_text('Comment', note)
    buffer = io.BytesIO()
    image.save(buffer, 'PNG', pnginfo=info)
    return buffer.getvalue()


class ASpellIconWhosePictureChangedIsReplacedTests(SimpleTestCase):

    def setUp(self):
        self.module = _load()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / 'source'
        self.static = self.root / 'static'
        self.source.mkdir()
        self.static.mkdir()

    def _copy(self, name, source_bytes, static_bytes=None):
        (self.source / '7.png').write_bytes(source_bytes)
        if static_bytes is not None:
            (self.static / name).write_bytes(static_bytes)
        record = self.module.SpellIconRecord(ankama_id=1, icon_id=7,
                                             english_name=name[:-4],
                                             filename_stem=name[:-4])
        stats, _ = self.module.copy_spell_icons(
            self.source, [self.static], [(record, name)], overwrite=False)
        return stats, (self.static / name).read_bytes()

    def test_an_icon_the_game_redrew_is_replaced(self):
        new = _png((200, 30, 30, 255))
        stats, on_disk = self._copy('Collapse.png', new, _png((30, 200, 30, 255)))
        self.assertEqual(new, on_disk)
        self.assertEqual(1, stats.written)

    def test_the_same_picture_saved_another_way_is_left_alone(self):
        old = _png((200, 30, 30, 255), note='optimised', hidden=(9, 9, 9))
        stats, on_disk = self._copy('Collapse.png', _png((200, 30, 30, 255)), old)
        self.assertEqual(old, on_disk)
        self.assertEqual(1, stats.skipped_existing)

    def test_a_missing_icon_is_written(self):
        new = _png((1, 2, 3, 255))
        _, on_disk = self._copy('Wandering (14604).png', new)
        self.assertEqual(new, on_disk)

    def test_an_unreadable_icon_is_replaced(self):
        new = _png((1, 2, 3, 255))
        _, on_disk = self._copy('Leap.png', new, b'not a picture')
        self.assertEqual(new, on_disk)

    def test_the_extraction_cache_follows_the_archive(self):
        raw = self.root / 'raw'
        raw.mkdir()
        new = _png((10, 20, 30, 255))
        with tarfile.open(raw / 'spell_images_96.tar.gz', 'w:gz') as archive:
            member = tarfile.TarInfo('sort_7-96.png')
            member.size = len(new)
            archive.addfile(member, io.BytesIO(new))
        cache = self.root / 'cache'
        (cache / '96').mkdir(parents=True)
        (cache / '96' / '7.png').write_bytes(_png((90, 90, 90, 255)))
        written, skipped = self.module.extract_spell_images(raw, '96', cache, False)
        self.assertEqual((1, 0), (written, skipped))
        self.assertEqual(new, (cache / '96' / '7.png').read_bytes())
        self.assertEqual((0, 1), self.module.extract_spell_images(raw, '96', cache, False))
