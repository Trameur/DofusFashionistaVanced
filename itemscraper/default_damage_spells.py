from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DefaultSpellSpec:
    """Un sort que porte un objet et non une classe, donc partage par tous.

    Ces sorts etaient apparies au client par NOM, ce qui ne tient que tant
    que le nom ne bouge pas. Le client de Dofus 3 a rebaptise l'attaque du
    Dofus Ebene en <<Ebony Black>>: l'appariement a echoue, le repli sur les
    valeurs ecrites a la main a pris le relais, et rien ne l'a dit. D'ou les
    champs ci-dessous, et l'identifiant essaye avant le nom.
    """

    name: str
    prefer_variant: bool = False
    #: Identifiant Ankama verifie dans les donnees du client. Il est essaye
    #: avant le nom, parce qu'un identifiant ne se renomme pas.
    ankama_id: int = 0
    #: Vrai quand le client ne porte AUCUNE ligne de degats pour ce sort et
    #: que les valeurs ecrites a la main sont donc inevitables. Le generateur
    #: n'avertit que pour les replis non declares ici.
    hand_written: bool = False
    #: Niveau a partir duquel le sort est atteignable, quand c'est l'OBJET
    #: qui le donne qui decide et non le sort. Ankama ecrit l'attaque du
    #: Dofus Ebene comme atteignable au niveau 1, ce qui est vrai du sort et
    #: faux du joueur: il faut porter le Dofus, et le Dofus se porte a 180.
    #: Un test relit ce nombre dans le catalogue, il n'est pas une croyance.
    level_requirement: int = 0
    #: Vrai quand les paliers du client sont des etats de CHARGE et non des
    #: rangs que le joueur choisit. Le client de Dofus 3 ecrit l'attaque du
    #: Dofus Ebene en neuf paliers gagnant un element chacun; ce ne sont pas
    #: neuf niveaux de sort, c'est une attaque qui se charge. Lus comme des
    #: rangs ils dessinent un triangle de zeros et la page montre un objet qui
    #: forcit quand le lecteur monte en niveau, ce qui est faux. On garde donc
    #: l'attaque CHARGEE, exactement la forme sous laquelle le client de
    #: Dofus 2 livre deja le meme sort. `get_spells._collapse_element_variants`
    #: fait ce travail en amont quand chaque palier ne porte qu'un element;
    #: ici les quatre derniers en portent plusieurs, donc il ne s'applique pas.
    grades_are_charges: bool = False


DEFAULT_DAMAGE_SPELL_SPECS: Sequence[DefaultSpellSpec] = (
    # Le client porte bien 24006 et 3506, mais sans la moindre ligne de
    # degats: leurs valeurs ne peuvent venir que de nous.
    DefaultSpellSpec("Burnt Pie", prefer_variant=True, ankama_id=24006,
                     hand_written=True),
    DefaultSpellSpec("Leek Pie", prefer_variant=True),
    DefaultSpellSpec("Grunob's Lightning Strike"),
    DefaultSpellSpec("Grunob's Lesson"),
    DefaultSpellSpec("Kannibubble"),
    DefaultSpellSpec("Kanniboil"),
    DefaultSpellSpec("Mantiscroc"),
    DefaultSpellSpec("Dart Mocles"),
    DefaultSpellSpec("Moon Hammer", prefer_variant=True),
    DefaultSpellSpec("Darkli Moon Hammer"),
    DefaultSpellSpec("Perfidious Boomerang"),
    DefaultSpellSpec("Diamondine Boomerang"),
    DefaultSpellSpec("Weapon Skill", ankama_id=3506, hand_written=True),
    DefaultSpellSpec("Ebony Dofus", ankama_id=18645, level_requirement=180,
                     grades_are_charges=True),
    DefaultSpellSpec("Crocobur's Appetite"),
    DefaultSpellSpec("Pestilential Fog"),
    DefaultSpellSpec("Scurvion Toxicity"),
)


DEFAULT_DAMAGE_SPELL_NAMES: Sequence[str] = tuple(spec.name for spec in DEFAULT_DAMAGE_SPELL_SPECS)
