# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'adresse publique d'un build doit marcher pour celui a qui on la donne.

`char_name` arrive de `request.POST.get('charname')` sans aucune validation:
c'est ce que le joueur a tape, espaces et ponctuation compris. Deux fautes
distinctes en sortaient, et chacune se voit seulement de l'exterieur.
"""

from urllib.parse import urlsplit

from django.test import TestCase

from chardata.util import shared_build_path
from chardata.url_language import SITE_URL


class ANameWithPunctuationStillGivesAWorkingUrlTests(TestCase):
    """Mesure du 10 septembre 2026 sur la forme non echappee:

        <<Mon Cra>>  -> l'espace coupe le lien des qu'un salon l'auto-lie
        <<Cra #1>>   -> le chemin s'arrete a `/s/Cra` et **l'identifiant du
                        build part dans le fragment**
        <<Cra?PvP>>  -> le chemin s'arrete a `/s/Cra`, l'identifiant part dans
                        la chaine de requete
        <<100% Cra>> -> `% C` n'est pas une sequence d'echappement valide

    Cette adresse est le champ `url` de l'API publique et le lien <<builds qui
    utilisent cet objet>> de l'encyclopedie.
    """

    NOMS = ('Cra', 'Mon Cra', 'Cra #1', 'Cra?PvP', 'Cra&Iop', '100% Cra',
            'Crâ du Chêne')

    class _Build:
        def __init__(self, nom, version='dofus3'):
            self.id = 42
            self.char_name = nom
            self.game_version = version

    def test_the_id_never_leaves_the_path(self):
        """La faute la plus grave: avec un `#`, l'identifiant partait dans le
        fragment et le lien ne designait plus aucun build."""
        perdus = []
        for nom in self.NOMS:
            url = SITE_URL + shared_build_path(self._Build(nom))
            morceaux = urlsplit(url)
            if morceaux.fragment or morceaux.query:
                perdus.append((nom, url))
            elif not morceaux.path.rstrip('/').split('/')[-1]:
                perdus.append((nom, url))
        self.assertFalse(
            perdus,
            'the build id fell out of the path, so the link points at no '
            'build at all: %s' % perdus)

    def test_no_url_carries_a_raw_space(self):
        """Un salon qui transforme le texte en lien s'arrete au premier
        espace, donc le lien colle est tronque avant l'identifiant."""
        avec_espace = [nom for nom in self.NOMS
                       if ' ' in shared_build_path(self._Build(nom))]
        self.assertEqual([], avec_espace)

    def test_the_version_prefix_is_still_the_build_own(self):
        """L'echappement ne doit pas avoir emporte la regle du prefixe: une
        page Touch n'existe que sous `/touch/`."""
        self.assertTrue(
            shared_build_path(self._Build('Mon Cra', 'touch'))
            .startswith('/touch/s/'))
        self.assertTrue(
            shared_build_path(self._Build('Mon Cra', 'dofus3'))
            .startswith('/s/'))

    def test_the_escaped_url_really_reaches_the_build(self):
        """Le garde de l'autre cote: echapper ne sert a rien si la route ne
        reconnait plus l'adresse. Django decode le chemin avant de router, ce
        qui se verifie plutot que de se supposer.
        """
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.char_name = 'Cra #1 100%'
        char.link_shared = True
        char.save()

        chemin = shared_build_path(char)
        self.assertNotIn('#', chemin)
        reponse = self.client.get(chemin)
        self.assertEqual(200, reponse.status_code,
                         'the escaped path no longer routes: %s' % chemin)


class TheSharedLinkIsCanonicalTests(TestCase):
    """Ce lien est fait pour etre colle sur un Discord, donc il doit valoir
    pour tout le monde et pas seulement pour celui qui l'a copie.

    `request.build_absolute_uri` rendait l'hote de l'appelant, et
    `ALLOWED_HOSTS` en compte neuf en production. Mesure du 10 septembre 2026:
    le meme build sortait en `http://178.105.48.220/s/...` depuis une IP et
    `http://fashionistavanced.com/s/...` depuis l'ancien domaine, en `http`
    dans les deux cas.
    """

    def _char(self):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def test_the_link_does_not_follow_the_host_the_reader_came_by(self):
        from django.test import RequestFactory
        from chardata.solution_view import generate_link
        char = self._char()
        rendus = set()
        for hote in ('dofusfashionista.gg', 'fashionistavanced.com',
                     '178.105.48.220', 'localhost:8090'):
            requete = RequestFactory().get('/', HTTP_HOST=hote)
            requete.game_version = 'dofus3'
            rendus.add(generate_link(requete, char))
        self.assertEqual(1, len(rendus),
                         'the shared link changes with the door the reader '
                         'came in by: %s' % sorted(rendus))
        seul = rendus.pop()
        self.assertTrue(seul.startswith(SITE_URL), seul)
        self.assertTrue(seul.startswith('https://'), seul)

    def test_the_share_text_carries_that_same_canonical_link(self):
        from django.test import RequestFactory
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        char = self._char()
        char.link_shared = True
        char.save()
        requete = RequestFactory().get('/', HTTP_HOST='178.105.48.220')
        requete.game_version = 'dofus3'
        texte = _build_share_text(requete, char, get_solution(char))
        self.assertIn(SITE_URL, texte)
        self.assertNotIn('178.105.48.220', texte)
