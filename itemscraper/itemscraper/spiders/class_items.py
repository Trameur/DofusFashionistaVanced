# -*- coding: utf-8 -*-

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

import scrapy
from scrapy import Request
from itemscraper.items import MissingNo,\
    ItemscraperClassItemData
from fashionistapulp.structure import get_structure

ITEMS_IDS = [8636, 8648, 8714, 8728, 8660, #Cra
             8652, 8715, 8628, 8640, 8664, #Ecaflip
             16143, 16140, 16141, 16142, 16144, #Eliotrope
             8655, 8720, 8631, 8643, 8667, #Eniripsa
             8662, 8638, 8650, 8726, 8719, #Enutrof
             8661, 8727, 8637, 8649, 8718, #Feca
             13264, 13265, 13263, 13261, 13262, #Foggernaut
             17449, 17448, 17450, 17452, 17451, #Huppermage
             8651, 8717, 8663, 8639, 8619, #Iop
             12392, 12394, 12390, 12386, 12388, #Masqueraider
             8658, 8716, 8634, 8646, 8670, #Osamodas
             18615, 18616, 18617, 18621, 18622, #Ouginak
             8659, 8635, 8647, 8713, 8721, #Pandawa
             12391, 12387, 12393, 12389, 12385, #Rogue
             8657, 8725, 8633, 8645, 8669, #Sacrier
             8656, 8724, 8632, 8644, 8668, #Sadida
             8653, 8722, 8629, 8641, 8665, #Sram
             8654, 8723, 8630, 8642, 8666, #Xelor
             ]
structure = get_structure()

BASE_URL = 'http://www.dofus.com/en/linker/item?l=en&id=%d'
BASE_URLS = [
        'http://www.dofus.com/pt/linker/item?l=pt&id=%d',
        'http://www.dofus.com/fr/linker/item?l=fr&id=%d',
        'http://www.dofus.com/de/linker/item?l=de&id=%d',
        'http://www.dofus.com/es/linker/item?l=es&id=%d',
        'http://www.dofus.com/it/linker/item?l=it&id=%d',
    ]

START_URLS = [BASE_URL % weapon_id for weapon_id in ITEMS_IDS]

class ClassItemsSpider(scrapy.Spider):
    name = "class_items"
    download_delay=1
    allowed_domains = ["dofus.com"]
    start_urls = START_URLS
    handle_httpstatus_list = [404]

    def parse(self, response):
        if response.status == 404:
            item = MissingNo()
            item['ankama_id'] = int(response.request.url.split('=')[-1])
            item['removed'] = True
            yield item
            return
        
        class_item = ItemscraperClassItemData()
        class_item['ankama_id'] = int(response.request.url.split('=')[-1])
        
        e = response.xpath('//div[@class=\'ak-top\']//div[@class=\'ak-detail\']')
        if len(e.xpath('.//div[@class=\'ak-name\']/text()')) <= 0:
            item = MissingNo()
            item['ankama_id'] = int(response.request.url.split('=')[-1])
            item['removed'] = True
            yield item
            return
        item_name = e.xpath('.//div[@class=\'ak-name\']/text()')[0].extract().strip()
        class_item['name'] = item_name
        item_type = e.xpath('.//div[@class=\'ak-type\']/text()')[0].extract().strip()
        class_item['w_type'] = item_type
        item_level = e.xpath('.//div[@class=\'ak-level\']/text()')[0].extract().strip()
        class_item['level'] = int(item_level.split()[1])
        print('%s - %s - %s' % (item_name, item_type, item_level))
        
        extra_lines = {}
        lang = 'en'
        if '/pt/' in response.request.url:
            lang = 'pt'
        elif '/fr/' in response.request.url:
            lang = 'fr'
        elif '/es/' in response.request.url:
            lang = 'es'
        elif '/de/' in response.request.url:
            lang = 'de'
        class_item['lang'] = lang
        extra_lines[lang] = []
        for element in response.xpath('//div[@id=\'tab1\']//div[@class=\'ak-list-element\']'):
            title = element.xpath('.//div[@class=\'ak-title\']')
            attr = title[0].xpath('./text()')[0].extract().strip()
            if attr != '1 PM' and attr != '1 MP' and attr != '+1 BP':
                extra_lines[lang].append(attr)
        class_item['extra_lines'] = extra_lines
        yield class_item
        
        print(BASE_URLS)
        if '/en/' in response.request.url:
            for i in range(len(BASE_URLS)):
                yield Request(BASE_URLS[i] % class_item['ankama_id'], callback = self.parse)
        
