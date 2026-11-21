# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The build page marks every date-time so the browser can show it in the player's time zone."""

import re
from datetime import datetime, timezone as dt_timezone

from django.test import TestCase

from chardata.tests_the_solution_best_turn_card_gets_its_casts import TheBestTurnCardTests


class TheBuildPageTimeTests(TestCase):

    setUp = TheBestTurnCardTests.setUp
    _response = TheBestTurnCardTests._response

    def _solved_page(self):
        from chardata.char_blobs import read_char_blob
        from chardata.models import Char, SolutionGeneration
        from chardata.solution_history import record_solution_generation
        self._response()
        solved = datetime(2026, 11, 21, 1, 43, 5, tzinfo=dt_timezone.utc)
        Char.objects.filter(pk=self.char.pk).update(solved_time=solved)
        self.char.refresh_from_db()
        generation = record_solution_generation(
            self.char, read_char_blob(self.char.minimal_solution, None, 'minimal_solution', self.char))
        self.assertIsNotNone(generation)
        saved = datetime(2026, 11, 20, 23, 15, 0, tzinfo=dt_timezone.utc)
        SolutionGeneration.objects.filter(pk=generation.pk).update(created_time=saved)
        generation.refresh_from_db()
        self.solved = solved
        self.generation = generation
        return self.client.get('/solution/%d/' % self.char.id, follow=True)

    def _time_tags(self, html):
        tags = []
        for attributes, text in re.findall(r'<time(\s[^>]*)>([^<]*)</time>', html):
            if 'data-fm-local-time' in attributes:
                value = re.search(r'datetime="([^"]*)"', attributes)
                tags.append((value.group(1) if value else '', text))
        return tags

    def test_the_header_and_the_history_dates_sit_in_marked_time_elements(self):
        html = self._solved_page().content.decode('utf-8')
        values = [value for value, text in self._time_tags(html)]
        self.assertIn(self.solved.isoformat(), values)
        self.assertIn(self.generation.created_time.isoformat(), values)

    def test_the_snapshot_notice_date_sits_in_a_marked_time_element(self):
        response = self._solved_page()
        url = response.context['generation_history'][0]['view_url']
        html = self.client.get(url, follow=True).content.decode('utf-8')
        values = [value for value, text in self._time_tags(html)]
        self.assertIn(self.generation.created_time.isoformat(), values)

    def test_every_marked_time_keeps_its_server_text_for_a_page_without_script(self):
        from django.utils import formats, timezone, translation
        response = self._solved_page()
        tags = dict(self._time_tags(response.content.decode('utf-8')))
        with translation.override(response.wsgi_request.LANGUAGE_CODE):
            for value in (self.solved, self.generation.created_time):
                self.assertEqual(formats.date_format(timezone.localtime(value), 'SHORT_DATETIME_FORMAT'),
                                 tags[value.isoformat()])

    def test_a_comment_date_sits_in_a_marked_time_element_and_so_does_a_new_one(self):
        from chardata.models import BuildComment, Char
        self._response()
        Char.objects.filter(pk=self.char.pk).update(link_shared=True)
        comment = BuildComment.objects.create(user=self.owner, build=self.char, content='Nice build')
        posted = datetime(2026, 11, 21, 0, 5, 0, tzinfo=dt_timezone.utc)
        BuildComment.objects.filter(pk=comment.pk).update(created_time=posted)
        html = self.client.get('/solution/%d/' % self.char.id, follow=True).content.decode('utf-8')
        self.assertIn(posted.isoformat(), [value for value, text in self._time_tags(html)])
        self.assertIn("$('<time>').attr('datetime', comment.created_time).attr('data-fm-local-time', '')", html)
        self.assertIn('window.fmLocalizeTimes($li[0]);', html)

    def test_the_page_loads_the_script_that_converts_them(self):
        from django.contrib.staticfiles import finders
        html = self._solved_page().content.decode('utf-8')
        match = re.search(r'<script src="([^"]*local_time[^"]*\.js)', html)
        self.assertIsNotNone(match)
        path = finders.find('chardata/local_time.js')
        self.assertIsNotNone(path)
        with open(path, encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn('toLocaleString', source)
        self.assertIn('time[data-fm-local-time]', source)
