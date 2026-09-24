# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the pages claim must hold against the code behind them."""
import os
import re

from django.test import SimpleTestCase

_ICI = os.path.dirname(os.path.abspath(__file__))
_GABARITS = os.path.join(_ICI, 'templates', 'chardata')


def _lit(*morceaux):
    with open(os.path.join(*morceaux), encoding='utf-8') as f:
        return f.read()


# A Discord invite and the visible text of its button
_INVITATION = re.compile(
    r'<a\b[^>]*href\s*=\s*[\'"][^\'"]*discord\.gg/([A-Za-z0-9]+)[^\'"]*'
    r'[\'"][^>]*>(.*?)</a>', re.I | re.S)

# Invite code -> guild; ours is 1188892643766321173, the GUILD discordbot reads
_GUILDE = {
    'J842fFxU7r': 'fashionista',
    'a7b4a4dnVU': 'dofusdude',
}

_A_NOUS = {'J842fFxU7r'}


class EveryDiscordLinkSaysWhoseServerItIsTests(SimpleTestCase):
    """A Discord button that does not name its guild must lead to ours."""

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


# What an account unlocks: FAQ word -> (module, view behind @login_required)
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
        """The FAQ line about accounts."""
        for ligne in _lit(_GABARITS, 'faq.html').split('\n'):
            if 'An account' in ligne:
                return ligne
        return ''

    def test_each_named_feature_really_is_behind_a_login(self):
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


# Smart build meta description; the example in parentheses must parse
_META_PHRASE = (
    'Describe your Dofus build in plain words (like an agility Sram level 200 '
    'for PvP), and get a full optimized set in seconds with the '
    'Fashionista\u2019s smart build.')

_ENTRE_PARENTHESES = re.compile(r'\(([^)]*)\)')


class TheSmartBuildExampleActuallyParsesTests(SimpleTestCase):
    """The example parses in all five languages."""

    def test_the_template_still_carries_the_phrase_the_guard_checks(self):
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
        """The farm style does not add the element the reader asked for."""
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
    """`level` is in "level 200" and in "level up"; only the second is farm."""

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
        for phrase, attendu in (('an agility Sram level 200', 200),
                                ('un Sram agilite niveau 175', 175),
                                ('Iop lvl 150', 150)):
            with self.subTest(phrase=phrase):
                lu = self._lu(phrase)
                self.assertEqual(lu['level'], attendu, lu)
                self.assertTrue(lu['matched_level'], lu)


# Pages that show or link to the most used items table
_PAGES_DES_PLUS_UTILISES = ('encyclopedia_most_used.html',
                            'encyclopedia.html',
                            'shared_builds.html')

# Counts come from solver solutions, the site never sees what is worn in game
_HORS_DE_PORTEE = (
    'actually wear', 'really equip', 'most worn',
    'portent vraiment', 'portent r\u00e9ellement', 'les plus port\u00e9s',
    'llevan de verdad', 'usan de verdad', 'los m\u00e1s llevados',
    'usam de verdade', 'realmente usam', 'os mais usados pelos',
    'wirklich tragen', 'tats\u00e4chlich tragen',
)


class TheMostUsedPageCountsWhatItSaysItCountsTests(SimpleTestCase):

    def test_the_index_really_reads_solver_solutions(self):
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
        corps = _lit(_GABARITS, 'encyclopedia_most_used.html')
        self.assertIn('builds calculated on this site', corps)
        self.assertIn('the share is of the builds that could equip it', corps)

    def test_the_empty_page_claims_no_count_at_all(self):
        """The no-index branch of the meta description names no count."""
        corps = _lit(_GABARITS, 'encyclopedia_most_used.html')
        sans_compte = corps.split('{% else %}')
        self.assertGreater(len(sans_compte), 1, 'the two branches merged')
        branche = sans_compte[1].split('{% endif %}')[0]
        for compte in ('calculated on this site', 'Counted over', '{{ n }}'):
            self.assertNotIn(
                compte, branche,
                'the no-index branch of the meta description claims a count '
                'that has not been made')
