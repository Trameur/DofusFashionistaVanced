# -*- coding: utf-8 -*-
"""An asset missing from the S3 map must still get a url.

The site serves its static files locally: `/etc/fashionista/serve_static`
exists, so `static_s3.static()` hands everything to Django. The other branch --
the one that maps a path through `static_file_map.csv` -- is dormant, and it is
a trap. That map was last written in October 2023 by `upload_static_files.py`,
which has not run since and could not run anyway. It holds 9 683 rows and
**not one** for the encyclopedia or for smithmagic.

So the day that one file disappears from the server, every asset added in the
last three years would render as `src=""`: a blank page with nothing in the log.
The two behaviours this file pins down turn that into a warning and a working
local url.
"""
from unittest import mock

from django.test import SimpleTestCase

from static_s3.templatetags import static_s3


class AnAssetMissingFromTheMap(SimpleTestCase):

    def setUp(self):
        static_s3.file_map = None
        self.addCleanup(setattr, static_s3, 'file_map', None)

    def test_it_is_served_locally_rather_than_not_at_all(self):
        with mock.patch.object(static_s3, 'SERVING_STATIC', False):
            with mock.patch.object(static_s3, '_get_mapped_file',
                                   return_value=None):
                with self.assertLogs('static_s3.templatetags.static_s3',
                                     level='WARNING'):
                    url = static_s3.static('chardata/forgemagie.css')
        self.assertTrue(url, 'an unmapped asset still renders src=""')
        self.assertIn('forgemagie.css', url)

    def test_a_mapped_asset_still_goes_through_the_map(self):
        """The half that keeps the fallback honest: it must not shadow the map."""
        with mock.patch.object(static_s3, 'SERVING_STATIC', False):
            with mock.patch.object(static_s3, '_get_mapped_file',
                                   return_value='chardata/x.deadbeef.css'):
                url = static_s3.static('chardata/x.css')
        self.assertIn('deadbeef', url)

    def test_a_missing_map_file_does_not_take_the_page_down(self):
        with mock.patch.object(static_s3, 'get_fashionista_path',
                               return_value='/nowhere-at-all'):
            with self.assertLogs('static_s3.templatetags.static_s3',
                                 level='WARNING'):
                self.assertIsNone(static_s3._get_mapped_file('chardata/x.css'))

    def test_the_sentinel_path_is_still_refused(self):
        self.assertIsNone(static_s3.static('chardata/[!]placeholder.png'))
