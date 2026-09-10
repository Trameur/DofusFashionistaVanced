# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La galerie des builds partages porte le verdict du solveur.

C'est la surface ou l'on decouvre les builds, et le fait qui porte tout le
positionnement, <<optimum demontre>> ou <<meilleur atteint a la limite de
temps>>, n'y etait pas. La carte ouvre deja le pickle de chaque build pour
dessiner ses objets, donc le lire ne coute rien de plus.
"""

import pickle
import re

from django.core.cache import cache
from django.test import TestCase

PROUVE = 'Proven optimum'
LIMITE = 'Best found at the time limit, not a proof'


def _build_partage(nom):
    from chardata.models import Char
    from django.test import Client
    from fashionistapulp.structure import get_structure, set_current_game_version
    set_current_game_version('dofus3')
    structure = get_structure('dofus3')
    item = next(i for i in structure.types[200]['Hat'] if not i.removed)
    Client().post('/import/text/', {
        'text': structure.get_item_name_in_language(item, 'en'),
        'confirm': '1', 'char_class': 'Cra', 'level': '200'})
    char = Char.objects.order_by('-id').first()
    char.name = char.char_name = nom
    char.link_shared = True
    char.save()
    return char


def _pose_le_fait(char, proven):
    try:
        minimal = pickle.loads(char.minimal_solution)
    except Exception as erreur:
        raise AssertionError(
            'the freshly imported build has no readable solution: %s' % erreur)
    if proven is None:
        if hasattr(minimal, 'proven'):
            delattr(minimal, 'proven')
    else:
        minimal.proven = proven
    char.minimal_solution = pickle.dumps(minimal)
    char.save()
    # Le meta de la carte est cache: un test qui lirait le cache d'un autre
    # verrait le verdict d'avant.
    cache.clear()


def _carte(page, nom):
    """Le HTML de la carte qui porte ce nom, et elle seule."""
    cartes = re.split(r'<div class="build-card">', page)
    for carte in cartes[1:]:
        if nom in carte:
            return carte
    raise AssertionError('no card named %s on the gallery' % nom)


class TheCardSaysWhatTheSolverProvedTests(TestCase):

    def test_a_proven_optimum_is_marked(self):
        char = _build_partage('GalerieProuve')
        _pose_le_fait(char, True)
        carte = _carte(self.client.get('/sharedbuilds/').content.decode('utf-8'),
                       'GalerieProuve')
        self.assertIn(PROUVE, carte)
        self.assertNotIn(LIMITE, carte)

    def test_a_timeout_is_marked_as_not_a_proof(self):
        char = _build_partage('GalerieLimite')
        _pose_le_fait(char, False)
        carte = _carte(self.client.get('/sharedbuilds/').content.decode('utf-8'),
                       'GalerieLimite')
        self.assertIn(LIMITE, carte)
        self.assertNotIn('build-proof-badge"', carte.replace(
            'build-proof-badge build-proof-badge-limit', ''))

    def test_an_old_solution_shows_nothing_rather_than_a_guess(self):
        """None n'est pas False: la carte se tait."""
        char = _build_partage('GalerieAncienne')
        _pose_le_fait(char, None)
        carte = _carte(self.client.get('/sharedbuilds/').content.decode('utf-8'),
                       'GalerieAncienne')
        self.assertNotIn('build-proof-badge', carte)

    def test_a_meta_cached_before_the_key_existed_still_renders(self):
        """Le meta de carte vit dans le cache jusqu'a son delai; celui d'avant
        ce commit n'a pas la cle, et la page doit le lire comme <<inconnu>>,
        pas tomber."""
        from chardata import shared_builds_view as vue
        char = _build_partage('GalerieCacheAncien')
        _pose_le_fait(char, True)
        meta = vue._get_shared_build_meta(char)
        del meta['solver_proven']
        cache.set(vue._get_shared_build_meta_cache_key(char), meta, 600)
        reponse = self.client.get('/sharedbuilds/')
        self.assertEqual(200, reponse.status_code)
        carte = _carte(reponse.content.decode('utf-8'), 'GalerieCacheAncien')
        self.assertNotIn('build-proof-badge', carte)

    def test_the_words_carry_the_verdict_not_the_colour(self):
        """Les deux badges ne different pas que par la couleur: chacun a ses
        mots, pour un lecteur qui ne distingue pas les teintes."""
        char = _build_partage('GalerieMots')
        _pose_le_fait(char, False)
        carte = _carte(self.client.get('/sharedbuilds/').content.decode('utf-8'),
                       'GalerieMots')
        self.assertIn('not a proof', carte)


class TheBadgeIsTranslatedTests(TestCase):

    def test_both_labels_read_in_the_four_other_languages(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for chaine in (PROUVE, LIMITE):
                    if gettext(chaine) == chaine:
                        muettes.append((langue, chaine))
        self.assertEqual([], muettes)
