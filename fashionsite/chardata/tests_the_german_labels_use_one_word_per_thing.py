# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Chaque notion que le lecteur allemand voit porte un seul mot.

Trouve en parcourant le site en allemand, page par page, depuis ses propres
liens. Dix-huit entrees corrigees, reparties sur dix contradictions qui se
lisaient a l'ecran, chaque fois entre deux elements **voisins**, ce qui est
la seule forme de ce defaut qu'un lecteur peut remarquer:

| ou | ce qui etait ecrit | a cote de |
|----|--------------------|-----------|
| menu d'un projet | <<Elemente sperren>> | <<Gegenstande verbieten>>, lien suivant |
| boutons des sorts | <<Vollstandig poliert>> | <<Saubere Buffs>>, bouton colle a sa droite |
| page de creation | <<Charakterebene>> | <<Charaktername>> et <<Charakterklasse>> |
| builds partages | <<Min. Level>>, <<Max. Level>> | <<Stufe:>> sur chaque carte de la meme page |
| bandeau | <<Satze vergleichen>> | <<Wahlen Sie Sets zum Vergleichen aus>>, titre de la page ou il mene |
| page A propos | onglet <<Um>>, une preposition | <<Hilfe und Info>>, le h1 de la meme page |
| FAQ, tableau | <<Punkt A>> | <<wie viele Punkte ... wert ist>>, ou Punkte sont des points de score |
| FAQ, phrase | <<Ausrustung A ... Punkt A>> | dans **une seule phrase** |
| FAQ, phrase | <<Ausrustung A ... Element B>> | dans **une seule phrase** |
| page infeasible | <<ein Element ... gesperrt>> | <<einige Gegenstande>>, la puce suivante |

**Le mot retenu n'est pas une preference.** C'est celui que le catalogue
allemand emploie deja le plus pour cette notion, compte fait le 20 septembre
2026 sur les 1425 entrees traduites, en ne comptant que les entrees dont le
msgid **anglais** porte la notion:

| notion | mot retenu, avant -> apres | concurrents, avant -> apres |
|--------|---------------------------|-----------------------------|
| item | Gegenstand, 82 -> 87 | Punkt 4 -> 2, Element 4 -> 0 |
| level | Stufe, 23 -> 26 | Ebene 1 -> 0 |
| set | Set, 114 -> 120 | Satze 3 -> 0 |
| buff | Buff, 10 -> 11 | poliert 1 -> 0 |

Les deux <<Punkt>> qui restent sont les deux phrases de la FAQ ou le mot dit
bien un point de score; voir la mesure grossiere plus bas.

**L'exception est nommee et mesuree.** Neuf entrees de prose gardent
<<Level>>, parce que c'est le mot allemand courant en langue courante:
<<dein Level>>, <<Level 200>>, <<Farmen / Leveln>>. Aucune n'est un libelle
de controle: la plus courte fait six mots, et la regle ci-dessous porte sur
les libelles de cinq mots au plus, ou elle tient sans une seule exception.

**Une mesure grossiere mentirait ici.** Chercher la sous-chaine <<Punkt>>
dans la FAQ attrape <<Punkte>> et <<Punktzahl>>, qui disent bien des points
de score. Les tests visent donc le referent (<<Punkt A>>) et non le mot seul.

Les traductions sont lues par `gettext`, donc dans le catalogue **compile**:
un `.po` corrige mais non recompile ne passe pas plus qu'un `.po` fautif.
"""

import io
import os
import re

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext

#: Notion -> (le mot retenu, son compte apres le lot, les mots ecartes avec
#: leur compte **avant** le lot, qui est ce qui en faisait la minorite).
#: Le compte retenu est un plancher exact: si l'un de ces mots recule, c'est
#: que la regle est en train de se defaire, et il faut le regarder.
_NOTIONS = {
    'item': ('Gegenst', 87, {'Punkt': 4, 'Element': 4}),
    'level': ('Stufe', 26, {'Ebene': 1}),
    'set': ('Set', 120, {'Sätz': 3}),
    'buff': ('Buff', 11, {'poliert': 1}),
}

#: Au-dela de cinq mots un msgid n'est plus un libelle mais une phrase, ou
#: <<Level>> est le mot allemand courant. La frontiere est mesuree:
#: `test_the_five_word_boundary_is_where_the_rule_stops` la tient.
_LONGUEUR_LIBELLE = 5

#: Les voisinages ou la contradiction se lisait. Chaque paire est deux
#: elements que le lecteur voit en meme temps.
_VOISINS = (
    ('Lock Items', 'Forbid Items', 'Gegenst', 'le menu d\'un projet'),
    ('Fully Buff', 'Clean Buffs', 'Buff', 'les deux boutons des sorts'),
    ('Character Level', 'Character Name', 'Charakter', 'la page de creation'),
    ('Character Level', 'Character Class', 'Charakter', 'la page de creation'),
    ('Min Level', 'Max Level', 'Stufe', 'les filtres des builds partages'),
    ('Compare sets', 'Choose sets to compare', 'Set', 'le bandeau'),
)

#: Ce qui etait ecrit, et ce que cela voulait dire. Nomme pour qu'un retour
#: en arriere se lise au lieu de repasser inapercu.
_MOTS_FAUX = (
    ('About', 'Um', 'une preposition: autour de, vers'),
    ('Item A', 'Punkt A', 'un point, comme un point de score'),
    ('Item B', 'Punkt B', 'un point, comme un point de score'),
    ('Lock Items', 'Elemente sperren', 'element, pas objet'),
    ('Character Level', 'Charakterebene', 'ebene: un plan, une couche'),
    ('Min Level', 'Min. Level', 'la meme page dit Stufe sur chaque carte'),
    ('Max Level', 'Max. Level', 'la meme page dit Stufe sur chaque carte'),
    ('Compare sets', 'Sätze vergleichen', 'satz: une phrase, un jeu'),
    ('Compare Sets', 'Sätze vergleichen', 'satz: une phrase, un jeu'),
    ('Change Sets', 'Änderungssätze', 'un nom compose sur un bouton'),
    ('Fully Buff', 'Vollständig poliert', 'poliert: poli, lustre'),
)

#: La phrase dont le lien ne doit porter que le verbe, comme dans les trois
#: autres langues. <<freischalten>> etant un verbe a particule separable, la
#: traduction avait enferme la phrase entiere dans le lien.
_PHRASE_DU_LIEN = '<a href=%(lock_link)s>Unlock</a> some items'

_ENTREE = re.compile(r'(?m)^msgid ((?:"[^\n]*"\n)+)msgstr ((?:"[^\n]*"\n?)+)')


def _catalogue(langue):
    """[(msgid, msgstr)] du .po, msgid tel que le code le demande."""
    chemin = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'locale', langue, 'LC_MESSAGES', 'django.po')
    with io.open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()
    entrees = []
    for bloc in _ENTREE.finditer(contenu):
        msgid = ''.join(re.findall(r'"([^\n]*)"', bloc.group(1)))
        msgstr = ''.join(re.findall(r'"([^\n]*)"', bloc.group(2)))
        if msgid and msgstr:
            entrees.append((msgid, msgstr))
    return entrees


def _traduit(msgid):
    """Ce que le lecteur recoit vraiment, donc le catalogue compile."""
    with translation.override('de'):
        return gettext(msgid)


class EveryGermanLabelUsesTheWordTheSiteAlreadyUsesTests(SimpleTestCase):

    def test_no_short_label_names_a_thing_the_site_names_otherwise(self):
        """Le test qui aurait attrape les onze libelles."""
        ecarts = []
        for msgid, _ in _catalogue('de'):
            if len(msgid.split()) > _LONGUEUR_LIBELLE:
                continue
            for notion, (retenu, _n, ecartes) in _NOTIONS.items():
                if notion not in msgid.lower():
                    continue
                rendu = _traduit(msgid)
                if retenu.lower() in rendu.lower():
                    continue
                for mauvais in ecartes:
                    if mauvais.lower() in rendu.lower():
                        ecarts.append((msgid, rendu, notion, retenu))
                        break
        self.assertEqual(
            [], ecarts,
            'these German labels name a thing with a word the site does not '
            'use for it: %s' % ecarts)

    def test_the_chosen_word_dominates_the_ones_set_aside(self):
        """Le plancher qui rend le test ci-dessus autre chose qu'un gout.

        Il tenait deja **avant** le lot, et c'est ce qui le rend utile: le
        mot retenu etait deja celui du site (82 contre 4 pour item, 23 contre
        1 pour level), donc corriger les ecarts suivait le vocabulaire au
        lieu d'en imposer un.
        """
        entrees = _catalogue('de')
        for notion, (retenu, _stamp, ecartes) in _NOTIONS.items():
            with self.subTest(notion=notion):
                compte = len([1 for msgid, msgstr in entrees
                              if notion in msgid.lower()
                              and retenu.lower() in msgstr.lower()])
                for mauvais in ecartes:
                    reste = len([1 for msgid, msgstr in entrees
                                 if notion in msgid.lower()
                                 and retenu.lower() not in msgstr.lower()
                                 and mauvais.lower() in msgstr.lower()])
                    self.assertGreater(
                        compte, reste * 5,
                        '%r no longer clearly dominates %r for %r (%d against '
                        '%d)' % (retenu, mauvais, notion, compte, reste))

    def test_the_recorded_counts_are_the_ones_measured(self):
        """L'estampille de la mesure du 20 septembre 2026.

        Elle tombe si l'un des mots retenus recule, ce que mon propre travail
        ulterieur est le plus a meme de provoquer.
        """
        entrees = _catalogue('de')
        for notion, (retenu, attendu, _ecartes) in _NOTIONS.items():
            with self.subTest(notion=notion):
                compte = len([1 for msgid, msgstr in entrees
                              if notion in msgid.lower()
                              and retenu.lower() in msgstr.lower()])
                self.assertGreaterEqual(
                    compte, attendu,
                    '%r was measured %d times for %r and is now used %d '
                    'times' % (retenu, attendu, notion, compte))

    def test_the_rule_covers_enough_labels_to_prove_something(self):
        """La regle porte-t-elle encore sur quelque chose?

        Elle s'arrete a cinq mots, et une frontiere peut se vider sans que
        rien ne casse: si le catalogue evoluait au point qu'il ne reste que
        deux libelles sous la barre, les tests ci-dessus passeraient en ne
        mesurant plus rien. Que les entrees au-dela soient bien de la prose
        est garde separement, par le test de l'exception idiomatique.
        """
        entrees = _catalogue('de')
        sous_la_frontiere = [
            msgid for msgid, _ in entrees
            if len(msgid.split()) <= _LONGUEUR_LIBELLE
            and any(n in msgid.lower() for n in _NOTIONS)]
        self.assertGreaterEqual(
            len(sous_la_frontiere), 30,
            'the rule now covers almost nothing, so it proves nothing: %d '
            'labels' % len(sous_la_frontiere))

    def test_the_prose_that_keeps_Level_is_prose_and_is_counted(self):
        """L'exception est nommee, et son compte est garde.

        <<Level>> reste dans la prose parce que c'est le mot courant. Si
        cette liste enflait, la regle serait en train d'etre contournee
        plutot que respectee.
        """
        prose = [msgid for msgid, msgstr in _catalogue('de')
                 if 'level' in msgid.lower()
                 and 'Stufe' not in msgstr and 'Level' in msgstr]
        self.assertTrue(prose, 'the idiomatic exception vanished entirely')
        courts = [m for m in prose if len(m.split()) <= _LONGUEUR_LIBELLE]
        self.assertEqual(
            [], courts,
            'these are control labels, not prose, so they may not claim the '
            'idiomatic exception: %s' % courts)
        self.assertLessEqual(
            len(prose), 9,
            'the idiomatic exception was 9 entries and is now %d; the rule '
            'is being worked around' % len(prose))


class NoLabelKeepsAWordThatMeansSomethingElseTests(SimpleTestCase):

    def test_the_wrong_words_are_gone_and_stay_gone(self):
        revenus = [(msgid, faux, sens) for msgid, faux, sens in _MOTS_FAUX
                   if _traduit(msgid) == faux]
        self.assertEqual(
            [], revenus,
            'these labels are back to a word that says something else: %s'
            % revenus)

    def test_the_faq_never_calls_an_item_a_score_point(self):
        """La FAQ compte des points juste au-dessus de son tableau, donc le
        mot <<Punkt>> y est pris. Viser la sous-chaine attraperait
        <<Punkte>>; on vise le referent."""
        fautifs = []
        for msgid, _ in _catalogue('de'):
            rendu = _traduit(msgid)
            if re.search(r'\b(Punkt|Element) [AB]\b', rendu):
                fautifs.append((msgid[:60], rendu[:80]))
        self.assertEqual(
            [], fautifs,
            'these say Punkt A or Element A where the table says Gegenstand '
            'A: %s' % fautifs)


class TwoThingsSeenTogetherUseTheSameWordTests(SimpleTestCase):

    def test_neighbouring_labels_agree_on_the_word(self):
        """Le seul defaut qu'un lecteur peut voir: deux mots pour une meme
        notion, sur un ecran qui les montre ensemble."""
        desaccords = []
        for gauche, droite, mot, ou in _VOISINS:
            rg, rd = _traduit(gauche), _traduit(droite)
            if mot.lower() not in rg.lower() or mot.lower() not in rd.lower():
                desaccords.append((ou, gauche, rg, droite, rd, mot))
        self.assertEqual(
            [], desaccords,
            'these labels sit side by side and name the same thing with two '
            'words: %s' % desaccords)

    def test_the_neighbours_really_are_translated_apart(self):
        """Sans cela le test ci-dessus passerait sur des chaines identiques
        et ne garderait rien."""
        identiques = [(g, d) for g, d, _mot, _ou in _VOISINS
                      if _traduit(g) == _traduit(d)]
        self.assertEqual(
            [], identiques,
            'these pairs render the same string, so agreeing proves nothing: '
            '%s' % identiques)


class TheLinkCoversTheVerbOnlyTests(SimpleTestCase):

    def test_every_language_links_the_verb_and_not_the_sentence(self):
        """L'anglais ne met que <<Unlock>> dans le lien. Trois langues sur
        quatre le suivaient; l'allemand enfermait la phrase entiere."""
        trop_larges = []
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(langue):
                rendu = gettext(_PHRASE_DU_LIEN)
            lien = re.search(r'<a href=[^>]*>(.*?)</a>(.*)', rendu)
            self.assertIsNotNone(
                lien, '%s lost the link entirely: %r' % (langue, rendu))
            if not lien.group(2).strip():
                trop_larges.append((langue, rendu))
        self.assertEqual(
            [], trop_larges,
            'these languages put the whole sentence inside the link, so the '
            'reader cannot tell what the link does: %s' % trop_larges)
