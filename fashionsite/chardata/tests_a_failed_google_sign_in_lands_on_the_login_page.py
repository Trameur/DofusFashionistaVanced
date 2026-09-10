# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une connexion Google qui echoue ramene a la page de connexion, jamais a
une page <<Internal Server Error>>.

Source: le mail d'erreur du site du 8 septembre 2026, 21h37 UTC. Un lecteur
(Accept-Language es-ES) revient de Google sur /complete/google-oauth2/, le
point userinfo de Google repond 401, social_core l'emballe en AuthForbidden
(<<Your credentials aren't allowed>>), et la page servie est une 500. Le
middleware de social_django ne gere une SocialAuthBaseException que s'il a
une adresse ou renvoyer (SOCIAL_AUTH_LOGIN_ERROR_URL); sans elle il pose un
`messages.error` que la page de connexion n'affiche pas, rend None, et
l'exception traverse. Notre middleware ne rattrapait que quatre exceptions
benignes; les autres suivaient ce chemin.
"""

from unittest import mock

from django.test import RequestFactory, SimpleTestCase, TestCase
from social_core.exceptions import (AuthCanceled, AuthFailed, AuthForbidden,
                                    AuthMissingParameter, AuthStateForbidden,
                                    AuthStateMissing, AuthTokenError,
                                    AuthUnknownError)

from chardata.SocialAuthExceptionMiddleware import (
    SOCIAL_FAILED_PARAM, SOCIAL_FAILED_VALUE, SocialAuthExceptionMiddleware)

PHRASE = ('Signing in with Google did not go through. You can try again, or '
          'enter with your username and password.')
JOURNAL = 'chardata.SocialAuthExceptionMiddleware'


def _middleware():
    return SocialAuthExceptionMiddleware(lambda r: None)


def _requete():
    requete = RequestFactory().get('/complete/google-oauth2/',
                                   {'state': 'x', 'code': 'y'})
    requete.backend = mock.Mock(name='google-oauth2')
    requete.backend.name = 'google-oauth2'
    return requete


class TheMiddlewareTurnsEveryAuthFailureIntoARedirectTests(SimpleTestCase):

    def test_the_forbidden_of_the_eighth_of_september_redirects_with_the_flag(self):
        with self.assertLogs(JOURNAL, level='ERROR') as journal:
            reponse = _middleware().process_exception(
                _requete(), AuthForbidden('google-oauth2'))
        self.assertEqual(302, reponse.status_code)
        self.assertTrue(reponse['Location'].startswith('/login_page/?'),
                        reponse['Location'])
        self.assertIn('%s=%s' % (SOCIAL_FAILED_PARAM, SOCIAL_FAILED_VALUE),
                      reponse['Location'])
        # L'erreur reste visible du proprietaire: classe, backend, message.
        ligne = '\n'.join(journal.output)
        self.assertIn('AuthForbidden', ligne)
        self.assertIn('google-oauth2', ligne)
        self.assertIn("Your credentials aren't allowed", ligne)

    def test_the_other_auth_failures_take_the_same_door(self):
        for exception in (AuthFailed('google-oauth2', 'boom'),
                          AuthTokenError('google-oauth2', 'expired'),
                          AuthUnknownError('google-oauth2', 'odd')):
            with self.subTest(exception=type(exception).__name__):
                with self.assertLogs(JOURNAL, level='ERROR'):
                    reponse = _middleware().process_exception(_requete(),
                                                              exception)
                self.assertEqual(302, reponse.status_code)
                self.assertIn(SOCIAL_FAILED_PARAM + '=', reponse['Location'])

    def test_client_noise_stays_silent_as_before(self):
        """Consentement refuse, robot sur /complete/, etat perime: retour a
        la page de connexion sans phrase et sans mail."""
        for exception in (AuthCanceled('google-oauth2'),
                          AuthMissingParameter('google-oauth2', 'state'),
                          AuthStateMissing('google-oauth2'),
                          AuthStateForbidden('google-oauth2')):
            with self.subTest(exception=type(exception).__name__):
                with self.assertNoLogs(JOURNAL, level='ERROR'):
                    reponse = _middleware().process_exception(_requete(),
                                                              exception)
                self.assertEqual(302, reponse.status_code)
                self.assertEqual('/login_page/', reponse['Location'])

    def test_an_unrelated_exception_is_left_to_django(self):
        self.assertIsNone(_middleware().process_exception(_requete(),
                                                          ValueError('x')))


class TheCallbackItselfLandsOnTheLoginPageTests(TestCase):
    """De bout en bout, par la vraie chaine de middlewares: la vue
    /complete/ leve AuthForbidden la ou Google a repondu 401 le 8
    septembre, et le lecteur recoit une redirection, pas une 500."""

    def test_a_forbidden_callback_is_a_redirect_not_a_500(self):
        with mock.patch('social_core.backends.oauth.BaseOAuth2.auth_complete',
                        side_effect=AuthForbidden('google-oauth2')):
            with self.assertLogs(JOURNAL, level='ERROR'):
                reponse = self.client.get('/complete/google-oauth2/',
                                          {'state': 'x', 'code': 'y'})
        self.assertEqual(302, reponse.status_code)
        self.assertIn('/login_page/?%s=%s' % (SOCIAL_FAILED_PARAM,
                                              SOCIAL_FAILED_VALUE),
                      reponse['Location'])


class TheLoginPageSaysWhatHappenedTests(TestCase):

    def test_the_flag_shows_the_sentence(self):
        reponse = self.client.get('/login_page/',
                                  {SOCIAL_FAILED_PARAM: SOCIAL_FAILED_VALUE},
                                  HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, reponse.status_code)
        page = reponse.content.decode('utf-8')
        self.assertIn('social-login-failed', page)
        self.assertIn(PHRASE, page)

    def test_without_the_flag_nothing_is_said(self):
        page = self.client.get('/login_page/',
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertNotIn('social-login-failed', page)
        self.assertNotIn(PHRASE, page)

    def test_the_sentence_speaks_the_language_of_the_reader(self):
        """Le lecteur du 8 septembre etait espagnol."""
        page = self.client.get('/login_page/',
                               {SOCIAL_FAILED_PARAM: SOCIAL_FAILED_VALUE},
                               HTTP_ACCEPT_LANGUAGE='es').content.decode('utf-8')
        self.assertIn('El inicio de sesión con Google no se completó.', page)
        self.assertNotIn(PHRASE, page)


class TheSentenceIsInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations_compiled(self):
        import gettext
        import os
        from django.conf import settings
        vues = set()
        for langue in ('fr', 'es', 'pt', 'de'):
            t = gettext.translation('django',
                                    os.path.join(settings.BASE_DIR, 'locale'),
                                    languages=[langue])
            phrase = t.gettext(PHRASE)
            self.assertNotEqual(PHRASE, phrase, langue)
            self.assertIn('Google', phrase, langue)
            vues.add(phrase)
        self.assertEqual(4, len(vues))
