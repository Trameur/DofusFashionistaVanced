# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chardata.models import BuildView


class Command(BaseCommand):
    help = 'Delete BuildView records older than 24 hours to keep database clean'

    #: Combien de lignes par passe. Le premier menage a supprimer 156 914
    #: lignes d'un coup, parce que rien n'avait jamais appele cette commande.
    #: Elle tourne desormais au demarrage du serveur, donc pendant la fenetre
    #: de maintenance : une seule requete de cette taille tient un verrou sur
    #: la table tout du long, la ou des lots le rendent entre chaque.
    TAILLE_DE_LOT = 5000

    #: Garde-fou : sans lui, une erreur de filtre qui ne supprimerait rien
    #: tournerait sans fin au demarrage et le serveur ne repartirait jamais.
    PASSES_MAX = 1000

    def handle(self, *args, **options):
        cutoff_time = timezone.now() - timedelta(hours=24)
        total = 0
        for _passe in range(self.PASSES_MAX):
            lot = list(BuildView.objects
                       .filter(viewed_at__lt=cutoff_time)
                       .values_list('pk', flat=True)[:self.TAILLE_DE_LOT])
            if not lot:
                break
            supprimees, _ = BuildView.objects.filter(pk__in=lot).delete()
            total += supprimees
            # Un lot incomplet est le dernier : inutile de redemander pour
            # s'entendre repondre zero.
            if len(lot) < self.TAILLE_DE_LOT:
                break
        else:
            self.stdout.write(self.style.WARNING(
                'stopped after %d passes with rows still older than the '
                'cutoff; something is keeping them.' % self.PASSES_MAX))

        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {total} old view records')
        )
