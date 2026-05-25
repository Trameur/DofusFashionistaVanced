# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from fashionsite.settings import DEFAULT_THEME
from static_s3.templatetags.static_s3 import static

CSS_NAMES = ['changelog', 'common', 'compare', 'exclusions', 'forms', 'home', 'solution', 'spells']

def get_css_for_theme(theme, request):
    theme_css = {}
    if theme == 'auto':
        for css in CSS_NAMES:
            if 'current_auto' in request.COOKIES: 
                auto_theme = request.COOKIES['current_auto']
                theme_css[css] = "chardata/%s_%s.css" % (css, auto_theme)
            else:
                theme_css[css] = "chardata/%s_%s.css" % (css, 'darktheme')         
    else:
        for css in CSS_NAMES:
            theme_css[css] = "chardata/%s_%s.css" % (css, theme)
    for css in CSS_NAMES:
        theme_css['%s%s' % (css, 'lighttheme')] = "chardata/%s_%s.css" % (css, 'lighttheme')
        theme_css['%s%s' % (css, 'darktheme')] = "chardata/%s_%s.css" % (css, 'darktheme')
    return theme_css

def get_css_static_for_theme(theme, request):
    theme_css = {}
    if theme == 'auto':
        for css in CSS_NAMES:
            if 'current_auto' in request.COOKIES: 
                auto_theme = request.COOKIES['current_auto']
                theme_css[css] = static("chardata/%s_%s.css" % (css, auto_theme))
            else: 
                theme_css[css] = static("chardata/%s_%s.css" % (css, 'darktheme'))
            theme_css['%s%s' % (css, 'lighttheme')] = static("chardata/%s_%s.css" % (css, 'lighttheme'))
            theme_css['%s%s' % (css, 'darktheme')] = static("chardata/%s_%s.css" % (css, 'darktheme'))
    else:
        for css in CSS_NAMES:
            theme_css[css] = static("chardata/%s_%s.css" % (css, theme))
    return theme_css

def get_theme(request):
    theme = DEFAULT_THEME;
    if 'theme' in request.COOKIES:
        theme = request.COOKIES['theme']
    return theme

def check_theme(request, response):
    if 'theme' not in request.COOKIES:
        response.set_cookie('theme', DEFAULT_THEME);
        
def get_triangle_URL(request):
    theme = get_theme(request)
    if theme == 'auto':
        triangle_pic = {}
        triangle_pic['lighttheme'] = static('chardata/triangle-%s.png' % ('lighttheme'))
        triangle_pic['darktheme'] = static('chardata/triangle-%s.png' % ('darktheme'))
    else:    
        triangle_pic = static('chardata/triangle-%s.png' % (theme))
    return triangle_pic

def get_needle_URL(request):
    theme = get_theme(request)
    if theme == 'auto':
        needle_pic = {}
        needle_pic['lighttheme'] = static('chardata/needle-%s.png' % ('lighttheme'))
        needle_pic['darktheme'] = static('chardata/needle-%s.png' % ('darktheme'))
    else:    
        needle_pic = static('chardata/needle-%s.png' % (theme))
    return needle_pic

def get_ajax_loader_URL(request):
    theme = get_theme(request)
    if theme == 'auto':
        loader_pic = {}
        loader_pic['lighttheme'] = static('chardata/ajax-loader-%s-2.gif' % ('lighttheme'))
        loader_pic['darktheme'] = static('chardata/ajax-loader-%s-2.gif' % ('darktheme'))
    else:    
        loader_pic = static('chardata/ajax-loader-%s-2.gif' % (theme))
    return loader_pic

def get_external_image_URL(request):
    theme = get_theme(request)
    if theme == 'auto':
        external_image = {}
        external_image['lighttheme'] = static('chardata/link-external-%s.png' % ('lighttheme'))
        external_image['darktheme'] = static('chardata/link-external-%s.png' % ('darktheme'))
    else:    
        external_image = static('chardata/link-external-%s.png' % (theme))
    return external_image

def get_questionmark_URL(request):
    theme = get_theme(request)
    if theme == 'auto':
        questionmark = {}
        questionmark['lighttheme'] = static('chardata/QuestionMark-%s.png' % ('lighttheme'))
        questionmark['darktheme'] = static('chardata/QuestionMark-%s.png' % ('darktheme'))
    else:    
        questionmark = static('chardata/QuestionMark-%s.png' % (theme))
    return questionmark

def get_all_images_URLs(request):
    images = {}
    images['lighttheme'] = {}
    images['darktheme'] = {}
    
    images['lighttheme']['triangle'] = static('chardata/triangle-%s.png' % ('lighttheme'))
    images['lighttheme']['loader'] = static('chardata/ajax-loader-%s-2.gif' % ('lighttheme'))
    images['lighttheme']['external'] = static('chardata/link-external-%s.png' % ('lighttheme'))
    images['lighttheme']['needle'] = static('chardata/needle-%s.png' % ('lighttheme'))
    images['lighttheme']['questionmark'] = static('chardata/QuestionMark-%s.png' % ('lighttheme'))
    
    images['darktheme']['triangle'] = static('chardata/triangle-%s.png' % ('darktheme'))
    images['darktheme']['loader'] = static('chardata/ajax-loader-%s-2.gif' % ('darktheme'))
    images['darktheme']['external'] = static('chardata/link-external-%s.png' % ('darktheme'))
    images['darktheme']['needle'] = static('chardata/needle-%s.png' % ('darktheme'))
    images['darktheme']['questionmark'] = static('chardata/QuestionMark-%s.png' % ('darktheme'))
    return images