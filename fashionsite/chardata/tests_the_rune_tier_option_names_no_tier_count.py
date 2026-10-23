from django.test import SimpleTestCase

from chardata.management.commands.wakfu_build import Command


class TheRuneTierOptionNamesNoTierCountTests(SimpleTestCase):
    def test_the_help_of_rune_tier_holds_no_number_but_the_zero(self):
        parser = Command().create_parser('manage.py', 'wakfu_build')
        action = next(one for one in parser._actions if '--rune-tier' in one.option_strings)
        self.assertEqual([], [word for word in action.help.replace('(', ' ').split()
                              if any(char.isdigit() for char in word) and word != '0'])
