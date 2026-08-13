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
import re
import json
from itemscraper.items import ItemscraperWeaponData, MissingNo
from fashionistapulp.structure import get_structure

UNDER_100_IDS = []
def get_deleted_ids():
    items = []
    with open('allitemsnew.json') as f:
        item_list = json.load(f)
        for entry in item_list:
            if 'removed' in entry:
                items.append(entry)
    return items
def get_ids():
    with open('allitemsnew.json') as f:
        items = json.load(f)
    return items

BASE_URL = 'https://www.dofus.com/en/mmorpg/encyclopedia/equipment/%d-age-old-amulet'
#BASE_URL = 'https://www.dofus-touch.com/en/linker/ride?l=en&id=%d'
STAT_TRANSLATE = {
    '% Power': 'Power',
    'Damage': 'Damage',
    'Heals': 'Heals',
    'AP': 'AP',
    'MP': 'MP',
    '% Critical': 'Critical Hits',
    'Agility': 'Agility',
    'Strength': 'Strength',
    'Neutral Damage': 'Neutral Damage',
    'Earth Damage': 'Earth Damage',
    'Intelligence': 'Intelligence',
    'Fire Damage': 'Fire Damage',
    'Air Damage': 'Air Damage',
    'Chance': 'Chance',
    'Water Damage': 'Water Damage',
    'Vitality': 'Vitality',
    'Initiative': 'Initiative',
    'Summons': 'Summon',
    'Range': 'Range',
    'Wisdom': 'Wisdom',
    'Neutral Resistance': 'Neutral Resist',
    'Water Resistance': 'Water Resist',
    'Air Resistance': 'Air Resist',
    'Fire Resistance': 'Fire Resist',
    'Earth Resistance': 'Earth Resist',
    '% Neutral Resistance': '% Neutral Resist',
    '% Air Resistance': '% Air Resist',
    '% Fire Resistance': '% Fire Resist',
    '% Water Resistance': '% Water Resist',
    '% Earth Resistance': '% Earth Resist',
    'Neutral Resistance in PvP': 'Neutral Resist in PVP',
    'Water Resistance in PvP': 'Water Resist in PVP',
    'Air Resistance in PvP': 'Air Resist in PVP',
    'Fire Resistance in PvP': 'Fire Resist in PVP',
    'Earth Resistance in PvP': 'Earth Resist in PVP',
    '% Neutral Resistance in PvP': '% Neutral Resist in PVP',
    '% Air Resistance in PvP': '% Air Resist in PVP',
    '% Fire Resistance in PvP': '% Fire Resist in PVP',
    '% Water Resistance in PvP': '% Water Resist in PVP',
    '% Earth Resistance in PvP': '% Earth Resist in PVP',
    'Prospecting': 'Prospecting',
    'pods': 'Pods',
    'AP Reduction': 'AP Reduction',
    'MP Reduction': 'MP Reduction',
    'Lock': 'Lock',
    'Dodge': 'Dodge',
    'Reflects': 'Reflects',
    'Reflects ': 'Reflects',
    'Reflects  damage': 'Reflects',
    'Pushback Damage': 'Pushback Damage',
    'Trap Damage': 'Trap Damage',
    'Power (traps)': '% Trap Damage',
    'Critical Resistance': 'Critical Resist',
    'Pushback Resistance': 'Pushback Resist',
    'MP Parry': 'MP Loss Resist',
    'AP Parry': 'AP Loss Resist',
    'Critical Damage': 'Critical Damage',
    'HP': 'HP',
    'MP Dodge': 'MP Loss Resist',
    '% Air Resist in PVP': '% Air Resist in PVP',
    '% Water Resist in PVP': '% Water Resist in PVP',
    'Fire Resist in PVP': 'Fire Resist in PVP',
    '% Melee Resistance': '% Melee Resist',
    '% Ranged Resistance': '% Ranged Resist',
    'AP Dodge': 'AP Loss Resist',
    '% Melee Damage': '% Melee Damage',
    '% Ranged Damage': '% Ranged Damage',
    '% Weapon Damage': '% Weapon Damage',
    '% Spell Damage': '% Spell Damage',
    '% Weapon Resistance': '% Weapon Resist',
}
UNDER_100_IDS = [item['ankama_id'] for item in get_ids()]
START_URLS = [BASE_URL % item_id for item_id in UNDER_100_IDS]
structure = get_structure()

class TouchVenom2Spider(scrapy.Spider):
    #print START_URLS
    name = "venom_part2"
    download_delay=1
    allowed_domains = ["dofus.com"]
    start_urls = START_URLS
    handle_httpstatus_list = [404]
    
    def _get_id_from_url(self, url):
        number = url.strip('-age-old-amulet')
        number = number.strip('https://www.dofus.com/en/mmorpg/encyclopedia/equipment/')
        return int(number)
    
    def parse(self, response):
        this_item_id = self._get_id_from_url(response.request.url)
        if response.status == 404:
            item = MissingNo()
            item['ankama_id'] = this_item_id
            item['removed'] = True
            yield item
            return
        
        weapon = ItemscraperWeaponData()
        weapon['ankama_id'] = this_item_id
        
        e = response.xpath('//div[@class=\'ak-container ak-content-list ak-displaymode-col\']')
        if len(e.xpath('.//div[@class=\'ak-title\']/text()')) <= 0:
            item = MissingNo()
            item['ankama_id'] = this_item_id
            item['removed'] = True #Gotta check if its not an item with only weird effects
            yield item
            return
        
        print('------------------------------------------------------------')
        print(response.xpath('.//h1[@class=\'ak-return-link\']/text()').extract()[1].strip())
        item_name = response.xpath('.//h1[@class=\'ak-return-link\']/text()').extract()[1].strip()
        weapon['name'] = item_name
        print(response.xpath('.//div[@class=\'ak-encyclo-detail-type col-xs-6\']//span/text()')[0].extract().strip())
        item_type = response.xpath('.//div[@class=\'ak-encyclo-detail-type col-xs-6\']//span/text()')[0].extract().strip()
        if item_type == 'Mounts':
            item_type = 'Pet'
        weapon['w_type'] = item_type
        item_level = response.xpath('.//div[@class=\'ak-encyclo-detail-level col-xs-6 text-right\']/text()')[0].extract().strip()
        weapon['level'] = int(item_level.split()[1])
        print('%s - %s - %s' % (item_name, item_type, item_level))
        
        weapon['dofustouch'] = False
            
        regex_pattern = re.compile('(-?\d+)?( to (-?\d+))? ?(\D+)')
        stats = []
        is_stat = False
        is_hit = True
        
        xpath_str = '//div[@class=\'ak-container ak-content-list ak-displaymode-col\']//div[@class=\'ak-title\']'
            
        print('------------------------------------------------------------------------------')
        for element in response.xpath(xpath_str):
            title = element
            attr = title.xpath('./text()').extract()[0].strip()
            print(attr)
            if attr not in ['AP:', 'Range:', 'CH:']:
                if '>' in attr or '<' in attr:
                    weapon['conditions'] = [cond.extract().strip() for cond in title.xpath('./text()')]
                else:
                    match = regex_pattern.match(attr)
                    if not match.group(4).startswith('('):
                        if (match.group(4) == 'AP') and (int(match.group(1)) < 0) and not is_stat:
                            print('Weapon %s with -AP' % title)
                            is_hit = False
                        else:
                            is_stat = True
                    if is_stat or is_hit: 
                        min_value = (int(match.group(1)) if match.group(1) else None)
                        max_value = (int(match.group(3)) if match.group(3) else None)
                        stat = STAT_TRANSLATE[match.group(4).lstrip()] if match.group(4).lstrip() in STAT_TRANSLATE else match.group(4).lstrip()
                        stats.append((min_value, max_value, stat))
            else:
                value = title.xpath('.//span[@class=\'ak-title-info\']')
                weapon_value = value[0].xpath('./text()')[0].extract().strip()
                if attr == 'AP:':
                    weapon['ap'] = int(weapon_value.split()[0])
                    weapon['uses_per_turn'] = int(weapon_value.split('(')[1].split()[0])
                    print('AP: %d' % weapon['ap'])
                    print('Uses per turn: %d' % weapon['uses_per_turn'])
                elif attr == 'Range:':
                    if ' to ' in weapon_value:
                        weapon['range'] = [int(x) for x in weapon_value.split(' to ')]
                    else:
                        weapon['range'] = [int(weapon_value), int(weapon_value)]
                    print('Range: ') 
                    print(weapon['range'])
                elif attr == 'CH:':
                    print('tem CH')
                    weapon['crit_chance'] = int(weapon_value.split()[0].split('/')[1])
                    if weapon['crit_chance'] != 0:
                        weapon['crit_bonus'] = int(weapon_value.split('(')[1].split(')')[0].split('+')[1])
                        print('CH: %d (+%d)' % (weapon['crit_chance'], weapon['crit_bonus']))

        weapon['stats'] = stats
        
        print('ELEMENTS')
        weapon['has_conditions'] = False
        for element in response.xpath('.//div[@class=\'ak-container ak-panel no-padding\']'):
            title = element.xpath('.//div[@class=\'ak-panel-title\']/text()[last()]')
            if title.get().strip() == 'Conditions':
                weapon['has_conditions'] = True
        print('END')

        image_url_xpath = "//div[@class='ak-encyclo-detail-illu']/img[@class='img-maxresponsive']/@src"
        image_url = response.xpath(image_url_xpath).extract_first()

        if image_url:
            weapon['image_url'] = image_url

        yield weapon
