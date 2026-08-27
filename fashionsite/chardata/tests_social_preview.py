# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The picture a page offers when its link is pasted somewhere.

og:image is the one meta tag with a hard numeric floor underneath it. Facebook
documents 200x200 as the smallest image it accepts, and a Twitter summary card
asks 144x144. Under those, the link does not render a small picture -- it
renders none, which reads as "this site has no preview" rather than "this
image is too small". A tag can therefore be present, well formed, point at a
file that exists, and still produce nothing.

So this file does not check that the tag is there. It resolves the file the tag
names and measures it.
"""
import re
import struct

from django.contrib.staticfiles import finders
from django.test import TestCase

#: Le plus haut des deux seuils documentes. Une image qui le passe passe les
#: deux ; une image entre les deux ne rend que sur une plateforme, ce qui est
#: la situation la plus penible a diagnostiquer.
PLANCHER = 200


def dimensions(chemin):
    """Largeur et hauteur d'un PNG ou d'un JPEG, sans dependance."""
    with open(chemin, 'rb') as fichier:
        donnees = fichier.read()
    if donnees[12:16] == b'IHDR':
        return struct.unpack('>II', donnees[16:24])
    if donnees[:2] == bytes([0xFF, 0xD8]):
        i = 2
        while i < len(donnees) - 9:
            if donnees[i] != 0xFF:
                i += 1
                continue
            marqueur = donnees[i + 1]
            if marqueur in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                hauteur, largeur = struct.unpack('>HH', donnees[i + 5:i + 9])
                return largeur, hauteur
            if marqueur in (0xD8, 0xD9) or 0xD0 <= marqueur <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack('>H', donnees[i + 2:i + 4])[0]
    return None


class ThePreviewPictureIsBigEnoughToRenderTests(TestCase):
    """Forgelance is the one class with no artwork.

    get_class_avatar hands back a 16x16 question mark for it, which is a fine
    placeholder beside a build and a broken preview in a chat window. The
    template guarded the tag with an "if class_avatar" test, but that value is
    never empty -- the placeholder IS the value -- so the guard never fired,
    and 198 shared builds in the production copy offered a 16 pixel question
    mark as their picture.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        self.owner = User.objects.create_user('previewowner',
                                              'preview@test.local',
                                              'pw-42-solid')
        self.client.force_login(self.owner)

    def _char(self, char_class='Iop', shared=True):
        import pickle as _pickle
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        hat = next(item for item
                   in get_structure('dofus3')
                   .get_unique_items_by_type_and_level('Hat', 200)
                   if not item.removed)
        return Char.objects.create(
            name='Preview', char_name='Preview', char_class=char_class,
            char_build='Str', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=_pickle.dumps({'vit': 1}),
            options=b'', inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(ModelResultMinimal(
                {'hat': hat.id}, {'options': {'ap_exo': False,
                                              'mp_exo': False},
                                  'origin': 'generated', 'char_level': 200,
                                  'base_stats_by_attr': {
                                      'Vitality': 0, 'Wisdom': 0,
                                      'Strength': 0, 'Intelligence': 0,
                                      'Chance': 0, 'Agility': 0},
                                  'locked_equips': {}}, {})),
            owner=self.owner, link_shared=shared, game_version='dofus3')

    def _og_image(self, char):
        from chardata.solution_view import shared_build_path
        url = (shared_build_path(char) if char.link_shared
               else '/solution/%d/' % char.id)
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(response.status_code, 200, url)
        html = response.content.decode('utf-8', 'replace')
        tags = [tag for tag in re.findall('<meta[^>]*>', html)
                if 'og:image"' in tag]
        self.assertEqual(len(tags), 1,
                         '%s declares %d og:image tags' % (url, len(tags)))
        return re.search('content="([^"]*)"', tags[0]).group(1)

    def _fichier(self, url):
        """The file on disk an og:image url names, or None."""
        chemin = url.split('/static/')[-1].split('?')[0]
        return finders.find(chemin)

    def test_the_class_without_artwork_gets_a_card_not_a_16_pixel_mark(self):
        url = self._og_image(self._char(char_class='Forgelance'))
        self.assertIn('og-card', url, 'Forgelance still offers %s' % url)

    def test_a_class_with_artwork_keeps_its_own_avatar(self):
        # Le remede ne doit pas remplacer les dix-huit autres par une carte
        # generique : leur avatar fait 260x260 et passe les deux seuils.
        url = self._og_image(self._char(char_class='Cra'))
        self.assertIn('myWizardCra', url, 'Cra lost its avatar: %s' % url)

    def test_every_class_offers_a_picture_that_can_actually_render(self):
        """The whole point, measured rather than assumed.

        Enumerated over every class the site knows instead of the two I had in
        mind. The last rule here checked against a hand-picked pair passed on
        both and was wrong on a third.
        """
        from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
        trop_petites = []
        mesurees = 0
        for char_class in sorted(LOCALIZED_CHARACTER_CLASSES):
            with self.subTest(char_class=char_class):
                url = self._og_image(self._char(char_class=char_class))
                chemin = self._fichier(url)
                self.assertIsNotNone(
                    chemin, '%s names %s which is not on disk'
                    % (char_class, url))
                taille = dimensions(chemin)
                self.assertIsNotNone(
                    taille, '%s is neither PNG nor JPEG' % chemin)
                mesurees += 1
                if min(taille) < PLANCHER:
                    trop_petites.append((char_class, url, taille))
        self.assertFalse(
            trop_petites, 'these previews are under %dx%d and render as no '
            'image at all: %s' % (PLANCHER, PLANCHER, trop_petites))
        # Sans ce compte, une liste de classes vide rendrait ce test vert en
        # ne mesurant rien du tout.
        self.assertGreaterEqual(mesurees, 19,
                                'only %d classes measured' % mesurees)

    def test_a_page_that_is_not_shared_still_offers_a_picture(self):
        # La branche privee du gabarit remplacait tout le bloc de base sans
        # redeclarer d'image : le lien n'avait aucune vignette du tout.
        url = self._og_image(self._char(shared=False))
        chemin = self._fichier(url)
        self.assertIsNotNone(chemin, 'the private page names %s' % url)
        self.assertGreaterEqual(min(dimensions(chemin)), PLANCHER)
