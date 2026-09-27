import os
import sys

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.append(SCRAPER)
import get_spells_wakfu as harvest  # noqa: E402


def picto(name):
    return ('<span class="picto"><img src="http://staticns.ankama.com/wakfu/'
            'portal/game/element/%s.png" /></span>' % name)


# Label before the element in French, Spanish and Portuguese, after it in English
ROW = {
    'fr': 'Dommage %s : {value}' % picto('FIRE'),
    'en': '%s %s Damage: {value}' % (picto('enemy'), picto('FIRE')),
    'es': 'Daños %s : {value}' % picto('FIRE'),
    'pt': 'Dano de %s : {value}' % picto('FIRE'),
}
NORMAL = {'fr': 'Effets normaux', 'en': 'Normal Effects',
          'es': 'Efectos normales', 'pt': 'Efeitos normais'}
STATE = {'fr': 'Effets si', 'en': 'Effects if',
         'es': 'Efectos si', 'pt': 'Efeitos se'}
AREAS = {
    'fr': ('En zone carré %s :' % picto('SQUARE'), 'En zone croix :',
           'En cercle de taille 2 :', 'En ligne verticale de taille 5 :',
           'Sur le chemin (ligne de 3) :', 'Sur le chemin :'),
    'en': ('In a square %s area of effect:' % picto('SQUARE'),
           'In a cross area of effect:', 'In a 2-cell circle:',
           'In a 5-cell vertical line:', 'Along the path (3-cell line):',
           'Along the path:'),
    'es': ('En zona de cuadrado :', 'En zona de cruz:',
           'En círculo de tamaño 2:', 'En línea vertical de tamaño 5:',
           'En el camino (línea de 3):', 'En el camino:'),
    'pt': ('Em uma zona quadrada :', 'Em zona de cruz:',
           'Em um círculo de tamanho 2:', 'Em linha vertical de tamanho 5:',
           'No caminho (linha de 3):', 'No caminho:'),
}
CONDITIONS = {
    'fr': ('Lancé sur ennemi :', 'Par Portail dans la zone (max 2) :',
           "Si le Sacrieur possède de l'Armure :"),
    'en': ('Cast on an enemy:', 'Per portal in the area (max 2):',
           'If a is in the area of effect:'),
    'es': ('Lanzado sobre enemigo:', 'Por portal en la zona (máx. 2):'),
    'pt': ('Quando lançado em um inimigo:', 'Por portal na zona (máx. 2):'),
}


def row(language, value):
    return ROW[language].format(value=value)


def flags(markup):
    return [conditional for _label, _element, _value, _unit, conditional
            in harvest.effect_rows(markup)]


class AWakfuSpellRowUnderAStateHeadingLandsOnlyInThatStateTests(SimpleTestCase):

    def test_a_row_under_the_state_heading_is_conditional_and_one_before_is_not(self):
        for language in ROW:
            with self.subTest(language=language):
                markup = '%s\n%s\n\n%s <span class="ak-linker">Berserk</span>\n%s' % (
                    NORMAL[language], row(language, 26),
                    STATE[language], row(language, 83))
                self.assertEqual([False, True], flags(markup))

    def test_the_last_heading_decides(self):
        for language in ROW:
            with self.subTest(language=language):
                markup = '%s Berserk\n%s\n%s\n%s' % (
                    STATE[language], row(language, 83),
                    NORMAL[language], row(language, 26))
                self.assertEqual([True, False], flags(markup))

    def test_a_heading_glued_to_the_word_before_it_still_counts(self):
        for language in ROW:
            with self.subTest(language=language):
                markup = 'Armure<b>%s</b> Berserk\n%s' % (
                    STATE[language], row(language, 83))
                self.assertEqual([True], flags(markup))

    def test_the_same_words_inside_a_word_are_no_heading(self):
        self.assertEqual([False], flags('SideEffects if\n%s' % row('en', 83)))


class AWakfuSpellRowUnderAnAreaHeadingLandsOnEveryCastTests(SimpleTestCase):

    def test_an_area_heading_is_no_condition(self):
        for language, headings in sorted(AREAS.items()):
            for heading in headings:
                with self.subTest(language=language, heading=heading):
                    markup = '%s\n    - %s\n    - 20 Armure' % (
                        heading, row(language, 130))
                    self.assertEqual([False], flags(markup))

    def test_a_condition_heading_still_is_one(self):
        for language, headings in sorted(CONDITIONS.items()):
            for heading in headings:
                with self.subTest(language=language, heading=heading):
                    markup = '%s\n    - %s' % (heading, row(language, 121))
                    self.assertEqual([True], flags(markup))

    def test_a_condition_after_an_area_is_still_a_condition(self):
        markup = 'En zone croix :\n    - %s\nPar cible touchée :\n    - %s' % (
            row('fr', 55), row('fr', 20))
        self.assertEqual([False, True], flags(markup))
