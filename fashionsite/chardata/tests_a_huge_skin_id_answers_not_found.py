"""An oversized digit id on a character route is a 404, never a server error."""
from django.test import SimpleTestCase, TestCase

from chardata.character_assets import ensure_skin


class AnOversizedSkinId(TestCase):

    def test_a_65_digit_manifest_id_answers_404(self):
        response = self.client.get('/character/parts/%s/parts.json' % ('1' * 65))
        self.assertEqual(404, response.status_code)

    def test_a_65_digit_atlas_id_answers_404(self):
        response = self.client.get('/character/parts/%s/atlas.webp' % ('1' * 65))
        self.assertEqual(404, response.status_code)

    def test_an_id_too_long_for_int_to_read_answers_404(self):
        response = self.client.get('/character/parts/%s/parts.json' % ('1' * 4400))
        self.assertEqual(404, response.status_code)


class EnsureSkinRefusesWhatIsNotAPathComponent(SimpleTestCase):

    def test_an_id_longer_than_a_safe_id_is_none(self):
        self.assertIsNone(ensure_skin('1' * 65))

    def test_text_is_none(self):
        self.assertIsNone(ensure_skin('../x'))
