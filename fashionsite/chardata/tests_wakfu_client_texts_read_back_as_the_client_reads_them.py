import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import get_wakfu_client  # noqa: E402
import wakfu_client  # noqa: E402

BS = chr(92)


def esc(text):
    """Write `\\` as the properties escape: every '@' in the text stands for a backslash."""
    return text.replace('@', BS)


# One file holding every rule of java.util.Properties.load that the client relies on. A
# line ends at CRLF, CR or LF; '@' stands for a backslash.
LINES = (
    ('# a comment', '\r\n'),
    ('! another comment', '\r'),
    (esc('content.3.1=Line@none@ttab @u00e9'), '\n'),
    ('content.3.2=trail   ', '\r\n'),
    ('content.3.3 =   spaced', '\r'),
    ('content.3.4:colon', '\n'),
    ('content.3.5 space value', '\r\n'),
    (esc('content.3.6=@ lead'), '\n'),
    (esc('content.3.7=a@:b@=c'), '\n'),
    (esc('content.3.8=one@'), '\n'),
    ('      two', '\n'),
    (esc('content.3.9=end@@'), '\n'),
    ('content.3.10=next', '\n'),
    ('content.3.11=first', '\n'),
    ('content.3.11=second', '\n'),
    ('content.3.-1=ignored', '\n'),
    ('content.35.7=not a family', '\n'),
    ('content.4.1=Jalat\u00f3', '\n'),
    ('critere.target= (cible)', '\n'),
    (esc('nation.short.3=Br@u00e2kmar'), '\n'),
    ('nation.short.x=not a number', '\n'),
)


def properties(lines=LINES):
    return ''.join(text + end for text, end in lines).encode('utf-8')


def write_jar(path, language, body):
    with zipfile.ZipFile(path, 'w') as jar:
        jar.writestr('texts_%s.properties' % language, body)


def expected_texts(**families):
    out = {family: {} for family in wakfu_client.TEXT_FAMILIES}
    out.update(families)
    return out


class TheWakfuClientTextsReadBackAsTheClientReadsThemTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.jar = self.directory / 'i18n_fr.jar'
        write_jar(self.jar, 'fr', properties())

    def test_every_rule_of_the_java_properties_reader_is_applied(self):
        self.assertEqual(expected_texts(
            spell_names={
                1: 'Line\none\ttab \u00e9', 2: 'trail   ', 3: 'spaced', 4: 'colon',
                5: 'space value', 6: ' lead', 7: 'a:b=c', 8: 'onetwo', 9: 'end' + BS,
                10: 'next', 11: 'second'},
            spell_descriptions={1: 'Jalat\u00f3'}),
            wakfu_client.read_texts(self.jar, 'fr'))

    def test_the_key_and_the_value_are_not_stripped_beyond_the_rules(self):
        body = properties((
            ('  content.3.1  =  value  ', '\n'),
            ('content.3.2\t\tvalue\t', '\n'),
            ('content.3.3=', '\n'),
            ('content.3.4', '\n')))
        write_jar(self.jar, 'fr', body)
        self.assertEqual({1: 'value  ', 2: 'value\t', 3: '', 4: ''},
                         wakfu_client.read_texts(self.jar, 'fr')['spell_names'])

    def test_the_families_are_the_eleven_the_client_numbers(self):
        self.assertEqual(
            {'spell_names': 3, 'spell_descriptions': 4, 'monster_names': 7,
             'state_names': 8, 'state_descriptions': 9, 'action_texts': 10,
             'set_names': 20, 'effect_texts': 33, 'monster_family_names': 38,
             'ability_names': 146, 'ability_category_names': 147},
            wakfu_client.TEXT_FAMILIES)

    def test_the_labels_drop_the_leading_space_of_a_value_and_read_the_nations(self):
        labels, nations = wakfu_client.read_labels(self.jar, 'fr')
        self.assertEqual({'critere.target': '(cible)'}, labels)
        self.assertEqual({3: 'Br\u00e2kmar'}, nations)

    def test_a_jar_without_the_language_file_stops_the_read(self):
        other = self.directory / 'other.jar'
        with zipfile.ZipFile(other, 'w') as jar:
            jar.writestr('texts_en.properties', b'content.3.1=x')
        with self.assertRaisesRegex(wakfu_client.TableError, 'has no entry texts_fr'):
            wakfu_client.read_texts(other, 'fr')
        with self.assertRaisesRegex(wakfu_client.TableError, 'has no entry texts_fr'):
            wakfu_client.read_labels(other, 'fr')

    def test_a_file_that_is_not_a_jar_stops_the_read(self):
        plain = self.directory / 'plain.jar'
        plain.write_text('not a jar')
        with self.assertRaisesRegex(wakfu_client.TableError, 'is not a jar'):
            wakfu_client.read_texts(plain, 'fr')
        with self.assertRaisesRegex(wakfu_client.TableError, 'is not a jar'):
            wakfu_client.read_labels(plain, 'fr')

    def test_a_malformed_unicode_escape_stops_the_read(self):
        write_jar(self.jar, 'fr', esc('content.3.1=@u12').encode('utf-8'))
        with self.assertRaisesRegex(wakfu_client.TableError, 'unicode escape'):
            wakfu_client.read_texts(self.jar, 'fr')

    def test_the_texts_of_the_four_languages_are_decoded_by_family_and_id(self):
        for language in get_wakfu_client.LANGUAGES:
            body = properties((('content.8.21=%s name' % language, '\n'),
                               ('content.9.21=%s text' % language, '\n')))
            write_jar(self.directory / ('i18n_%s.jar' % language), language, body)
        payload = get_wakfu_client.decode_texts(self.directory, '6.0_1.93.1.5312.334')
        self.assertEqual('1.93.1', payload['game_version'])
        self.assertEqual('6.0_1.93.1.5312.334', payload['client_version'])
        self.assertEqual(set(wakfu_client.TEXT_FAMILIES), set(payload['texts']))
        self.assertEqual(
            {language: {'21': language + ' name'} for language in get_wakfu_client.LANGUAGES},
            payload['texts']['state_names'])
        self.assertEqual({'21': 'es text'}, payload['texts']['state_descriptions']['es'])
        self.assertEqual({}, payload['texts']['set_names']['pt'])

    def test_a_decoded_folder_without_texts_json_is_not_current(self):
        folder = self.directory / 'client'
        folder.mkdir()
        (folder / 'decoded.json').write_text(
            json.dumps({'files': {'a.jar': {'sha1': 'x'}}}), encoding='utf-8')
        (folder / 'tables.json').write_text('{}', encoding='utf-8')
        self.assertFalse(get_wakfu_client.is_current(folder, {'a.jar': 'x'}))
        (folder / 'texts.json').write_text('{}', encoding='utf-8')
        self.assertTrue(get_wakfu_client.is_current(folder, {'a.jar': 'x'}))
        self.assertFalse(get_wakfu_client.is_current(folder, {'a.jar': 'y'}))
