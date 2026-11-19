from types import SimpleNamespace

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

from chardata.home_view import _featured_avatar
from chardata.solution_view import get_class_avatar
from fashionistapulp.dofus_constants import CHARACTER_CLASSES


class EveryClassHasSixAvatarsOnDiskTests(SimpleTestCase):
    """Every class the site offers gets an avatar that exists, on the build page and the home page."""

    def _file(self, url):
        return finders.find(url.split('/static/')[-1].split('?')[0])

    def test_every_class_names_six_avatar_files_that_exist(self):
        for char_class in CHARACTER_CLASSES:
            for avatar in (get_class_avatar, _featured_avatar):
                urls = {avatar(SimpleNamespace(char_class=char_class, id=n)) for n in range(6)}
                with self.subTest(char_class=char_class, avatar=avatar.__name__):
                    self.assertEqual(len(urls), 6, urls)
                    for url in urls:
                        self.assertNotIn('QuestionMark', url)
                        self.assertIsNotNone(self._file(url), '%s is not on disk' % url)
        self.assertGreaterEqual(len(CHARACTER_CLASSES), 19)
