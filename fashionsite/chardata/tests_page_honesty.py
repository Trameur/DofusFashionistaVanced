# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Ce que les pages affirment doit tenir face au code qui est en dessous.

Deux affirmations sont gardees ici, parce que toutes deux etaient fausses et
qu'aucune n'aurait pu etre attrapee en relisant la page: il fallait aller voir
ailleurs. Un garde-fou qui ne lit que la phrase ne verifie que l'orthographe.
"""
import os
import re

from django.test import SimpleTestCase

_ICI = os.path.dirname(os.path.abspath(__file__))
_GABARITS = os.path.join(_ICI, 'templates', 'chardata')


def _lit(*morceaux):
    with open(os.path.join(*morceaux), encoding='utf-8') as f:
        return f.read()


#: Un lien Discord et le texte visible du bouton qui le porte.
_INVITATION = re.compile(
    r'<a\b[^>]*href\s*=\s*[\'"][^\'"]*discord\.gg/([A-Za-z0-9]+)[^\'"]*'
    r'[\'"][^>]*>(.*?)</a>', re.I | re.S)

#: Ou mene chaque invitation ecrite sur le site.
#:
#: Mesure faite le 10 septembre 2026 sur l'API de Discord, pas sur une
#: supposition: rien dans un code d'invitation ne dit ou il mene.
#:
#:   J842fFxU7r -> guilde "dofus fashionista", 1188892643766321173, 101 membres
#:   a7b4a4dnVU -> guilde "dofusdude",         1012966571959910502, 221 membres
#:
#: La notre est celle que le bot du depot lit deja
#: (`discordbot/index_contributions.py`, GUILD = 1188892643766321173) et celle
#: que les annonces de docs/marketing donnent, dix fois.
_GUILDE = {
    'J842fFxU7r': 'fashionista',
    'a7b4a4dnVU': 'dofusdude',
}

#: Celles qui sont a nous.
_A_NOUS = {'J842fFxU7r'}


class EveryDiscordLinkSaysWhoseServerItIsTests(SimpleTestCase):
    """Pointer vers le serveur d'un tiers n'est pas une faute; le faire passer
    pour le sien en est une.

    `support.html` disait <<or join our Discord>> et menait chez dofusdude:
    quelqu'un qui venait signaler un bug du site atterrissait ailleurs. Le
    pied de page, lui, propose les deux serveurs et ecrit le nom de chacun sur
    son bouton, ce qui est exact et doit le rester. La regle n'est donc pas
    <<aucun lien vers un tiers>>, c'est <<un bouton qui ne dit pas chez qui il
    mene doit mener chez nous>>.
    """

    def _invitations(self):
        trouve = []
        for dossier, _sous, fichiers in os.walk(_GABARITS):
            for f in fichiers:
                if not f.endswith('.html'):
                    continue
                for m in _INVITATION.finditer(_lit(dossier, f)):
                    etiquette = re.sub(r'<[^>]*>', ' ', m.group(2))
                    trouve.append((f, m.group(1), ' '.join(etiquette.split())))
        return trouve

    def test_the_scan_actually_finds_the_invites(self):
        """Le plancher du temoin: sans invitation trouvee, tout est vert.

        Quatre liens le 10 septembre 2026, dans base.html (deux), contacts.html
        et support.html.
        """
        trouve = self._invitations()
        self.assertGreaterEqual(
            len(trouve), 4,
            'only %d Discord links found; the scan is too narrow to be '
            'guarding anything' % len(trouve))

    def test_every_invite_leads_somewhere_we_have_measured(self):
        inconnues = sorted(set(code for _f, code, _e in self._invitations()
                               if code not in _GUILDE))
        self.assertFalse(
            inconnues,
            'nobody checked where these invites lead, and an invite code does '
            'not say: %s' % inconnues)

    def test_no_unlabelled_button_sends_readers_to_a_third_party(self):
        trompeuses = []
        for fichier, code, etiquette in self._invitations():
            if code in _A_NOUS:
                continue
            if _GUILDE[code].lower() not in etiquette.lower():
                trompeuses.append((fichier, code, etiquette))
        self.assertFalse(
            trompeuses,
            'these lead to a third-party guild without naming it, so a reader '
            'takes them for ours: %s' % trompeuses)


#: Ce qu'un compte debloque vraiment, et ou le verifier.
#:
#: La FAQ repondait qu'un compte <<ONLY lets you save your projects and share
#: them with a link>>. Il y avait bien plus derriere `@login_required`, et
#: repondre moins que la verite est une facon curieuse de vendre un compte.
_DERRIERE_UN_COMPTE = {
    'inventory': ('inventory_view.py', 'inventory'),
    'workshop': ('workshop_view.py', 'workshop'),
    'comments': ('comment_view.py', 'post_comment'),
    'votes': ('shared_builds_view.py', 'vote_build'),
    'tags': ('tag_view.py', 'add_tag'),
    'following': ('profile_view.py', 'follow_user'),
}


class TheFaqDescribesWhatAnAccountReallyUnlocksTests(SimpleTestCase):

    def _reponse(self):
        """Le paragraphe de la FAQ qui parle du compte."""
        for ligne in _lit(_GABARITS, 'faq.html').split('\n'):
            if 'An account' in ligne:
                return ligne
        return ''

    def test_each_named_feature_really_is_behind_a_login(self):
        """L'autre moitie du garde: la FAQ ne doit pas non plus promettre
        qu'un compte debloque une chose qui est deja ouverte a tous."""
        ouvertes = []
        for nom, (module, fonction) in sorted(_DERRIERE_UN_COMPTE.items()):
            source = _lit(_ICI, module)
            motif = re.compile(
                r'@login_required[^\n]*\n(?:\s*@[^\n]*\n)*\s*def\s+%s\s*\('
                % re.escape(fonction))
            if not motif.search(source):
                ouvertes.append((nom, module, fonction))
        self.assertFalse(
            ouvertes,
            'the FAQ says an account unlocks these but they are not behind '
            '@login_required: %s' % ouvertes)

    def test_the_faq_does_not_undersell_the_account(self):
        reponse = self._reponse().lower()
        self.assertTrue(reponse, 'the account answer disappeared from the FAQ')
        muettes = [nom for nom in sorted(_DERRIERE_UN_COMPTE)
                   if nom not in reponse]
        self.assertFalse(
            muettes,
            'an account unlocks these and the FAQ never mentions them: %s'
            % muettes)

    def test_the_faq_no_longer_says_an_account_does_only_that(self):
        self.assertNotIn('account only lets you', self._reponse().lower())


#: La meta description de la page <<build en une phrase>>, telle qu'elle est
#: ecrite dans le gabarit. Elle donne un exemple entre parentheses, et un
#: exemple donne par le site doit marcher sur le site.
#:
#: Elle proposait <<with 11 AP>>. Aucun aspect de PA n'existe dans
#: ALL_ASPECTS_LIST (`aprape` et `mprape` sont le RETRAIT de PA, pas un
#: objectif), donc le nombre etait ignore sans un mot. Pire, la phrase entiere
#: partait en build de farm, parce que `level` est un mot-cle de farm et que
#: <<level 200>> le declenchait: mesure du 10 septembre 2026, {'wis', 'pp'} au
#: lieu de {'glasscannon', 'agi'}, element demande jete. Le parseur est
#: corrige, l'exemple aussi.
_META_PHRASE = (
    'Describe your Dofus build in plain words (like an agility Sram level 200 '
    'for PvP), and get a full optimized set in seconds with the '
    'Fashionista\u2019s smart build.')

_ENTRE_PARENTHESES = re.compile(r'\(([^)]*)\)')


class TheSmartBuildExampleActuallyParsesTests(SimpleTestCase):
    """Dans les cinq langues, et pas seulement en anglais.

    Le test lit la traduction compilee, donc il couvre aussi le cas ou une
    entree `fuzzy` ferait retomber la page en anglais: l'exemple francais
    serait alors la phrase anglaise, et il devrait tout de meme s'analyser.
    Ce qu'il attrape, c'est un exemple qu'on aurait reecrit a la main dans une
    seule langue sans le repasser au parseur.
    """

    def test_the_template_still_carries_the_phrase_the_guard_checks(self):
        """Sinon le test suivant garderait une chaine que plus rien n'affiche."""
        self.assertIn(_META_PHRASE, _lit(_GABARITS, 'smart_build.html'))

    def test_every_translation_of_the_example_parses_completely(self):
        from django.utils import translation
        from chardata.nl_parser import parse_build_request

        incompris = []
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(langue):
                phrase = translation.gettext(_META_PHRASE)
            trouve = _ENTRE_PARENTHESES.search(phrase)
            self.assertTrue(trouve, (langue, phrase[:60]))
            exemple = trouve.group(1)
            lu = parse_build_request(exemple)
            for quoi in ('matched_class', 'matched_level', 'matched_element',
                         'matched_style'):
                if not lu[quoi]:
                    incompris.append((langue, exemple, quoi))
        self.assertFalse(
            incompris,
            'the page offers these examples and its own parser does not '
            'understand them: %s' % incompris)

    def test_the_example_is_not_silently_turned_into_a_farm_build(self):
        """La regression precise, dans les cinq langues.

        `farm` n'ajoute pas l'element demande: un lecteur qui ecrit <<agility
        Sram>> recevait de la sagesse et de la prospection.
        """
        from django.utils import translation
        from chardata.nl_parser import parse_build_request

        detournes = []
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(langue):
                phrase = translation.gettext(_META_PHRASE)
            exemple = _ENTRE_PARENTHESES.search(phrase).group(1)
            lu = parse_build_request(exemple)
            if lu['style'] == 'farm' or lu['element'] not in lu['aspects']:
                detournes.append((langue, exemple, lu['style'],
                                  sorted(lu['aspects'])))
        self.assertFalse(
            detournes,
            'these lose the element the reader asked for: %s' % detournes)


class StatingALevelIsNotAskingToLevelUpTests(SimpleTestCase):
    """`level` sert deux fois: <<level 200>> et <<I want to level up>>.

    Le second est bien du farm. Le premier est la facon la plus courante
    d'annoncer un niveau, et il basculait tout le build. Les deux sens doivent
    survivre, sinon corriger l'un casse l'autre en silence.
    """

    def _lu(self, phrase):
        from chardata.nl_parser import parse_build_request
        return parse_build_request(phrase)

    def test_a_stated_level_leaves_the_style_alone(self):
        for phrase in ('an agility Sram level 200',
                       'un Sram agilite niveau 200',
                       'Iop lvl 150',
                       'ein Agi-Sram Stufe 200'):
            with self.subTest(phrase=phrase):
                lu = self._lu(phrase)
                self.assertEqual(lu['style'], 'solo_pvm', lu)
                self.assertNotIn('pp', lu['aspects'], lu)
                self.assertNotIn('wis', lu['aspects'], lu)

    def test_really_asking_to_level_is_still_a_farm_build(self):
        for phrase in ('I want to level up', 'xp 200', 'level 200 farm',
                       'prospection 200', 'sagesse niveau 200'):
            with self.subTest(phrase=phrase):
                self.assertEqual(self._lu(phrase)['style'], 'farm', phrase)

    def test_a_stated_level_is_still_read_as_the_level(self):
        """Le correctif retire le mot du texte de style. Il ne doit pas
        retirer le niveau lui-meme."""
        for phrase, attendu in (('an agility Sram level 200', 200),
                                ('un Sram agilite niveau 175', 175),
                                ('Iop lvl 150', 150)):
            with self.subTest(phrase=phrase):
                lu = self._lu(phrase)
                self.assertEqual(lu['level'], attendu, lu)
                self.assertTrue(lu['matched_level'], lu)


#: Les pages qui menent a la table des objets les plus utilises, ou qui la
#: portent.
_PAGES_DES_PLUS_UTILISES = ('encyclopedia_most_used.html',
                            'encyclopedia.html',
                            'shared_builds.html')

#: Ce que la page ne peut pas affirmer, dans les cinq langues.
#:
#: `reindex_builds_by_item.py` lit `get_solution(build).item_list`: ce sont les
#: objets que LE SOLVEUR a mis dans chaque build calcule ici. Le site n'a aucun
#: acces au personnage en jeu, donc rien ne peut dire qu'un seul de ces builds
#: ait ete equipe. Le paragraphe de methode le disait deja correctement; le
#: titre, le H1, la meta description et les deux liens entrants affirmaient le
#: contraire, sur la meme page.
_HORS_DE_PORTEE = (
    'actually wear', 'really equip', 'most worn',
    'portent vraiment', 'portent r\u00e9ellement', 'les plus port\u00e9s',
    'llevan de verdad', 'usan de verdad', 'los m\u00e1s llevados',
    'usam de verdade', 'realmente usam', 'os mais usados pelos',
    'wirklich tragen', 'tats\u00e4chlich tragen',
)


class TheMostUsedPageCountsWhatItSaysItCountsTests(SimpleTestCase):

    def test_the_index_really_reads_solver_solutions(self):
        """La mesure qui rend l'ancienne formulation fausse.

        Si un jour l'index comptait autre chose, c'est cette phrase-la qu'il
        faudrait relire, pas la page.
        """
        source = _lit(_ICI, 'management', 'commands',
                      'reindex_builds_by_item.py')
        self.assertIn('get_solution', source)
        self.assertIn('item_list', source)

    def test_no_page_claims_these_items_are_worn_in_game(self):
        coupables = []
        for fichier in _PAGES_DES_PLUS_UTILISES:
            corps = _lit(_GABARITS, fichier).lower()
            for interdit in _HORS_DE_PORTEE:
                if interdit.lower() in corps:
                    coupables.append((fichier, interdit))
        self.assertFalse(
            coupables,
            'the counts come from solver solutions for builds made here, so '
            'these claim something the site cannot know: %s' % coupables)

    def test_no_translation_claims_it_either(self):
        """Le gabarit est en anglais; quatre lecteurs sur cinq lisent autre
        chose."""
        from django.utils import translation

        titres = ('The Most Used Dofus Items in Calculated Builds',
                  'The most used items in builds calculated here',
                  'Most used items in builds')
        coupables = []
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            for msgid in titres:
                with translation.override(langue):
                    rendu = translation.gettext(msgid).lower()
                for interdit in _HORS_DE_PORTEE:
                    if interdit.lower() in rendu:
                        coupables.append((langue, msgid[:30], interdit))
        self.assertFalse(coupables, coupables)

    def test_the_page_still_prints_where_the_counts_come_from(self):
        """Retirer la surenchere ne doit pas retirer la methode: un
        pourcentage sans denominateur est un pourcentage incontestable."""
        corps = _lit(_GABARITS, 'encyclopedia_most_used.html')
        self.assertIn('builds calculated on this site', corps)
        self.assertIn('the share is of the builds that could equip it', corps)

    def test_the_empty_page_claims_no_count_at_all(self):
        """Le piege dans lequel je suis tombe en corrigeant le reste.

        La meta description a deux branches. En remplacant la surenchere par
        une phrase honnete, j'ai mis <<builds calculated on this site>> dans
        les DEUX, y compris celle qui sert quand l'index n'existe pas encore,
        soit exactement l'etat de la production entre un deploiement et la
        premiere indexation. La page annoncait alors un comptage dans sa
        balise `description` et, deux phrases plus bas, que les comptes
        n'etaient pas encore construits.

        `tests.py` porte deja le garde qui l'a attrape en interrogeant la
        page; celui-ci nomme la contrainte a l'endroit ou la phrase s'ecrit,
        pour que le prochain a la relire la voie.
        """
        corps = _lit(_GABARITS, 'encyclopedia_most_used.html')
        sans_compte = corps.split('{% else %}')
        self.assertGreater(len(sans_compte), 1, 'les deux branches ont fondu')
        branche = sans_compte[1].split('{% endif %}')[0]
        for compte in ('calculated on this site', 'Counted over', '{{ n }}'):
            self.assertNotIn(
                compte, branche,
                'the no-index branch of the meta description claims a count '
                'that has not been made')
