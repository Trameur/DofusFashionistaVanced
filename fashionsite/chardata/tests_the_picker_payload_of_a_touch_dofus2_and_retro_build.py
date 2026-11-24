# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A posted grade on a Touch, Dofus 2 or Retro build answers with the target, the raw total, the notes and no flat, critical or pushback line."""
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import translation

from chardata.targets import _monster_index
from chardata.tests_the_target_picker_belongs_to_the_versions_with_targets import _make_build, _prefix

RETRO_NOTE = ('On Dofus Retro, a roll is a sum of dice; against the target, '
              'every value between its two ends counts as equally likely.')


class ThePickerPayloadTests(TestCase):

    def _answer(self, version, token, language='en'):
        owner = User.objects.create_user(
            'payload%d' % User.objects.count(), 'pl@test.local', 'pw-42-solid')
        build = _make_build(owner, version, 'payload')
        self.client.force_login(owner)
        lang = '' if language == 'en' else '/' + language
        response = self.client.post('%s%s/best_combo/%d/' % (lang, _prefix(version), build.pk),
                                    {'target': token, 'pushback': 'false'})
        self.assertEqual(200, response.status_code)
        return json.loads(response.content)

    def _token(self, version):
        monster_id, _names, grades = _monster_index(version)[0][0]
        return 'm%d.%d' % (monster_id, grades[0][0])

    def test_a_grade_on_each_percent_only_version_answers_with_its_target_and_the_raw_total(self):
        for version in ('dofus2', 'touch', 'retro'):
            token = self._token(version)
            payload = self._answer(version, token)
            combo = payload['best_combo']
            with self.subTest(version=version):
                self.assertNotIn('target_refused', payload)
                self.assertEqual(token, combo['target']['token'])
                self.assertIn('raw_total', combo)
                self.assertTrue(combo['target']['name'])
                self.assertIn('hp_share', combo['target'])

    def test_a_grade_on_these_versions_reports_no_missing_flat_critical_or_pushback_value(self):
        for version in ('dofus2', 'touch', 'retro'):
            combo = self._answer(version, self._token(version))['best_combo']
            notes = ' '.join(combo['not_counted'])
            with self.subTest(version=version):
                self.assertNotIn('Not counted yet', notes)
                self.assertIn('Summons are not counted', notes)

    def test_the_uniform_roll_note_is_on_retro_alone_and_in_every_language(self):
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                expected = translation.gettext(RETRO_NOTE)
            for version, present in (('retro', True), ('touch', False), ('dofus2', False)):
                notes = self._answer(version, self._token(version), language)[
                    'best_combo']['not_counted']
                with self.subTest(language=language, version=version):
                    self.assertEqual(present, expected in notes)
            if language != 'en':
                self.assertNotEqual(RETRO_NOTE, expected)
