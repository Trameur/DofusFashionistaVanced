# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No build route changes the character on a GET (Django skips CSRF on GET)."""
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.management.commands.check_pages import BUILD_PATHS
from chardata.models import Char

# Solver result, cached by /solution/<id>/ on a GET
_CHAMPS_CALCULES = ('minimal_solution',)

# Fields a GET must never change
_CHAMPS_SURVEILLES = (
    'name', 'char_name', 'char_class', 'char_build', 'level',
    'minimum_stats', 'minimum_crits', 'stats_weight', 'options',
    'inclusions', 'exclusions', 'link_shared', 'deleted', 'game_version',
)

# Routes that still write on a GET
_TOLEREES = {
    # get_resetted_sliders calls reapply_weights(char) and its caller uses GET
    '/wizardgetsliders/%s/': 'get_resetted_sliders reapplique les poids en GET',
}


def _dict_ou_none(brut):
    """The unpickled dict, or None."""
    if not isinstance(brut, (bytes, bytearray)) or not brut:
        return None
    try:
        valeur = pickle.loads(brut)
    except Exception:                               # noqa: BLE001
        return None
    return valeur if isinstance(valeur, dict) else None


def _est_un_simple_remplissage(avant, apres):
    """True if only missing keys were added, as get_stats_weights(persist=True) does."""
    a, b = _dict_ou_none(avant), _dict_ou_none(apres)
    if a is None or b is None:
        return False
    if not set(a) <= set(b):
        return False
    return all(b[cle] == valeur for cle, valeur in a.items())


class NoGetRequestWritesToTheCharacterTests(TestCase):

    def setUp(self):
        self.proprio = User.objects.create_user(
            username='proprio', email='p@test.local', password='pw-42-solid')
        self.char = Char.objects.create(
            name='projet temoin', char_name='perso', char_class='Iop',
            char_build='build', level=200,
            # Not empty, or a view writing zeros changes nothing
            minimum_stats=pickle.dumps({'AP': 11, 'MP': 5, 'Vitality': 3000}),
            minimum_crits=pickle.dumps({}),
            stats_weight=pickle.dumps({'str': 80, 'vit': 40, 'ap': 100}),
            options=pickle.dumps({'ap_exo': True, 'dragoturkey': True}),
            # slot -> item id, as set_inclusions_dict_and_check_exclusions saves it
            inclusions=pickle.dumps({'hat': 44, 'cloak': 1500}),
            exclusions=pickle.dumps([101, 202, 303, 404]),
            owner=self.proprio, game_version='dofus3',
            link_shared=False, deleted=False, minimal_solution=b'')

    def _etat(self):
        c = Char.objects.get(pk=self.char.pk)
        return {champ: getattr(c, champ) for champ in _CHAMPS_SURVEILLES}

    def test_the_seeded_state_is_not_empty(self):
        """The seeded character carries non-empty settings."""
        etat = self._etat()
        non_vides = [k for k, v in etat.items()
                     if isinstance(v, (bytes, bytearray)) and len(v) > 12]
        self.assertGreaterEqual(
            len(non_vides), 4,
            'only %d seeded blobs carry anything, so an erasing view would be '
            'invisible to this module: %s' % (len(non_vides), etat))

    def test_no_build_route_writes_on_a_get_from_its_owner(self):
        self.client.force_login(self.proprio)
        avant = self._etat()
        modifiees = []
        for route in BUILD_PATHS:
            if route in _TOLEREES:
                continue
            chemin = route % self.char.id
            try:
                self.client.get(chemin)
            except Exception:                       # noqa: BLE001
                # A view that raises does not write
                continue
            apres = self._etat()
            change = [k for k in avant
                      if avant[k] != apres[k]
                      and not _est_un_simple_remplissage(avant[k], apres[k])]
            if change:
                modifiees.append((chemin, change))
                avant = apres            # only blame the route that changed it
        self.assertFalse(
            modifiees,
            'a GET changed the character here, so any page on the web could '
            'trigger it with an <img> tag: %s' % modifiees[:6])

    def test_the_hardened_routes_answer_405_rather_than_running(self):
        self.client.force_login(self.proprio)
        DURCIES = ('/statspost/%s/', '/minstatspost/%s/', '/optionspost/%s/',
                   '/saveproject/%s/', '/exclusionspost/%s/',
                   '/inclusionspost/%s/', '/setitemlocked/%s/',
                   '/setchargender/%s/', '/setcharcolors/%s/',
                   '/setcharhidden/%s/', '/setitemforbidden/%s/',
                   '/setslotlockempty/%s/', '/setitemstatoverride/%s/')
        mauvaises = []
        for route in DURCIES:
            code = self.client.get(route % self.char.id).status_code
            if code != 405:
                mauvaises.append((route, code))
        self.assertFalse(
            mauvaises, 'these answer something other than 405 to a GET: %s'
            % mauvaises)

    def test_a_post_still_reaches_the_view(self):
        """A POST still reaches the view and writes."""
        self.client.force_login(self.proprio)
        reponse = self.client.post('/statspost/%d/' % self.char.id,
                                   {'weight_str': '55'})
        self.assertIn(reponse.status_code, (200, 302),
                      'a legitimate POST answered %s' % reponse.status_code)
        # Check the posted value: get_stats_weights re-saves the blob on its own
        apres = _dict_ou_none(self._etat()['stats_weight'])
        self.assertIsNotNone(apres, 'stats_weight is no longer a stored dict')
        self.assertEqual(
            55, apres.get('str'),
            'the POST did not land: str weight is %r, so this module is '
            'guarding a view that no longer writes what it is sent'
            % apres.get('str'))

    def test_every_tolerated_route_still_exists_and_still_writes(self):
        """Each tolerated route is still walked and still writes on a GET."""
        self.client.force_login(self.proprio)
        inconnues = sorted(set(_TOLEREES) - set(BUILD_PATHS))
        self.assertFalse(
            inconnues,
            'these tolerated routes are no longer walked at all: %s'
            % inconnues)
        guerie = []
        for route in _TOLEREES:
            avant = self._etat()
            self.client.get(route % self.char.id)
            apres = self._etat()
            reel = [k for k in avant
                    if avant[k] != apres[k]
                    and not _est_un_simple_remplissage(avant[k], apres[k])]
            if not reel:
                guerie.append(route)
        self.assertFalse(
            guerie,
            'these no longer write on a GET, so their exemption is stale and '
            'now hides the next one: %s' % guerie)
