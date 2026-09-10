# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une politique qui signale, jamais une politique qui bloque.

Le site n'avait aucun `Content-Security-Policy`. En poser un qui BLOQUE, ecrit
en lisant le depot, aurait casse le site pour une partie des visiteurs et pour
eux seulement, ce qui est la panne la plus difficile a voir.
"""

import json

from django.test import SimpleTestCase, TestCase, override_settings

from chardata.csp import (REPORT_PATH, _SOURCES, build_policy,
                          policy_is_enabled)
from chardata.csp_report_view import MAX_CORPS, MAX_PAR_MINUTE


class ThePolicyCoversWhatTheSiteActuallyLoadsTests(SimpleTestCase):
    """Les origines viennent d'une MESURE, pas d'une lecture du depot.

    Le 10 septembre 2026, quatre pages chargees dans un navigateur et
    `performance.getEntriesByType('resource')` interroge, le site va chercher:

        https://ajax.googleapis.com           jQuery,    ecrit dans base.html
        https://www.googletagmanager.com      gtag,      ecrit dans base.html
        https://region1.analytics.google.com  la mesure, NULLE PART dans le depot
        https://www.google.fr                 reCAPTCHA, NULLE PART dans le depot

    Les deux dernieres n'existent dans aucun gabarit et leur nom **change
    selon le visiteur**: `region1` est la region du compte Analytics et
    `www.google.fr` le domaine national vers lequel reCAPTCHA bascule. C'est
    la raison d'etre du mode rapport, et c'est ce que ces tests gardent.
    """

    def test_the_two_origins_that_are_written_in_the_repo_are_allowed(self):
        politique = build_policy()
        for origine in ('https://ajax.googleapis.com',
                        'https://www.googletagmanager.com'):
            self.assertIn(origine, politique)

    def test_the_analytics_region_is_matched_by_a_wildcard(self):
        """`region1` est la region du compte: un autre compte verra
        `region5`, et l'ecrire en dur couperait la mesure d'audience."""
        connect = _SOURCES['connect-src']
        self.assertIn('https://*.analytics.google.com', connect)
        self.assertNotIn('https://region1.analytics.google.com', connect)

    def test_the_recaptcha_country_domain_is_left_to_the_reports(self):
        """Mesure sur /contact/: le navigateur est alle chercher
        `https://www.google.fr`. Un lecteur allemand ira sur `.de`.

        Et il n'y a AUCUN moyen de l'ecrire: un joker CSP ne vaut qu'a gauche
        d'un hote. `https://www.google.*` a ete essaye et le navigateur l'a
        rejete comme source invalide. Ni le domaine national mesure ici ni un
        joker impossible ne figurent donc dans la politique: ce sont les
        rapports qui diront lesquels apparaissent vraiment, et c'est
        precisement le travail que le mode rapport doit faire.
        """
        frames = _SOURCES['frame-src']
        self.assertNotIn('https://www.google.*', frames)
        self.assertNotIn('https://www.google.fr', frames)
        self.assertIn('https://www.google.com', frames)

    def test_the_policy_names_the_report_endpoint(self):
        self.assertIn('report-uri %s' % REPORT_PATH, build_policy())

    def test_every_directive_carries_at_least_one_source(self):
        """Une directive vide n'est pas <<tout permis>>, c'est <<tout
        refuse>>: la poser par distraction bloquerait la categorie entiere."""
        vides = [d for d, sources in _SOURCES.items() if not sources]
        self.assertEqual([], vides)

    def test_no_source_puts_its_wildcard_on_the_wrong_side(self):
        """La faute que seul le navigateur signale.

        Un joker CSP ne vaut qu'a GAUCHE d'un hote: `*.google.com` est
        valide, `www.google.*` ne l'est pas. Le premier jet portait
        `https://www.google.*` pour attraper les domaines nationaux de
        reCAPTCHA, et Chrome a repondu <<contains an invalid source, it will
        be ignored>>: la source disparaissait entierement, et RIEN cote
        serveur ne le disait. Une politique se relit dans un navigateur, pas
        seulement dans un editeur.
        """
        import re
        mauvais = []
        for directive, sources in sorted(_SOURCES.items()):
            for source in sources:
                if source.startswith("'") or source.endswith(':'):
                    continue
                hote = re.sub(r'^https?://', '', source).split('/')[0]
                if '*' in hote and not hote.startswith('*.'):
                    mauvais.append((directive, source))
        self.assertFalse(
            mauvais,
            'a CSP wildcard only works on the left of a host, so the browser '
            'throws these away without telling the server: %s' % mauvais)

    def test_the_ad_verification_domain_nobody_could_guess_is_allowed(self):
        """Mesure du 10 septembre 2026, console du navigateur: la regie charge
        `ep2.adtrafficquality.google/sodar/sodar2.js` et ouvre une connexion
        vers `ep1.adtrafficquality.google`. Ce domaine n'apparait dans aucun
        gabarit du depot. C'est la demonstration la plus nette qu'une
        politique BLOQUANTE ecrite ici aurait casse la publicite."""
        for directive in ('script-src', 'connect-src', 'frame-src'):
            with self.subTest(directive=directive):
                self.assertIn('https://*.adtrafficquality.google',
                              _SOURCES[directive])

    def test_the_policy_is_one_line_and_ends_each_directive(self):
        politique = build_policy()
        self.assertNotIn('\n', politique)
        self.assertEqual(len(_SOURCES) + 1, len(politique.split(';')))


class TheHeaderIsReportOnlyTests(TestCase):
    """La difference entre les deux en-tetes est la difference entre
    <<le site marche>> et <<le site est casse pour les Allemands>>."""

    def test_an_html_page_carries_the_report_only_header(self):
        reponse = self.client.get('/faq/')
        self.assertEqual(200, reponse.status_code)
        self.assertIn('Content-Security-Policy-Report-Only', reponse)

    def test_no_page_carries_the_blocking_header(self):
        """Le garde qui compte. Poser `Content-Security-Policy` tout court
        ferait appliquer la regle, et une origine oubliee casserait la page
        pour les visiteurs qui en dependent, en silence."""
        for chemin in ('/faq/', '/privacy/', '/import/text/', '/about/'):
            with self.subTest(chemin=chemin):
                reponse = self.client.get(chemin)
                self.assertNotIn('Content-Security-Policy', reponse)

    def test_the_header_says_the_same_thing_as_the_builder(self):
        reponse = self.client.get('/faq/')
        self.assertEqual(build_policy(),
                         reponse['Content-Security-Policy-Report-Only'])

    def test_a_non_html_response_carries_nothing(self):
        """Une image n'applique aucune politique, et l'en-tete pese quelques
        centaines d'octets sur chacune des dizaines de requetes d'une page."""
        reponse = self.client.get('/jsi18n/')
        self.assertEqual(200, reponse.status_code)
        self.assertNotIn('Content-Security-Policy-Report-Only', reponse)

    @override_settings(CSP_REPORT_ONLY_ENABLED=False)
    def test_the_setting_can_turn_it_off_without_a_deploy(self):
        self.assertFalse(policy_is_enabled())
        reponse = self.client.get('/faq/')
        self.assertNotIn('Content-Security-Policy-Report-Only', reponse)


class TheReportEndpointRecordsWithoutDrowningTests(TestCase):

    def _rapport(self, **champs):
        base = {'document-uri': 'https://dofusfashionista.gg/faq/?q=secret',
                'effective-directive': 'script-src',
                'blocked-uri': 'https://example.invalid/x.js'}
        base.update(champs)
        return json.dumps({'csp-report': base})

    def _poste(self, corps, type_contenu='application/csp-report'):
        return self.client.post(REPORT_PATH, data=corps,
                                content_type=type_contenu)

    def test_a_real_report_is_accepted(self):
        reponse = self._poste(self._rapport())
        self.assertEqual(204, reponse.status_code)

    def test_the_browser_needs_no_csrf_token(self):
        """Un navigateur n'en envoie pas, donc exiger le jeton reviendrait a
        n'avoir jamais aucun rapport."""
        reponse = self._poste(self._rapport())
        self.assertNotEqual(403, reponse.status_code)

    def test_a_get_is_refused(self):
        self.assertEqual(405, self.client.get(REPORT_PATH).status_code)

    def test_junk_is_refused_rather_than_logged(self):
        for corps in ('pas du json', '[]', '{}', '{"csp-report": 3}',
                      '{"csp-report": {}}'):
            with self.subTest(corps=corps):
                self.assertEqual(400, self._poste(corps).status_code)

    def test_an_oversized_body_is_refused(self):
        gros = json.dumps({'csp-report': {'blocked-uri': 'x' * (MAX_CORPS + 50)}})
        self.assertEqual(400, self._poste(gros).status_code)

    def test_what_is_logged_keeps_the_page_but_drops_the_query(self):
        """`document-uri` est la page que le lecteur regardait. Le chemin
        suffit a corriger une directive; la chaine de requete peut porter ce
        qu'il cherchait et n'aide en rien."""
        with self.assertLogs('chardata.csp_report_view', level='WARNING') as vu:
            self._poste(self._rapport())
        ligne = '\n'.join(vu.output)
        self.assertIn('/faq/', ligne)
        self.assertNotIn('secret', ligne)
        self.assertIn('example.invalid', ligne)

    def test_the_same_violation_stops_being_logged_after_a_few(self):
        """Une page populaire qui viole une directive enverrait un rapport
        par lecteur. Le journal garde le premier exemple, pas le millieme."""
        from django.core.cache import cache
        cache.clear()
        with self.assertLogs('chardata.csp_report_view', level='WARNING') as vu:
            for _ in range(MAX_PAR_MINUTE + 6):
                self._poste(self._rapport())
        self.assertEqual(MAX_PAR_MINUTE, len(vu.output), vu.output)

    def test_two_different_violations_are_both_kept(self):
        """Le plafond est par violation, pas global: sinon le premier
        probleme cacherait tous les autres."""
        from django.core.cache import cache
        cache.clear()
        with self.assertLogs('chardata.csp_report_view', level='WARNING') as vu:
            self._poste(self._rapport(**{'blocked-uri': 'https://a.invalid/1'}))
            self._poste(self._rapport(**{'blocked-uri': 'https://b.invalid/2'}))
        self.assertEqual(2, len(vu.output), vu.output)

    def test_the_endpoint_does_not_police_itself(self):
        """Poser la politique sur sa propre reponse ferait signaler
        l'endpoint a lui-meme le jour ou quelque chose y deraille."""
        reponse = self._poste(self._rapport())
        self.assertNotIn('Content-Security-Policy-Report-Only', reponse)


class AStatLabelIsANameNotAKeyTests(TestCase):
    """`localized_stat_name` traduit un NOM ('AP', 'Vitality').

    Une cle ('ap', 'vit') n'est dans aucun catalogue, donc elle ressort telle
    quelle. Deux endroits lui passaient une cle: le panneau des contraintes de
    la page de solution, qui affichait <<ap 12>> au lieu de <<PA 12>>, et les
    libelles du texte partage, qui restaient anglais sur une page francaise.
    """

    def test_the_helper_translates_a_name_and_not_a_key(self):
        """La mesure qui explique les deux fautes."""
        from django.utils import translation
        from chardata.translation_util import localized_stat_name
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        stat = get_structure('dofus3').get_stat_by_key('ap')
        with translation.override('fr'):
            self.assertEqual('ap', localized_stat_name('ap'),
                             'a key would translate, and the bug would not '
                             'exist')
            self.assertEqual('PA', localized_stat_name(stat.name))

    def test_the_shared_text_labels_follow_the_reader(self):
        from django.test import RequestFactory
        from django.utils import translation
        from chardata.models import Char
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        rendus = {}
        for langue in ('en', 'fr'):
            with translation.override(langue):
                rendus[langue] = _build_share_text(
                    RequestFactory().get('/'), char, get_solution(char))
        self.assertIn('Vitality', rendus['en'])
        self.assertIn('Vitalit\u00e9', rendus['fr'])
        self.assertNotIn('Vitality', rendus['fr'])

    def test_the_constraints_panel_shows_a_label_not_a_key(self):
        """Le panneau ne s'affiche qu'avec des minimums, donc on interroge la
        fonction qui le remplit plutot que d'en fabriquer un."""
        from django.utils import translation
        from chardata.models import Char
        from chardata.min_stats import set_min_stats
        from chardata.solution import get_solution
        from chardata.solution_view import _constraints_reached
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        # set_min_stats est indexe par NOM ('AP'), pas par cle ('ap'):
        # la meme confusion que celle que ce test garde.
        set_min_stats(char, {'AP': 1})
        with translation.override('fr'):
            lignes = _constraints_reached(char, get_solution(char))
        self.assertTrue(lignes, 'no constraint came back, nothing is guarded')
        noms = [l['name'] for l in lignes]
        self.assertNotIn('ap', noms, 'the panel shows the raw stat key')
        self.assertIn('PA', noms, noms)
