from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class ItemEffect:
    """Ce que l'OBJET dit de son effet, quand le sort cache ne le dit pas.

    Le client range ces effets comme des sorts, avec des lignes de degats et
    un cout en PA. La fiche de l'objet, elle, dit ce qui se passe vraiment. Le
    Dofus Ebene en est l'exemple: le client lui donne cinq lignes de 16 et 1 PA,
    et l'objet dit <<la prochaine attaque applique un poison de 16 DANS SON
    ELEMENT>>. Cinq lignes lues comme simultanees, c'est 80 annonces la ou le
    jeu en met 16.
    """

    #: Les lignes elementaires sont les faces d'un meme effet et une seule
    #: tombe, donc elles s'annoncent comme des choix et non comme une somme.
    element_alternatives: bool = False
    #: Le nombre de cumuls que l'objet annonce, quand il n'est pas celui que
    #: le client porte. Le Dofus Ebene cumule son POISON 2 fois; le 5 du
    #: client est celui d'un autre effet, le bonus de 2%.
    stacks: int = 0
    #: Ce qui doit arriver pour que ces lignes tombent. La cle est nommee dans
    #: `spells_view._CONDITIONAL_LABELS`, donc traduite.
    conditional_trigger: str = ''
    #: Faux quand le joueur ne lance jamais cet effet lui-meme: il n'a donc
    #: pas de cout en PA a montrer.
    cast_by_the_player: bool = True


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
    #: Ce que la fiche de l'objet dit de cet effet, quand elle contredit la
    #: forme que le client donne au sort cache.
    item_effect: Optional[ItemEffect] = None


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
    # La fiche de l'objet, lue le 12 septembre 2026 dans notre catalogue, sur
    # Dofus 3 comme sur Dofus 2: <<Declencher les 2 effets dans le tour permet
    # a la prochaine attaque d'appliquer un poison de 16 DANS SON ELEMENT
    # pendant 2 tours (cumulable 2 fois)>>. Un poison, un element, deux
    # cumuls, et rien que le joueur lance.
    DefaultSpellSpec("Ebony Dofus", ankama_id=18645, level_requirement=180,
                     grades_are_charges=True,
                     item_effect=ItemEffect(element_alternatives=True,
                                            stacks=2,
                                            conditional_trigger='melee_and_ranged',
                                            cast_by_the_player=False)),
    DefaultSpellSpec("Crocobur's Appetite"),
    DefaultSpellSpec("Pestilential Fog"),
    DefaultSpellSpec("Scurvion Toxicity"),
)


DEFAULT_DAMAGE_SPELL_NAMES: Sequence[str] = tuple(spec.name for spec in DEFAULT_DAMAGE_SPELL_SPECS)
