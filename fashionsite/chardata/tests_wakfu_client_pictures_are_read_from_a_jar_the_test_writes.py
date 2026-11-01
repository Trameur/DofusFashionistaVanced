import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase
from PIL import Image

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import get_wakfu_images  # noqa: E402

PREFIX = 'jar:file:./contents/gui_jar/gui.jar!/'
TEMPLATES = {
    'itemsIconsPath': 'icons/items/64/%d.tga',
    'spellsIconsPath': 'icons/spells/64/%d.tga',
    'statesIconsPath': 'icons/states/%s.tga',
    'aptitudeIconsPath': 'icons/aptitudes/%d.tga',
    'monsterIllustrationPath': 'icons/monsterIllustrations/%d.tga',
    'monstersFamily': 'icons/monstersFamily/%d.tga',
    'breedSmallIconPath': 'breeds/icons/small/%s.tga',
    'breedCharacterPortrait80Path': 'breeds/illustrations/portrait80/%s.tga',
    'defaultIconPath': 'icons/default64.tga',
    'defaultMonsterIllustrationPath': 'icons/monsterIllustrations/default.tga',
}
RED, BLUE = (200, 10, 10, 255), (10, 10, 200, 255)

TABLES = (
    'CREATE TABLE client_pictures (family TEXT NOT NULL, id INTEGER NOT NULL,'
    ' picture TEXT NOT NULL, PRIMARY KEY (family, id))',
    'CREATE TABLE items (id INTEGER)',
    'CREATE TABLE pets (item INTEGER)',
    'CREATE TABLE mounts (item INTEGER)',
    'CREATE TABLE effects (container INTEGER, container_type TEXT)',
    'CREATE TABLE item_recipes (item INTEGER, ingredient_ankama_id INTEGER)',
    'CREATE TABLE monster_drops (item INTEGER)',
    'CREATE TABLE loot_list_rows (item INTEGER)',
)
PICTURES = (
    ('item', 1, '500'), ('item', 2, '600'), ('item', 3, '700'), ('item', 4, '9999'),
    ('spell', 10, '7'), ('spell', 11, '7'), ('spell', 12, '99'),
    ('state', 21, 'malus_portee'),
    ('ability', 1, '3'),
    ('monster', 5, '143604168'), ('monster_family', 68, '68'),
    ('class', 10, '10'),
)


def tga(size, pixel, transparent_corner=False):
    image = Image.new('RGBA', size, pixel)
    if transparent_corner:
        image.paste((0, 0, 0, 0), (0, 0, 16, 16))
    out = io.BytesIO()
    image.save(out, 'TGA')
    return out.getvalue()


RARITY_MEMBER = 'theme/images/itemsRarityBorders/old.tga'


def members(items_member='icons/items/64/%d.tga', color=RED):
    return {
        items_member % 500: tga((80, 80), color, True),
        items_member % 700: tga((64, 64), color),
        'icons/spells/64/7.tga': tga((64, 64), RED),
        'icons/states/malus_portee.tga': tga((64, 64), RED),
        'icons/aptitudes/3.tga': tga((22, 22), RED),
        'icons/monsterIllustrations/143604168.tga': tga((132, 41), RED),
        'icons/monstersFamily/68.tga': tga((32, 32), RED),
        'breeds/icons/small/10.tga': tga((146, 168), RED),
        'breeds/illustrations/portrait80/100.tga': tga((80, 80), RED),
        'breeds/illustrations/portrait80/101.tga': tga((80, 80), BLUE),
        'icons/default64.tga': tga((64, 64), BLUE),
        'icons/monsterIllustrations/default.tga': tga((132, 41), BLUE),
    }


class TheWakfuClientPicturesAreReadFromAJarTheTestWritesTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.static = self.root / 'static'
        self.db = self.root / 'items.db'
        conn = sqlite3.connect(str(self.db))
        for statement in TABLES:
            conn.execute(statement)
        conn.executemany('INSERT INTO client_pictures VALUES (?, ?, ?)', PICTURES)
        conn.execute('INSERT INTO items (id) VALUES (1)')
        conn.execute("INSERT INTO effects VALUES (3, 'ITEM_USE')")
        conn.execute("INSERT INTO effects VALUES (2, 'SPELL')")
        conn.commit()
        conn.close()

    def write_client(self, name='6.0_1.2.3.4.5', templates=None, files=None):
        folder = self.root / 'client' / name
        folder.mkdir(parents=True, exist_ok=True)
        merged = {**TEMPLATES, **(templates or {})}
        (folder / 'config.properties').write_text(
            '# the client\n' + ''.join('%s=%s%s\n' % (key, PREFIX, value)
                                       for key, value in merged.items()), encoding='utf-8')
        with zipfile.ZipFile(folder / 'gui.jar', 'w') as jar:
            for member, blob in {**(members() if files is None else files),
                                 RARITY_MEMBER: tga((36, 36), RED, True)}.items():
                jar.writestr(member, blob)
        (folder / 'client_code.json').write_text(
            json.dumps({'rarities': {'COMMON': 0}, 'rarity_files': {'COMMON': 'old'}}),
            encoding='utf-8')
        return folder

    def run_script(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = get_wakfu_images.main(['--client', str(self.root / 'client'),
                                          '--db', str(self.db),
                                          '--static', str(self.static), *extra])
        return code, out.getvalue()

    def size_of(self, relative):
        with Image.open(self.static / relative) as picture:
            return picture.size

    def test_two_spells_that_share_an_icon_produce_one_file(self):
        self.write_client()
        code, text = self.run_script()
        self.assertEqual(0, code, text)
        self.assertEqual(['7.webp', 'default.webp'], sorted(
            path.name for path in (self.static / 'spells' / 'wakfu').iterdir()))
        self.assertRegex(text, r'spells\s+wanted 2 written 1 kept 0 missing 1')

    def test_a_state_file_is_named_by_its_key_and_a_portrait_by_breed_and_sex(self):
        self.write_client()
        self.run_script()
        self.assertTrue((self.static / 'states' / 'wakfu' / 'malus_portee.webp').is_file())
        portraits = self.static / 'classes' / 'wakfu' / 'portrait80'
        self.assertEqual(['100.webp', '101.webp', 'default.webp'],
                         sorted(path.name for path in portraits.iterdir()))
        self.assertTrue((self.static / 'classes' / 'wakfu' / 'icons' / '10.webp').is_file())

    def test_a_large_picture_is_downscaled_and_a_small_one_is_kept(self):
        self.write_client()
        self.run_script()
        self.assertEqual((64, 64), self.size_of('items/wakfu/64/500.webp'))
        self.assertEqual((22, 22), self.size_of('abilities/wakfu/3.webp'))
        self.assertEqual((132, 41), self.size_of('monsters/wakfu/143604168.webp'))
        self.assertEqual((32, 32), self.size_of('monsters/wakfu/families/68.webp'))
        width, height = self.size_of('classes/wakfu/icons/10.webp')
        self.assertEqual(64, height)
        self.assertLess(width, 64)

    def test_a_transparent_pixel_stays_transparent(self):
        self.write_client()
        self.run_script()
        with Image.open(self.static / 'items' / 'wakfu' / '64' / '500.webp') as picture:
            self.assertEqual(0, picture.convert('RGBA').getpixel((0, 0))[3])
            self.assertEqual(255, picture.convert('RGBA').getpixel((32, 32))[3])

    def test_an_existing_file_is_left_byte_for_byte_unless_forced(self):
        self.write_client()
        kept = self.static / 'spells' / 'wakfu' / '7.webp'
        kept.parent.mkdir(parents=True)
        kept.write_bytes(b'not a picture')
        code, text = self.run_script()
        self.assertEqual(0, code, text)
        self.assertEqual(b'not a picture', kept.read_bytes())
        self.assertRegex(text, r'spells\s+wanted 2 written 0 kept 1 missing 1')
        self.run_script('--force')
        self.assertNotEqual(b'not a picture', kept.read_bytes())

    def test_a_missing_picture_is_counted_and_named_and_the_default_is_written(self):
        self.write_client()
        code, text = self.run_script()
        self.assertEqual(0, code, text)
        self.assertIn('missing ids 12', text)
        for folder in ('items/wakfu/64', 'spells/wakfu', 'states/wakfu', 'abilities/wakfu',
                       'classes/wakfu/icons', 'classes/wakfu/portrait80', 'monsters/wakfu',
                       'monsters/wakfu/families'):
            self.assertTrue((self.static / folder / 'default.webp').is_file(), folder)

    def test_only_the_items_the_database_refers_to_are_extracted(self):
        self.write_client()
        self.run_script()
        names = sorted(path.name for path in (self.static / 'items' / 'wakfu' / '64').iterdir())
        self.assertEqual(['500.webp', '700.webp', 'default.webp'], names)

    def test_a_template_changed_in_the_config_changes_the_member_that_is_read(self):
        self.write_client()
        self.run_script()
        with Image.open(self.static / 'items' / 'wakfu' / '64' / '500.webp') as picture:
            self.assertGreater(picture.convert('RGBA').getpixel((32, 32))[0], 150)
        self.write_client(templates={'itemsIconsPath': 'icons/items/big/%d.tga'},
                    files=members('icons/items/big/%d.tga', BLUE))
        self.run_script('--force')
        with Image.open(self.static / 'items' / 'wakfu' / '64' / '500.webp') as picture:
            self.assertGreater(picture.convert('RGBA').getpixel((32, 32))[2], 150)

    def test_the_newest_client_folder_is_the_one_read(self):
        self.write_client('6.0_1.99.0.1.1', files={})
        self.write_client('6.0_1.100.0.1.1')
        code, text = self.run_script()
        self.assertEqual(0, code, text)
        self.assertIn('client 6.0_1.100.0.1.1', text)

    def test_a_missing_archive_or_config_exits_one(self):
        code, _text = self.run_script()
        self.assertEqual(1, code)
        folder = self.write_client()
        (folder / 'config.properties').unlink()
        code, text = self.run_script()
        self.assertEqual(1, code, text)

    def test_a_config_without_a_key_it_needs_exits_one(self):
        folder = self.write_client()
        lines = (folder / 'config.properties').read_text(encoding='utf-8').splitlines()
        (folder / 'config.properties').write_text(
            '\n'.join(line for line in lines if not line.startswith('statesIconsPath')),
            encoding='utf-8')
        code, text = self.run_script()
        self.assertEqual(1, code)
        self.assertIn('statesIconsPath', text)

    def test_a_family_with_no_file_at_all_exits_one(self):
        files = members()
        del files['icons/states/malus_portee.tga']
        self.write_client(files=files)
        code, text = self.run_script()
        self.assertEqual(1, code, text)
        self.assertIn('no file at all for states', text)
