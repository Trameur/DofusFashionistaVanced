# Copyright (C) 2026 The Dofus Fashionista
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

"""One URL slug per guide and language.

Written down rather than derived at import time: computing a slug from the
title would mean an editorial tweak to a title silently moves a published URL
and drops whatever ranking it had.

The English slug is the guide key itself, so the URLs already indexed do not
move. The others were derived from the localised titles, then adjusted where a
mechanical cut read badly or where two languages landed on the same string.

Two rules the tests enforce: every guide has a slug in every language it is
translated into, and no two entries share a slug -- the slug is what tells the
view which language to serve, so a duplicate would make the URL ambiguous.
"""

GUIDE_SLUGS = {
    'getting-started': {
        'en': 'getting-started',
        'fr': 'premier-stuff-dofus-etape',
        'es': 'primer-build-de-dofus',
        'pt': 'primeiro-build-de-dofus',
        'de': 'erstes-dofus-build-schritt',
    },
    'beginner-mistakes': {
        'en': 'beginner-mistakes',
        'fr': 'six-pieges-de-debutant',
        'es': 'seis-errores-de-novato',
        'pt': 'seis-erros-de-iniciante',
        'de': 'sechs-anfangerfehler',
    },
    'choosing-your-class': {
        'en': 'choosing-your-class',
        'fr': 'choisir-sa-classe',
        'es': 'elegir-tu-clase',
        'pt': 'escolhendo-sua-classe',
        'de': 'klassenwahl-in-dofus-version',
    },
    'how-it-works': {
        'en': 'how-it-works',
        'fr': 'comment-l-optimiseur-fonctionne',
        'es': 'como-funciona-de-verdad',
        'pt': 'como-o-otimizador-funciona',
        'de': 'wie-der-optimierer-arbeitet',
    },
    'stats-explained': {
        'en': 'stats-explained',
        'fr': 'stats-de-dofus',
        'es': 'estadisticas-de-dofus',
        'pt': 'atributos-de-dofus',
        'de': 'dofus-werte',
    },
    'critical-hits': {
        'en': 'critical-hits',
        'fr': 'coups-critiques',
        'es': 'golpes-criticos',
        'pt': 'golpes-criticos-no-dofus',
        'de': 'kritische-treffer',
    },
    'scrolls-and-characteristics': {
        'en': 'scrolls-and-characteristics',
        'fr': 'parchemins-et-caracteristiques',
        'es': 'pergaminos-y-caracteristicas',
        'pt': 'pergaminhos-e-caracteristicas',
        'de': 'rollen-und-charakteristiken',
    },
    'ap-mp-range-caps': {
        'en': 'ap-mp-range-caps',
        'fr': 'pa-pm-et-portee',
        'es': 'pa-pm-y-alcance',
        'pt': 'pa-pm-e-alcance',
        'de': 'ap-mp-und-reichweite',
    },
    'tuning-your-weights': {
        'en': 'tuning-your-weights',
        'fr': 'bien-regler-tes-poids',
        'es': 'ajustar-tus-pesos',
        'pt': 'ajustar-seus-pesos',
        'de': 'gewichte-einstellen',
    },
    'game-modes': {
        'en': 'game-modes',
        'fr': 'optimiser-son-stuff',
        'es': 'optimizar-tu-build',
        'pt': 'otimizar-seu-build',
        'de': 'builds-fur-pvm-pvp',
    },
    'reading-an-item': {
        'en': 'reading-an-item',
        'fr': 'comment-lire-un-item',
        'es': 'como-leer-un-item',
        'pt': 'como-ler-um-item',
        'de': 'man-ein-dofus-item',
    },
    'set-bonuses': {
        'en': 'set-bonuses',
        'fr': 'bonus-de-panoplie',
        'es': 'bonus-de-conjunto',
        'pt': 'bonus-de-conjunto-no-dofus',
        'de': 'set-boni',
    },
    'dofus-and-trophies': {
        'en': 'dofus-and-trophies',
        'fr': 'dofus-et-trophees',
        'es': 'dofus-y-trofeos',
        'pt': 'dofus-e-trofeus',
        'de': 'dofus-und-trophaen',
    },
    'understanding-your-solution': {
        'en': 'understanding-your-solution',
        'fr': 'lire-ta-page',
        'es': 'leer-tu-solucion',
        'pt': 'ler-sua-solucao',
        'de': 'losung-lesen',
    },
    'mono-vs-multi-element': {
        'en': 'mono-vs-multi-element',
        'fr': 'mono-ou-multi-element',
        'es': 'monoelemento-o-multielemento',
        'pt': 'mono-ou-multi-elemento',
        'de': 'mono-oder-multi-element',
    },
    'resistance-explained': {
        'en': 'resistance-explained',
        'fr': 'combien-de-resistance',
        'es': 'cuanta-resistencia-necesitas',
        'pt': 'quanta-resistencia-voce-realmente',
        'de': 'resistenz-du-wirklich-brauchst',
    },
    'monster-weaknesses': {
        'en': 'monster-weaknesses',
        'fr': 'faiblesses-des-monstres',
        'es': 'debilidades-de-los-monstruos',
        'pt': 'fraquezas-dos-monstros',
        'de': 'monster-schwachen',
    },
    'vitality-and-hp': {
        'en': 'vitality-and-hp',
        'fr': 'vitalite-et-pv',
        'es': 'vitalidad-y-pdv',
        'pt': 'vitalidade-e-pv',
        'de': 'vitalitaet-und-lp',
    },
    'gearing-up': {
        'en': 'gearing-up',
        'fr': 'trouver-son-stuff',
        'es': 'conseguir-el-equipo',
        'pt': 'conseguir-o-equipamento',
        'de': 'ausruestung-bekommen',
    },
    'comparing-builds': {
        'en': 'comparing-builds',
        'fr': 'comparer-deux-builds',
        'es': 'comparar-dos-builds',
        'pt': 'comparar-builds',
        'de': 'builds-vergleichen',
    },
    'forgemagie-planning': {
        'en': 'forgemagie-planning',
        'fr': 'planifier-ta-forgemagie',
        'es': 'planificar-tu-forjamagia',
        'pt': 'planejar-sua-forjamagia',
        'de': 'schmiedemagie-planen',
    },
    'crafting-and-professions': {
        'en': 'crafting-and-professions',
        'fr': 'craft-et-metiers',
        'es': 'fabricacion-y-oficios',
        'pt': 'fabricacao-e-profissoes',
        'de': 'handwerk-und-berufe',
    },
    'prospecting-and-drops': {
        'en': 'prospecting-and-drops',
        'fr': 'prospection-et-taux',
        'es': 'prospeccion-y-tasas',
        'pt': 'prospeccao-e-taxas',
        'de': 'prospektion-und-drop-raten',
    },
    'pets-mounts-and-shields': {
        'en': 'pets-mounts-and-shields',
        'fr': 'familiers-montures-et-boucliers',
        'es': 'mascotas-monturas-y-escudos',
        'pt': 'mascotes-montarias-e-escudos',
        'de': 'begleiter-reittiere-und-schilde',
    },
    'building-on-a-budget': {
        'en': 'building-on-a-budget',
        'fr': 'construire-avec-un-budget',
        'es': 'construir-con-presupuesto',
        'pt': 'montar-com-orcamento',
        'de': 'budget-bauen',
    },
    'inventory-and-your-own-rolls': {
        'en': 'inventory-and-your-own-rolls',
        'fr': 'inventaire-et-tes-jets',
        'es': 'inventario-y-tus-tiradas',
        'pt': 'inventario-e-teus-valores',
        'de': 'inventar-und-deine-werte',
    },
    'gearing-a-healer': {
        'en': 'gearing-a-healer',
        'fr': 'stuff-de-soigneur',
        'es': 'equipo-de-sanador',
        'pt': 'equipamento-de-curandeiro',
        'de': 'heiler-ausrusten',
    },
    'best-turn-damage': {
        'en': 'best-turn-damage',
        'fr': 'meilleur-tour-de-degats',
        'es': 'mejor-turno-de-dano',
        'pt': 'melhor-turno-de-dano',
        'de': 'bester-schadenszug',
    },
    'transcendence-runes': {
        'en': 'transcendence-runes',
        'fr': 'runes-de-transcendance',
        'es': 'runas-de-transcendencia',
        'pt': 'runas-de-transcendencia-no-dofus',
        'de': 'transzendenzrunen-der-letzte-wert',
    },
    'pvp-resistance': {
        'en': 'pvp-resistance',
        'fr': 'resistance-pvp',
        'es': 'resistencia-pvp',
        'pt': 'resistencia-pvp-no-dofus',
        'de': 'pvp-resistenz',
    },
    'versions-explained': {
        'en': 'versions-explained',
        'fr': 'versions-de-dofus',
        'es': 'versiones-de-dofus',
        'pt': 'versoes-de-dofus',
        'de': 'dofus-versionen',
    },
    'lock-and-dodge': {
        'en': 'lock-and-dodge',
        'fr': 'tacle-et-fuite',
        'es': 'placaje-y-huida',
        'pt': 'placagem-e-fuga',
        'de': 'fesseln-und-ausweichen',
    },
}
