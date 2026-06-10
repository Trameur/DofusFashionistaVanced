# -*- coding: utf-8 -*-

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

import math

from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.utils import translation

from chardata.forgemagie_data import (
    MAGEABLE_TYPES, ONE_PERCENT_EXO_STATS, OVER_WEIGHT_CAP,
    get_fm_stats, get_ruleset,
)
from chardata.image_store import get_image_url
from chardata.stat_icons import get_stat_icon_path
from chardata.util import set_response, version_reverse
from fashionistapulp.dofus_constants import STAT_ORDER
from fashionistapulp.fashion_util import strip_accents
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


LOCALIZED_UI = {
    'en': {
        'title': 'Smithmagic Lab',
        'subtitle': 'Plan your maging: sink math, rune counts and risk for this game version.',
        'version_note_modern': 'Values for the current PC game (Dofus 2 / Dofus 3).',
        'version_note_touch': 'Values for Dofus Touch, which kept the pre-2.29 weights: Vi runes give +3/+10/+30, Crit weighs 30, Heal weighs 20.',
        'version_note_retro': 'Values for Dofus Retro 1.29: fixed resists weigh 5, % resists 4, Reflects 30, Trap damage 15.',
        'search_label': 'Item',
        'search_placeholder': 'Type an item name (example: Gelano)',
        'search_hint': 'Pick an item to load its best rolls, then enter your actual rolls and targets.',
        'search_no_results': 'No item found.',
        'item_level': 'Lvl.',
        'wb_title': 'Maging workbench',
        'wb_stat': 'Stat',
        'wb_best_roll': 'Best roll',
        'wb_current': 'Your roll',
        'wb_target': 'Target',
        'wb_unit_weight': 'Weight/pt',
        'wb_missing_weight': 'Missing weight',
        'wb_needed_weight': 'Weight to add',
        'wb_runes': 'Suggested runes',
        'wb_difficulty': 'Risk',
        'wb_not_mageable': 'not mageable',
        'wb_add_exo': 'Add a stat (over/exo)',
        'wb_exo_pick': 'Choose a stat',
        'wb_add': 'Add',
        'wb_remove': 'Remove',
        'total_sink': 'Available sink (rolls below max)',
        'total_needed': 'Total weight to add',
        'total_balance': 'Balance',
        'verdict_ok': 'Your plan fits in the item’s sink: with patience it can pass without overmage.',
        'verdict_over': 'Overmage: your plan needs %s more weight than the item’s sink. Expect many attempts and sacrificed stats.',
        'verdict_cap': 'Impossible: %s exceeds the cap of 101 over/exo weight on a single stat.',
        'exo_one_percent': 'AP/MP/Range exos only land on a critical success (~1% per rune).',
        'diff_safe': 'very likely',
        'diff_likely': 'likely',
        'diff_risky': 'risky',
        'diff_hard': 'hard',
        'diff_exo': 'exo (~1%)',
        'diff_over': 'overmage',
        'how_title': 'How smithmagic works',
        'how_p1': 'Each rune attempt has three possible outcomes:',
        'how_sc': 'Critical success - the bonus is added and nothing else moves.',
        'how_sn': 'Neutral success - the bonus is added, but the item loses an equivalent weight in other stats (taken from the sink first).',
        'how_ec': 'Critical failure - no bonus, and the item loses stats worth the rune’s weight.',
        'how_sink': 'The sink (reliquat): when a lost stat weighs more than the rune you threw, the difference is stored invisibly on the item and absorbs future losses. The available sink is estimated as the weight gap between your rolls and the item’s best rolls.',
        'how_over': 'Overmage: pushing a stat above its best roll, or adding a stat the item does not have (an exo), costs sink. The total over/exo weight on one stat can never exceed 101.',
        'how_exo': 'Exo runes for AP, MP and Range only pass on a critical success, commonly estimated at 1% per attempt. Other exos pass like normal runes but count against the 101 cap.',
        'how_rule20': 'Rule of thumb: a rune passes reliably while the stat is below ~20x the rune’s bonus (+1 runes up to ~20, +3 up to ~60, +10 up to ~200). Above that, expect failures - that is where sink and patience matter.',
        'how_sink_loss': 'Careful: the sink is tied to the maging session. Equipping, trading or listing the item is commonly reported to reset it.',
        'how_disclaimer': 'Ankama has never published the exact success formula; rates shown here are community estimates.',
        'tips_title': 'Strategy tips',
        'tip_1': 'Mage one stat at a time: big runes first while the stat is low, small runes to finish near the cap.',
        'tip_2': 'Build sink before expensive runes: sacrifice a heavy stat you do not need and its weight will absorb later losses.',
        'tip_3': 'Throw AP/MP exo runes on an item with a full sink, so critical failures eat the sink instead of your good rolls.',
        'tip_4': 'Compare prices both ways: crushing items into runes versus buying runes directly - whichever is cheaper that day.',
        'ref_title': 'Rune & weight reference',
        'ref_stat': 'Stat',
        'ref_density': 'Weight per point',
        'ref_runes': 'Runes (bonus / weight)',
        'ref_max_over': 'Max over/exo',
        'ref_no_rune': 'No rune',
        'ref_approx': 'approximate',
        'footer_sources': 'Mechanics compiled from community references (Ankama tutorials, JeuxOnLine, Dofus pour les Noobs, Dofuzion 1.29 table, Dofus Touch rune lists).',
    },
    'fr': {
        'title': 'Atelier de Forgemagie',
        'subtitle': 'Planifiez vos FM : calcul du puits, nombre de runes et risque pour cette version du jeu.',
        'version_note_modern': 'Valeurs pour le jeu PC actuel (Dofus 2 / Dofus 3).',
        'version_note_touch': 'Valeurs pour Dofus Touch, qui a conservé les poids d’avant la 2.29 : runes Vi +3/+10/+30, Critique au poids 30, Soin au poids 20.',
        'version_note_retro': 'Valeurs pour Dofus Retro 1.29 : résistances fixes au poids 5, % résistances 4, Renvoi de dommages 30, Dommages aux pièges 15.',
        'search_label': 'Objet',
        'search_placeholder': 'Tapez un nom d’objet (exemple : Gelano)',
        'search_hint': 'Choisissez un objet pour charger ses jets parfaits, puis entrez vos jets réels et vos objectifs.',
        'search_no_results': 'Aucun objet trouvé.',
        'item_level': 'Niv.',
        'wb_title': 'Établi de forgemagie',
        'wb_stat': 'Caractéristique',
        'wb_best_roll': 'Jet parfait',
        'wb_current': 'Votre jet',
        'wb_target': 'Objectif',
        'wb_unit_weight': 'Poids/pt',
        'wb_missing_weight': 'Poids manquant',
        'wb_needed_weight': 'Poids à poser',
        'wb_runes': 'Runes suggérées',
        'wb_difficulty': 'Risque',
        'wb_not_mageable': 'non forgemageable',
        'wb_add_exo': 'Ajouter une caractéristique (over/exo)',
        'wb_exo_pick': 'Choisir une caractéristique',
        'wb_add': 'Ajouter',
        'wb_remove': 'Retirer',
        'total_sink': 'Puits disponible (jets sous le max)',
        'total_needed': 'Poids total à poser',
        'total_balance': 'Bilan',
        'verdict_ok': 'Votre plan tient dans le puits de l’objet : avec de la patience, il peut passer sans overmage.',
        'verdict_over': 'Overmage : votre plan demande %s de poids de plus que le puits de l’objet. Attendez-vous à de nombreux essais et des stats sacrifiées.',
        'verdict_cap': 'Impossible : %s dépasse le plafond de 101 de poids en over/exo sur une même caractéristique.',
        'exo_one_percent': 'Les exos PA/PM/PO ne passent que sur un succès critique (~1 % par rune).',
        'diff_safe': 'très probable',
        'diff_likely': 'probable',
        'diff_risky': 'risqué',
        'diff_hard': 'difficile',
        'diff_exo': 'exo (~1 %)',
        'diff_over': 'overmage',
        'how_title': 'Comment fonctionne la forgemagie',
        'how_p1': 'Chaque pose de rune a trois issues possibles :',
        'how_sc': 'Succès critique - le bonus est ajouté et rien d’autre ne bouge.',
        'how_sn': 'Succès neutre - le bonus est ajouté, mais l’objet perd un poids équivalent dans d’autres stats (pris d’abord dans le puits).',
        'how_ec': 'Échec critique - pas de bonus, et l’objet perd des stats à hauteur du poids de la rune.',
        'how_sink': 'Le puits (reliquat) : quand une stat perdue pèse plus lourd que la rune lancée, la différence est stockée invisiblement sur l’objet et absorbe les pertes suivantes. Le puits disponible est estimé comme l’écart de poids entre vos jets et les jets parfaits.',
        'how_over': 'Overmage : monter une stat au-dessus de son jet parfait, ou ajouter une stat absente de l’objet (un exo), consomme du puits. Le poids total en over/exo sur une stat ne peut jamais dépasser 101.',
        'how_exo': 'Les runes exo PA, PM et PO ne passent que sur un succès critique, estimé à 1 % par essai. Les autres exos passent comme des runes normales mais comptent dans le plafond de 101.',
        'how_rule20': 'Règle empirique : une rune passe bien tant que la stat est sous ~20x le bonus de la rune (+1 jusqu’à ~20, +3 jusqu’à ~60, +10 jusqu’à ~200). Au-delà, attendez-vous à des échecs - c’est là que le puits et la patience comptent.',
        'how_sink_loss': 'Attention : le puits est lié à la session de forgemagie. Équiper, échanger ou mettre l’objet en vente le réinitialise selon les retours de la communauté.',
        'how_disclaimer': 'Ankama n’a jamais publié la formule exacte de réussite ; les taux affichés ici sont des estimations communautaires.',
        'tips_title': 'Conseils de stratégie',
        'tip_1': 'Forgemagez une stat à la fois : grosses runes d’abord quand la stat est basse, petites runes pour finir près du max.',
        'tip_2': 'Créez du puits avant les runes chères : sacrifiez une stat lourde dont vous ne voulez pas, son poids absorbera les pertes suivantes.',
        'tip_3': 'Lancez les runes exo PA/PM sur un objet au puits plein : les échecs critiques mangeront le puits au lieu de vos bons jets.',
        'tip_4': 'Comparez les prix dans les deux sens : briser des objets en runes ou acheter les runes directement - selon ce qui est le moins cher ce jour-là.',
        'ref_title': 'Référence des runes et des poids',
        'ref_stat': 'Caractéristique',
        'ref_density': 'Poids par point',
        'ref_runes': 'Runes (bonus / poids)',
        'ref_max_over': 'Over/exo max',
        'ref_no_rune': 'Pas de rune',
        'ref_approx': 'approximatif',
        'footer_sources': 'Mécaniques compilées à partir de références communautaires (tutoriels Ankama, JeuxOnLine, Dofus pour les Noobs, tableau 1.29 de Dofuzion, listes de runes Dofus Touch).',
    },
    'es': {
        'title': 'Taller de Forjamagia',
        'subtitle': 'Planifica tu forjamagia: cálculo del pozo, cantidad de runas y riesgo para esta versión del juego.',
        'version_note_modern': 'Valores para el juego de PC actual (Dofus 2 / Dofus 3).',
        'version_note_touch': 'Valores para Dofus Touch, que conservó los pesos anteriores a la 2.29: runas Vi +3/+10/+30, Crítico con peso 30, Curación con peso 20.',
        'version_note_retro': 'Valores para Dofus Retro 1.29: resistencias fijas con peso 5, % resistencias 4, Reenvío de daños 30, Daños de trampa 15.',
        'search_label': 'Objeto',
        'search_placeholder': 'Escribe el nombre de un objeto (ejemplo: Gelano)',
        'search_hint': 'Elige un objeto para cargar sus tiradas perfectas y luego escribe tus tiradas reales y tus objetivos.',
        'search_no_results': 'No se encontró ningún objeto.',
        'item_level': 'Nv.',
        'wb_title': 'Banco de forjamagia',
        'wb_stat': 'Característica',
        'wb_best_roll': 'Tirada perfecta',
        'wb_current': 'Tu tirada',
        'wb_target': 'Objetivo',
        'wb_unit_weight': 'Peso/pt',
        'wb_missing_weight': 'Peso que falta',
        'wb_needed_weight': 'Peso a colocar',
        'wb_runes': 'Runas sugeridas',
        'wb_difficulty': 'Riesgo',
        'wb_not_mageable': 'no forjamageable',
        'wb_add_exo': 'Añadir una característica (over/exo)',
        'wb_exo_pick': 'Elige una característica',
        'wb_add': 'Añadir',
        'wb_remove': 'Quitar',
        'total_sink': 'Pozo disponible (tiradas bajo el máximo)',
        'total_needed': 'Peso total a colocar',
        'total_balance': 'Balance',
        'verdict_ok': 'Tu plan cabe en el pozo del objeto: con paciencia puede pasar sin overmage.',
        'verdict_over': 'Overmage: tu plan necesita %s de peso más que el pozo del objeto. Espera muchos intentos y características sacrificadas.',
        'verdict_cap': 'Imposible: %s supera el límite de 101 de peso en over/exo sobre una misma característica.',
        'exo_one_percent': 'Los exos de PA/PM/Alcance solo pasan con un éxito crítico (~1 % por runa).',
        'diff_safe': 'muy probable',
        'diff_likely': 'probable',
        'diff_risky': 'arriesgado',
        'diff_hard': 'difícil',
        'diff_exo': 'exo (~1 %)',
        'diff_over': 'overmage',
        'how_title': 'Cómo funciona la forjamagia',
        'how_p1': 'Cada intento de runa tiene tres resultados posibles:',
        'how_sc': 'Éxito crítico - el bono se añade y nada más cambia.',
        'how_sn': 'Éxito neutro - el bono se añade, pero el objeto pierde un peso equivalente en otras características (tomado primero del pozo).',
        'how_ec': 'Fracaso crítico - no hay bono y el objeto pierde características por el peso de la runa.',
        'how_sink': 'El pozo (reliquia): cuando una característica perdida pesa más que la runa lanzada, la diferencia se guarda de forma invisible en el objeto y absorbe pérdidas futuras. El pozo disponible se estima como la diferencia de peso entre tus tiradas y las tiradas perfectas.',
        'how_over': 'Overmage: subir una característica por encima de su tirada perfecta, o añadir una que el objeto no tiene (un exo), consume pozo. El peso total en over/exo sobre una característica nunca puede superar 101.',
        'how_exo': 'Las runas exo de PA, PM y Alcance solo pasan con un éxito crítico, estimado en un 1 % por intento. Los demás exos pasan como runas normales pero cuentan para el límite de 101.',
        'how_rule20': 'Regla práctica: una runa pasa bien mientras la característica esté por debajo de ~20x el bono de la runa (+1 hasta ~20, +3 hasta ~60, +10 hasta ~200). Por encima, espera fracasos: ahí cuentan el pozo y la paciencia.',
        'how_sink_loss': 'Cuidado: el pozo está ligado a la sesión de forjamagia. Equipar, intercambiar o poner el objeto en venta lo reinicia según la comunidad.',
        'how_disclaimer': 'Ankama nunca publicó la fórmula exacta de éxito; las tasas mostradas aquí son estimaciones de la comunidad.',
        'tips_title': 'Consejos de estrategia',
        'tip_1': 'Forja una característica a la vez: runas grandes primero cuando la característica está baja, runas pequeñas para terminar cerca del máximo.',
        'tip_2': 'Genera pozo antes de las runas caras: sacrifica una característica pesada que no necesites y su peso absorberá las pérdidas siguientes.',
        'tip_3': 'Lanza las runas exo de PA/PM sobre un objeto con el pozo lleno: los fracasos críticos se comerán el pozo en lugar de tus buenas tiradas.',
        'tip_4': 'Compara precios en ambos sentidos: romper objetos en runas o comprar las runas directamente, según lo que esté más barato ese día.',
        'ref_title': 'Referencia de runas y pesos',
        'ref_stat': 'Característica',
        'ref_density': 'Peso por punto',
        'ref_runes': 'Runas (bono / peso)',
        'ref_max_over': 'Over/exo máx.',
        'ref_no_rune': 'Sin runa',
        'ref_approx': 'aproximado',
        'footer_sources': 'Mecánicas compiladas a partir de referencias de la comunidad (tutoriales de Ankama, JeuxOnLine, Dofus pour les Noobs, tabla 1.29 de Dofuzion, listas de runas de Dofus Touch).',
    },
    'pt': {
        'title': 'Oficina de Forjamagia',
        'subtitle': 'Planeje sua forjamagia: cálculo do poço, quantidade de runas e risco para esta versão do jogo.',
        'version_note_modern': 'Valores para o jogo de PC atual (Dofus 2 / Dofus 3).',
        'version_note_touch': 'Valores para o Dofus Touch, que manteve os pesos anteriores à 2.29: runas Vi +3/+10/+30, Crítico com peso 30, Cura com peso 20.',
        'version_note_retro': 'Valores para o Dofus Retro 1.29: resistências fixas com peso 5, % resistências 4, Reenvio de danos 30, Danos de armadilha 15.',
        'search_label': 'Item',
        'search_placeholder': 'Digite o nome de um item (exemplo: Gelano)',
        'search_hint': 'Escolha um item para carregar suas rolagens perfeitas e depois informe suas rolagens reais e suas metas.',
        'search_no_results': 'Nenhum item encontrado.',
        'item_level': 'Nv.',
        'wb_title': 'Bancada de forjamagia',
        'wb_stat': 'Atributo',
        'wb_best_roll': 'Rolagem perfeita',
        'wb_current': 'Sua rolagem',
        'wb_target': 'Meta',
        'wb_unit_weight': 'Peso/pt',
        'wb_missing_weight': 'Peso faltante',
        'wb_needed_weight': 'Peso a colocar',
        'wb_runes': 'Runas sugeridas',
        'wb_difficulty': 'Risco',
        'wb_not_mageable': 'não forjamageável',
        'wb_add_exo': 'Adicionar um atributo (over/exo)',
        'wb_exo_pick': 'Escolha um atributo',
        'wb_add': 'Adicionar',
        'wb_remove': 'Remover',
        'total_sink': 'Poço disponível (rolagens abaixo do máximo)',
        'total_needed': 'Peso total a colocar',
        'total_balance': 'Saldo',
        'verdict_ok': 'Seu plano cabe no poço do item: com paciência ele pode passar sem overmage.',
        'verdict_over': 'Overmage: seu plano precisa de %s de peso a mais do que o poço do item. Espere muitas tentativas e atributos sacrificados.',
        'verdict_cap': 'Impossível: %s ultrapassa o limite de 101 de peso em over/exo em um mesmo atributo.',
        'exo_one_percent': 'Exos de PA/PM/Alcance só passam com um sucesso crítico (~1% por runa).',
        'diff_safe': 'muito provável',
        'diff_likely': 'provável',
        'diff_risky': 'arriscado',
        'diff_hard': 'difícil',
        'diff_exo': 'exo (~1%)',
        'diff_over': 'overmage',
        'how_title': 'Como funciona a forjamagia',
        'how_p1': 'Cada tentativa de runa tem três resultados possíveis:',
        'how_sc': 'Sucesso crítico - o bônus é adicionado e nada mais muda.',
        'how_sn': 'Sucesso neutro - o bônus é adicionado, mas o item perde um peso equivalente em outros atributos (tirado primeiro do poço).',
        'how_ec': 'Falha crítica - nenhum bônus, e o item perde atributos no valor do peso da runa.',
        'how_sink': 'O poço (resíduo): quando um atributo perdido pesa mais que a runa lançada, a diferença fica armazenada de forma invisível no item e absorve perdas futuras. O poço disponível é estimado como a diferença de peso entre suas rolagens e as rolagens perfeitas.',
        'how_over': 'Overmage: subir um atributo acima da rolagem perfeita, ou adicionar um atributo que o item não tem (um exo), consome poço. O peso total em over/exo em um atributo nunca pode passar de 101.',
        'how_exo': 'Runas exo de PA, PM e Alcance só passam com um sucesso crítico, estimado em 1% por tentativa. Os outros exos passam como runas normais, mas contam para o limite de 101.',
        'how_rule20': 'Regra prática: uma runa passa bem enquanto o atributo está abaixo de ~20x o bônus da runa (+1 até ~20, +3 até ~60, +10 até ~200). Acima disso, espere falhas - é aí que o poço e a paciência contam.',
        'how_sink_loss': 'Cuidado: o poço está ligado à sessão de forjamagia. Equipar, trocar ou colocar o item à venda o reinicia, segundo a comunidade.',
        'how_disclaimer': 'A Ankama nunca publicou a fórmula exata de sucesso; as taxas mostradas aqui são estimativas da comunidade.',
        'tips_title': 'Dicas de estratégia',
        'tip_1': 'Forje um atributo de cada vez: runas grandes primeiro enquanto o atributo está baixo, runas pequenas para terminar perto do máximo.',
        'tip_2': 'Crie poço antes das runas caras: sacrifique um atributo pesado que você não precisa e o peso dele absorverá as perdas seguintes.',
        'tip_3': 'Lance runas exo de PA/PM em um item com o poço cheio: as falhas críticas comerão o poço em vez das suas boas rolagens.',
        'tip_4': 'Compare preços dos dois lados: quebrar itens em runas ou comprar runas diretamente - o que estiver mais barato no dia.',
        'ref_title': 'Referência de runas e pesos',
        'ref_stat': 'Atributo',
        'ref_density': 'Peso por ponto',
        'ref_runes': 'Runas (bônus / peso)',
        'ref_max_over': 'Over/exo máx.',
        'ref_no_rune': 'Sem runa',
        'ref_approx': 'aproximado',
        'footer_sources': 'Mecânicas compiladas a partir de referências da comunidade (tutoriais da Ankama, JeuxOnLine, Dofus pour les Noobs, tabela 1.29 do Dofuzion, listas de runas do Dofus Touch).',
    },
    'de': {
        'title': 'Schmiedemagie-Labor',
        'subtitle': 'Plane deine Schmiedemagie: Senken-Berechnung, Runenanzahl und Risiko fuer diese Spielversion.',
        'version_note_modern': 'Werte fuer das aktuelle PC-Spiel (Dofus 2 / Dofus 3).',
        'version_note_touch': 'Werte fuer Dofus Touch, das die Gewichte von vor 2.29 behalten hat: Vi-Runen +3/+10/+30, Kritisch mit Gewicht 30, Heilung mit Gewicht 20.',
        'version_note_retro': 'Werte fuer Dofus Retro 1.29: feste Resistenzen mit Gewicht 5, % Resistenzen 4, Schadensreflexion 30, Fallenschaden 15.',
        'search_label': 'Gegenstand',
        'search_placeholder': 'Gegenstandsname eingeben (Beispiel: Gelano)',
        'search_hint': 'Waehle einen Gegenstand, um seine perfekten Werte zu laden, und trage dann deine echten Werte und Ziele ein.',
        'search_no_results': 'Kein Gegenstand gefunden.',
        'item_level': 'St.',
        'wb_title': 'Schmiedemagie-Werkbank',
        'wb_stat': 'Wert',
        'wb_best_roll': 'Perfekter Wurf',
        'wb_current': 'Dein Wurf',
        'wb_target': 'Ziel',
        'wb_unit_weight': 'Gewicht/Pkt',
        'wb_missing_weight': 'Fehlendes Gewicht',
        'wb_needed_weight': 'Zu setzendes Gewicht',
        'wb_runes': 'Vorgeschlagene Runen',
        'wb_difficulty': 'Risiko',
        'wb_not_mageable': 'nicht magbar',
        'wb_add_exo': 'Wert hinzufuegen (Over/Exo)',
        'wb_exo_pick': 'Wert auswaehlen',
        'wb_add': 'Hinzufuegen',
        'wb_remove': 'Entfernen',
        'total_sink': 'Verfuegbare Senke (Wuerfe unter dem Maximum)',
        'total_needed': 'Gesamtgewicht zu setzen',
        'total_balance': 'Bilanz',
        'verdict_ok': 'Dein Plan passt in die Senke des Gegenstands: Mit Geduld kann er ohne Overmage gelingen.',
        'verdict_over': 'Overmage: Dein Plan braucht %s Gewicht mehr, als die Senke des Gegenstands hergibt. Rechne mit vielen Versuchen und geopferten Werten.',
        'verdict_cap': 'Unmoeglich: %s ueberschreitet die Grenze von 101 Over/Exo-Gewicht auf einem einzelnen Wert.',
        'exo_one_percent': 'AP/BP/Reichweite-Exos gelingen nur mit einem kritischen Erfolg (~1% pro Rune).',
        'diff_safe': 'sehr wahrscheinlich',
        'diff_likely': 'wahrscheinlich',
        'diff_risky': 'riskant',
        'diff_hard': 'schwer',
        'diff_exo': 'Exo (~1%)',
        'diff_over': 'Overmage',
        'how_title': 'So funktioniert Schmiedemagie',
        'how_p1': 'Jeder Runenversuch hat drei moegliche Ausgaenge:',
        'how_sc': 'Kritischer Erfolg - der Bonus wird hinzugefuegt und sonst aendert sich nichts.',
        'how_sn': 'Neutraler Erfolg - der Bonus wird hinzugefuegt, aber der Gegenstand verliert ein gleichwertiges Gewicht an anderen Werten (zuerst aus der Senke).',
        'how_ec': 'Kritischer Misserfolg - kein Bonus, und der Gegenstand verliert Werte im Umfang des Runengewichts.',
        'how_sink': 'Die Senke (Reliquat): Wenn ein verlorener Wert mehr wiegt als die geworfene Rune, wird die Differenz unsichtbar auf dem Gegenstand gespeichert und faengt spaetere Verluste ab. Die verfuegbare Senke wird als Gewichtsabstand zwischen deinen Wuerfen und den perfekten Wuerfen geschaetzt.',
        'how_over': 'Overmage: Einen Wert ueber seinen perfekten Wurf zu heben oder einen neuen Wert hinzuzufuegen (ein Exo) kostet Senke. Das gesamte Over/Exo-Gewicht auf einem Wert kann nie 101 ueberschreiten.',
        'how_exo': 'Exo-Runen fuer AP, BP und Reichweite gelingen nur mit einem kritischen Erfolg, geschaetzt 1% pro Versuch. Andere Exos gelingen wie normale Runen, zaehlen aber zur 101-Grenze.',
        'how_rule20': 'Faustregel: Eine Rune gelingt zuverlaessig, solange der Wert unter ~20x dem Runenbonus liegt (+1 bis ~20, +3 bis ~60, +10 bis ~200). Darueber sind Fehlschlaege zu erwarten - dort zaehlen Senke und Geduld.',
        'how_sink_loss': 'Vorsicht: Die Senke ist an die Schmiedemagie-Sitzung gebunden. Anlegen, Tauschen oder Verkaufen des Gegenstands setzt sie laut Community zurueck.',
        'how_disclaimer': 'Ankama hat die genaue Erfolgsformel nie veroeffentlicht; die hier gezeigten Raten sind Schaetzungen der Community.',
        'tips_title': 'Strategie-Tipps',
        'tip_1': 'Schmiede einen Wert nach dem anderen: grosse Runen zuerst, solange der Wert niedrig ist, kleine Runen zum Abschluss nahe dem Maximum.',
        'tip_2': 'Baue Senke auf, bevor du teure Runen wirfst: Opfere einen schweren Wert, den du nicht brauchst - sein Gewicht faengt spaetere Verluste ab.',
        'tip_3': 'Wirf AP/BP-Exo-Runen auf einen Gegenstand mit voller Senke, damit kritische Misserfolge die Senke fressen statt deiner guten Wuerfe.',
        'tip_4': 'Vergleiche die Preise in beide Richtungen: Gegenstaende zu Runen zerbrechen oder Runen direkt kaufen - je nachdem, was an dem Tag guenstiger ist.',
        'ref_title': 'Runen- und Gewichtsreferenz',
        'ref_stat': 'Wert',
        'ref_density': 'Gewicht pro Punkt',
        'ref_runes': 'Runen (Bonus / Gewicht)',
        'ref_max_over': 'Max. Over/Exo',
        'ref_no_rune': 'Keine Rune',
        'ref_approx': 'ungefaehr',
        'footer_sources': 'Mechaniken zusammengetragen aus Community-Referenzen (Ankama-Tutorials, JeuxOnLine, Dofus pour les Noobs, Dofuzion-1.29-Tabelle, Dofus-Touch-Runenlisten).',
    },
}


def _ui_text():
    language = get_supported_language()
    if language not in LOCALIZED_UI:
        language = 'en'
    return LOCALIZED_UI[language]


def _localized_label(label, language):
    if not label:
        return ''
    with translation.override(language):
        return _(label)


def _get_stat_icon_url(stat_key):
    icon_path = get_stat_icon_path(stat_key)
    if icon_path is None:
        return None
    return static(icon_path)


def _format_weight(value):
    if value == int(value):
        return '%d' % int(value)
    return ('%.2f' % value).rstrip('0').rstrip('.')


def _rune_full_name(rune, tier):
    if tier:
        return 'Rune %s %s' % (tier, rune)
    return 'Rune %s' % rune


def _ordered_fm_stat_keys(structure, fm_stats):
    return sorted(
        fm_stats.keys(),
        key=lambda key: STAT_ORDER.get(key, 9999),
    )


def _build_stat_payload(structure, game_version, language):
    """JSON-friendly stat map consumed by the workbench JS."""
    fm_stats = get_fm_stats(game_version)
    payload = {}
    for stat_key, fm_stat in fm_stats.items():
        stat = structure.get_stat_by_key(stat_key)
        if stat is None:
            continue
        payload[stat_key] = {
            'name': _localized_label(stat.name, language),
            'icon': _get_stat_icon_url(stat_key),
            'density': fm_stat['density'],
            'rune': fm_stat['rune'],
            'tiers': [
                {
                    'name': _rune_full_name(fm_stat['rune'], tier),
                    'bonus': bonus,
                    'weight': round(bonus * fm_stat['density'], 2),
                }
                for tier, bonus in fm_stat['tiers']
            ],
            'approx': fm_stat['approx'],
        }
    return payload


def _build_reference_rows(structure, game_version, language, t):
    fm_stats = get_fm_stats(game_version)
    rows = []
    for stat_key in _ordered_fm_stat_keys(structure, fm_stats):
        fm_stat = fm_stats[stat_key]
        stat = structure.get_stat_by_key(stat_key)
        if stat is None:
            continue
        if fm_stat['tiers']:
            rune_cells = [
                '%s: +%d / %s' % (
                    _rune_full_name(fm_stat['rune'], tier),
                    bonus,
                    _format_weight(bonus * fm_stat['density']),
                )
                for tier, bonus in fm_stat['tiers']
            ]
        else:
            rune_cells = []
        rows.append({
            'key': stat_key,
            'name': _localized_label(stat.name, language),
            'icon_url': _get_stat_icon_url(stat_key),
            'density': _format_weight(fm_stat['density']),
            'runes': rune_cells,
            'no_rune': not fm_stat['tiers'],
            'approx': fm_stat['approx'],
            'max_over': int(math.floor(OVER_WEIGHT_CAP / fm_stat['density'])),
        })
    return rows


def forgemagie(request):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')
    ruleset = get_ruleset(game_version)

    stat_payload = _build_stat_payload(structure, game_version, language)
    reference_rows = _build_reference_rows(structure, game_version, language, t)

    js_config = {
        'overCap': OVER_WEIGHT_CAP,
        'onePercentExo': list(ONE_PERCENT_EXO_STATS),
        'stats': stat_payload,
        'statOrder': _ordered_fm_stat_keys(structure, get_fm_stats(game_version)),
        'searchUrl': version_reverse(request, 'forgemagie_items'),
        't': {
            key: t[key] for key in (
                'search_no_results', 'item_level', 'wb_not_mageable',
                'wb_exo_pick', 'wb_remove', 'verdict_ok', 'verdict_over',
                'verdict_cap', 'exo_one_percent', 'diff_safe', 'diff_likely',
                'diff_risky', 'diff_hard', 'diff_exo', 'diff_over',
                'ref_no_rune',
            )
        },
    }

    return set_response(
        request,
        'chardata/forgemagie.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'version_note': t['version_note_%s' % ruleset],
            'reference_rows': reference_rows,
            'has_approx_rows': any(row['approx'] for row in reference_rows),
            'js_config': js_config,
            'tips': [t['tip_1'], t['tip_2'], t['tip_3'], t['tip_4']],
        },
    )


def _normalized_text(value):
    if not value:
        return ''
    return strip_accents(value).lower().strip()


def forgemagie_items(request):
    """Item autocomplete for the workbench: name search over mageable items."""
    structure = get_structure()
    language = get_supported_language()
    query = _normalized_text(request.GET.get('q') or '')
    if len(query) < 2:
        return JsonResponse({'items': []})

    matches = []
    seen_ids = set()
    for type_name in MAGEABLE_TYPES:
        for item in structure.get_unique_items_by_type_and_level(type_name, 200):
            if item.id in seen_ids or item.removed:
                continue
            seen_ids.add(item.id)
            localized_name = structure.get_item_name_in_language(item, language)
            candidate = _normalized_text('%s %s' % (localized_name, item.or_name or ''))
            if query not in candidate:
                continue
            matches.append((
                0 if _normalized_text(localized_name).startswith(query) else 1,
                len(localized_name),
                item,
                localized_name,
                type_name,
            ))

    matches.sort(key=lambda entry: (entry[0], entry[1], -entry[2].level))

    items = []
    for _rank, _name_len, item, localized_name, type_name in matches[:20]:
        # Items with several possible roll sets (Gelano-style "or items") have
        # their stats on per-variant entries; surface each variant separately.
        variants = [item]
        if not item.stats:
            or_variants = structure.get_items_by_or_name(
                item.or_name or item.name, item.dofus_touch)
            with_stats = [variant for variant in (or_variants or [])
                          if variant is not None and variant.stats]
            if with_stats:
                variants = with_stats

        for variant in variants:
            stats = []
            for stat_id, stat_value in variant.stats:
                stat = structure.get_stat_by_id(stat_id)
                if stat is None:
                    continue
                stats.append({
                    'key': stat.key,
                    'name': _localized_label(stat.name, language),
                    'icon': _get_stat_icon_url(stat.key),
                    'value': int(round(stat_value)),
                })
            stats.sort(key=lambda entry: STAT_ORDER.get(entry['key'], 9999))
            items.append({
                'id': variant.id,
                'name': (localized_name if variant is item
                         else structure.get_item_name_in_language(variant, language)),
                'level': variant.level,
                'type_name': _localized_label(type_name, language),
                'image_url': static(get_image_url(type_name, item.name)),
                'stats': stats,
            })

    return JsonResponse({'items': items})
