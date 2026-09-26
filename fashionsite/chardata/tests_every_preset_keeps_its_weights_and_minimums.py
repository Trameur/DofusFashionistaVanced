# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every door that creates a build keeps the aspects, weights, minimums and options in golden_presets/.

Regenerate after an intended change, every door or a comma list of them
(quick_start, setup, smart_build, import), from fashionsite/:
    REGENERATE_GOLDEN_PRESETS=1 py manage.py test chardata.tests_every_preset_keeps_its_weights_and_minimums --settings=fashionsite.settings_test --noinput --parallel 1
"""
import ast
import hashlib
import html
import itertools
import json
import os
import re
import sys

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.utils import translation

from chardata.char_blobs import read_char_blob
from chardata.coaching_view import coaching
from chardata.create_project_view import create_project, save_project
from chardata.models import Char
from chardata.nl_build_view import smart_build
from chardata.nl_parser import parse_build_request
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import get_structure, set_current_game_version

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'golden_presets')
REGENERATE = 'REGENERATE_GOLDEN_PRESETS'
DOORS = ('quick_start', 'setup', 'smart_build', 'import')
VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
LEVELS = (50, 100, 199, 200)
BAND_LEVELS = (1, 20, 150, 170, 180)
MAX_FIXTURE_BYTES = 1000000
SHOWN_CHANGES = 40
INTERNED = ('minimums', 'options', 'weights')
# Read from the item data, not from the preset
DATA_DERIVED_OPTIONS = ('dofuses', 'dofusnotforchar')

SMART_BUILD_PHRASES = {
    'en': ['Iop 200 earth PvM', 'Cra agi pvp level 150', 'Eniripsa fire healer',
           'Enutrof farm drop 100', 'Sacrier tank dungeon level 180',
           'Osamodas summoner water 120', 'Sram traps duel 199',
           'Xelor 1v1 koli 3v3', 'Huppermage multi element 200',
           'Cra dream 200', 'Pandawa', 'earth damage 200'],
    'fr': ['Iop 200 terre PvM', 'Cra agi pvp niveau 150', 'Eniripsa feu soigneur',
           'Enutrof farm drop 100', 'Sacrieur tank donjon niveau 180',
           'Osamodas invocateur eau 120', 'Sram pièges duel 199',
           'Zobal retrait PM kolizeum', 'Steamer multi 200',
           'Crâ songe 200', 'Roublard poussée', 'Féca vitalité résistances 50'],
    'es': ['Iop 200 tierra PvM', 'Cra agi pvp nivel 150', 'Eniripsa fuego sanador',
           'Enutrof farm drop 100', 'Sacrier tanque mazmorra nivel 180',
           'Osamodas invocador agua 120', 'Sram trampas duelo 199',
           'Xelor crítico arena', 'Ecaflip suerte prospección 60'],
    'pt': ['Iop 200 terra PvM', 'Cra agi pvp nível 150', 'Eniripsa fogo cura',
           'Enutrof farm drop 100', 'Sacrier tanque masmorra nível 180',
           'Osamodas invocador água 120', 'Sram armadilhas duelo 199',
           'Xelor crítico arena', 'Ecaflip sorte sabedoria 60'],
    'de': ['Iop 200 Erde PvM', 'Crâ Flinkheit PvP Stufe 150', 'Eniripsa Feuer Heiler',
           'Enutrof farmen Stufe 100', 'Sacrier Tank Verlies Stufe 180',
           'Osamodas Beschwörer Wasser 120', 'Sram Fallen Duell 199',
           'Xelor kritisch Kolosseum', 'Halsabschneider Glück Weisheit 60'],
}
IMPORT_CASES = (('Iop', 200, ('Hat', 'Cloak', 'Belt')),
                ('Cra', 100, ('Hat', 'Cloak', 'Belt')))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False)


def _ref(value):
    return hashlib.sha1(_canonical(value).encode('utf-8')).hexdigest()[:10]


def _intern(table, value):
    ref = _ref(value)
    if table.setdefault(ref, value) != value:
        raise ValueError('two values share the reference %s' % ref)
    return ref


def _pack(cases):
    """Created builds as rows in case_fields order; minimums, options and weights stored once."""
    built = [record for record in cases.values() if 'weights' in record]
    fields = sorted({field for record in built for field in record})
    weight_keys = sorted({key for record in built for key in record['weights']})
    tables = {table: {} for table in INTERNED}
    packed = {}
    for name, record in cases.items():
        if 'weights' not in record:
            packed[name] = record
            continue
        packed[name] = [_intern(tables[field], record[field]) if field in INTERNED
                        else record.get(field) for field in fields]
    tables['weights'] = {ref: ','.join('' if values.get(key) is None
                                       else _canonical(values[key]) for key in weight_keys)
                         for ref, values in tables['weights'].items()}
    return dict(tables, case_fields=fields, cases=packed, weight_keys=weight_keys)


def _expand(packed):
    fields, keys = packed['case_fields'], packed['weight_keys']
    cases = {}
    for name, entry in packed['cases'].items():
        if isinstance(entry, dict):
            cases[name] = entry
            continue
        record = dict(zip(fields, entry))
        for table in INTERNED:
            record[table] = packed[table][record[table]]
        record['weights'] = {key: json.loads(value) for key, value
                             in zip(keys, record['weights'].split(',')) if value}
        cases[name] = record
    return cases


def _dumps(packed):
    """Compact JSON, sorted keys, one case or table row per line."""
    sections = []
    for section in sorted(packed):
        value = packed[section]
        if isinstance(value, dict) and value:
            rows = ',\n'.join('%s:%s' % (_canonical(key), _canonical(value[key]))
                              for key in sorted(value))
            body = '{\n%s\n}' % rows
        else:
            body = _canonical(value)
        sections.append('%s:%s' % (_canonical(section), body))
    return '{\n%s\n}\n' % ',\n'.join(sections)


def fixture_path(door):
    return os.path.join(GOLDEN_DIR, '%s.json' % door)


def load_fixture(door):
    with open(fixture_path(door), encoding='utf-8') as handle:
        return _expand(json.load(handle))


def write_fixture(door, cases):
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    text = _dumps(_pack(cases))
    if _expand(json.loads(text)) != cases:
        raise ValueError('the %s fixture does not read back as written' % door)
    with open(fixture_path(door), 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def regenerating(door):
    wanted = os.environ.get(REGENERATE, '').strip()
    if not wanted:
        return False
    return wanted == '1' or door in {part.strip() for part in wanted.split(',')}


_ABSENT = '(absent)'


def differences(old, new):
    """[(case, key, old value, new value)], one row per changed key."""
    rows = []
    for case in sorted(set(old) | set(new)):
        if case not in new:
            rows.append((case, '(case)', 'recorded', _ABSENT))
            continue
        if case not in old:
            rows.append((case, '(case)', _ABSENT, 'new'))
            continue
        before, after = old[case], new[case]
        for field in sorted(set(before) | set(after)):
            was, now = before.get(field, _ABSENT), after.get(field, _ABSENT)
            if was == now:
                continue
            if isinstance(was, dict) and isinstance(now, dict):
                for key in sorted(set(was) | set(now)):
                    if was.get(key, _ABSENT) != now.get(key, _ABSENT):
                        rows.append((case, '%s.%s' % (field, key),
                                     was.get(key, _ABSENT), now.get(key, _ABSENT)))
            else:
                rows.append((case, field, was, now))
    return rows


def describe(door, rows, total):
    cases = sorted({row[0] for row in rows})
    lines = ['%s: %d of %d cases changed.' % (door, len(cases), total)]
    for case, key, was, now in rows[:SHOWN_CHANGES]:
        lines.append('  %s | %s: %s -> %s' % (case, key, _canonical(was), _canonical(now)))
    if len(rows) > SHOWN_CHANGES:
        lines.append('  ... and %d more changes' % (len(rows) - SHOWN_CHANGES))
    per_key = {}
    for case, key, _was, _now in rows:
        per_key.setdefault(key, set()).add(case)
    lines.append('Cases changed per key:')
    for key in sorted(per_key, key=lambda k: (-len(per_key[k]), k)):
        lines.append('  %s: %d' % (key, len(per_key[key])))
    lines.append('If the change is intended: %s=%s' % (REGENERATE, door))
    return '\n'.join(lines)


def _record(char, identity=False):
    options = dict(read_char_blob(char.options, {}, 'options', char))
    for key in DATA_DERIVED_OPTIONS:
        options.pop(key, None)
    record = {
        'aspects': sorted(read_char_blob(char.aspects, set(), 'aspects', char)),
        'build': char.char_build,
        'minimums': read_char_blob(char.minimum_stats, {}, 'minimum_stats', char),
        'options': options,
        'weights': read_char_blob(char.stats_weight, {}, 'stats_weight', char),
    }
    if identity:
        record['class'] = char.char_class
        record['level'] = char.level
    return record


def _parsed(parsed):
    return {key: sorted(value) if isinstance(value, set) else value
            for key, value in parsed.items()}


def _version_path(version, path):
    return path if version == 'dofus3' else '/%s%s' % (version, path)


def _classes(version):
    return filter_classes_for_version(CHARACTER_CLASSES, version)


def _page(version, path):
    set_current_game_version(version)
    response = Client().get(_version_path(version, path))
    if response.status_code != 200:
        raise AssertionError('%s answered %d' % (_version_path(version, path),
                                                 response.status_code))
    return response.content.decode('utf-8')


def _script_value(page, name, until=';'):
    match = re.search(r'var %s = (.*?)%s' % (name, re.escape(until)), page, re.S)
    if match is None:
        raise AssertionError('the page no longer sets var %s' % name)
    return match.group(1).strip()


def _offered_styles(version):
    page = _page(version, '/quickstart/')
    block = re.search(r'<select[^>]*name="?play_style"?[^>]*>(.*?)</select>', page, re.S)
    if block is None:
        raise AssertionError('the quick start no longer offers a play_style list')
    return [[value, html.unescape(label.strip())] for value, label in
            re.findall(r'<option[^>]*value="?([\w-]+)"?[^>]*>(.*?)</option>',
                       block.group(1), re.S)]


def _offered_setup(version):
    page = _page(version, '/setup/')
    layout = ast.literal_eval(_script_value(page, 'aspectLayout', '.map'))
    inert = json.loads(_script_value(page, 'inertAspects'))
    labels = json.loads(_script_value(page, 'aspectToName'))
    columns = [[aspect for aspect in column if aspect not in inert]
               for column in layout]
    temporix = re.search(r'<input[^>]*name="?temporix"?[\s/>]', page) is not None
    return columns, labels, temporix


class _GoldenDoorMixin(object):
    door = None

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('golden-presets', 'golden@test.local',
                                             'pw-golden-presets-17')

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def collect(self):
        raise NotImplementedError

    def _post(self, view, version, data, *args, expected=302):
        set_current_game_version(version)
        request = RequestFactory().post('/', data)
        request.user = self.owner
        request.game_version = version
        response = view(request, *args)
        self.assertEqual(expected, response.status_code)
        return Char.objects.order_by('-id').first()

    def test_every_case_keeps_its_recorded_values(self):
        with translation.override('en'):
            current = self.collect()
        if regenerating(self.door):
            old = load_fixture(self.door) if os.path.exists(fixture_path(self.door)) else {}
            write_fixture(self.door, current)
            sys.stderr.write('\n%s written, %d cases.\n' % (fixture_path(self.door),
                                                           len(current)))
            rows = differences(old, current)
            if old and rows:
                sys.stderr.write(describe(self.door, rows, len(current)) + '\n')
            self.skipTest('%s fixture regenerated, %d changes' % (self.door, len(rows)))
        rows = differences(load_fixture(self.door), current)
        if rows:
            self.fail(describe(self.door, rows, len(current)))


class TheQuickStartKeepsItsAspectsWeightsAndMinimumsTests(_GoldenDoorMixin, TestCase):
    """Every version, class, offered style and level 50, 100, 199 and 200."""
    door = 'quick_start'

    def collect(self):
        cases = {}
        for version in VERSIONS:
            styles = _offered_styles(version)
            cases['%s offered' % version] = {'styles': styles}
            for char_class in _classes(version):
                for level in LEVELS:
                    for style, _label in styles:
                        char = self._post(coaching, version, {
                            'char_class': char_class, 'char_level': str(level),
                            'play_style': style})
                        cases['%s %s %d %s' % (version, char_class, level, style)] = \
                            _record(char)
        return cases


def _element_choices(elements):
    """Every set of element boxes the page can post; all four always come with omni."""
    singles = [aspect for aspect in elements if aspect != 'omni']
    choices = []
    for count in range(len(singles) + 1):
        for subset in itertools.combinations(singles, count):
            boxes = set(subset)
            if count == len(singles) and 'omni' in elements:
                boxes.add('omni')
            choices.append(boxes)
    return choices


def _allowed_pairs(boxes):
    return [set(pair) for pair in itertools.combinations(boxes, 2)
            if set(pair) != {'crit', 'noncrit'}]


def _boxes_name(boxes):
    return '+'.join(sorted(boxes)) or 'none'


def _pick(options, *key):
    """Rendezvous hash: a new or removed option only moves the keys that pick it."""
    seed = '|'.join(str(part) for part in key)
    return max(options, key=lambda option: hashlib.sha1(
        ('%s|%s' % (seed, option)).encode('utf-8')).hexdigest())


def _turning(version, choices, classes):
    """Each choice at each level, the class picked from the version, choice and level."""
    for boxes in choices:
        for level in LEVELS:
            yield boxes, _pick(classes, version, _boxes_name(boxes), level), level


def _spread(version, choices, classes):
    """Each choice once, the class and the level picked from the version and choice."""
    for boxes in choices:
        name = _boxes_name(boxes)
        yield boxes, _pick(classes, version, name), _pick(LEVELS, version, name, 'level')


class TheSetupPageKeepsItsAspectsWeightsAndMinimumsTests(_GoldenDoorMixin, TestCase):
    """The checkboxes /setup/ offers: elements, each box alone, with Fire, and each allowed pair."""
    door = 'setup'
    focus_column = ()

    def _form(self, char_class, level, boxes, button=None):
        data = {'project': '', 'charname': '', 'class': char_class,
                'level': str(level)}
        if button:
            data[button] = button
        for aspect in boxes:
            data['check_%s' % aspect] = 'on'
        if 'balanced' in self.focus_column and not boxes & set(self.focus_column):
            data['check_balanced'] = 'on'
        return data

    def _create(self, cases, version, char_class, level, boxes, button='wizard',
                temporix=False):
        data = self._form(char_class, level, boxes, button)
        if temporix:
            data['temporix'] = 'on'
        char = self._post(create_project, version, data)
        name = '%s %s %d %s %s%s' % (version, char_class, level, button,
                                     _boxes_name(boxes), ' temporix' if temporix else '')
        if name in cases:
            raise AssertionError('two setup cases are named %s' % name)
        cases[name] = _record(char)
        return char

    def collect(self):
        cases = {}
        fire = {'int'}
        for version in VERSIONS:
            columns, labels, temporix = _offered_setup(version)
            cases['%s offered' % version] = {'columns': columns, 'labels': labels,
                                             'temporix': temporix}
            self.focus_column = [aspect for column in columns[2:] for aspect in column]
            boxes = columns[1] + [aspect for aspect in self.focus_column
                                  if aspect != 'balanced']
            classes = _classes(version)
            choices = _element_choices(columns[0])
            for char_class in classes:
                for level in LEVELS:
                    self._create(cases, version, char_class, level, fire)
                for choice in choices:
                    if len(choice) == 1 and choice != fire:
                        self._create(cases, version, char_class, 200, choice)
            # Osamodas asks for a different summon minimum below and above level 180
            for char_class in sorted({'Osamodas', _pick(classes, version, 'bands')}
                                     & set(classes)):
                for level in BAND_LEVELS:
                    self._create(cases, version, char_class, level, fire)
            others = [choice for choice in choices if len(choice) != 1]
            for choice, char_class, level in _turning(version, others, classes):
                self._create(cases, version, char_class, level, choice)
            alone = [{aspect} for aspect in boxes]
            for choice, char_class, level in _spread(version, alone, classes):
                self._create(cases, version, char_class, level, choice)
            with_fire = [{aspect} | fire for aspect in boxes]
            for choice, char_class, level in _turning(version, with_fire, classes):
                self._create(cases, version, char_class, level, choice)
            pairs = [pair | fire for pair in _allowed_pairs(boxes)]
            for choice, char_class, level in _spread(version, pairs, classes):
                self._create(cases, version, char_class, level, choice)
            for level in LEVELS:
                self._create(cases, version, 'Iop', level, fire, 'byhand')
            if temporix:
                for button in ('wizard', 'byhand'):
                    self._create(cases, version, 'Iop', 200, fire, button, temporix=True)
            self._edits(cases, version)
        return cases

    def _edits(self, cases, version):
        for char_class, level, boxes, reapply in (('Iop', 200, {'int', 'vit'}, True),
                                                  ('Iop', 200, {'int', 'vit'}, False),
                                                  ('Cra', 100, {'int'}, True)):
            char = self._post(create_project, version,
                              self._form(char_class, 200, {'int'}, 'wizard'))
            data = self._form(char_class, level, boxes)
            if reapply:
                data['reapply'] = 'reapply'
            self._post(save_project, version, data, char.id, expected=200)
            char = Char.objects.get(id=char.id)
            moved = '' if level == 200 else ' to %d' % level
            cases['%s %s 200%s %s %s' % (version, char_class, moved,
                                         'edit_reapply' if reapply else 'edit',
                                         _boxes_name(boxes))] = _record(char)


class TheSmartBuildKeepsItsParsingAndPresetsTests(_GoldenDoorMixin, TestCase):
    """Phrases per language and every class alone: what the parser reads and the build created."""
    door = 'smart_build'

    def collect(self):
        cases = {}
        for language, phrases in sorted(SMART_BUILD_PHRASES.items()):
            for phrase in phrases:
                parsed = parse_build_request(phrase)
                cases['parse %s %s' % (language, phrase)] = _parsed(parsed)
                if not parsed['matched_class']:
                    continue
                for version in VERSIONS:
                    char = self._post(smart_build, version, {'q': phrase, 'confirm': '1'})
                    cases['%s %s %s' % (version, language, phrase)] = \
                        _record(char, identity=True)
        for char_class in CHARACTER_CLASSES:
            cases['parse class %s' % char_class] = _parsed(parse_build_request(char_class))
            char = self._post(smart_build, 'dofus3', {'q': char_class, 'confirm': '1'})
            cases['dofus3 class %s' % char_class] = _record(char, identity=True)
        return cases


class TheImportKeepsItsPresetsTests(_GoldenDoorMixin, TestCase):
    """What a pasted build receives, in every version."""
    door = 'import'

    def collect(self):
        cases = {}
        client = Client()
        client.force_login(self.owner)
        for version in VERSIONS:
            set_current_game_version(version)
            structure = get_structure(version)
            for char_class, level, types in IMPORT_CASES:
                names = []
                for type_name in types:
                    item = next(item for item in structure.types[level][type_name]
                                if not item.removed)
                    names.append(structure.get_item_name_in_language(item, 'en'))
                response = client.post(_version_path(version, '/import/text/'), {
                    'text': '\n'.join(names), 'confirm': '1',
                    'char_class': char_class, 'level': str(level)})
                self.assertEqual(302, response.status_code)
                char = Char.objects.order_by('-id').first()
                cases['%s %s %d' % (version, char_class, level)] = \
                    _record(char, identity=True)
        return cases


class TheGoldenPresetFixturesStayCompactTests(SimpleTestCase):

    def test_every_door_has_a_fixture_under_the_size_cap(self):
        total = 0
        for door in DOORS:
            with self.subTest(door=door):
                self.assertTrue(os.path.exists(fixture_path(door)))
                total += os.path.getsize(fixture_path(door))
        self.assertLess(total, MAX_FIXTURE_BYTES)

    def test_a_fixture_reads_back_as_written(self):
        cases = {'a': {'aspects': ['int'], 'build': 'Int', 'minimums': {'AP': 11},
                       'options': {'dofus': True}, 'weights': {'ap': 1, 'ch': 0, 'mp': 2.5}},
                 'b': {'aspects': [], 'build': '', 'minimums': {},
                       'options': {'dofus': True}, 'weights': {'ap': 1, 'mp': -3}},
                 'c': {'aspects': [], 'build': '', 'minimums': {},
                       'options': {}, 'weights': {'ap': 1}}}
        text = _dumps(_pack(cases))
        self.assertEqual(cases, _expand(json.loads(text)))
        self.assertEqual(text, _dumps(_pack(json.loads(json.dumps(cases)))))

    def test_a_change_names_its_case_its_key_and_both_values(self):
        old = {'dofus3 Iop 200 farm': {'weights': {'wis': 0, 'pp': 200}}}
        new = {'dofus3 Iop 200 farm': {'weights': {'wis': 500, 'pp': 200}}}
        rows = differences(old, new)
        self.assertEqual([('dofus3 Iop 200 farm', 'weights.wis', 0, 500)], rows)
        self.assertIn('dofus3 Iop 200 farm | weights.wis: 0 -> 500',
                      describe('quick_start', rows, 1))
