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
from itemscraper.items import ItemscraperWeaponData, MissingNo
from fashionistapulp.structure import get_structure

UNDER_100_IDS = []



#WEAPON_IDS = []
structure = get_structure()
a = 0
for item in structure.get_available_items_list():
    if item.type != structure.get_type_id_by_name('Pet'):
        ankama_id = item.ankama_id
        if ankama_id:
            UNDER_100_IDS.append(ankama_id)
            #if a >= 1500 and a < 1800:
            #WEAPON_IDS.append(ankama_id) 
        #a += 1
#WEAPON_IDS = [11471]
BASE_URL = 'https://www.dofus.com/en/mmorpg/encyclopedia/equipment/%d-age-old-amulet'
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
}
#ID = 8993
#ID = 14084
#ID = 15495

START_URLS = [BASE_URL % item_id for item_id in UNDER_100_IDS]

class TrapDoorSpider(scrapy.Spider):
    name = "trap_door"
    download_delay=1
    allowed_domains = ["https://dofus.com"]
    start_urls = START_URLS
    handle_httpstatus_list = [404]

    def parse(self, response):
        if response.status == 404:
            item = MissingNo()
            item['ankama_id'] = int((response.request.url.split('-')[0]).split('equipment/')[1])
            item['removed'] = True
            yield item
            return
        
        weapon = ItemscraperWeaponData()
        weapon['ankama_id'] = int((response.request.url.split('-')[0]).split('equipment/')[1])

        e = response.xpath('//h1[@class=\'ak-return-link\']')
        if len(e) <= 0:
            item = MissingNo()
            item['ankama_id'] = int((response.request.url.split('-')[0]).split('equipment/')[1])
            item['removed'] = True
            yield item
            return
        item_name = e.xpath('./text()')[1].extract().strip()
        weapon['name'] = item_name
        item_type = response.xpath('.//div[@class=\'ak-encyclo-detail-type col-xs-6\']//span/text()')[0].extract().strip()
        weapon['w_type'] = item_type
        item_level = response.xpath('.//div[@class=\'ak-encyclo-detail-level col-xs-6 text-right\']/text()')[0].extract().strip()
        weapon['level'] = int(item_level.split()[1])
        print('%s - %s - %s' % (item_name, item_type, item_level))
            
        regex_pattern = re.compile(r'(-?\d+)?( to (-?\d+))? ?(\D+)')
        stats = []
        is_stat = False
        is_hit = True
        for element in response.xpath('//div[@class=\'ak-container ak-content-list ak-displaymode-col\']//div[@class=\'ak-content\']'):
            title = element.xpath('.//div[@class=\'ak-title\']')
            attr = title[0].xpath('./text()')[0].extract().strip()
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
                stat = STAT_TRANSLATE[match.group(4)] if match.group(4) in STAT_TRANSLATE else match.group(4)
                if min_value != None or max_value != None:
                    stats.append((min_value, max_value, stat))
        weapon['stats'] = stats
        for element in response.xpath('//div[@class=\'ak-container ak-content-list ak-displaymode-col\']//div[@class=\'ak-content\']'):
            title = element.xpath('.//div[@class=\'ak-title\']')
            value = title.xpath('.//span[@class=\'ak-title-info\']')
            
            if len(value) > 0:
                item_type = structure.get_type_id_by_name(weapon['w_type'])
                if not item_type:
                    weapon_attr = title[0].xpath('./text()')[0].extract().strip()
                    weapon_value = value[0].xpath('./text()')[0].extract().strip()
                    if weapon_attr == 'AP:':
                        weapon['ap'] = int(weapon_value.split()[0])
                        weapon['uses_per_turn'] = int(weapon_value.split('(')[1].split()[0])
                    elif weapon_attr == 'Range:':
                        if ' to ' in weapon_value:
                            weapon['range'] = [int(x) for x in weapon_value.split(' to ')]
                        else:
                            weapon['range'] = [int(weapon_value), int(weapon_value)]
                    elif weapon_attr == 'CH:':
                        weapon['crit_chance'] = int(weapon_value.split()[0].split('/')[1])
                        if weapon['crit_chance'] != 0:
                            weapon['crit_bonus'] = int(weapon_value.split('(')[1].split(')')[0].split('+')[1])

        yield weapon
