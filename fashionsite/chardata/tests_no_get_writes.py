# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un GET ne modifie pas le personnage.

Django ne verifie PAS le jeton CSRF sur les methodes dites sures -- GET, HEAD,
OPTIONS, TRACE. Une vue qui ECRIT et qui accepte GET est donc declenchable
depuis n'importe quelle page du web : une balise <img src="https://.../statspost
/12/"> suffit, le navigateur de la victime envoie son cookie de session, et la
vue s'execute avec ses droits. **La verification de propriete ne protege pas de
ca** : c'est justement la victime qui est proprietaire.

Quinze vues ecrivaient sans exiger POST. Toutes leurs appelantes reelles
postaient deja -- `stateengine.js:24` fait `$.post`, `projdetails.html` a
`<form method="post">`, et les six de `solution_view` sont appelees par `$.post`
litteral dans `solution.html`. Poser `@require_POST` ne change donc rien pour un
appelant legitime.

**Ce module enumere au lieu de choisir.** Un test ecrit a la main garde les
quinze que j'ai vues ; il ne garde pas la seizieme. Il parcourt donc TOUTES les
routes de `check_pages.BUILD_PATHS` et exige qu'aucune ne modifie le personnage
sur un GET -- une route ajoutee la se retrouve gardee ici sans que personne y
pense.

Le detail qui rendait la panne invisible : sur un GET, `request.POST` est un
dictionnaire vide, donc `safe_int(request.POST.get('weight_x', 0), 0)` rend 0
pour chaque statistique et la vue enregistre consciencieusement des zeros
partout. Rien ne plante, rien ne se signale, les reglages disparaissent.

Le commentaire de `check_pages.py` disait deja l'attendu : « The *post routes
expect a POST: answering 405 or redirecting is right, a 500 is not. » L'outil de
diagnostic du projet parcourt ces routes EN GET et EN PROPRIETAIRE : il effacait
donc les reglages des builds qu'il visitait.
"""
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.management.commands.check_pages import BUILD_PATHS
from chardata.models import Char

#: Les champs dont un GET peut legitimement changer la valeur.
#:
#: `minimal_solution` est le resultat calcule du solveur, mis en cache par
#: `/solution/<id>/` au moment ou on regarde la page. C'est une consequence de
#: la lecture, pas une intention de l'utilisateur : personne ne perd un reglage
#: parce qu'un tiers a fait recalculer sa solution.
_CHAMPS_CALCULES = ('minimal_solution',)

#: Ce qu'un GET ne doit jamais toucher.
_CHAMPS_SURVEILLES = (
    'name', 'char_name', 'char_class', 'char_build', 'level',
    'minimum_stats', 'minimum_crits', 'stats_weight', 'options',
    'inclusions', 'exclusions', 'link_shared', 'deleted', 'game_version',
)

#: Les routes qui ecrivent sur un GET et qu'on NE PEUT PAS durcir seules.
#:
#: Deux seulement, et chacune porte sa raison : une regle elargie couvre la
#: prochaine faute en silence, une exception nommee la laisse rougir. Ce sont
#: deux DETTES, pas deux acquittements.
_TOLEREES = {
    # Appelee en GET par le site lui-meme, solution.html:1060. Poser
    # @require_POST sans changer le JavaScript casserait le partage : a
    # corriger des deux cotes en meme temps.
    '/getsharinglink/%s/': 'solution.html:1060 appelle en $.get',
    # wizard_view.get_resetted_sliders appelle reapply_weights(char), donc
    # ecrit ; son appelant est en GET lui aussi.
    '/wizardgetsliders/%s/': 'get_resetted_sliders reapplique les poids en GET',
}


def _dict_ou_none(brut):
    """Le dictionnaire enregistre, ou None si ce n'en est pas un."""
    if not isinstance(brut, (bytes, bytearray)) or not brut:
        return None
    try:
        valeur = pickle.loads(brut)
    except Exception:                               # noqa: BLE001
        return None
    return valeur if isinstance(valeur, dict) else None


def _est_un_simple_remplissage(avant, apres):
    """L'ecart se reduit-il a l'ajout de cles absentes.

    `get_stats_weights(char, persist=True)` complete les statistiques qui
    manquent -- 0, ou une valeur par defaut de smart_build -- puis re-sauvegarde.
    Son docstring le dit, et une demi-douzaine de pages de LECTURE la traversent
    (/stats/, /wizard/, /infeasible/, ...). Ce n'est pas destructif : ca COMPLETE
    l'enregistrement.

    Exclure par CAUSE plutot que par adresse est le point de ce module. Une
    liste d'adresses aurait grossi d'une ligne a chaque page de lecture, et une
    liste qui grossit finit par exempter la vraie faute. Ici la faute reste
    prise : un GET qui remet a zero une statistique DEJA pesee change une cle
    existante, et cette fonction rend False.
    """
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
            # Des valeurs NON VIDES : c'est tout l'interet. Sur des blobs
            # vides, une vue qui ecrit des zeros ne changerait rien de
            # visible et le test passerait sur une panne reelle.
            minimum_stats=pickle.dumps({'AP': 11, 'MP': 5, 'Vitality': 3000}),
            minimum_crits=pickle.dumps({}),
            stats_weight=pickle.dumps({'str': 80, 'vit': 40, 'ap': 100}),
            options=pickle.dumps({'ap_exo': True, 'dragoturkey': True}),
            # slot -> identifiant d'objet : la forme que
            # `set_inclusions_dict_and_check_exclusions` enregistre.
            # Une liste ici faisait exploser le solveur sur
            # `frozenset(d.items())`, et le bruit venait de ma graine.
            inclusions=pickle.dumps({'hat': 44, 'cloak': 1500}),
            exclusions=pickle.dumps([101, 202, 303, 404]),
            owner=self.proprio, game_version='dofus3',
            link_shared=False, deleted=False, minimal_solution=b'')

    def _etat(self):
        c = Char.objects.get(pk=self.char.pk)
        return {champ: getattr(c, champ) for champ in _CHAMPS_SURVEILLES}

    def test_the_seeded_state_is_not_empty(self):
        """Le plancher du temoin.

        Sur un personnage dont les reglages sont deja vides, une vue qui les
        efface ne change rien et tous les tests ci-dessous passent au vert sur
        la panne exacte qu'ils pretendent attraper.
        """
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
                # Une exception est un autre defaut, garde ailleurs. Ici on ne
                # regarde que l'ecriture, et une vue qui explose n'ecrit pas.
                continue
            apres = self._etat()
            change = [k for k in avant
                      if avant[k] != apres[k]
                      and not _est_un_simple_remplissage(avant[k], apres[k])]
            if change:
                modifiees.append((chemin, change))
                avant = apres            # ne pas re-accuser les suivantes
        self.assertFalse(
            modifiees,
            'a GET changed the character here, so any page on the web could '
            'trigger it with an <img> tag: %s' % modifiees[:6])

    def test_the_hardened_routes_answer_405_rather_than_running(self):
        """Refuser franchement, pas repondre 200 en ne faisant rien.

        Une vue qui rend 200 sur un GET laisse croire a l'appelant que son
        geste a abouti. `@require_POST` rend 405, ce que le commentaire de
        `check_pages` nommait deja comme la bonne reponse.
        """
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
        """Le controle positif de tout le module.

        Sans lui, `@require_POST` pose sur une vue morte -- ou une route qui
        404 -- rendrait les trois tests precedents verts. Le POST doit encore
        arriver jusqu'au code, et ecrire.
        """
        self.client.force_login(self.proprio)
        reponse = self.client.post('/statspost/%d/' % self.char.id,
                                   {'weight_str': '55'})
        self.assertIn(reponse.status_code, (200, 302),
                      'a legitimate POST answered %s' % reponse.status_code)
        # La VALEUR postee, pas seulement « le blob a change ». Une premiere
        # version comparait les octets avant et apres : elle restait VERTE avec
        # l'ecriture retiree de la vue, parce que `get_stats_weights` remplit
        # les defauts et re-sauvegarde au passage. Le controle positif se
        # laissait berner par la cause meme que ce module exclut plus haut.
        apres = _dict_ou_none(self._etat()['stats_weight'])
        self.assertIsNotNone(apres, 'stats_weight is no longer a stored dict')
        self.assertEqual(
            55, apres.get('str'),
            'the POST did not land: str weight is %r, so this module is '
            'guarding a view that no longer writes what it is sent'
            % apres.get('str'))

    def test_every_tolerated_route_still_exists_and_still_writes(self):
        """Une exception qui ne designe plus rien est une dette oubliee.

        Deux moities. Si la route disparait du parcours, la ligne exempte du
        vide et masquera la prochaine. Et si elle cesse d'ecrire -- parce que
        quelqu'un l'a corrigee -- la ligne doit partir, sinon la liste raconte
        un probleme qui n'existe plus.
        """
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
