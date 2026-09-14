#!/usr/bin/env python3
"""
Build the Dofus Touch damage-spells dataset (per class) from the Touch backend.

Breeds gives each class its spell ids (breedSpellsId), Spells gives each spell
its grades (spellLevels), and SpellLevels carries the per-grade non-crit
(`effects`) and crit (`criticalEffect`) lists. Elemental damage uses the same
effect ids as items (96 Water, 97 Earth, 98 Air, 99 Fire, 100 Neutral);
diceNum/diceSide are the min/max of the hit.

Output: fashionistapulp/dofus_constants_touch_spells.py defining
TOUCH_DAMAGE_SPELLS (Spell/Effects objects) and TOUCH_SPELL_NAMES
({fr_name: {lang: name}}), shaped like the retro module.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import requests

LANGS = ['fr', 'en', 'es', 'pt', 'de']
CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json"
FALLBACK_DATA_URL = "https://dt-proxy-production-login.ankama-games.com"
UA = "Dofus/2 CFNetwork"
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fashionistapulp'))

from fashionistapulp.reserved_filenames import safe_asset_stem  # noqa: E402

# Spell icons live on the assets CDN, prefixed "sort_".
SPELL_ICON_URL = "%s/gfx/spells/sort_%s.png"
SPELLS_STATIC = (Path(__file__).resolve().parent.parent / 'fashionsite' / 'chardata'
                 / 'static' / 'chardata' / 'spells' / 'touch')

# 96-100 elemental damage, 91-95 elemental steals (same hit, heals the caster).
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral',
                  91: 'water', 92: 'earth', 93: 'air', 94: 'fire', 95: 'neutral'}

#: Ankama's "#1 a #2 (meilleur element)". It never names an element: it says
#: the elemental rows beside it are the SAME hit landing in whichever element
#: suits the caster, not several hits that add up.
BEST_ELEMENT_EFFECT = 1200

#: The label Dofus 3 writes on the first group of such a spell, kept identical
#: so both tables read the same downstream.
BEST_ELEMENT_LABEL = 'Hit in best element'

# NINE DAMAGE SPELLS USED TO BE MISSING FROM THIS TABLE, and the reason was
# that same effect id. Swept 2026-09-01 against the live backend: 330 class
# spells over the 15 classes carry 112 effect ids this file never reads, and
# exactly one of them is a plain damage row.
#
#   1200  "#1 a #2 (meilleur element)"    11 class spells
#
# Nine of them because that row is their only damage. They showed a card with
# no damage at all, and the turn could not cast them.
#
# The row names no element, so reading it means writing one row per element,
# and the question that held it back was which elements are candidates.
# Settled 2026-09-14: the four that have a characteristic of their own. Neutral
# is not one -- the damage formula reads it off Strength exactly as it reads
# Earth (DAMAGE_TYPE_TO_MAIN_STAT), so a neutral face could never be the
# caster's best on its own account, and Dofus 3's own generator writes the
# same four. See BEST_ELEMENT_TOKENS and BEST_ELEMENT_IS_THE_WHOLE_HIT, which
# also names the three of the nine that stay out and why.
#
# THE OTHER TWO SPELLS ARE NOT THAT CASE, and reading them as if they were
# cost two thirds of each. "Fanfaronnade" and "Embuscade" carry the id BESIDE
# named elemental rows holding the same values, and that was read as "those
# rows ARE the best-element hit written out", the way Dofus 3 writes such a
# spell. But Dofus 3 FABRICATES its rows from an effect that names no element,
# while these rows are Ankama's own, and Ankama's own sentence lists them as
# landing:
#
#   Ambush   "Inflicts Fire, Water and Earth damage AND damage in the
#             caster's best element."
#   Bravado  "Inflicts Air, Water, Earth AND best-element damage."
#
# Both sibling clients agree: Dofus 2 and Dofus 3 write Ambush as four rows
# with no group, under the same sentence shape, and add them up. Grouping them
# here showed one hit where the game lands three. See NAMED_ROWS_ALSO_LAND,
# whose quotes are read back at generation time.
#
# The best-element hit itself is a FOURTH row this file does not record, so
# both spells are still short of it. That is a gap, not a grouping: it belongs
# with the nine absent spells above, and inventing a value for it would be
# worse than leaving it out.
#
# Two more unread ids, neither of them a damage row:
#   293   "Augmente les degats de base du sort #1 de #3"   8 spells, all in the
#         table already on other rows, so only a bonus is missed. The modern
#         generator gives this id its own handling (MP_DAMAGE_EFFECT_ID).
#   2812  "#1 a #2% Dommages aux sorts occasionnes"        the 16 "Exaltation"
#         spells, one per class, all absent. A self-buff, so it belongs to the
#         same four-version scope question as the AP, MP and flat Damage ids.

# Characteristic effects, read since 2026-08-27.
#
# This generator used to read only the ten ids above, so every self-buff and
# every characteristic steal a Touch spell grants was dropped on the floor. The
# Touch table held ZERO buff rows, which looked like "Touch has no such spells"
# and was really "this file never asked". Swept against the live Touch backend:
# 23 class spells out of 330 carry one, among them the Iop's own "Puissance" at
# +400 and four Sram spells that steal a characteristic.
#
# A steal is modelled as a self-buff, exactly as the Dofus 2 and 3 tables
# already model Furrow's Intelligence theft: the caster ends the cast with the
# characteristic, which is what a build optimizer needs to know. Bonus ids
# (118/119/123/126/138) and steal ids (266-271) both verified against the live
# effects endpoint, keeping every description that begins with "Vole".
# The bonus and the steal of the same characteristic are two ids, and this
# table carried both for Strength, Agility, Chance and Intelligence while
# Wisdom and Vitality had only their steal. Not a decision: the table was
# transcribed from what one sweep happened to meet, and no Touch spell in that
# sweep granted plain Wisdom. Enutrof's "Lancer de Pieces" does, and it was
# missing for that reason alone.
#
# 124 and 125 read "+X Sagesse" and "+X Vitalite" on the effects endpoint, in
# POINTS. They are not 1033 and 1078, which carry Vitality as a PERCENTAGE
# under the same word; wiring one of those to buff_vit would credit -40 points
# where the game means -40 per cent, and nothing would go red.
#
# Measured on 2026-08-27: 124 is carried by one Touch spell, mask `C`, whose
# description says "donne de la Sagesse au lanceur"; 125 by none today. 125 is
# here to close the asymmetry that caused the miss rather than to fix a spell.
CHARACTERISTIC_EFFECTS = {
    138: 'buff_pow',
    118: 'buff_str', 119: 'buff_agi', 123: 'buff_cha', 126: 'buff_int',
    124: 'buff_wis', 125: 'buff_vit',
    271: 'buff_str', 268: 'buff_agi', 266: 'buff_cha', 269: 'buff_int',
    270: 'buff_wis', 267: 'buff_vit',
}
ROW_EFFECTS = dict(DAMAGE_EFFECTS)
ROW_EFFECTS.update(CHARACTERISTIC_EFFECTS)

# Spells whose characteristic line provably does not reach the caster.
#
# The line carries a target mask and the mask alphabet is not published: `C` is
# the caster, established on Touch by two single-line spells whose text says
# "du lanceur", and the rest of the letters resist measurement. Two filtering
# rules were built on the alphabet and both were refuted, each one costing a
# value that is right today.
#
# What is NOT ambiguous is Ankama's own sentence when a spell carries a single
# characteristic line: what the text says about the beneficiary can only be
# about that line. Four spells fall there, and the quoted sentence is what
# settles each one. Reading a description is first hand; guessing a letter is
# not.
#
# The quote is not decoration. _check_still_says below refuses to generate when
# a description no longer contains it, so a spell Ankama rewrites raises the
# question again instead of keeping an exclusion nobody rechecks.
NOT_A_SELF_BUFF = {
    52: 'augmente la puissance de tous les alli',          # Enutrof Cupidite
    9919: 'puissance des invocations',                     # Osamodas Crocs du Mulou
    3215: 'Sur un alli',                                   # Foggernaut Evolution
    9685: 'bonus Puissance sur les alli',                  # Osamodas Fouet
    # Ecaflip Roulette. The caster IS among the targets, which is why the mask
    # says nothing useful here: what disqualifies it is that the spell fires ONE
    # random effect, so the Power row is a possible outcome and not a thing the
    # caster gets by casting it. The same spell was wrong on Retro for the same
    # reason, where it granted four characteristics at once.
    7449: 'effet al',
}

# The four exclusions above were found by reading spells one at a time, which
# works once and then stops: Ankama adds spells, nobody re-derives the list, and
# the new one is credited to the player without a word. Roulette was found by
# screening instead, months after the list was written.
#
# So the generator screens every buff it is about to KEEP. If the spell's own
# description names summons, allies or enemies and the spell is settled nowhere,
# the run stops. It is deliberately noisy: 8 of the 20 kept buffs trip it, and
# seven of those are legitimate. Being made to answer for eight spells once is
# the price of not missing the ninth.
SOMEBODY_ELSE = ('invocation', 'alli', 'adversaire', 'ennemi')

BUFFS_THE_CASTER_TOO = {
    # Cra, Maitrise de l'Arc: buffs allies AND the caster, him the most.
    5523: 'plus important sur le lanceur',
    # Iop, Puissance: the caster gets it in full when he targets himself.
    8137: 'le lanceur gagne',
    # Ecaflip, Perception: the caster gets the full bonus, allies get less.
    7463: 'plus faible sur les alli',
    # Rogue, Dernier Souffle: names the caster before the allies.
    2810: 'Puissance du lanceur',
    # Xelor, Vortex: the caster may be the target, one turn later.
    9737: 'Si le lanceur est cibl',
    # Xelor, Poussiere Temporelle: STEALS Wisdom, so the caster gains it. The
    # word "adversaires" belongs to the theft, not to the beneficiary.
    8031: 'vole de la Sagesse aux adversaires',
    # Sram, Larcin: same shape, an Intelligence theft. "ennemis" belongs to the
    # damage half of the sentence.
    8747: "l'Intelligence",
}

ELEMENT_TOKEN_TO_CONST = {'earth': 'EARTH', 'fire': 'FIRE', 'water': 'WATER',
                          'air': 'AIR', 'neutral': 'NEUTRAL'}
# Buff rows are written as plain quoted strings in the module, the way the
# Dofus 2 and 3 tables write them, not as element constants.
ELEMENT_TOKEN_TO_CONST.update(
    {token: repr(token) for token in CHARACTERISTIC_EFFECTS.values()})

# Touch breed id -> Fashionista class name (the 15 Touch classes).
CLASS_ID_TO_NAME = {
    1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor', 6: 'Ecaflip',
    7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida', 11: 'Sacrier', 12: 'Pandawa',
    13: 'Rogue', 14: 'Masqueraider', 15: 'Foggernaut',
}


def resolve_config():
    """Return (dataUrl, assetsUrl) from the live client config."""
    try:
        cfg = requests.get(CONFIG_URL + '?lang=fr', headers={'User-Agent': UA}, timeout=30).json()
        return ((cfg.get('dataUrl') or FALLBACK_DATA_URL).rstrip('/'),
                (cfg.get('assetsUrl') or '').rstrip('/'))
    except Exception:
        return FALLBACK_DATA_URL, ''


def download_spell_images(by_class, spells, assets_url):
    """Save each damage spell's icon 96x96 as chardata/spells/touch/<French name>.png,
    where spells_view looks for it."""
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow not installed; skipping spell images", file=sys.stderr)
        return
    if not assets_url:
        print("  no assetsUrl; skipping spell images", file=sys.stderr)
        return
    SPELLS_STATIC.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    seen, written, missing = set(), 0, 0
    for class_spells in by_class.values():
        for s in class_spells:
            name = s['name']
            if name in seen:
                continue
            seen.add(name)
            icon_id = (spells.get(str(s['id'])) or {}).get('iconId')
            if icon_id is None:
                continue
            safe = safe_asset_stem(re.sub(r'[\\/*?:"<>|]', '', name).strip())
            dest = SPELLS_STATIC / ('%s.png' % safe)
            try:
                r = session.get(SPELL_ICON_URL % (assets_url, icon_id),
                                headers={'User-Agent': WEB_UA}, timeout=30)
                if r.status_code != 200 or not r.content:
                    missing += 1
                    continue
                img = Image.open(io.BytesIO(r.content)).convert('RGBA').resize((96, 96), Image.LANCZOS)
                out = io.BytesIO()
                img.save(out, format='PNG')
                dest.write_bytes(out.getvalue())
                written += 1
            except Exception:
                missing += 1
    print(f"  spell images: written={written} missing={missing}")


def fetch_table(data_url, cls, lang='fr'):
    return requests.post(f"{data_url}/data/map", json={'class': cls, 'lang': lang},
                         headers={'User-Agent': UA, 'Accept': 'application/json'},
                         timeout=180).json()


# Touch marks every row with when it lands, the same way the modern client
# does: "I" on cast, "TB" at the start of a turn, "TE" at the end. Poison
# insidieux and Toxines are Sram poisons that never landed on the turn they
# were cast, and the panel counted them as if they had.
DELAYED_TRIGGERS = {'TB': 'turn_begin', 'TE': 'turn_end'}


def when_it_lands(triggers):
    """The moment a row waits for, or None when it lands with the cast."""
    codes = {code for code in str(triggers or '').split('|') if code}
    if len(codes) != 1:
        return None
    return DELAYED_TRIGGERS.get(next(iter(codes)))


#: The four elements a best-element hit can land in, in the order Dofus 3's
#: own generator writes them. Neutral is not among them: it has no
#: characteristic of its own, and the damage formula reads it off Strength
#: exactly as it reads Earth, so a neutral face could never be the caster's
#: best on its own account.
BEST_ELEMENT_TOKENS = ('earth', 'fire', 'water', 'air')

#: The Touch spells whose ONLY damage row is the best-element one, with the
#: fragment of Ankama's own sentence that says the caster deals it to an
#: enemy. Read back at generation time by `_best_element_is_the_whole_hit`.
#:
#: Before this table those nine spells showed a card with no damage at all:
#: the row names no element, so reading it means writing one row per element,
#: and nothing had been checked about which elements are candidates. Three of
#: the nine stay out, and their reason is beside them.
BEST_ELEMENT_IS_THE_WHOLE_HIT = {
    5513: 'occasionne des dommages dans le meilleur ',   # Cra, Fleche Cinglante
    5901: 'occasionne des dommages dans le meilleur ',   # Sacrieur, Punition
    7987: 'occasionne des dommages dans le meilleur ',   # Xelor, Vol du Temps
    8131: 'dommages en croix dans le meilleur ',         # Iop, Epee Divine
    8133: 'occasionne des dommages dans le meilleur ',   # Iop, Intimidation
    12433: 'occasionne des dommages dans le meilleur ',  # Sacrieur, Projection
}

# THREE OF THE NINE ARE LEFT OUT, each on Ankama's own sentence:
#
#   6997  Pandawa, Flasque Explosive. The damage is not the caster's: "la
#         CIBLE infligera des dommages dans le meilleur element du lanceur
#         autour de sa cellule d'arrivee lorsqu'elle est lancee", and the cast
#         needs the state Porteur. A turn on one target does not model an
#         entity being thrown.
#   9685  Osamodas, Fouet. "Tue une invocation de classe du lanceur" first, so
#         counting its damage assumes a summon to sacrifice, which the turn
#         does not model. It also carries TWO best-element rows per grade
#         (the second for an enemy summon), and nothing says which one a cast
#         on a player lands.
#   6095  Zobal, Carnavalo. Two rows per grade as well, the second for the
#         state Psychopathe; the turn assumes no state standing, so picking
#         one would be picking the state.
#
# Measured 14 September 2026 against the live Touch backend: 11 class spells
# carry effect 1200, two of them beside named rows (see NAMED_ROWS_ALSO_LAND)
# and nine alone. Six of those nine are read here.


def _best_element_is_the_whole_hit(spell):
    """True when Ankama's sentence says this spell's best-element row is
    damage the caster deals, checked at generation time."""
    quote = BEST_ELEMENT_IS_THE_WHOLE_HIT.get(spell.get('id'))
    if quote is None:
        return False
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    if quote.lower() not in str(text).lower():
        raise SystemExit(
            'touch spell %s no longer says %r, so nothing says its '
            'best-element row is damage the caster deals. Re-read Ankama '
            'before regenerating. It now says: %r'
            % (spell.get('id'), quote, str(text)[:200]))
    return True


def collect_damage(effect_list, best_element_rows=False):
    """One effect list -> {row token: (min, max, when)}.

    Rows are the elemental damage hits plus the characteristic buffs and
    steals; the token is an element name for the first and a 'buff_<stat>'
    pseudo-element for the second.

    A spell level can carry several lines of the same element: state-dependent
    branches (targetMask '#A,E<state>' or 'v50') and damage/steal pairs. The
    strongest line per element (by midpoint) wins, and carries its own moment:
    the line the reader is shown is the line whose timing is reported."""
    out = {}
    for e in (effect_list or []):
        eid = e.get('effectId')
        if eid == BEST_ELEMENT_EFFECT and best_element_rows:
            # One row per element, the way Dofus 3's generator writes such a
            # hit: the effect names none, and the model needs a row to score.
            # They are grouped as alternatives by emit_aggregates, so the
            # four are the faces of one hit and not four hits.
            tokens = BEST_ELEMENT_TOKENS
        elif eid in ROW_EFFECTS:
            tokens = (ROW_EFFECTS[eid],)
        else:
            continue
        lo = e.get('diceNum') or 0
        hi = e.get('diceSide') or 0
        if hi < lo:                          # diceSide==0 (or < min) => fixed hit
            hi = lo
        for elem in tokens:
            prev = out.get(elem)
            if prev is None or lo + hi > prev[0] + prev[1]:
                out[elem] = (lo, hi, when_it_lands(e.get('triggers')))
    return out


# What a cast costs, how often the game allows it, and how often it crits.
# Touch runs the same percentage crit system as Dofus since its own overhaul.
CASTING_FIELDS = {'ap': 'apCost', 'per_turn': 'maxCastPerTurn',
                  'per_target': 'maxCastPerTarget', 'cooldown': 'minCastInterval',
                  'crit': 'criticalHitProbability'}


def _check_still_says(spell):
    """The exclusion's own evidence, verified at generation time.

    A quoted sentence in a table is a claim about a file nobody rereads. This
    reads it back: if Ankama has rewritten the description, the quote no longer
    matches and generating stops rather than carrying an exclusion whose reason
    has quietly expired.
    """
    quote = NOT_A_SELF_BUFF.get(spell.get('id'))
    if quote is None:
        return False
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    if quote.lower() not in str(text).lower():
        raise SystemExit(
            'spell %s no longer says %r; its buff was excluded on that '
            'sentence and the exclusion has to be decided again'
            % (spell.get('id'), quote))
    return True


def _description_of(spell):
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    return str(text)


def _screen_kept_buff(spell):
    """Stop the run if a KEPT buff's own sentence names somebody else.

    Runs on what the generator is about to write rather than on a list somebody
    maintains, so a spell added after this was written cannot be credited to
    the caster in silence: the run fails, names the spell and the words that
    flagged it, and quotes Ankama.
    """
    text = _description_of(spell)
    lowered = text.lower()
    named = [word for word in SOMEBODY_ELSE if word in lowered]
    if not named:
        return
    spell_id = spell.get('id')
    quote = BUFFS_THE_CASTER_TOO.get(spell_id)
    if quote is None:
        raise SystemExit(
            'touch spell %s (%s) keeps a characteristic buff and its own '
            'description names %s. Settle it in NOT_A_SELF_BUFF or in '
            'BUFFS_THE_CASTER_TOO before regenerating. Ankama wrote: %r'
            % (spell_id, spell.get('nameId'), '/'.join(named), text[:160]))
    if quote.lower() not in lowered:
        raise SystemExit(
            'touch spell %s no longer says %r; re-read it before trusting that '
            'the caster is among those it buffs' % (spell_id, quote))


def _says_best_element(level):
    """Does this grade carry Ankama's best-element row?"""
    for key in ('effects', 'criticalEffect'):
        for row in (level.get(key) or []):
            if isinstance(row, dict) and row.get('effectId') == BEST_ELEMENT_EFFECT:
                return True
    return False


#: The Touch spells whose NAMED elemental rows land together with the
#: best-element hit instead of being its faces, with Ankama's own sentence as
#: the evidence. Checked at generation time by `_named_rows_also_land`.
#:
#: Carrying the best-element effect id beside named rows was read as "those
#: rows ARE the best-element hit written out", the way Dofus 3 writes such a
#: spell -- but Dofus 3 FABRICATES its rows from an effect that names no
#: element, while these rows are Ankama's own. Its sentence lists them as
#: landing, and both sibling clients agree: Dofus 2 and Dofus 3 write Ambush
#: as four rows with no group and add them up, under the same sentence shape.
#: Grouping them here showed one hit of three, roughly a third of the spell.
NAMED_ROWS_ALSO_LAND = {
    3218: 'Feu, Eau et Terre ainsi que',        # Foggernaut Embuscade
    7612: 'Air, Eau, Terre et dans le meilleur',  # Ecaflip Fanfaronnade
}


def _named_rows_also_land(spell):
    """True when Ankama's sentence says the named rows land with the best one.

    Same device as `_check_still_says`: the quote is read back out of the
    description, so a rewording stops the run instead of leaving a grouping
    whose reason has quietly expired.
    """
    quote = NAMED_ROWS_ALSO_LAND.get(spell.get('id'))
    if quote is None:
        return False
    text = spell.get('descriptionId') or ''
    if isinstance(text, dict):
        text = text.get('fr') or ''
    if quote.lower() not in str(text).lower():
        raise SystemExit(
            'touch spell %s no longer says %r, so nothing says its named '
            'elemental rows land beside the best-element hit. Re-read Ankama '
            'before regenerating. It now says: %r'
            % (spell.get('id'), quote, str(text)[:200]))
    return True


def emit_aggregates(best_element, elements, spell=None):
    """One group per row when the rows are alternatives, else None.

    Written only for a spell whose rows are ALL elemental damage. A buff row is
    not an alternative to a hit, and putting it in a group of its own would
    make the model score the spell on the buff alone; a spell that mixes the
    two therefore keeps the old shape and is left for a later pass. Two rows at
    least, because one row is not a choice.

    And not written at all when Ankama says the named rows land together with
    the best-element hit: see `NAMED_ROWS_ALSO_LAND`.
    """
    if not best_element or len(elements) < 2:
        return None
    if any(str(token).startswith('buff_') for token in elements):
        return None
    if spell is not None and _named_rows_also_land(spell):
        return None
    return [(BEST_ELEMENT_LABEL if index == 0 else '', [index])
            for index in range(len(elements))]


def decode_spell(spell, spell_levels):
    """Touch spell -> damage-spell dict, or None if it carries no row at all.

    A spell that only buffs a characteristic and deals no damage is kept: the
    Dofus 2 and 3 tables keep theirs, and the optimizer needs the Iop's
    "Puissance" even though it hits nobody."""
    per_nc, per_cr, levels_req, elements, stacks = [], [], [], [], []
    casting_levels = []
    best_element = False
    # Ankama's sentence says this spell's only damage IS the best-element
    # row, so it is read as one row per element instead of being dropped.
    lire_le_meilleur = _best_element_is_the_whole_hit(spell)
    for lid in (spell.get('spellLevels') or []):
        lv = spell_levels.get(str(lid))
        if not lv:
            continue
        best_element = best_element or _says_best_element(lv)
        nc = collect_damage(lv.get('effects'), lire_le_meilleur)
        cr = collect_damage(lv.get('criticalEffect'), lire_le_meilleur)
        if _check_still_says(spell):
            # Ankama's own sentence says this buff goes to allies, summons or
            # a turret. Dropping the row leaves whatever damage the spell also
            # deals, which is what a Touch player casting it actually gets.
            nc = {k: v for k, v in nc.items() if not k.startswith('buff_')}
            cr = {k: v for k, v in cr.items() if not k.startswith('buff_')}
        per_nc.append(nc)
        per_cr.append(cr)
        levels_req.append(max(1, int(lv.get('minPlayerLevel') or 1)))
        try:
            stack = int(lv.get('maxStack') or 0)
        except (TypeError, ValueError):
            stack = 0
        if stack > 1:
            stacks.append(stack)
        level_casting = {}
        for key, field in CASTING_FIELDS.items():
            try:
                level_casting[key] = int(lv.get(field) or 0)
            except (TypeError, ValueError):
                level_casting[key] = 0
        casting_levels.append(level_casting)
        for elem in list(nc) + list(cr):
            if elem not in elements:
                elements.append(elem)
    if not elements:
        return None

    def when_by_row(per_level):
        """{row index: moment}, and only when every rank that has it agrees."""
        late = {}
        for index, elem in enumerate(elements):
            moments = {level[elem][2] for level in per_level if elem in level}
            if len(moments) == 1:
                moment = moments.pop()
                if moment:
                    late[index] = moment
        return late

    non_crit, crit = [], []
    for elem in elements:
        nc_row, cr_row = [], []
        for i in range(len(per_nc)):
            n = per_nc[i].get(elem)
            c = per_cr[i].get(elem) or n
            nc_row.append('%d-%d' % (n[0], n[1]) if n else '0-0')
            cr_row.append('%d-%d' % (c[0], c[1]) if c else '0-0')
        non_crit.append(nc_row)
        crit.append(cr_row)
    return {
        'id': spell['id'],
        'name': spell.get('nameId') or '',
        'levels_req': levels_req,
        'elements': elements,
        'non_crit_ranges': non_crit,
        'crit_ranges': crit,
        # Rows that are alternatives, not a sum. See emit_aggregates.
        'aggregates': emit_aggregates(best_element, elements, spell),
        # maxStack in the game data: the buff can accumulate.
        'stacks': max(stacks) if stacks else None,
        # A cast limit of 0 means no limit, so all-zero keys are dropped.
        'casting': {key: [level[key] for level in casting_levels]
                    for key in CASTING_FIELDS
                    if any(level[key] for level in casting_levels)} or None,
        'delayed': when_by_row(per_nc) or None,
        'delayed_crit': (when_by_row(per_cr)
                         if when_by_row(per_cr) != when_by_row(per_nc)
                         else None),
    }


def build(breeds, spells, spell_levels):
    by_class = {}
    for bid, app_name in CLASS_ID_TO_NAME.items():
        breed = breeds.get(str(bid))
        spell_ids = (breed or {}).get('breedSpellsId') or []
        damage_spells = []
        seen = set()
        for sid in spell_ids:
            spell = spells.get(str(sid))
            if not spell or sid in seen:
                continue
            seen.add(sid)
            decoded = decode_spell(spell, spell_levels)
            if decoded and any(str(token).startswith('buff_')
                               for token in decoded.get('elements') or []):
                _screen_kept_buff(spell)
            if decoded:
                damage_spells.append(decoded)
        by_class[app_name] = damage_spells
    return by_class


def build_spell_names(by_class, spells_by_lang):
    """{fr_name: {lang: localized name}} for every damage spell."""
    out = {}
    for spells in by_class.values():
        for s in spells:
            sid = str(s['id'])
            fr = s['name']
            names = {}
            for lang in LANGS:
                rec = (spells_by_lang.get(lang) or {}).get(sid)
                names[lang] = (rec or {}).get('nameId') or fr
            out[fr] = names
    return out


def emit_module(by_class, spell_names, path):
    lines = [
        "# AUTO-GENERATED by itemscraper/get_spells_touch.py -- do not edit by hand.",
        "# Dofus Touch damage spells per class, decoded from the Touch spell data.",
        "from .dofus_constants import Spell, Effects, EARTH, FIRE, WATER, AIR, NEUTRAL",
        "",
        "TOUCH_DAMAGE_SPELLS = {",
    ]
    for cls, spells in sorted(by_class.items()):
        lines.append("    %s: [" % json.dumps(cls))
        for s in sorted(spells, key=lambda sp: (sp['name'], sp['id'])):
            elems = ", ".join(ELEMENT_TOKEN_TO_CONST[e] for e in s['elements'])
            lines.append("        Spell(%s, %s, Effects(" % (
                json.dumps(s['name'], ensure_ascii=False), s['levels_req']))
            lines.append("            %s," % json.dumps(s['non_crit_ranges']))
            lines.append("            %s," % json.dumps(s['crit_ranges']))
            lines.append("            [%s]," % elems)
            tail = []
            if s.get('aggregates'):
                tail.append("aggregates=%r" % (s['aggregates'],))
            if s.get('stacks'):
                tail.append("stacks=%d" % s['stacks'])
            if s.get('casting'):
                tail.append("casting=%s" % json.dumps(s['casting'], sort_keys=True))
            # The id ties the spell to what the game says about it, in
            # chardata/spell_reference/touch.json.
            if s.get('id') is not None:
                tail.append("spell_id=%d" % s['id'])
            # repr, not json: the row index is an int on the Spell and a
            # json key would be the string "0", which never matches.
            if s.get('delayed'):
                tail.append("delayed=%r" % (dict(sorted(s['delayed'].items())),))
            if s.get('delayed_crit') is not None:
                tail.append("delayed_crit=%r"
                            % (dict(sorted(s['delayed_crit'].items())),))
            lines.append("        )%s)," % (", " + ", ".join(tail) if tail else ""))
        lines.append("    ],")
    lines.append("    'default': [],")
    lines.append("}")
    lines.append("")
    lines.append("TOUCH_SPELL_NAMES = " + json.dumps(spell_names, ensure_ascii=False, indent=1, sort_keys=True))
    Path(path).write_text("\n".join(lines) + "\n", encoding='utf-8')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--module-out',
                   default=str(Path(__file__).resolve().parent.parent
                               / 'fashionistapulp' / 'fashionistapulp'
                               / 'dofus_constants_touch_spells.py'))
    p.add_argument('--skip-images', action='store_true', help='Skip the spell-icon download')
    args = p.parse_args(argv)

    data_url, assets_url = resolve_config()
    print(f"Dofus Touch data proxy: {data_url}")
    breeds = fetch_table(data_url, 'Breeds')
    spell_levels = fetch_table(data_url, 'SpellLevels')
    spells_by_lang = {lang: fetch_table(data_url, 'Spells', lang) for lang in LANGS}
    spells = spells_by_lang['fr']
    print(f"  Breeds={len(breeds)} Spells={len(spells)} SpellLevels={len(spell_levels)}")

    by_class = build(breeds, spells, spell_levels)
    spell_names = build_spell_names(by_class, spells_by_lang)
    emit_module(by_class, spell_names, args.module_out)

    total = sum(len(v) for v in by_class.values())
    print(f"Wrote {total} damage spells across {len(by_class)} classes to {args.module_out}")
    empty = [c for c, v in by_class.items() if not v]
    if empty:
        print("  classes with no damage spells: " + ", ".join(empty))

    if not args.skip_images:
        download_spell_images(by_class, spells, assets_url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
