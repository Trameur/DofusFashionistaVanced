#!/usr/bin/env python3
"""Fill the Wakfu crafting tables from Ankama's mirrored data.

    python build_wakfu_recipes.py  (after build_wakfu_db.py, which wipes the db)
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'fashionistapulp'))
from fashionistapulp.fashionista_config import get_items_db_path  # noqa: E402

HERE = Path(__file__).resolve().parent.parent

# Wakfu has no German
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
FALLBACK = {'de': 'en'}

# Ingredient subtype, same in both tables: readers join on it
EQUIPMENT = 'equipment'
RESOURCE = 'resources'


def read(raw_dir, name):
    with io.open(Path(raw_dir) / name, encoding='utf-8') as handle:
        return json.load(handle)


def titles(node):
    """One name per language, English standing in for German."""
    body = node or {}
    out = {language: body[language] for language in LANGUAGES
           if body.get(language)}
    for missing, instead in FALLBACK.items():
        if out.get(instead):
            out[missing] = out[instead]
    return out


def every_name(raw_dir):
    """{ankama id: {language: name}} for everything a recipe can mention."""
    names = {}
    for name, nested in (('items.json', True), ('jobsItems.json', False)):
        for row in read(raw_dir, name):
            definition = row['definition']
            ident = definition['item']['id'] if nested else definition['id']
            said = titles(row.get('title'))
            if said:
                names.setdefault(ident, {}).update(said)
    return names


def chosen_recipes(raw_dir, counts):
    """{product ankama id: recipe} keeping the lowest recipe id per product."""
    recipes = {row['id']: row for row in read(raw_dir, 'recipes.json')}
    best = {}
    for row in read(raw_dir, 'recipeResults.json'):
        product = row['productedItemId']
        recipe = recipes.get(row['recipeId'])
        if recipe is None:
            counts['result names no recipe'] += 1
            continue
        if row.get('productedItemQuantity', 1) != 1:
            counts['makes more than one, quantity not stored'] += 1
        current = best.get(product)
        if current is None:
            best[product] = recipe
        else:
            counts['extra recipe for a product already seen'] += 1
            if recipe['id'] < current['id']:
                best[product] = recipe
    return best


def build(db_path, raw_dir):
    counts = collections.Counter()
    names = every_name(raw_dir)
    best = chosen_recipes(raw_dir, counts)
    ingredients = collections.defaultdict(list)
    for row in read(raw_dir, 'recipeIngredients.json'):
        ingredients[row['recipeId']].append(row)

    conn = sqlite3.connect(str(db_path))
    try:
        gear = {ankama_id: item_id for item_id, ankama_id in
                conn.execute('SELECT id, ankama_id FROM items')}
        for table in ('item_recipes', 'item_recipe_ingredient_names',
                      'item_craft_jobs', 'job_names'):
            conn.execute('DELETE FROM %s' % table)

        for category in read(raw_dir, 'recipeCategories.json'):
            job_id = category['definition']['id']
            for language, name in sorted(titles(category.get('title')).items()):
                conn.execute('INSERT INTO job_names (job_ankama_id, language,'
                             ' name) VALUES (?, ?, ?)', (job_id, language, name))
            counts['jobs'] += 1

        mentioned = set()
        for product, recipe in sorted(best.items()):
            item_id = gear.get(product)
            if item_id is None:
                counts['makes something this database has no row for'] += 1
                continue
            lines = sorted(ingredients.get(recipe['id']) or (),
                           key=lambda row: (row['ingredientOrder'],
                                            row['itemId']))
            if not lines:
                counts['recipe with no ingredient'] += 1
                continue
            # Not ingredientOrder: it has gaps and repeats, and position is in the key
            for position, line in enumerate(lines):
                ingredient = line['itemId']
                subtype = EQUIPMENT if ingredient in gear else RESOURCE
                conn.execute(
                    'INSERT INTO item_recipes (item, position,'
                    ' ingredient_ankama_id, ingredient_subtype, quantity)'
                    ' VALUES (?, ?, ?, ?, ?)',
                    (item_id, position, ingredient, subtype, line['quantity']))
                mentioned.add((ingredient, subtype))
                counts['ingredient lines'] += 1
            conn.execute('INSERT INTO item_craft_jobs (item, job_ankama_id,'
                         ' level) VALUES (?, ?, ?)',
                         (item_id, recipe['categoryId'], recipe['level']))
            counts['craftable items'] += 1

        for ingredient, subtype in sorted(mentioned):
            said = names.get(ingredient) or {}
            if not said:
                counts['ingredient nobody names'] += 1
                continue
            for language, name in sorted(said.items()):
                conn.execute(
                    'INSERT INTO item_recipe_ingredient_names'
                    ' (ingredient_ankama_id, ingredient_subtype, language,'
                    ' name) VALUES (?, ?, ?, ?)',
                    (ingredient, subtype, language, name))
            counts['named ingredients'] += 1
        conn.commit()
    finally:
        conn.close()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', default=None,
                        help='the mirrored build (default: the only one there)')
    parser.add_argument('--db', default=None)
    args = parser.parse_args(argv)

    raw_dir = args.raw
    if raw_dir is None:
        mirror = HERE / 'itemscraper' / 'wakfu_raw'
        builds = sorted(p for p in mirror.glob('*') if p.is_dir())
        if not builds:
            parser.error('no mirrored build; run get_items_wakfu.py first')
        raw_dir = builds[-1]
    db_path = Path(args.db or get_items_db_path('wakfu'))
    if not db_path.exists():
        parser.error('%s is missing; run build_wakfu_db.py first' % db_path)

    counts = build(db_path, raw_dir)
    print('filled the crafting tables of %s' % db_path)
    for name, count in sorted(counts.items()):
        print('   %-44s %6d' % (name, count))
    return 0


if __name__ == '__main__':
    sys.exit(main())
