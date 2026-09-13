# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'en-tete de projet nomme le build comme le reste du site le nomme.

Trouve en creant un build de bout en bout, en portugais sur Retro, par les
propres pages du site. L'en-tete de projet, present sur toutes les pages d'un
projet, disait:

    Elemento  Str Glass Cannon Iop

pendant que le titre de la **meme page** disait <<Iop Forca Glass Cannon
200>>. Deux fautes dans une ligne de trois mots.

**La valeur.** L'en-tete rendait `char.char_build`, la chaine interne, quand
la liste des projets et la galerie passent toutes deux par `build_string()`,
qui la traduit. Mesure du 19 septembre 2026:

| interne | en | fr | de |
|---------|----|----|----|
| Str | Strength | Force | Starke |
| Str Glass Cannon | Strength Glass-Cannon | Force Canon de verre | Starke Glaskanone |

Faux dans les **cinq** langues, l'anglais compris, ou <<Str>> se lit
<<Strength>>.

**Le libelle.** `Build` etait traduit par <<Element>> en francais, en espagnol
et en portugais, et par <<Bauen>> en allemand, qui est le verbe construire.
Le site emploie pourtant deja le mot tel quel dans les quatre langues, dans
<<Build intelligent>>, <<Build inteligente>> et <<Intelligenter Build>>: on
suit son vocabulaire au lieu d'en inventer un.

**Deux voisins du meme en-tete, mesures dans la foulee.** L'allemand disait
<<Verkohlen>> pour `Char`, qui est le verbe carboniser: la traduction a pris
le mot pour <<to char>> et non pour l'abreviation de <<character>>. Et
<<Duplikat>>, le nom, sur un bouton place a cote de <<Bearbeiten>>, ou c'est
le verbe qu'il faut.
"""

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Ce que la page du build montre a cote du libelle, et ce que le titre de la
#: meme page dit. Les deux doivent venir de la meme source.
_EXEMPLES = ('Str', 'Int', 'Str Glass Cannon', 'Int Crit')

#: Les mots qui etaient la et qui ne disaient pas ce que la page dit. Nommes
#: pour qu'un retour en arriere se voie, avec ce qu'ils veulent dire.
_MOTS_FAUX = (
    ('Build', 'fr', 'Élément', 'element, pas build'),
    ('Build', 'es', 'Elemento', 'element, pas build'),
    ('Build', 'pt', 'Elemento', 'element, pas build'),
    ('Build', 'de', 'Bauen', 'le verbe construire'),
    ('Char', 'de', 'Verkohlen', 'le verbe carboniser'),
    ('Duplicate', 'de', 'Duplikat', 'le nom, sur un bouton'),
)


def _gabarit():
    import os
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', 'main-header.html')
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class TheHeaderShowsTheTranslatedBuildTests(SimpleTestCase):

    def test_the_header_reads_the_same_source_as_the_page_title(self):
        """L'invariant qui aurait attrape le defaut.

        Le titre passe par `WrappedChar.build_string()`. L'en-tete rendait la
        chaine interne a cote, sur la meme page.
        """
        source = _gabarit()
        self.assertIn('{{wrapped_char.build_string}}', source)
        self.assertNotIn('{{char.char_build}}', source)

    def test_the_internal_name_is_not_what_a_reader_should_see(self):
        """Sans cet ecart, la correction ne changerait rien et le test
        ci-dessus garderait une preference d'ecriture, pas un defaut."""
        from chardata.model_wrappers import translate_build_name
        identiques = []
        for brut in _EXEMPLES:
            for langue in LANGUES:
                with translation.override(langue):
                    if translate_build_name(brut) == brut:
                        identiques.append((langue, brut))
        self.assertFalse(
            identiques,
            'these internal names come out unchanged, so showing them raw '
            'would have been harmless: %s' % identiques)

    def test_every_language_names_the_build_in_its_own_words(self):
        from chardata.model_wrappers import translate_build_name
        vus = {}
        for langue in LANGUES:
            with translation.override(langue):
                vus[langue] = translate_build_name('Str Glass Cannon')
        for langue in ('fr', 'es', 'de'):
            with self.subTest(langue=langue):
                self.assertNotEqual(vus['en'], vus[langue])


class NoHeaderLabelKeepsAWordThatMeansSomethingElseTests(SimpleTestCase):

    def test_the_wrong_words_are_gone_and_stay_gone(self):
        revenus = []
        for msgid, langue, faux, _sens in _MOTS_FAUX:
            with translation.override(langue):
                if gettext(msgid) == faux:
                    revenus.append((langue, msgid, faux))
        self.assertFalse(
            revenus,
            'these labels are back to a word that means something else: %s'
            % revenus)

    def test_the_label_follows_the_word_the_site_already_uses(self):
        """<<Smart Build>> dit deja <<Build>> dans les quatre langues."""
        for langue in ('fr', 'es', 'pt', 'de'):
            with self.subTest(langue=langue):
                with translation.override(langue):
                    self.assertIn('Build', gettext('Smart Build'))
                    self.assertEqual('Build', gettext('Build'))

    def test_the_german_buttons_are_verbs_like_their_neighbour(self):
        """<<Bearbeiten>> et <<Duplizieren>> sont cote a cote sur l'en-tete."""
        with translation.override('de'):
            self.assertEqual('Bearbeiten', gettext('Edit'))
            self.assertEqual('Duplizieren', gettext('Duplicate'))
            self.assertEqual('Charakter', gettext('Char'))
