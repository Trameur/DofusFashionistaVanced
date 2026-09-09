# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un script servi par quelqu'un d'autre doit annoncer ce qu'il pese.

`base.html` charge jQuery depuis `ajax.googleapis.com`, donc sur CHAQUE page ;
`jqueryui.html` ajoute jQuery UI et son theme sur sept pages, dont la page de
resultat du solveur. Trois fichiers qu'un tiers sert, qui s'executent avec tous
les droits de la page, et que rien ne verifiait.

C'est a ca que sert `integrity` : le navigateur calcule l'empreinte de ce qu'il
recoit et REFUSE de l'executer si elle ne correspond pas. Sans elle, un CDN
compromis, un DNS detourne ou une autorite de certification malveillante font
tourner le code de leur choix sur toutes les pages, y compris celles ou le
lecteur est connecte.

Ce test ne verifie pas QUELLE empreinte est ecrite -- affirmer qu'une constante
egale elle-meme ne prouve rien. Il verifie qu'aucune ressource tierce n'entre
SANS empreinte, ce qui est la regression reelle : quelqu'un ajoute un `<script
src="https://...">` en 2027 et personne ne remarque qu'il n'a pas de garde.

Les empreintes posees le 28 aout 2026 ont ete calculees sur les octets decodes
et corroborees par une SECONDE origine, `code.jquery.com` -- une infrastructure
differente, pas le meme fichier lu deux fois. Les trois concordent au bit pres.

Note sur `crossorigin` : une empreinte sur une ressource d'une autre origine
n'est verifiable que si la reponse autorise la lecture. Les trois adresses
renvoient `Access-Control-Allow-Origin: *`, ce qui a ete verifie avant de poser
quoi que ce soit -- sans cet en-tete, ajouter `integrity` aurait CASSE le
chargement au lieu de le proteger.
"""
import os
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.test import SimpleTestCase, TestCase

#: Une balise <script src> ou <link href> pointant vers une autre origine.
#:
#: Les DEUX formes de guillemets, et pas seulement la double. Le motif exigeait
#: `"`, et les deux seules balises tierces ecrites en apostrophes simples sont
#: precisement les deux chargeurs reCAPTCHA (contacts.html, login.html) : le
#: test etait vert et ne les avait jamais vues. Un garde qui ne connait qu'une
#: facon d'ecrire garde une facon d'ecrire, pas une surface, exactement comme
#: pour tesseract.js plus bas.
#:
#: La retro-reference \2 impose que le guillemet fermant soit celui qui a
#: ouvert, sinon une valeur en apostrophes se terminerait au premier `"` trouve
#: ailleurs dans la balise.
_EXTERNE = re.compile(
    r'<(script|link)\b[^>]*\b(?:src|href)\s*=\s*'
    r'([\'"])(https?://[^\'"]+)\2[^>]*>',
    re.I | re.S)

#: Le meme chargement, ecrit en JavaScript. Un script cree avec
#: createElement puis appendChild s'execute avec exactement les memes droits
#: qu'une balise, et le motif ci-dessus ne le voit pas: il cherche un `<`.
#:
#: C'est ainsi que tesseract.js est entre sans empreinte et y est reste. Le
#: test etait vert, le compte de ressources tierces disait treize, et la
#: quatorzieme, la seule que la page de l'inventaire telechargeait chez un
#: lecteur connecte, n'etait comptee nulle part. Un garde qui ne regarde qu'une
#: forme d'ecriture garde une forme d'ecriture, pas une surface.
_EXTERNE_JS = re.compile(
    r'\.src\s*=\s*[\'"](https?://[^\'"]+)[\'"]', re.I)

#: Combien de caracteres apres l'affectation on cherche `integrity` et
#: `crossOrigin`. Les proprietes d'un meme element se posent a la suite; au
#: dela, on serait en train de lire le reglage d'un autre script.
_FENETRE_JS = 400

#: Les origines qui n'executent rien et ne stylent rien : les declarer avec
#: une empreinte n'aurait pas de sens.
_SANS_OBJET = ('schema.org', 'www.w3.org', 'creativecommons.org')

#: Les scripts qu'on NE PEUT PAS epingler, et pourquoi.
#:
#: Une empreinte fige un contenu. Ceux-la sont mis a jour en continu par leur
#: editeur, a la meme adresse : les epingler ne les protegerait pas, ca les
#: casserait -- en quelques jours, silencieusement, sur toutes les pages.
#: C'est une limite connue de la specification, pas un oubli.
#:
#: La liste est deliberement une liste d'ADRESSES et non d'origines : si
#: quelqu'un ajoute demain une bibliotheque versionnee sur `googletagmanager`,
#: elle doit rougir, parce qu'elle, on peut l'epingler.
_NON_EPINGLABLES = {
    # Regie publicitaire : le script se reecrit a chaque changement de format.
    'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js',
    # Gestion du consentement, imposee par la regie ; suit ses evolutions.
    'https://fundingchoicesmessages.google.com/i/{{ ad_publisher }}?ers=1',
    # Mesure d'audience : Google republie ce fichier en continu.
    'https://www.googletagmanager.com/gtag/js?id={{ google_analytics_id }}',
    # Le chargeur reCAPTCHA, sur la page de contact et sur la connexion.
    # Deux mesures prises sur l'adresse elle-meme le 9 septembre 2026, et
    # chacune suffirait a elle seule :
    #   Cache-Control: private, max-age=300   -- republie toutes les 5 minutes
    #   Access-Control-Allow-Origin: (absent) -- reponse opaque
    # C'est le second qui tranche : sans cet en-tete le navigateur n'a pas le
    # droit de lire la reponse, donc pas le moyen de la hacher. Une empreinte
    # ici ne protegerait pas les deux pages, elle les CASSERAIT -- exactement
    # la panne que la note sur `crossorigin` en tete de fichier decrit.
    'https://www.google.com/recaptcha/api.js?hl={{language}}',
    'https://www.google.com/recaptcha/api.js',
}


def _gabarits():
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates')
    for dossier, _sous, fichiers in os.walk(racine):
        for f in fichiers:
            if f.endswith('.html'):
                yield os.path.join(dossier, f)


def _ressources_tierces():
    """(chemin, balise) pour chaque ressource chargee depuis un tiers."""
    trouve = []
    for chemin in _gabarits():
        with open(chemin, encoding='utf-8', errors='replace') as f:
            texte = f.read()
        for m in _EXTERNE.finditer(texte):
            balise = m.group(0)
            url = m.group(3)
            if any(d in url for d in _SANS_OBJET):
                continue
            # Un <link rel="canonical"> ou "alternate" ne charge rien.
            if m.group(1).lower() == 'link':
                rel = re.search(r'\brel\s*=\s*[\'"]([^\'"]*)[\'"]', balise,
                                re.I)
                if not rel or 'stylesheet' not in rel.group(1).lower():
                    continue
            trouve.append((os.path.basename(chemin), balise, url))
        for m in _EXTERNE_JS.finditer(texte):
            url = m.group(1)
            if any(d in url for d in _SANS_OBJET):
                continue
            # Une pseudo-balise, pour que les quatre assertions ci-dessous
            # jugent un script ecrit en JavaScript exactement comme un autre,
            # sans qu'aucune ait a connaitre les deux formes.
            suite = texte[m.end():m.end() + _FENETRE_JS]
            # La VRAIE empreinte, pas un marqueur: le test qui exige sha384
            # lit cette valeur, et lui donner un jeton la ferait echouer sur
            # une balise pourtant correctement epinglee.
            empreinte = re.search(r"""integrity\s*=\s*['"]([^'"]+)['"]""",
                                  suite, re.I)
            balise = '<script src="%s"%s%s>' % (
                url,
                ' integrity="%s"' % empreinte.group(1) if empreinte else '',
                ' crossorigin="js"' if 'crossorigin' in suite.lower() else '')
            trouve.append((os.path.basename(chemin), balise, url))
    return trouve


class EveryThirdPartyResourceIsPinnedTests(SimpleTestCase):

    def test_the_scan_actually_finds_third_party_resources(self):
        """Le plancher du temoin.

        Sans lui, un motif trop etroit rendrait zero ressource, zero faute, et
        un vert parfait qui ne garde rien.

        Le plancher a longtemps ete `>= 3`, et il n'a rien garde du tout : le
        motif n'acceptait que les guillemets doubles, les deux balises
        reCAPTCHA sont ecrites en apostrophes, et six autres ressources
        suffisaient a satisfaire le compte. Un nombre se contente de n'importe
        quels temoins. Ce qu'il faut exiger, c'est que les TROIS facons
        d'ecrire un chargement tiers soient chacune representee, chacune par
        un fichier qui la porte reellement.
        """
        trouve = _ressources_tierces()
        vus = set(f for f, _b, _u in trouve)
        for fichier, forme in (
                ('base.html', 'une balise en guillemets doubles'),
                ('contacts.html', 'une balise en apostrophes simples'),
                ('inventory.html', 'un src affecte en JavaScript')):
            self.assertIn(
                fichier, vus,
                'the scan no longer sees %s (%s), so that whole way of '
                'writing a third-party load is unguarded' % (fichier, forme))
        self.assertGreaterEqual(
            len(trouve), 9,
            'only %d third-party resources found, down from the 9 measured on '
            '2026-09-09; the scan has narrowed' % len(trouve))

    def test_no_third_party_script_or_stylesheet_runs_unpinned(self):
        nus = [(f, u) for f, b, u in _ressources_tierces()
               if 'integrity=' not in b.lower()
               and u not in _NON_EPINGLABLES]
        self.assertFalse(
            nus,
            'these load third-party code with no subresource integrity, so a '
            'compromised CDN would run its own: %s' % nus[:4])

    def test_the_exemption_list_still_describes_real_tags(self):
        """Une exemption qui ne correspond plus a rien est un mensonge poli.

        Si l'adresse d'AdSense change, la ligne exemptee cesse de designer
        quoi que ce soit -- et la NOUVELLE adresse, elle, tombe dans le test
        precedent. Ce test-ci attrape l'autre moitie : une liste qui grossit
        de lignes mortes finit par exempter des choses qu'on croit connaitre.
        """
        vues = set(u for _f, _b, u in _ressources_tierces())
        fantomes = sorted(_NON_EPINGLABLES - vues)
        self.assertFalse(
            fantomes,
            'these exemptions no longer match any tag, so nothing checks '
            'what they claim to excuse: %s' % fantomes)

    def test_a_pinned_resource_also_allows_the_check(self):
        """`integrity` sans `crossorigin` ne verifie rien sur une autre origine.

        Le navigateur ne peut pas lire une reponse opaque, donc il ne peut pas
        la hacher. La balise a l'air protegee et ne l'est pas -- pire qu'une
        balise nue, parce qu'elle rassure.
        """
        boiteux = [(f, u) for f, b, u in _ressources_tierces()
                   if 'integrity=' in b.lower()
                   and 'crossorigin' not in b.lower()]
        self.assertFalse(
            boiteux,
            'these carry an integrity hash the browser cannot verify without '
            'crossorigin: %s' % boiteux[:4])

    def test_every_hash_is_sha384_or_stronger(self):
        """sha256 reste accepte par la specification, mais sha384 est la
        recommandation, et c'est ce qui est pose ici. Une empreinte plus
        faible glissee plus tard passerait sinon inapercue.
        """
        faibles = []
        for f, b, u in _ressources_tierces():
            m = re.search(r'integrity\s*=\s*[\'"]([^\'"]*)[\'"]', b, re.I)
            if m and not re.search(r'sha(384|512)-', m.group(1)):
                faibles.append((f, m.group(1)[:24]))
        self.assertFalse(faibles, 'weaker than sha384: %s' % faibles)


#: Chaque origine tierce qu'un gabarit fait charger, et le nom sous lequel la
#: politique de confidentialite doit l'annoncer.
#:
#: La page listait AdSense, le consentement, Analytics, la connexion Google et
#: l'hebergement, puis s'arretait. Elle passait sous silence reCAPTCHA, charge
#: sur la page de contact et sur la connexion, et les deux CDN qui servent
#: jQuery sur CHAQUE page, jQuery UI sur sept, et la bibliotheque de lecture de
#: texte de l'inventaire. Une origine tierce recoit l'adresse du lecteur au
#: moment ou son navigateur va chercher le fichier, qu'elle depose un cookie ou
#: non : une politique qui en oublie la moitie decrit un autre site.
#:
#: Les valeurs sont des marques, pas des phrases : elles survivent a la
#: traduction, donc ce test garde les cinq langues en n'en lisant qu'une.
_ORIGINE_ANNONCEE = {
    'ajax.googleapis.com': 'Google Hosted Libraries',
    'cdn.jsdelivr.net': 'jsDelivr',
    'www.google.com': 'reCAPTCHA',
    'www.googletagmanager.com': 'Analytics',
    'pagead2.googlesyndication.com': 'AdSense',
    'fundingchoicesmessages.google.com': 'Consent',
}


class ThePrivacyPolicyNamesEveryThirdPartyTests(SimpleTestCase):
    """Ce que le site charge et ce qu'il dit charger doivent coincider.

    Le test precedent garde l'integrite ; celui-ci garde l'honnetete. Ils
    lisent la meme source -- les balises reellement ecrites dans les gabarits
    -- pour qu'aucun des deux ne puisse se contenter d'une liste tenue a la
    main qui a cesse d'etre vraie.
    """

    def _politique(self):
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'chardata', 'privacy.html')
        with open(chemin, encoding='utf-8') as f:
            return f.read()

    def _origines(self):
        return sorted(set(urlsplit(u).netloc
                          for _f, _b, u in _ressources_tierces()))

    def test_every_loaded_origin_has_been_decided_about(self):
        """Une origine nouvelle doit forcer une decision, pas passer.

        Sans ce test, ajouter un CDN demain ferait taire le suivant : il ne
        verifierait que les origines qu'on a pensees a inscrire.
        """
        inconnues = [o for o in self._origines()
                     if o not in _ORIGINE_ANNONCEE]
        self.assertFalse(
            inconnues,
            'these third-party origins are loaded but nobody decided how the '
            'privacy policy should name them: %s' % inconnues)

    def test_every_loaded_origin_is_named_in_the_policy(self):
        corps = self._politique().lower()
        muettes = []
        for origine in self._origines():
            nom = _ORIGINE_ANNONCEE[origine]
            if nom.lower() not in corps:
                muettes.append((origine, nom))
        self.assertFalse(
            muettes,
            'the site loads these but the privacy policy never names them, so '
            'it describes a different site: %s' % muettes)

    def test_the_policy_does_not_promise_a_deletion_nobody_performs(self):
        """La retention promettait un effacement <<after twenty-four hours>>.

        Le code elague bien au fil de l'eau, mais seulement pour le build
        qu'on vient de consulter (solution_view.py) : un build que plus
        personne ne regarde garde ses adresses jusqu'au prochain demarrage, ou
        cleanup_old_views passe. La phrase dit maintenant les deux, et ce
        test empeche qu'on la resimplifie sans toucher au code.
        """
        corps = self._politique()
        self.assertIn('when the server restarts', corps)
        self.assertNotIn('delete it after twenty-four hours', corps)

    def test_the_policy_carries_a_date_it_can_still_honour(self):
        """La page promet elle-meme que les changements importants se lisent
        sur sa date. Elle affichait juin 2026 apres deux refontes d'aout."""
        corps = self._politique()
        self.assertIn('Last updated:', corps)
        for perime in ('June 2026', 'July 2026', 'August 2026'):
            self.assertNotIn(
                'Last updated: %s' % perime, corps,
                'the policy changed since %s but still says it did not'
                % perime)


class ThePrivacyPolicyRendersInEveryLanguageTests(TestCase):
    """Le gabarit n'est pas la page.

    Les tests ci-dessus lisent `privacy.html`. Un lecteur, lui, recoit ce que
    gettext a compile : une entree marquee `fuzzy` est ignoree sans un mot,
    un msgid mal echappe compile proprement et ne correspond jamais, et dans
    les deux cas la page repasse en anglais pendant que le catalogue a l'air
    complet. Il faut donc demander la page.
    """

    #: Un temoin par langue et par correction, choisi dans la traduction
    #: elle-meme et pas dans une marque : `jsDelivr` prouverait seulement que
    #: le nom propre a survecu, pas que la phrase autour a ete traduite.
    TEMOINS = {
        'en': ('reCAPTCHA to tell people apart from bots',
               'is fetched from Google Hosted Libraries and jsDelivr',
               'when the server restarts',
               'Last updated: September 2026'),
        'fr': ('pour distinguer les humains des robots',
               'depuis Google Hosted Libraries et jsDelivr',
               'au red\u00e9marrage du serveur',
               'septembre 2026'),
        'es': ('para distinguir a las personas de los bots',
               'desde Google Hosted Libraries y jsDelivr',
               'al reiniciarse el servidor',
               'septiembre de 2026'),
        'pt': ('para distinguir pessoas de bots',
               'do Google Hosted Libraries e do jsDelivr',
               'ao reiniciar o servidor',
               'setembro de 2026'),
        'de': ('um Menschen von Bots zu unterscheiden',
               'von Google Hosted Libraries und jsDelivr geladen',
               'beim Neustart des Servers',
               'September 2026'),
    }

    def test_the_policy_is_served_translated_in_all_five_languages(self):
        manquants = []
        for langue, temoins in sorted(self.TEMOINS.items()):
            reponse = self.client.get(
                '/privacy/', headers={'accept-language': langue})
            self.assertEqual(reponse.status_code, 200, langue)
            corps = reponse.content.decode('utf-8')
            for temoin in temoins:
                if temoin not in corps:
                    manquants.append((langue, temoin))
        self.assertFalse(
            manquants,
            'the catalogue compiled but these never reached the page: %s'
            % manquants)

    def test_the_old_promises_are_served_nowhere(self):
        """Corriger le gabarit sans recompiler laisserait l'ancienne phrase
        vivre dans les quatre traductions, ce que rien n'aurait signale."""
        survivants = []
        for langue in sorted(self.TEMOINS):
            corps = self.client.get(
                '/privacy/',
                headers={'accept-language': langue}).content.decode('utf-8')
            for mort in ('delete it after twenty-four hours',
                         'au bout de vingt-quatre heures',
                         'a las veinticuatro horas',
                         'ao fim de vinte e quatro horas',
                         'nach vierundzwanzig Stunden',
                         'June 2026', 'juin 2026', 'junio de 2026',
                         'junho de 2026', 'Juni 2026'):
                if mort in corps:
                    survivants.append((langue, mort))
        self.assertFalse(
            survivants,
            'these were corrected in the template but are still served: %s'
            % survivants)
