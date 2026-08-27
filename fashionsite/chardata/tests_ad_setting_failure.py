# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Quand le reglage publicitaire ne se lit pas, la page d'administration le dit.

Le 8 aout la publicite tournait et rapportait. Le 27, aucune des six familles de
pages testees ne portait la moindre marque AdSense, et **rien n'avait prevenu
personne pendant dix-neuf jours**.

C'est la conception qui le veut, et pour une bonne raison : une ligne au JSON
casse fait echouer la lecture a CHAQUE requete, et `mail_admins` est en ERROR --
journaliser l'echec a ce niveau enverrait un courriel par page vue. Le niveau
reste donc `warning`, et ces tests le verrouillent : un futur passage a `error`
transformerait une panne en avalanche.

Le signal est mis la ou quelqu'un vient poser la question. Sans lui, le piege se
referme tout seul : la lecture echoue, la page d'administration affiche une case
DECOCHEE parce que c'est l'etat qu'elle recoit, et l'enregistrer persiste
l'extinction. **Une panne passagere devient definitive par un geste qui ne la
concernait pas.**
"""
import hashlib
import json
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from chardata.context_processors import AD_SETTING_KEY, ad_config


class AFailedAdSettingReadSaysSoTests(TestCase):

    def setUp(self):
        # ad_config() lit un cache local au worker : sans ce vidage, un test
        # herite de la reponse du precedent et mesure autre chose que lui-meme.
        cache.delete(AD_SETTING_KEY)

    def _casser(self):
        from chardata.models import SiteSetting
        return mock.patch.object(SiteSetting.objects, 'filter',
                                 side_effect=Exception('no such table'))

    def test_a_failed_read_serves_no_ads_and_marks_itself(self):
        with self._casser():
            with self.assertLogs('chardata.context_processors',
                                 level='WARNING') as journal:
                config = ad_config()
        self.assertFalse(config.get('enabled', True))
        self.assertTrue(config.get('read_failed'),
                        'the failure is invisible to whoever asks why')
        self.assertIn('could not be read', journal.output[0])

    def test_the_failure_stays_a_warning_on_purpose(self):
        """Un JSON casse echoue a chaque requete, et mail_admins est en ERROR.

        Passer ce message en `error` enverrait un courriel par page vue. Le test
        existe pour que ce raisonnement survive a quelqu'un qui trouverait le
        niveau trop bas -- il l'est, et c'est le moins mauvais des deux.
        """
        with self._casser():
            with self.assertLogs('chardata.context_processors',
                                 level='WARNING') as journal:
                ad_config()
        niveaux = [l.split(':', 1)[0] for l in journal.output]
        self.assertEqual(['WARNING'], niveaux, journal.output)

    def test_a_read_that_works_is_not_marked(self):
        """Sinon l'avertissement s'afficherait en permanence et ne dirait rien.

        C'est le controle positif de la paire : sans lui, un `read_failed`
        toujours vrai passerait le premier test sans rien garder.
        """
        from chardata.models import SiteSetting
        SiteSetting.objects.update_or_create(
            key=AD_SETTING_KEY,
            defaults={'value': json.dumps({'enabled': True, 'slots': {}})})
        cache.delete(AD_SETTING_KEY)
        config = ad_config()
        self.assertFalse(config.get('read_failed', False))
        self.assertTrue(config.get('enabled'))

    def _admin(self):
        call_command('create_local_admin', username='localadmin',
                     email='la@test.local', password='a-solid-pw-42')
        prehash = hashlib.sha256(
            ('dofusfashionista' + 'a-solid-pw-42').encode()).hexdigest()
        reponse = self.client.post('/local_login/',
                                   {'username': 'localadmin',
                                    'password': prehash})
        self.assertEqual(200, reponse.status_code)

    def test_the_admin_page_explains_the_unchecked_box(self):
        self._admin()
        with self._casser():
            page = self.client.get('/admin-tools/').content.decode(
                'utf-8', 'replace')
        self.assertIn('cannot be read', page,
                      'the admin page shows an unchecked box and no reason')
        # Le piege nomme : la case est decochee, et l'enregistrer persiste.
        # Sans la premiere lettre : la phrase a change de casse quand le
        # tiret cadratin en a ete retire, et le test a rougi pour ca seul.
        self.assertIn('his form would make the outage permanent', page)

    def test_the_admin_page_stays_quiet_when_the_read_works(self):
        self._admin()
        page = self.client.get('/admin-tools/').content.decode(
            'utf-8', 'replace')
        self.assertNotIn('cannot be read', page)
