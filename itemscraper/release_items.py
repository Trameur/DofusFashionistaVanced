"""The all_<category>_<lang>.json pages of the dofusdude API, rebuilt from the MAPPED_* files of its release."""

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']
ASSETS = ('MAPPED_ITEMS.json', 'MAPPED_SETS.json', 'MAPPED_RECIPES.json')
ITEM_CATEGORIES = {'equipment': 0, 'consumables': 1, 'resources': 2, 'quest_items': 3, 'cosmetics': 5}
INGREDIENT_SUBTYPES = {0: 'equipment', 1: 'consumables', 2: 'resources'}
DODUAPI_MOUNT_TYPE_IDS = {242, 245, 247}
IMAGE_SIZES = (('icon', '64'), ('sd', '128'))
NO_LINKS = {'first': None, 'prev': None, 'next': None, 'last': None}


class UnhandledShape(ValueError):
    def __init__(self, detail):
        super().__init__('%s; the release conversion does not handle it, wait for the dofusdude API '
                         'to serve this version' % detail)


def text(names, lang):
    return (names or {}).get(lang, '')


def image_urls(image_base, icon_id):
    return {key: '%s/%d-%s.png' % (image_base, icon_id, size) for key, size in IMAGE_SIZES}


def effects(rows, lang):
    rendered = [{
        'int_minimum': row['min'],
        'int_maximum': row['max'],
        'type': {'name': text(row['type'], lang), 'id': row['element_id'],
                 'is_meta': row['is_meta'], 'is_active': row['active']},
        'ignore_int_min': row['is_meta'] or row['min_max_irrelevant'] == -2,
        'ignore_int_max': row['is_meta'] or row['min_max_irrelevant'] <= -1,
        'formatted': text(row['templated'], lang),
    } for row in rows or []]
    return rendered or None


def condition_tree(node, lang):
    if node['is_operand']:
        value = node['value']
        return {'condition': {'operator': value['operator'], 'int_value': value['value'],
                              'element': {'name': text(value['templated'], lang), 'id': value['element_id']}},
                'is_operand': True}
    tree = {'is_operand': False}
    if node.get('relation') is not None:
        tree['relation'] = node['relation']
    children = [condition_tree(child, lang) for child in node.get('children') or []]
    if children:
        tree['children'] = children
    return tree


def recipe(item_id, recipes, items):
    entries = (recipes.get(item_id) or {}).get('entries')
    if not entries:
        return None
    rows = []
    for entry in entries:
        ingredient = items.get(entry['item_id'])
        if ingredient is None:
            raise UnhandledShape('the recipe of item %d needs %d, which is not an item' % (item_id, entry['item_id']))
        category = ingredient['type']['categoryId']
        if category not in INGREDIENT_SUBTYPES:
            raise UnhandledShape('the recipe of item %d needs %d, of category %d' % (item_id, entry['item_id'], category))
        rows.append({'item_ankama_id': entry['item_id'], 'item_subtype': INGREDIENT_SUBTYPES[category],
                     'quantity': entry['quantity']})
    return rows


def item_row(item, category, lang, recipes, items, image_base):
    row = {
        'ankama_id': item['ankama_id'],
        'name': text(item['name'], lang),
        'type': {'name': text(item['type']['name'], lang), 'id': item['type']['itemTypeId']},
        'level': item['level'],
        'image_urls': image_urls(image_base, item['iconId']),
        'description': text(item['description'], lang),
    }
    ingredients = recipe(item['ankama_id'], recipes, items)
    if ingredients:
        row['recipe'] = ingredients
    if item.get('conditions') is not None:
        row['conditions'] = condition_tree(item['conditions'], lang)
    rendered = effects(item.get('effects'), lang)
    if rendered:
        row['effects'] = rendered
    is_weapon = item['type']['superTypeId'] == 2
    if category == 'equipment':
        row['is_weapon'] = is_weapon
    row['pods'] = item['pods']
    if category == 'equipment':
        if item.get('hasParentSet'):
            row['parent_set'] = {'id': item['parentSet']['id'], 'name': text(item['parentSet']['name'], lang)}
        if is_weapon:
            row['critical_hit_probability'] = item['criticalHitProbability']
            row['critical_hit_bonus'] = item['criticalHitBonus']
            row['max_cast_per_turn'] = item['maxCastPerTurn']
            row['ap_cost'] = item['apCost']
            row['range'] = {'min': item['minRange'], 'max': item['range']}
    return row


def mount_row(item, lang, image_base):
    row = {
        'ankama_id': item['ankama_id'],
        'name': text(item['name'], lang),
        'family': {'ankama_id': item['type']['itemTypeId'], 'name': text(item['type']['name'], lang)},
        'image_urls': image_urls(image_base, item['iconId']),
    }
    rendered = effects(item.get('effects'), lang)
    if rendered:
        row['effects'] = rendered
    return row


def set_row(item_set, lang):
    row = {
        'ankama_id': item_set['ankama_id'],
        'name': text(item_set['name'], lang),
        'items': len(item_set.get('items') or []),
        'level': item_set['level'],
        'contains_cosmetics': item_set['contains_cosmetics'],
        'contains_cosmetics_only': item_set['contains_cosmetics_only'],
    }
    if item_set.get('effects'):
        row['effects'] = {count: effects(rows, lang) for count, rows in sorted(item_set['effects'].items())}
    if item_set.get('items'):
        row['equipment_ids'] = item_set['items']
    return row


def by_id(rows, key, label):
    indexed = {}
    for row in rows:
        if row[key] in indexed:
            raise UnhandledShape('%s %d appears twice' % (label, row[key]))
        indexed[row[key]] = row
    return indexed


def rebuild(items, sets, recipes, image_base, categories, languages=LANGUAGES):
    """{(category, lang): page} for the get_equipments.py categories, from the parsed MAPPED_* files."""
    items = by_id(items, 'ankama_id', 'item')
    sets = by_id(sets, 'ankama_id', 'set')
    recipes = by_id(recipes, 'result_id', 'recipe of item')
    for item in items.values():
        if item['type']['categoryId'] not in ITEM_CATEGORIES.values():
            raise UnhandledShape('item %d has category %d' % (item['ankama_id'], item['type']['categoryId']))
    item_ids, set_ids = sorted(items), sorted(sets)
    pages = {}
    for lang in languages:
        for category in categories:
            if category == 'mounts':
                rows = [mount_row(items[i], lang, image_base) for i in item_ids
                        if items[i]['type']['categoryId'] == 0
                        and items[i]['type']['itemTypeId'] in DODUAPI_MOUNT_TYPE_IDS]
            elif category == 'sets':
                rows = [set_row(sets[i], lang) for i in set_ids]
            else:
                rows = [item_row(items[i], category, lang, recipes, items, image_base) for i in item_ids
                        if items[i]['type']['categoryId'] == ITEM_CATEGORIES[category]]
            key = category if category in ('mounts', 'sets') else 'items'
            pages[category, lang] = {'_links': dict(NO_LINKS), key: rows}
    return pages
