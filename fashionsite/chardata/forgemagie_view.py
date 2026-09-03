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
    MAGEABLE_TYPES, OVER_WEIGHT_CAP,
    get_fm_stats, get_no_stat_runes, get_one_percent_over_weight,
    get_ruleset,
)
from chardata.forgemagie_odds import (get_documented_odds,
                                     get_odds_ladder)
from chardata.forgemagie_transcendance import get_transcendence_by_stat
from chardata.image_store import get_image_url
from chardata.stat_icons import get_stat_icon_path
from chardata.util import safe_int, set_response, version_reverse
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
        'version_note_dofus2': 'Values for Dofus 2, which has no Ra rune for the elemental resists or critical resist, and no Pa rune for reflect.',
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
        'exo_one_percent': "A line 30 weight past the item's own roll only lands "
                           'on a critical success (~1%% per rune): %(stats)s.',
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
        'how_exo': "A line that stands 30 weight or more past the item's own "
                   'roll only passes on a critical success, commonly '
                   'estimated at 1%% per attempt: %(stats)s. Lighter exos pass '
                   'like normal runes but count against the 101 cap.',
        'how_rule20': 'Rule of thumb: a rune passes reliably while the stat is below ~20x the rune’s bonus (+1 runes up to ~20, +3 up to ~60, +10 up to ~200). Above that, expect failures - that is where sink and patience matter.',
        'how_sink_loss': 'Careful: the sink is tied to the maging session. Equipping, trading or listing the item is commonly reported to reset it.',
        'how_disclaimer': 'Ankama has never published the exact success formula; rates shown here are community estimates.',
        'how_disclaimer_retro': 'Ankama did publish the Retro system and its odds, in the 1.27 dev post. The formula behind them was never given, so the per-throw rates the simulator shows are still estimates.',
        'how_malus': 'Malus lines: a malus can be cancelled but never turned into a bonus, so its line stops at 0. A malus sitting inside its natural range is not a sink; it only becomes one once smithmagic has pushed it past its natural best. A bonus can be drained to 0, a malus only back down to its natural minimum.',
        'odds_title': 'Odds Ankama published',
        'odds_intro': 'For Retro the success rates are not guesswork. Ankama documented the 1.27 smithmagic system and put a number on six situations. Neutral never passes 50%, and critical success never falls below 1% unless the attempt is outright impossible.',
        'odds_source': 'Figures from the 1.27 dev post of 18 May 2009. This page targets Retro 1.29, two versions later, so read them as the published baseline rather than a measurement of the live game.',
        'odds_col_case': 'Situation',
        'odds_col_sc': 'Critical success',
        'odds_col_n': 'Neutral',
        'odds_col_ec': 'Critical failure',
        'odds_remount': 'Raising a simple stat such as vitality on a plain item, master smith',
        'odds_perfect': 'Reaching a perfect roll, simple bonus on a plain item',
        'odds_remount_hard': 'Raising a heavy stat on a complex item, worst case',
        'odds_create_best': 'Creating a stat the item does not have, with a sink, best case',
        'odds_create_worst': 'Creating a stat, with a sink, worst case',
        'odds_create_nosink': 'Creating a stat with no sink at all',
        'tips_title': 'Strategy tips',
        'tip_1': 'Mage one stat at a time: big runes first while the stat is low, small runes to finish near the cap.',
        'tip_2': 'Build sink before expensive runes: sacrifice a heavy stat you do not need and its weight will absorb later losses.',
        'tip_3': 'Keep AP/MP for the very end: place your other stats in the sink first, then attempt the big rune with as much sink as possible - critical failures eat the sink instead of your good rolls.',
        'tip_4': 'Compare prices both ways: crushing items into runes versus buying runes directly - whichever is cheaper that day.',
        'ref_title': 'Rune & weight reference',
        'ref_stat': 'Stat',
        'ref_density': 'Weight per point',
        'ref_runes': 'Runes (bonus / weight)',
        'ref_max_over': 'Max over/exo',
        'ref_no_rune': 'No rune',
        'ref_approx': 'approximate',
        'footer_sources': 'Mechanics compiled from community references (Ankama tutorials, JeuxOnLine, Dofus pour les Noobs, Dofuzion 1.29 table, Dofus Touch rune lists).',
        'sim_title': 'Maging session (simulator)',
        'sim_intro': 'Throw runes virtually or record your in-game results: the sink, the losses and the runes used are tracked automatically. The session is saved in your browser.',
        'sim_start': 'Start session',
        'sim_reset': 'Reset session',
        'sim_undo': 'Undo last throw',
        'sim_sink': 'Current sink (reliquat)',
        'sim_throws': 'Throws',
        'sim_criticals': 'Criticals recorded',
        'sim_model': 'model',
        'sim_runes_used': 'Runes used',
        'sim_suggested': 'Suggested next rune',
        'sim_rune_label': 'Rune',
        'sim_throw': 'Simulate throw',
        'sim_record_hint': 'Maging in game? Record the real outcome instead:',
        'sim_sc': 'SC - critical success',
        'sim_sn': 'SN - neutral success',
        'sim_ec': 'EC - critical failure',
        'sim_history': 'History',
        'sim_done': 'Target reached!',
        'sim_no_target': 'Set targets above your rolls to get suggestions.',
        'sim_chance': 'Estimated pass chance',
        'sim_disclaimer': 'Simulated odds and losses are rough community estimates; the real game may differ.',
        'sim_now': 'Now',
        'sim_target': 'Target',
        'sim_remaining': 'Remaining',
        'sim_sink_gain': 'sink',
        'sim_sacrifice': 'sacrifice - throw small runes so the unwanted stat drops and banks its weight as sink',
        'sim_sacrifice_hint': 'Tip: the sink is empty. Lower the target of an expendable stat (e.g. AP to 0) so it gets sacrificed and fills the sink before you place expensive runes.',
        'sim_profit_title': 'Profitability',
        'sim_item_cost': 'Item buy price (kamas)',
        'sim_sale_price': 'Expected sale price (kamas)',
        'sim_runes_cost': 'Runes cost',
        'sim_total_cost': 'Total cost',
        'sim_profit': 'Profit',
        'sim_unit_price': 'unit price',
        'quality_title': 'Roll quality',
        'quality_bad': 'terrible',
        'quality_ok': 'decent',
        'quality_good': 'good',
        'quality_amazing': 'amazing',
        'quality_perfect': 'perfect',
        'quality_overperfect': 'beyond perfect',
        'sim_other_runes': 'Other runes',
        'stat_line_hunting': 'Hunting Weapon',
        'sim_landed': 'yes',
        'nostat_title': 'Runes that raise no characteristic',
        'nostat_rune': 'Rune',
        'nostat_what': 'What it does',
        'nostat_weight': 'Weight',
        'nostat_unknown': 'not known for this version',
        'rune_hunting': 'Hunting Rune',
        'rune_hunting_what': 'Turns a weapon into a hunting weapon, the kind that brings meat back from a fight.',
        'rune_signature': 'Signature Rune',
        'rune_signature_what': 'Signs the item with its crafter’s name. It goes in with the ingredients when the item is crafted, never during smithmagic.',
        'inv_save': 'Save to my inventory',
        'inv_save_smithed': 'Save the smithed item to my inventory',
        'inv_new_folder': 'New folder…',
        'inv_saved': 'Saved!',
        'search_inventory': 'Search my inventory (loads my saved rolls)',
        'sim_sink_empty': 'Sink empty - STOP throwing runes: the next failures will eat your placed stats. Rebuild some sink before continuing.',
        'inv_update': 'Update my saved item',
        'inv_save_copy': 'Save a new copy',
        'sim_improve': 'bonus - spend the spare sink on a free upgrade; enough sink stays reserved for the big rune',
        'sim_improve_done': 'Sink left over: you can still push %s for free.',
        'sim_mode_label': 'Mode',
        'sim_mode_sim': 'Simulation',
        'sim_mode_real': 'Real maging',
        'sim_mode_sim_hint': 'The tool throws the runes and estimates the outcomes and losses for you.',
        'sim_mode_real_hint': 'You mage in game: after each throw, pick the rune and tap the outcome (SC/SN/EC), then type your item’s new stats below. The Now and Target cells are editable.',
    },
    'fr': {
        'title': 'Atelier de Forgemagie',
        'subtitle': 'Planifiez vos FM : calcul du puits, nombre de runes et risque pour cette version du jeu.',
        'version_note_modern': 'Valeurs pour le jeu PC actuel (Dofus 2 / Dofus 3).',
        'version_note_dofus2': 'Valeurs pour Dofus 2, qui n’a pas de rune Ra pour les résistances élémentaires ni pour la résistance critique, ni de rune Pa pour le renvoi.',
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
        'exo_one_percent': "Une ligne à 30 de poids au-delà du roll de l'objet "
                           'ne passe que sur un succès critique (~1 %% par '
                           'rune) : %(stats)s.',
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
        'how_exo': "Une ligne qui dépasse de 30 de poids ou plus le roll de l'objet "
                   'ne passe que sur un succès critique, estimé à 1 %% par '
                   'essai : %(stats)s. Les exos plus légers passent comme des '
                   'runes normales mais comptent dans le plafond de 101.',
        'how_rule20': 'Règle empirique : une rune passe bien tant que la stat est sous ~20x le bonus de la rune (+1 jusqu’à ~20, +3 jusqu’à ~60, +10 jusqu’à ~200). Au-delà, attendez-vous à des échecs - c’est là que le puits et la patience comptent.',
        'how_sink_loss': 'Attention : le puits est lié à la session de forgemagie. Équiper, échanger ou mettre l’objet en vente le réinitialise selon les retours de la communauté.',
        'how_disclaimer': 'Ankama n’a jamais publié la formule exacte de réussite ; les taux affichés ici sont des estimations communautaires.',
        'how_disclaimer_retro': 'Ankama a bien publié le système Retro et ses probabilités, dans le devblog 1.27. La formule derrière ces chiffres n’a jamais été donnée, donc les taux par lancer affichés par le simulateur restent des estimations.',
        'how_malus': 'Lignes de malus : un malus peut être annulé, jamais transformé en bonus — sa ligne s’arrête à 0. Un malus resté dans sa plage naturelle ne sert pas de puits ; il n’en devient un qu’une fois poussé au-delà de son meilleur jet naturel. Un bonus peut être vidé jusqu’à 0, un malus seulement redescendu jusqu’à son minimum naturel.',
        'odds_title': 'Les probabilités publiées par Ankama',
        'odds_intro': 'En Retro, les taux de réussite ne sont pas des suppositions. Ankama a documenté le système de forgemagie de la 1.27 et chiffré six situations. Le neutre ne dépasse jamais 50 %, et le succès critique ne descend jamais sous 1 % tant que la tentative n’est pas purement impossible.',
        'odds_source': 'Chiffres du devblog 1.27 du 18 mai 2009. Cette page vise la Retro 1.29, deux versions plus tard : à lire comme la référence publiée, pas comme une mesure du jeu actuel.',
        'odds_col_case': 'Situation',
        'odds_col_sc': 'Succès critique',
        'odds_col_n': 'Neutre',
        'odds_col_ec': 'Échec critique',
        'odds_remount': 'Remonter un jet simple comme la vitalité sur un objet ordinaire, maître forgemage',
        'odds_perfect': 'Atteindre le jet parfait, bonus simple sur un objet simple',
        'odds_remount_hard': 'Remonter un jet lourd sur un objet complexe, pire cas',
        'odds_create_best': 'Créer un effet absent de l’objet, avec un puits, meilleur cas',
        'odds_create_worst': 'Créer un effet, avec un puits, pire cas',
        'odds_create_nosink': 'Créer un effet sans aucun puits',
        'tips_title': 'Conseils de stratégie',
        'tip_1': 'Forgemagez une stat à la fois : grosses runes d’abord quand la stat est basse, petites runes pour finir près du max.',
        'tip_2': 'Créez du puits avant les runes chères : sacrifiez une stat lourde dont vous ne voulez pas, son poids absorbera les pertes suivantes.',
        'tip_3': 'Gardez le PA/PM pour la toute fin : montez d’abord vos autres stats dans le puits, puis tentez la grosse rune avec le puits le plus plein possible - les échecs critiques mangeront le puits au lieu de vos bons jets.',
        'tip_4': 'Comparez les prix dans les deux sens : briser des objets en runes ou acheter les runes directement - selon ce qui est le moins cher ce jour-là.',
        'ref_title': 'Référence des runes et des poids',
        'ref_stat': 'Caractéristique',
        'ref_density': 'Poids par point',
        'ref_runes': 'Runes (bonus / poids)',
        'ref_max_over': 'Over/exo max',
        'ref_no_rune': 'Pas de rune',
        'ref_approx': 'approximatif',
        'footer_sources': 'Mécaniques compilées à partir de références communautaires (tutoriels Ankama, JeuxOnLine, Dofus pour les Noobs, tableau 1.29 de Dofuzion, listes de runes Dofus Touch).',
        'sim_title': 'Session de forgemagie (simulateur)',
        'sim_intro': 'Lancez des runes virtuellement ou enregistrez vos résultats en jeu : le puits, les pertes et les runes utilisées sont suivis automatiquement. La session est sauvegardée dans votre navigateur.',
        'sim_start': 'Démarrer la session',
        'sim_reset': 'Réinitialiser la session',
        'sim_undo': 'Annuler le dernier jet',
        'sim_sink': 'Puits en cours (reliquat)',
        'sim_throws': 'Jets',
        'sim_criticals': 'Critiques enregistrés',
        'sim_model': 'modèle',
        'sim_runes_used': 'Runes utilisées',
        'sim_suggested': 'Prochaine rune conseillée',
        'sim_rune_label': 'Rune',
        'sim_throw': 'Simuler le jet',
        'sim_record_hint': 'Vous forgemagez en jeu ? Enregistrez plutôt le résultat réel :',
        'sim_sc': 'SC - succès critique',
        'sim_sn': 'SN - succès neutre',
        'sim_ec': 'EC - échec critique',
        'sim_history': 'Historique',
        'sim_done': 'Objectif atteint !',
        'sim_no_target': 'Définissez des objectifs au-dessus de vos jets pour obtenir des suggestions.',
        'sim_chance': 'Chance de passer (estimée)',
        'sim_disclaimer': 'Les probabilités et pertes simulées sont des estimations communautaires ; le jeu réel peut différer.',
        'sim_now': 'Actuel',
        'sim_target': 'Objectif',
        'sim_remaining': 'Restant',
        'sim_sink_gain': 'puits',
        'sim_sacrifice': 'sacrifice - lancez de petites runes pour faire sauter la stat indésirable et stocker son poids en puits',
        'sim_sacrifice_hint': 'Astuce : le puits est vide. Baissez l’objectif d’une stat sacrifiable (ex. PA à 0) pour qu’elle saute et remplisse le puits avant de poser des runes chères.',
        'sim_profit_title': 'Rentabilité',
        'sim_item_cost': 'Prix d’achat de l’objet (kamas)',
        'sim_sale_price': 'Prix de vente estimé (kamas)',
        'sim_runes_cost': 'Coût des runes',
        'sim_total_cost': 'Coût total',
        'sim_profit': 'Bénéfice',
        'sim_unit_price': 'prix unitaire',
        'quality_title': 'Qualité du jet',
        'quality_bad': 'nul',
        'quality_ok': 'correct',
        'quality_good': 'bien',
        'quality_amazing': 'incroyable',
        'quality_perfect': 'parfait',
        'quality_overperfect': 'plus que parfait',
        'sim_other_runes': 'Autres runes',
        'stat_line_hunting': 'Arme de chasse',
        'sim_landed': 'oui',
        'nostat_title': 'Runes qui ne montent aucune caractéristique',
        'nostat_rune': 'Rune',
        'nostat_what': 'Ce qu’elle fait',
        'nostat_weight': 'Poids',
        'nostat_unknown': 'inconnu pour cette version',
        'rune_hunting': 'Rune de chasse',
        'rune_hunting_what': 'Transforme une arme en arme de chasse, celle qui ramène de la viande d’un combat.',
        'rune_signature': 'Rune de Signature',
        'rune_signature_what': 'Signe l’objet du nom de son artisan. Elle se met avec les ingrédients à la fabrication, jamais en forgemagie.',
        'inv_save': 'Sauvegarder dans mon inventaire',
        'inv_save_smithed': 'Sauvegarder l’objet forgemagé dans mon inventaire',
        'inv_new_folder': 'Nouveau dossier…',
        'inv_saved': 'Enregistré !',
        'search_inventory': 'Chercher dans mon inventaire (charge mes jets sauvegardés)',
        'sim_sink_empty': 'Puits épuisé - STOP, ne lancez plus de runes : les prochains échecs mangeront vos stats posées. Refaites du puits avant de continuer.',
        'inv_update': 'Mettre à jour l’objet enregistré',
        'inv_save_copy': 'Enregistrer une nouvelle copie',
        'sim_improve': 'bonus - profitez du puits excédentaire pour monter encore cette stat sans risque ; il reste assez de puits en réserve pour la grosse rune',
        'sim_improve_done': 'Il reste du puits : vous pouvez encore monter %s gratuitement.',
        'sim_mode_label': 'Mode',
        'sim_mode_sim': 'Simulation',
        'sim_mode_real': 'Forge réelle',
        'sim_mode_sim_hint': 'L’outil lance les runes et estime les résultats et les pertes à votre place.',
        'sim_mode_real_hint': 'Vous forgez en jeu : après chaque coup, choisissez la rune et indiquez le résultat (SC/SN/EC), puis saisissez les nouvelles stats de votre objet ci-dessous. Les cases Actuel et Objectif sont modifiables.',
    },
    'es': {
        'title': 'Taller de Forjamagia',
        'subtitle': 'Planifica tu forjamagia: cálculo del pozo, cantidad de runas y riesgo para esta versión del juego.',
        'version_note_modern': 'Valores para el juego de PC actual (Dofus 2 / Dofus 3).',
        'version_note_dofus2': 'Valores para Dofus 2, que no tiene runa Ra para las resistencias elementales ni para la resistencia crítica, ni runa Pa para el reenvío.',
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
        'exo_one_percent': 'Una línea con 30 de peso por encima de la tirada del '
                           'objeto solo pasa con un éxito crítico (~1 %% por '
                           'runa): %(stats)s.',
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
        'how_exo': 'Una línea que supera en 30 de peso o más la tirada del objeto '
                   'solo pasa con un éxito crítico, estimado en un 1 %% por '
                   'intento: %(stats)s. Los exos más ligeros pasan como runas '
                   'normales pero cuentan para el límite de 101.',
        'how_rule20': 'Regla práctica: una runa pasa bien mientras la característica esté por debajo de ~20x el bono de la runa (+1 hasta ~20, +3 hasta ~60, +10 hasta ~200). Por encima, espera fracasos: ahí cuentan el pozo y la paciencia.',
        'how_sink_loss': 'Cuidado: el pozo está ligado a la sesión de forjamagia. Equipar, intercambiar o poner el objeto en venta lo reinicia según la comunidad.',
        'how_disclaimer': 'Ankama nunca publicó la fórmula exacta de éxito; las tasas mostradas aquí son estimaciones de la comunidad.',
        'how_disclaimer_retro': 'Ankama sí publicó el sistema Retro y sus probabilidades, en el devblog de la 1.27. La fórmula que hay detrás nunca se dio, así que las tasas por lanzamiento que muestra el simulador siguen siendo estimaciones.',
        'how_malus': 'Líneas de penalización: una penalización puede anularse, pero nunca convertirse en bonificación, así que su línea se detiene en 0. Una penalización dentro de su rango natural no sirve de pozo; solo lo es una vez empujada más allá de su mejor tirada natural. Una bonificación puede vaciarse hasta 0, una penalización solo bajar hasta su mínimo natural.',
        'odds_title': 'Las probabilidades publicadas por Ankama',
        'odds_intro': 'En Retro las tasas de éxito no son suposiciones. Ankama documentó el sistema de forja mágica de la 1.27 y puso cifras a seis situaciones. El neutro nunca pasa del 50 % y el éxito crítico nunca baja del 1 % mientras el intento no sea imposible.',
        'odds_source': 'Cifras del devblog de la 1.27, del 18 de mayo de 2009. Esta página apunta a Retro 1.29, dos versiones después: léelas como la referencia publicada, no como una medida del juego actual.',
        'odds_col_case': 'Situación',
        'odds_col_sc': 'Éxito crítico',
        'odds_col_n': 'Neutro',
        'odds_col_ec': 'Fallo crítico',
        'odds_remount': 'Subir una característica simple como vitalidad en un objeto normal, maestro forjador',
        'odds_perfect': 'Alcanzar la tirada perfecta, bonificación simple en un objeto simple',
        'odds_remount_hard': 'Subir una característica pesada en un objeto complejo, peor caso',
        'odds_create_best': 'Crear un efecto que el objeto no tiene, con pozo, mejor caso',
        'odds_create_worst': 'Crear un efecto, con pozo, peor caso',
        'odds_create_nosink': 'Crear un efecto sin ningún pozo',
        'tips_title': 'Consejos de estrategia',
        'tip_1': 'Forja una característica a la vez: runas grandes primero cuando la característica está baja, runas pequeñas para terminar cerca del máximo.',
        'tip_2': 'Genera pozo antes de las runas caras: sacrifica una característica pesada que no necesites y su peso absorberá las pérdidas siguientes.',
        'tip_3': 'Deja el PA/PM para el final: coloca primero las demás estadísticas en el pozo y luego intenta la runa grande con el pozo lo más lleno posible - los fracasos críticos se comerán el pozo en lugar de tus buenas tiradas.',
        'tip_4': 'Compara precios en ambos sentidos: romper objetos en runas o comprar las runas directamente, según lo que esté más barato ese día.',
        'ref_title': 'Referencia de runas y pesos',
        'ref_stat': 'Característica',
        'ref_density': 'Peso por punto',
        'ref_runes': 'Runas (bono / peso)',
        'ref_max_over': 'Over/exo máx.',
        'ref_no_rune': 'Sin runa',
        'ref_approx': 'aproximado',
        'footer_sources': 'Mecánicas compiladas a partir de referencias de la comunidad (tutoriales de Ankama, JeuxOnLine, Dofus pour les Noobs, tabla 1.29 de Dofuzion, listas de runas de Dofus Touch).',
        'sim_title': 'Sesión de forjamagia (simulador)',
        'sim_intro': 'Lanza runas virtualmente o registra tus resultados del juego: el pozo, las pérdidas y las runas usadas se siguen automáticamente. La sesión se guarda en tu navegador.',
        'sim_start': 'Iniciar sesión de forja',
        'sim_reset': 'Reiniciar sesión',
        'sim_undo': 'Deshacer el último intento',
        'sim_sink': 'Pozo actual (reliquia)',
        'sim_throws': 'Intentos',
        'sim_criticals': 'Críticos registrados',
        'sim_model': 'modelo',
        'sim_runes_used': 'Runas usadas',
        'sim_suggested': 'Siguiente runa sugerida',
        'sim_rune_label': 'Runa',
        'sim_throw': 'Simular intento',
        'sim_record_hint': '¿Forjas en el juego? Registra el resultado real:',
        'sim_sc': 'SC - éxito crítico',
        'sim_sn': 'SN - éxito neutro',
        'sim_ec': 'EC - fracaso crítico',
        'sim_history': 'Historial',
        'sim_done': '¡Objetivo alcanzado!',
        'sim_no_target': 'Define objetivos por encima de tus tiradas para recibir sugerencias.',
        'sim_chance': 'Probabilidad de pasar (estimada)',
        'sim_disclaimer': 'Las probabilidades y pérdidas simuladas son estimaciones de la comunidad; el juego real puede diferir.',
        'sim_now': 'Actual',
        'sim_target': 'Objetivo',
        'sim_remaining': 'Restante',
        'sim_sink_gain': 'pozo',
        'sim_sacrifice': 'sacrificio - lanza runas pequeñas para que caiga la característica no deseada y su peso quede como pozo',
        'sim_sacrifice_hint': 'Consejo: el pozo está vacío. Baja el objetivo de una característica prescindible (p. ej. PA a 0) para sacrificarla y llenar el pozo antes de colocar runas caras.',
        'sim_profit_title': 'Rentabilidad',
        'sim_item_cost': 'Precio de compra del objeto (kamas)',
        'sim_sale_price': 'Precio de venta estimado (kamas)',
        'sim_runes_cost': 'Coste de las runas',
        'sim_total_cost': 'Coste total',
        'sim_profit': 'Beneficio',
        'sim_unit_price': 'precio unitario',
        'quality_title': 'Calidad de la tirada',
        'quality_bad': 'mala',
        'quality_ok': 'aceptable',
        'quality_good': 'buena',
        'quality_amazing': 'increíble',
        'quality_perfect': 'perfecta',
        'quality_overperfect': 'más que perfecta',
        'sim_other_runes': 'Otras runas',
        'stat_line_hunting': 'Arma de caza',
        'sim_landed': 'sí',
        'nostat_title': 'Runas que no suben ninguna característica',
        'nostat_rune': 'Runa',
        'nostat_what': 'Qué hace',
        'nostat_weight': 'Peso',
        'nostat_unknown': 'desconocido en esta versión',
        'rune_hunting': 'Runa de caza',
        'rune_hunting_what': 'Convierte un arma en arma de caza, la que trae carne de un combate.',
        'rune_signature': 'Runa de firma',
        'rune_signature_what': 'Firma el objeto con el nombre de su artesano. Se añade con los ingredientes al fabricarlo, nunca en la forjamagia.',
        'inv_save': 'Guardar en mi inventario',
        'inv_save_smithed': 'Guardar el objeto forjado en mi inventario',
        'inv_new_folder': 'Nueva carpeta…',
        'inv_saved': '¡Guardado!',
        'search_inventory': 'Buscar en mi inventario (carga mis tiradas guardadas)',
        'sim_sink_empty': 'Pozo agotado - PARA de lanzar runas: los próximos fracasos se comerán tus estadísticas colocadas. Recupera pozo antes de continuar.',
        'inv_update': 'Actualizar mi objeto guardado',
        'inv_save_copy': 'Guardar una copia nueva',
        'sim_improve': 'extra - usa el pozo sobrante para subir esta estadística sin riesgo; queda pozo reservado para la runa grande',
        'sim_improve_done': 'Queda pozo: aún puedes subir %s gratis.',
        'sim_mode_label': 'Modo',
        'sim_mode_sim': 'Simulación',
        'sim_mode_real': 'Forja real',
        'sim_mode_sim_hint': 'La herramienta lanza las runas y estima los resultados y las pérdidas por ti.',
        'sim_mode_real_hint': 'Forjas en el juego: tras cada tirada, elige la runa e indica el resultado (SC/SN/EC), luego escribe abajo las nuevas estadísticas de tu objeto. Las casillas Ahora y Objetivo son editables.',
    },
    'pt': {
        'title': 'Oficina de Forjamagia',
        'subtitle': 'Planeje sua forjamagia: cálculo do poço, quantidade de runas e risco para esta versão do jogo.',
        'version_note_modern': 'Valores para o jogo de PC atual (Dofus 2 / Dofus 3).',
        'version_note_dofus2': 'Valores para o Dofus 2, que não tem runa Ra para as resistências elementares nem para a resistência crítica, nem runa Pa para o reenvio.',
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
        'exo_one_percent': 'Uma linha com 30 de peso além da rolagem do item só '
                           'passa com um sucesso crítico (~1%% por runa): '
                           '%(stats)s.',
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
        'how_exo': 'Uma linha que ultrapassa em 30 de peso ou mais a rolagem do '
                   'item só passa com um sucesso crítico, estimado em 1%% por '
                   'tentativa: %(stats)s. Os exos mais leves passam como runas '
                   'normais, mas contam para o limite de 101.',
        'how_rule20': 'Regra prática: uma runa passa bem enquanto o atributo está abaixo de ~20x o bônus da runa (+1 até ~20, +3 até ~60, +10 até ~200). Acima disso, espere falhas - é aí que o poço e a paciência contam.',
        'how_sink_loss': 'Cuidado: o poço está ligado à sessão de forjamagia. Equipar, trocar ou colocar o item à venda o reinicia, segundo a comunidade.',
        'how_disclaimer': 'A Ankama nunca publicou a fórmula exata de sucesso; as taxas mostradas aqui são estimativas da comunidade.',
        'how_disclaimer_retro': 'A Ankama publicou sim o sistema Retro e as suas probabilidades, no devblog da 1.27. A fórmula por trás deles nunca foi dada, por isso as taxas por lançamento mostradas pelo simulador continuam a ser estimativas.',
        'how_malus': 'Linhas de penalidade: uma penalidade pode ser anulada, mas nunca transformada em bônus, por isso a linha para em 0. Uma penalidade dentro do seu intervalo natural não serve de poço; só se torna um depois de empurrada para além do seu melhor valor natural. Um bônus pode ser esvaziado até 0, uma penalidade só desce até ao seu mínimo natural.',
        'odds_title': 'As probabilidades publicadas pela Ankama',
        'odds_intro': 'No Retro as taxas de sucesso não são suposições. A Ankama documentou o sistema de forjamagia da 1.27 e deu números a seis situações. O neutro nunca passa dos 50 % e o sucesso crítico nunca desce abaixo de 1 % enquanto a tentativa não for impossível.',
        'odds_source': 'Números do devblog da 1.27, de 18 de maio de 2009. Esta página visa o Retro 1.29, duas versões depois: leia-os como a referência publicada, não como uma medição do jogo atual.',
        'odds_col_case': 'Situação',
        'odds_col_sc': 'Sucesso crítico',
        'odds_col_n': 'Neutro',
        'odds_col_ec': 'Falha crítica',
        'odds_remount': 'Subir um atributo simples como vitalidade num objeto comum, mestre forjador',
        'odds_perfect': 'Atingir o valor perfeito, bônus simples num objeto simples',
        'odds_remount_hard': 'Subir um atributo pesado num objeto complexo, pior caso',
        'odds_create_best': 'Criar um efeito que o objeto não tem, com poço, melhor caso',
        'odds_create_worst': 'Criar um efeito, com poço, pior caso',
        'odds_create_nosink': 'Criar um efeito sem poço nenhum',
        'tips_title': 'Dicas de estratégia',
        'tip_1': 'Forje um atributo de cada vez: runas grandes primeiro enquanto o atributo está baixo, runas pequenas para terminar perto do máximo.',
        'tip_2': 'Crie poço antes das runas caras: sacrifique um atributo pesado que você não precisa e o peso dele absorverá as perdas seguintes.',
        'tip_3': 'Deixe o PA/PM para o final: coloque primeiro os outros atributos no poço e então tente a runa grande com o poço o mais cheio possível - as falhas críticas comerão o poço em vez das suas boas rolagens.',
        'tip_4': 'Compare preços dos dois lados: quebrar itens em runas ou comprar runas diretamente - o que estiver mais barato no dia.',
        'ref_title': 'Referência de runas e pesos',
        'ref_stat': 'Atributo',
        'ref_density': 'Peso por ponto',
        'ref_runes': 'Runas (bônus / peso)',
        'ref_max_over': 'Over/exo máx.',
        'ref_no_rune': 'Sem runa',
        'ref_approx': 'aproximado',
        'footer_sources': 'Mecânicas compiladas a partir de referências da comunidade (tutoriais da Ankama, JeuxOnLine, Dofus pour les Noobs, tabela 1.29 do Dofuzion, listas de runas do Dofus Touch).',
        'sim_title': 'Sessão de forjamagia (simulador)',
        'sim_intro': 'Lance runas virtualmente ou registre seus resultados do jogo: o poço, as perdas e as runas usadas são acompanhados automaticamente. A sessão fica salva no seu navegador.',
        'sim_start': 'Iniciar sessão',
        'sim_reset': 'Reiniciar sessão',
        'sim_undo': 'Desfazer a última tentativa',
        'sim_sink': 'Poço atual (resíduo)',
        'sim_throws': 'Tentativas',
        'sim_criticals': 'Críticos registrados',
        'sim_model': 'modelo',
        'sim_runes_used': 'Runas usadas',
        'sim_suggested': 'Próxima runa sugerida',
        'sim_rune_label': 'Runa',
        'sim_throw': 'Simular tentativa',
        'sim_record_hint': 'Forjando no jogo? Registre o resultado real:',
        'sim_sc': 'SC - sucesso crítico',
        'sim_sn': 'SN - sucesso neutro',
        'sim_ec': 'EC - falha crítica',
        'sim_history': 'Histórico',
        'sim_done': 'Meta alcançada!',
        'sim_no_target': 'Defina metas acima das suas rolagens para receber sugestões.',
        'sim_chance': 'Chance de passar (estimada)',
        'sim_disclaimer': 'As probabilidades e perdas simuladas são estimativas da comunidade; o jogo real pode ser diferente.',
        'sim_now': 'Atual',
        'sim_target': 'Meta',
        'sim_remaining': 'Restante',
        'sim_sink_gain': 'poço',
        'sim_sacrifice': 'sacrifício - lance runas pequenas para derrubar o atributo indesejado e guardar o peso dele como poço',
        'sim_sacrifice_hint': 'Dica: o poço está vazio. Abaixe a meta de um atributo dispensável (ex.: PA para 0) para que ele caia e encha o poço antes de colocar runas caras.',
        'sim_profit_title': 'Rentabilidade',
        'sim_item_cost': 'Preço de compra do item (kamas)',
        'sim_sale_price': 'Preço de venda estimado (kamas)',
        'sim_runes_cost': 'Custo das runas',
        'sim_total_cost': 'Custo total',
        'sim_profit': 'Lucro',
        'sim_unit_price': 'preço unitário',
        'quality_title': 'Qualidade da rolagem',
        'quality_bad': 'ruim',
        'quality_ok': 'razoável',
        'quality_good': 'boa',
        'quality_amazing': 'incrível',
        'quality_perfect': 'perfeita',
        'quality_overperfect': 'além do perfeito',
        'sim_other_runes': 'Outras runas',
        'stat_line_hunting': 'Arma de caça',
        'sim_landed': 'sim',
        'nostat_title': 'Runas que não aumentam nenhum atributo',
        'nostat_rune': 'Runa',
        'nostat_what': 'O que faz',
        'nostat_weight': 'Peso',
        'nostat_unknown': 'desconhecido nesta versão',
        'rune_hunting': 'Runa de Caça',
        'rune_hunting_what': 'Transforma uma arma em arma de caça, aquela que traz carne de um combate.',
        'rune_signature': 'Runa de assinatura',
        'rune_signature_what': 'Assina o item com o nome de quem o fabricou. Entra junto com os ingredientes na fabricação, nunca na forjamagia.',
        'inv_save': 'Salvar no meu inventário',
        'inv_save_smithed': 'Salvar o item forjado no meu inventário',
        'inv_new_folder': 'Nova pasta…',
        'inv_saved': 'Salvo!',
        'search_inventory': 'Buscar no meu inventário (carrega minhas rolagens salvas)',
        'sim_sink_empty': 'Poço esgotado - PARE de lançar runas: as próximas falhas vão comer seus atributos colocados. Refaça o poço antes de continuar.',
        'inv_update': 'Atualizar meu item salvo',
        'inv_save_copy': 'Salvar uma nova cópia',
        'sim_improve': 'bônus - use o poço excedente para subir este atributo sem risco; ainda fica poço reservado para a runa grande',
        'sim_improve_done': 'Ainda há poço: você ainda pode subir %s de graça.',
        'sim_mode_label': 'Modo',
        'sim_mode_sim': 'Simulação',
        'sim_mode_real': 'Forja real',
        'sim_mode_sim_hint': 'A ferramenta lança as runas e estima os resultados e as perdas para você.',
        'sim_mode_real_hint': 'Você forja no jogo: após cada tentativa, escolha a runa e indique o resultado (SC/SN/EC), depois digite abaixo os novos atributos do seu item. As células Agora e Objetivo são editáveis.',
    },
    'de': {
        'title': 'Schmiedemagie-Labor',
        'subtitle': 'Plane deine Schmiedemagie: Senken-Berechnung, Runenanzahl und Risiko für diese Spielversion.',
        'version_note_modern': 'Werte für das aktuelle PC-Spiel (Dofus 2 / Dofus 3).',
        'version_note_dofus2': 'Werte für Dofus 2, das keine Ra-Rune für die Elementarresistenzen und die kritische Resistenz hat und keine Pa-Rune für die Schadensreflexion.',
        'version_note_touch': 'Werte für Dofus Touch, das die Gewichte von vor 2.29 behalten hat: Vi-Runen +3/+10/+30, Kritisch mit Gewicht 30, Heilung mit Gewicht 20.',
        'version_note_retro': 'Werte für Dofus Retro 1.29: feste Resistenzen mit Gewicht 5, % Resistenzen 4, Schadensreflexion 30, Fallenschaden 15.',
        'search_label': 'Gegenstand',
        'search_placeholder': 'Gegenstandsname eingeben (Beispiel: Gelano)',
        'search_hint': 'Wähle einen Gegenstand, um seine perfekten Werte zu laden, und trage dann deine echten Werte und Ziele ein.',
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
        'wb_add_exo': 'Wert hinzufügen (Over/Exo)',
        'wb_exo_pick': 'Wert auswählen',
        'wb_add': 'Hinzufügen',
        'wb_remove': 'Entfernen',
        'total_sink': 'Verfügbare Senke (Würfe unter dem Maximum)',
        'total_needed': 'Gesamtgewicht zu setzen',
        'total_balance': 'Bilanz',
        'verdict_ok': 'Dein Plan passt in die Senke des Gegenstands: Mit Geduld kann er ohne Overmage gelingen.',
        'verdict_over': 'Overmage: Dein Plan braucht %s Gewicht mehr, als die Senke des Gegenstands hergibt. Rechne mit vielen Versuchen und geopferten Werten.',
        'verdict_cap': 'Unmöglich: %s überschreitet die Grenze von 101 Over/Exo-Gewicht auf einem einzelnen Wert.',
        'exo_one_percent': 'Eine Zeile mit 30 Gewicht über dem eigenen Wurf des '
                           'Gegenstands gelingt nur mit einem kritischen '
                           'Erfolg (~1%% pro Rune): %(stats)s.',
        'diff_safe': 'sehr wahrscheinlich',
        'diff_likely': 'wahrscheinlich',
        'diff_risky': 'riskant',
        'diff_hard': 'schwer',
        'diff_exo': 'Exo (~1%)',
        'diff_over': 'Overmage',
        'how_title': 'So funktioniert Schmiedemagie',
        'how_p1': 'Jeder Runenversuch hat drei mögliche Ausgänge:',
        'how_sc': 'Kritischer Erfolg - der Bonus wird hinzugefügt und sonst ändert sich nichts.',
        'how_sn': 'Neutraler Erfolg - der Bonus wird hinzugefügt, aber der Gegenstand verliert ein gleichwertiges Gewicht an anderen Werten (zuerst aus der Senke).',
        'how_ec': 'Kritischer Misserfolg - kein Bonus, und der Gegenstand verliert Werte im Umfang des Runengewichts.',
        'how_sink': 'Die Senke (Reliquat): Wenn ein verlorener Wert mehr wiegt als die geworfene Rune, wird die Differenz unsichtbar auf dem Gegenstand gespeichert und fängt spätere Verluste ab. Die verfügbare Senke wird als Gewichtsabstand zwischen deinen Würfen und den perfekten Würfen geschätzt.',
        'how_over': 'Overmage: Einen Wert über seinen perfekten Wurf zu heben oder einen neuen Wert hinzuzufügen (ein Exo) kostet Senke. Das gesamte Over/Exo-Gewicht auf einem Wert kann nie 101 überschreiten.',
        'how_exo': 'Eine Zeile, die 30 Gewicht oder mehr über dem eigenen Wurf '
                   'des Gegenstands liegt, gelingt nur mit einem kritischen '
                   'Erfolg, geschätzt 1%% pro Versuch: %(stats)s. Leichtere '
                   'Exos gelingen wie normale Runen, zählen aber zur '
                   '101-Grenze.',
        'how_rule20': 'Faustregel: Eine Rune gelingt zuverlässig, solange der Wert unter ~20x dem Runenbonus liegt (+1 bis ~20, +3 bis ~60, +10 bis ~200). Darüber sind Fehlschläge zu erwarten - dort zählen Senke und Geduld.',
        'how_sink_loss': 'Vorsicht: Die Senke ist an die Schmiedemagie-Sitzung gebunden. Anlegen, Tauschen oder Verkaufen des Gegenstands setzt sie laut Community zurück.',
        'how_disclaimer': 'Ankama hat die genaue Erfolgsformel nie veröffentlicht; die hier gezeigten Raten sind Schätzungen der Community.',
        'how_disclaimer_retro': 'Für Retro hat Ankama das System und seine Wahrscheinlichkeiten sehr wohl veröffentlicht, im Devblog zur 1.27. Die Formel dahinter wurde nie genannt, daher bleiben die Raten pro Wurf im Simulator Schätzungen.',
        'how_malus': 'Malus-Zeilen: Ein Malus lässt sich aufheben, aber nie in einen Bonus verwandeln — seine Zeile endet bei 0. Ein Malus innerhalb seiner natürlichen Spanne dient nicht als Senke; erst wenn er über seinen besten natürlichen Wert hinausgeschoben wurde, wird er zu einer. Ein Bonus lässt sich bis 0 leeren, ein Malus nur bis zu seinem natürlichen Minimum senken.',
        'odds_title': 'Die von Ankama veröffentlichten Wahrscheinlichkeiten',
        'odds_intro': 'Bei Retro sind die Erfolgsraten keine Vermutung. Ankama hat das Schmiedemagie-System der 1.27 dokumentiert und sechs Situationen beziffert. Neutral übersteigt nie 50 %, und der kritische Erfolg fällt nie unter 1 %, solange der Versuch nicht schlicht unmöglich ist.',
        'odds_source': 'Zahlen aus dem Devblog zur 1.27 vom 18. Mai 2009. Diese Seite zielt auf Retro 1.29, zwei Versionen später: als veröffentlichte Grundlage lesen, nicht als Messung des heutigen Spiels.',
        'odds_col_case': 'Situation',
        'odds_col_sc': 'Kritischer Erfolg',
        'odds_col_n': 'Neutral',
        'odds_col_ec': 'Kritischer Fehlschlag',
        'odds_remount': 'Einen einfachen Wert wie Vitalität auf einem gewöhnlichen Gegenstand anheben, Meisterschmied',
        'odds_perfect': 'Den perfekten Wurf erreichen, einfacher Bonus auf einfachem Gegenstand',
        'odds_remount_hard': 'Einen schweren Wert auf einem komplexen Gegenstand anheben, schlimmster Fall',
        'odds_create_best': 'Einen Effekt erzeugen, den der Gegenstand nicht hat, mit Senke, bester Fall',
        'odds_create_worst': 'Einen Effekt erzeugen, mit Senke, schlimmster Fall',
        'odds_create_nosink': 'Einen Effekt ganz ohne Senke erzeugen',
        'tips_title': 'Strategie-Tipps',
        'tip_1': 'Schmiede einen Wert nach dem anderen: große Runen zuerst, solange der Wert niedrig ist, kleine Runen zum Abschluss nahe dem Maximum.',
        'tip_2': 'Baue Senke auf, bevor du teure Runen wirfst: Opfere einen schweren Wert, den du nicht brauchst - sein Gewicht fängt spätere Verluste ab.',
        'tip_3': 'Hebe AP/BP für ganz zum Schluss auf: setze erst die anderen Werte in die Senke und versuche die große Rune dann mit möglichst voller Senke - kritische Misserfolge fressen die Senke statt deiner guten Würfe.',
        'tip_4': 'Vergleiche die Preise in beide Richtungen: Gegenstände zu Runen zerbrechen oder Runen direkt kaufen - je nachdem, was an dem Tag günstiger ist.',
        'ref_title': 'Runen- und Gewichtsreferenz',
        'ref_stat': 'Wert',
        'ref_density': 'Gewicht pro Punkt',
        'ref_runes': 'Runen (Bonus / Gewicht)',
        'ref_max_over': 'Max. Over/Exo',
        'ref_no_rune': 'Keine Rune',
        'ref_approx': 'ungefähr',
        'footer_sources': 'Mechaniken zusammengetragen aus Community-Referenzen (Ankama-Tutorials, JeuxOnLine, Dofus pour les Noobs, Dofuzion-1.29-Tabelle, Dofus-Touch-Runenlisten).',
        'sim_title': 'Schmiedemagie-Sitzung (Simulator)',
        'sim_intro': 'Wirf Runen virtuell oder trage deine Ergebnisse aus dem Spiel ein: Senke, Verluste und verbrauchte Runen werden automatisch verfolgt. Die Sitzung wird im Browser gespeichert.',
        'sim_start': 'Sitzung starten',
        'sim_reset': 'Sitzung zurücksetzen',
        'sim_undo': 'Letzten Wurf rückgängig machen',
        'sim_sink': 'Aktuelle Senke (Reliquat)',
        'sim_throws': 'Würfe',
        'sim_criticals': 'Aufgezeichnete Kritische',
        'sim_model': 'Modell',
        'sim_runes_used': 'Verbrauchte Runen',
        'sim_suggested': 'Nächste empfohlene Rune',
        'sim_rune_label': 'Rune',
        'sim_throw': 'Wurf simulieren',
        'sim_record_hint': 'Du schmiedest im Spiel? Trage stattdessen das echte Ergebnis ein:',
        'sim_sc': 'SC - kritischer Erfolg',
        'sim_sn': 'SN - neutraler Erfolg',
        'sim_ec': 'EC - kritischer Misserfolg',
        'sim_history': 'Verlauf',
        'sim_done': 'Ziel erreicht!',
        'sim_no_target': 'Setze Ziele über deinen Würfen, um Vorschläge zu erhalten.',
        'sim_chance': 'Geschätzte Erfolgschance',
        'sim_disclaimer': 'Simulierte Wahrscheinlichkeiten und Verluste sind grobe Community-Schätzungen; das echte Spiel kann abweichen.',
        'sim_now': 'Aktuell',
        'sim_target': 'Ziel',
        'sim_remaining': 'Verbleibend',
        'sim_sink_gain': 'Senke',
        'sim_sacrifice': 'Opferwurf - wirf kleine Runen, damit der unerwünschte Wert fällt und sein Gewicht als Senke gespeichert wird',
        'sim_sacrifice_hint': 'Tipp: Die Senke ist leer. Senke das Ziel eines entbehrlichen Werts (z. B. AP auf 0), damit er fällt und die Senke füllt, bevor du teure Runen setzt.',
        'sim_profit_title': 'Rentabilität',
        'sim_item_cost': 'Kaufpreis des Gegenstands (Kamas)',
        'sim_sale_price': 'Erwarteter Verkaufspreis (Kamas)',
        'sim_runes_cost': 'Runenkosten',
        'sim_total_cost': 'Gesamtkosten',
        'sim_profit': 'Gewinn',
        'sim_unit_price': 'Stückpreis',
        'quality_title': 'Wurfqualität',
        'quality_bad': 'schlecht',
        'quality_ok': 'ordentlich',
        'quality_good': 'gut',
        'quality_amazing': 'unglaublich',
        'quality_perfect': 'perfekt',
        'quality_overperfect': 'besser als perfekt',
        'sim_other_runes': 'Andere Runen',
        'stat_line_hunting': 'Jagdwaffe',
        'sim_landed': 'ja',
        'nostat_title': 'Runen, die keinen Wert erhöhen',
        'nostat_rune': 'Rune',
        'nostat_what': 'Wirkung',
        'nostat_weight': 'Gewicht',
        'nostat_unknown': 'für diese Version nicht bekannt',
        'rune_hunting': 'Jagdrune',
        'rune_hunting_what': 'Macht aus einer Waffe eine Jagdwaffe, mit der man Fleisch aus einem Kampf mitbringt.',
        'rune_signature': 'Signier-Rune',
        'rune_signature_what': 'Versieht den Gegenstand mit dem Namen seines Handwerkers. Sie kommt bei der Herstellung zu den Zutaten, nie in die Schmiedemagie.',
        'inv_save': 'In meinem Inventar speichern',
        'inv_save_smithed': 'Den geschmiedeten Gegenstand in meinem Inventar speichern',
        'inv_new_folder': 'Neuer Ordner…',
        'inv_saved': 'Gespeichert!',
        'search_inventory': 'In meinem Inventar suchen (lädt meine gespeicherten Würfe)',
        'sim_sink_empty': 'Senke leer - STOPP, keine Runen mehr werfen: die nächsten Fehlschläge fressen deine gesetzten Werte. Baue erst wieder Senke auf.',
        'inv_update': 'Gespeicherten Gegenstand aktualisieren',
        'inv_save_copy': 'Neue Kopie speichern',
        'sim_improve': 'Bonus - nutze die überschüssige Senke für eine risikofreie Verbesserung; genug Senke bleibt für die große Rune reserviert',
        'sim_improve_done': 'Senke übrig: du kannst %s noch gratis erhöhen.',
        'sim_mode_label': 'Modus',
        'sim_mode_sim': 'Simulation',
        'sim_mode_real': 'Echte Schmiede',
        'sim_mode_sim_hint': 'Das Tool wirft die Runen und schätzt die Ergebnisse und Verluste für dich.',
        'sim_mode_real_hint': 'Du schmiedest im Spiel: nach jedem Wurf die Rune wählen und das Ergebnis angeben (SC/SN/EC), dann unten die neuen Werte deines Gegenstands eintippen. Die Felder Jetzt und Ziel sind bearbeitbar.',
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


def _one_percent_stat_names(structure, game_version, language):
    """The lines this version grants only on a critical, from its densities."""
    threshold = get_one_percent_over_weight(game_version)
    names = []
    for stat_key, fm_stat in get_fm_stats(game_version).items():
        if fm_stat['density'] < threshold:
            continue
        stat = structure.get_stat_by_key(stat_key)
        if stat is not None:
            names.append(_localized_label(stat.name, language))
    return sorted(names)


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


def _build_no_stat_rune_rows(game_version, t):
    """The runes of this version that change the item without raising a stat."""
    rows = []
    for rune in get_no_stat_runes(game_version):
        rows.append({
            'name': t['rune_%s' % rune['key']],
            'what': t['rune_%s_what' % rune['key']],
            'weight': (t['nostat_unknown'] if rune['weight'] is None
                       else _format_weight(rune['weight'])),
        })
    return rows


def _throwable_no_stat_runes(game_version, t):
    """The no-stat runes the simulator can actually throw: the signature rune
    never enters smithmagic, and a rune whose weight this version does not
    state cannot be weighed against the item."""
    return [{'key': rune['key'],
             'name': t['rune_%s' % rune['key']],
             'weight': rune['weight']}
            for rune in get_no_stat_runes(game_version)
            if rune['mageable'] and rune['weight']]


def _build_transcendence_rows(structure, game_version, language, trans_t):
    """One row per stat a transcendence rune can raise, in reference order."""
    by_stat = get_transcendence_by_stat(game_version)
    if not by_stat:
        return []
    rows = []
    for stat_key in _ordered_fm_stat_keys(structure, get_fm_stats(game_version)):
        entry = by_stat.get(stat_key)
        if entry is None:
            continue
        stat = structure.get_stat_by_key(stat_key)
        rows.append({
            'key': stat_key,
            'name': (_localized_label(stat.name, language) if stat is not None
                     else entry['label']),
            'icon_url': _get_stat_icon_url(stat_key),
            'runes': [
                '%s: +%d / %s' % (rune['name_fr'], rune['bonus'],
                                  trans_t['weight_word']
                                  % _format_weight(rune['weight']))
                for rune in entry['runes']
            ],
        })
    return rows


TRANSCENDENCE_UI = {
    'en': {
        'title': 'Transcendence runes (lock smithmagic)',
        'intro': 'Applied at 100% - they add a powerful bonus but permanently '
                 'lock the item (no further smithmagic). Only possible if the '
                 'item has no over and no exotic line, and if the rune\u2019s '
                 'weight plus the target stat\u2019s current weight stays '
                 'within 101.',
        'locked': 'Item transcended by %s - smithmagic locked.',
        'over_block': 'Impossible: the item exceeds its max roll on a line. '
                      'Remove the over before transcending.',
        'exo_block': 'Impossible: the item carries an exotic line. '
                     'A transcendence rune only lands on an unmodified item.',
        'weight_block': 'Impossible: the rune\u2019s weight plus this stat\u2019s '
                        'current weight exceeds 101.',
        'weight_word': 'weight %s',
    },
    'fr': {
        'title': 'Runes de transcendance (verrouillent la FM)',
        'intro': 'Pos\u00e9es \u00e0 100 % - elles ajoutent un bonus puissant mais '
                 'verrouillent d\u00e9finitivement l\u2019objet (plus aucune '
                 'forgemagie). Possible seulement si l\u2019objet n\u2019a ni over '
                 'ni ligne exotique, et si le poids de la rune plus le poids '
                 'actuel de la stat vis\u00e9e reste dans les 101.',
        'locked': 'Objet transcend\u00e9 par %s - forgemagie bloqu\u00e9e.',
        'over_block': 'Impossible : l\u2019objet d\u00e9passe son jet max sur une '
                      'ligne. Retirez l\u2019over avant de transcender.',
        'exo_block': 'Impossible : l\u2019objet porte une ligne exotique. Une rune '
                     'de transcendance ne se pose que sur un objet non modifi\u00e9.',
        'weight_block': 'Impossible : le poids de la rune plus le poids actuel '
                        'de cette stat d\u00e9passe 101.',
        'weight_word': 'poids %s',
    },
    'es': {
        'title': 'Runas de trascendencia (bloquean la forja)',
        'intro': 'Se aplican al 100 % - añaden un bono potente pero bloquean el '
                 'objeto para siempre (no más forja). Solo si el objeto no '
                 'tiene over ni línea exótica, y si el peso de la runa más el '
                 'peso actual de la característica elegida no pasa de 101.',
        'locked': 'Objeto trascendido con %s - forja bloqueada.',
        'over_block': 'Imposible: el objeto supera su tirada máxima en una '
                      'línea. Quita el over antes de trascender.',
        'exo_block': 'Imposible: el objeto lleva una línea exótica. Una runa '
                     'de trascendencia solo entra en un objeto sin modificar.',
        'weight_block': 'Imposible: el peso de la runa más el peso actual de '
                        'esta característica supera 101.',
        'weight_word': 'peso %s',
    },
    'pt': {
        'title': 'Runas de transcendência (bloqueiam a FM)',
        'intro': 'Aplicadas a 100% - adicionam um bônus poderoso mas bloqueiam '
                 'o item para sempre (sem mais forjamagia). Só se o item não '
                 'tiver over nem linha exótica, e se o peso da runa mais o '
                 'peso atual do atributo visado não passar de 101.',
        'locked': 'Item transcendido por %s - forjamagia bloqueada.',
        'over_block': 'Impossível: o item ultrapassa sua rolagem máxima em uma '
                      'linha. Remova o over antes de transcender.',
        'exo_block': 'Impossível: o item carrega uma linha exótica. Uma runa '
                     'de transcendência só entra em um item sem modificações.',
        'weight_block': 'Impossível: o peso da runa mais o peso atual deste '
                        'atributo ultrapassa 101.',
        'weight_word': 'peso %s',
    },
    'de': {
        'title': 'Transzendenz-Runen (sperren die Schmiedemagie)',
        'intro': 'Mit 100% gesetzt - sie geben einen starken Bonus, sperren den '
                 'Gegenstand aber dauerhaft (keine Schmiedemagie mehr). Nur '
                 'möglich, wenn der Gegenstand weder Over noch exotische Linie '
                 'trägt und das Gewicht der Rune plus das aktuelle Gewicht des '
                 'Zielwerts 101 nicht übersteigt.',
        'locked': 'Gegenstand durch %s transzendiert - Schmiedemagie gesperrt.',
        'over_block': 'Unmöglich: Der Gegenstand überschreitet auf einer Linie '
                      'seinen Maximalwurf. Entferne den Over vor dem '
                      'Transzendieren.',
        'exo_block': 'Unmöglich: Der Gegenstand trägt eine exotische Linie. '
                     'Eine Transzendenz-Rune passt nur auf einen unveränderten '
                     'Gegenstand.',
        'weight_block': 'Unmöglich: Das Gewicht der Rune plus das aktuelle '
                        'Gewicht dieses Werts übersteigt 101.',
        'weight_word': 'Gewicht %s',
    },
}


def forgemagie(request):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')
    ruleset = get_ruleset(game_version)

    # Both sentences name the lines this version grants only on a critical, so
    # Retro reads its own crit and reflect runes instead of the modern list.
    one_percent = ', '.join(_one_percent_stat_names(structure, game_version,
                                                    language))
    t = dict(t)
    for key in ('exo_one_percent', 'how_exo'):
        t[key] = t[key] % {'stats': one_percent}

    # Retro is the one ruleset whose odds Ankama published. Where there are
    # rows, the disclaimer saying nothing was ever published is wrong, so it
    # is swapped rather than left to contradict the table below it.
    documented_odds = [dict(row, label=t['odds_%s' % row['key']])
                       for row in get_documented_odds(ruleset)]
    if documented_odds:
        t['how_disclaimer'] = t['how_disclaimer_retro']

    stat_payload = _build_stat_payload(structure, game_version, language)
    reference_rows = _build_reference_rows(structure, game_version, language, t)
    trans_t = TRANSCENDENCE_UI.get(language, TRANSCENDENCE_UI['en'])
    no_stat_rune_rows = _build_no_stat_rune_rows(game_version, t)
    transcendence_rows = _build_transcendence_rows(
        structure, game_version, language, trans_t)

    js_config = {
        'overCap': OVER_WEIGHT_CAP,
        'onePercentOverWeight': get_one_percent_over_weight(game_version),
        # Empty for every ruleset but Retro. The simulator falls back to its
        # own fitted split when it is, which is the honest thing to do where
        # nothing was ever published.
        'oddsLadder': get_odds_ladder(ruleset),
        'stats': stat_payload,
        'statOrder': _ordered_fm_stat_keys(structure, get_fm_stats(game_version)),
        'searchUrl': version_reverse(request, 'forgemagie_items'),
        'gameVersion': game_version,
        'inventoryFoldersUrl': version_reverse(request, 'inventory_folders'),
        'inventoryAddUrl': version_reverse(request, 'inventory_add'),
        'inventoryUpdateUrl': version_reverse(request, 'inventory_update'),
        't': {
            key: t[key] for key in (
                'search_no_results', 'item_level', 'wb_not_mageable',
                'wb_exo_pick', 'wb_remove', 'verdict_ok', 'verdict_over',
                'verdict_cap', 'exo_one_percent', 'diff_safe', 'diff_likely',
                'diff_risky', 'diff_hard', 'diff_exo', 'diff_over',
                'ref_no_rune',
                'sim_sink', 'sim_throws', 'sim_criticals', 'sim_model',
                'sim_runes_used', 'sim_suggested',
                'sim_sc', 'sim_sn', 'sim_ec', 'sim_done', 'sim_no_target',
                'sim_chance', 'sim_now', 'sim_target', 'sim_remaining',
                'sim_sink_gain', 'sim_sacrifice', 'sim_sacrifice_hint',
                'sim_runes_cost', 'sim_total_cost', 'sim_profit',
                'sim_unit_price', 'quality_title', 'quality_bad',
                'quality_ok', 'quality_good', 'quality_amazing',
                'quality_perfect', 'quality_overperfect', 'inv_new_folder',
                'sim_sink_empty', 'inv_save_copy', 'wb_add',
                'sim_improve', 'sim_improve_done',
                'sim_mode_sim', 'sim_mode_real',
                'sim_mode_sim_hint', 'sim_mode_real_hint',
                'sim_other_runes', 'stat_line_hunting',
                'sim_landed',
            )
        },
        'noStatRunes': _throwable_no_stat_runes(game_version, t),
        'transcendence': get_transcendence_by_stat(game_version),
        'transT': trans_t,
    }

    preload = (_inventory_preload(request, structure, language, game_version)
               or _catalogue_preload(request, structure, language))
    if preload is not None:
        js_config['preload'] = preload

    return set_response(
        request,
        'chardata/forgemagie.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'version_note': t['version_note_%s' % ruleset],
            'documented_odds': documented_odds,
            'reference_rows': reference_rows,
            'has_approx_rows': any(row['approx'] for row in reference_rows),
            'no_stat_rune_rows': no_stat_rune_rows,
            'transcendence_rows': transcendence_rows,
            'trans_t': trans_t,
            'js_config': js_config,
            'tips': [t['tip_1'], t['tip_2'], t['tip_3'], t['tip_4']],
        },
    )


def _normalized_text(value):
    if not value:
        return ''
    return strip_accents(value).lower().strip()


def _item_payload(structure, item, language, display_name=None):
    """The JSON shape the workbench expects for a selectable item."""
    type_name = structure.get_type_name_by_id(item.type)
    stats = []
    stat_ranges = getattr(item, 'stat_ranges', {}) or {}
    for stat_id, stat_value in item.stats:
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        low = stat_ranges.get(stat_id, (None, None))[0]
        stats.append({
            'key': stat.key,
            'name': _localized_label(stat.name, language),
            'icon': _get_stat_icon_url(stat.key),
            'value': int(round(stat_value)),
            'min': int(round(low)) if low is not None else None,
        })
    stats.sort(key=lambda entry: STAT_ORDER.get(entry['key'], 9999))
    return {
        'id': item.id,
        'name': display_name or structure.get_item_name_in_language(item, language),
        'level': item.level,
        'type_name': _localized_label(type_name, language),
        # The hunting rune only goes on a weapon that is not one already, and
        # the label above is translated, so the canonical type and the flag
        # travel with the item.
        'is_weapon': type_name == 'Weapon',
        'is_hunting': 'Hunting Weapon' in (getattr(item, 'flags', None) or []),
        'image_url': static(get_image_url(type_name, item.name)),
        'stats': stats,
    }


def _catalogue_preload(request, structure, language):
    """Workbench preload for /forgemagie/?item=<item id>, for a reader arriving
    from a build instead of from their own inventory: no saved rolls, no login."""
    item_id = safe_int(request.GET.get('item'), None)
    if item_id is None:
        return None
    item = structure.get_item_by_id(item_id)
    if item is None:
        return None
    if structure.get_type_name_by_id(item.type) not in MAGEABLE_TYPES:
        return None
    return {'item': _item_payload(structure, item, language)}


def _inventory_preload(request, structure, language, game_version):
    """Workbench preload for /forgemagie/?inv=<inventory item id>."""
    inv_id = safe_int(request.GET.get('inv'), None)
    if inv_id is None or not request.user.is_authenticated:
        return None
    from chardata.models import InventoryItem
    from chardata.inventory_view import parse_custom_stats
    row = (InventoryItem.objects
           .filter(id=inv_id, folder__user=request.user,
                   folder__game_version=game_version)
           .select_related('folder').first())
    if row is None:
        return None
    item = structure.get_item_by_id(row.item_id)
    if item is None:
        return None
    return {
        'item': _item_payload(structure, item, language),
        'stats': parse_custom_stats(row.custom_stats, structure),
        'inv_id': row.id,
    }


def forgemagie_items(request):
    """Item autocomplete for the workbench: name search over mageable items,
    or over the user's inventory (with saved rolls) when inventory=1."""
    structure = get_structure()
    language = get_supported_language()
    query = _normalized_text(request.GET.get('q') or '')

    if request.GET.get('inventory') == '1':
        if not request.user.is_authenticated:
            return JsonResponse({'items': []})
        from chardata.models import InventoryItem
        from chardata.inventory_view import parse_custom_stats
        game_version = getattr(request, 'game_version', 'dofus3')
        results = []
        inventory_rows = (InventoryItem.objects
                          .filter(folder__user=request.user,
                                  folder__game_version=game_version)
                          .select_related('folder').order_by('-added_time')[:300])
        for row in inventory_rows:
            item = structure.get_item_by_id(row.item_id)
            if item is None:
                continue
            localized_name = structure.get_item_name_in_language(item, language)
            candidate = _normalized_text('%s %s' % (localized_name, item.or_name or ''))
            if query and query not in candidate:
                continue
            payload = _item_payload(structure, item, language, localized_name)
            payload['custom'] = parse_custom_stats(row.custom_stats, structure)
            payload['folder'] = row.folder.name
            payload['inv_id'] = row.id
            results.append(payload)
            if len(results) >= 20:
                break
        return JsonResponse({'items': results})

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
        # "Or items" (Gelano-style) carry their stats on per-variant entries.
        variants = [item]
        if not item.stats:
            or_variants = structure.get_items_by_or_name(
                item.or_name or item.name, item.dofus_touch)
            with_stats = [variant for variant in (or_variants or [])
                          if variant is not None and variant.stats]
            if with_stats:
                variants = with_stats

        for variant in variants:
            payload = _item_payload(
                structure, variant, language,
                localized_name if variant is item else None)
            # Variants share the parent's icon, they are the same object.
            payload['image_url'] = static(get_image_url(type_name, item.name))
            items.append(payload)

    return JsonResponse({'items': items})
