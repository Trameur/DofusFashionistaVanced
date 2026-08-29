import csv
import logging
import os
from django import template
from django.templatetags.static import static as built_in_static

from fashionistapulp.fashionista_config import serve_static_files, get_fashionista_path

logger = logging.getLogger(__name__)

register = template.Library()

SERVING_STATIC = serve_static_files()

@register.simple_tag
def static(path, astr=None, name=None):
    if '[!]' in path:
        return None
    if SERVING_STATIC:
        return built_in_static(path)
    else:
        mapped_file = _get_mapped_file(path)
        if mapped_file is not None:
            return built_in_static(mapped_file)
        # The map is written by upload_static_files.py, which has not run since
        # 2023 and holds no entry for the encyclopedia or for smithmagic.
        # Returning None here renders src="" -- a blank image with nothing in
        # the log to say why. The local path is what nginx serves anyway, so it
        # is a working answer instead of an empty one.
        logger.warning('static file absent from the S3 map, served locally: %s',
                       path)
        return built_in_static(path)

file_map = None
def _get_mapped_file(path):
    global file_map
    if file_map is None:
        file_map = {}
        fashionista_path = get_fashionista_path()

        # os.path.join covers every platform; the old branch left the path
        # unbound on anything that was neither Windows nor Linux, and such a
        # run raised UnboundLocalError instead of serving a page.
        file_map_file_path = os.path.join(fashionista_path,
                                          'static_file_map.csv')
        try:
            with open(file_map_file_path, 'rt') as f:
                for row in csv.reader(f):
                    if len(row) >= 2:
                        file_map[row[0]] = row[1]
        except OSError:
            # A missing map used to raise straight out of a template tag, so
            # one absent file took down every page instead of one image.
            logger.warning('no static file map at %s; every asset will be '
                           'served locally', file_map_file_path)

    return file_map.get(path)