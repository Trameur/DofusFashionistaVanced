from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase


class UpdateGenerationTests(TestCase):
    def test_each_dofus_version_can_generate_and_render_a_build(self):
        from chardata.coaching_view import create_build
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        from fashionistapulp.game_versions import dofus_versions
        from fashionistapulp.structure import set_current_game_version

        self.addCleanup(set_current_game_version, 'dofus3')
        for version in dofus_versions():
            with self.subTest(version=version):
                set_current_game_version(version)
                owner = User.objects.create_user('updater-' + version)
                request = RequestFactory().post('/')
                request.user = owner
                char = create_build(request, 'Iop', 50, {'str'}, version)
                self.client.force_login(owner)
                prefix = '' if version == 'dofus3' else '/' + version
                response = self.client.get('%s/fashion/%d/' % (prefix, char.pk))
                self.assertIn(response.status_code, (200, 302))
                char.refresh_from_db()
                solution = get_solution(char)
                self.assertIsNotNone(solution, version)
                equipped = [item for item in solution.item_list if item.item_added]
                self.assertGreaterEqual(len(equipped), 3, version)
                self.assertTrue(all(item.level <= 50 for item in equipped), version)
                turn = _best_combo(char, solution, version)
                self.assertIsNotNone(turn, version)
                self.assertGreater(turn['total'], 0, version)
                for page in ('solution', 'spells'):
                    self.assertEqual(self.client.get('%s/%s/%d/' % (prefix, page, char.pk)).status_code, 200)
