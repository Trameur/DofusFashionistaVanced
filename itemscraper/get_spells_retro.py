#!/usr/bin/env python3
"""
Extract Dofus Retro (1.29) damage spells per class, for dofus_constants'
DAMAGE_SPELLS, from the lang files download_retro_langs.py writes.

    python get_spells_retro.py [--raw-dir retro_raw] [--module-out PATH]

A spell "level" array ends with two effect lists; each entry is
[dice, ..., effect_id], with the item effect ids for elemental damage.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Retro effect id -> element token. 96-100 elemental damage, 91-95 elemental
# steals (same hit, heals the caster).
DAMAGE_EFFECTS = {96: 'water', 97: 'earth', 98: 'air', 99: 'fire', 100: 'neutral',
                  91: 'water', 92: 'earth', 93: 'air', 94: 'fire', 95: 'neutral'}

# THE ONE DAMAGE FAMILY THIS FILE STILL CANNOT READ, screened 2026-08-31 over
# the 252 class spells against Ankama's own effects_fr.json: 88 and 89,
# "Dommages : #1 a #2% de la vie de l'attaquant" (fire and neutral), and 672,
# which carries the neutral wording a second time. Seven class spells use them.
#
# Three are absent from the generated table for want of any other row: the
# Eniripsa's "Mot Drainant" (123) and "Mot Stimulant" (126), and the Sacrieur's
# "Punition" (446). Four are in it and lose only this row, so their damage is
# understated: "Roue de la Fortune" (106), "Contrecoup" (111), "Mutilation"
# (149) and "Furie" (447).
#
# Not an oversight and not a one-line fix: a row here is a fixed range baked in
# per level, while these deal a share of the CASTER's health, which is a
# property of the build and not of the spell. Carrying them means a new kind of
# row that reaches the damage computation with the character's Vitality, and
# then a first-hand answer on whether Power and Damage apply to it. Every other
# unread id is a heal, a summon, a trap, a glyph, a state or a displacement.


# Characteristic effects, read since 2026-08-27.
#
# This file used to read only the ten ids above, so the class self-buffs of
# 1.29 were dropped and the table held zero buff rows. That reads as "Retro has
# no such spells" and was really "this file never asked": the Iop's own
# "Puissance" and "Vitalite", the Ecaflip's "Roulette", the Enutrof's "Chance"
# were all absent.
#
# NOTHING HERE IS COPIED FROM THE MODERN TABLE. 1.29 numbers its effects its own
# way, and 138 is the proof: Dofus 3 reads it "X Puissance" while 1.29 reads it
# "Augmente les dommages de #1 a #2%". Each id below was taken from Ankama's own
# effects_fr.json in retro_raw, with the label it carries there:
#     118  "+#1 a #2 en force"                    -> buff_str
#     119  "+#1 a #2 en agilite"                  -> buff_agi
#     123  "+#1 a #2 a la chance"                 -> buff_cha
#     126  "+#1 a #2 en intelligence"             -> buff_int
#     125  "+#1 a #2 en vitalite"                 -> buff_vit
#     138  "Augmente les dommages de #1 a #2%"    -> buff_pow
#
# 138 maps to buff_pow because the stat the Fashionista calls Power IS that
# effect on Retro; the site has shown it under Ankama's own wording, "% de
# dommages", since bb3dbcd11. Same internal stat, different label per version.
#
# LEFT OUT ON PURPOSE: 112 "+X de dommages" (flat Damage), 111 "+X PA", 128
# "+X PM", 117 "+X a la portee", 115 "+X aux coups critiques", 178 "+X de
# soins". 23 further class spells carry only those, among them the Cra's
# "Maitrise de l'Arc" and the Ecaflip's "Odorat".
#
# NOT for want of a key: `dam`, `ap` and `mp` are all three in the 64-stat
# structure of every version, Retro included, so 'buff_dam' would reach the
# turn the way 'buff_str' does. Measured 2026-08-31 with get_structure.
#
# The reason is that no version credits a self-buff of that kind, so adding
# one here would make Retro the only version that does. Counted the same day
# over the four generated tables: zero buff_dam, zero buff_ap, zero buff_mp.
# What they do carry is buff_pow, buff_str, buff_int, buff_cha, buff_agi,
# buff_vit, buff_wis, buff_pshdam, buff_final and buff_finalheals.
#
# So it stays a question for the four versions at once, not a Retro detail:
# whether a spell may hand a build AP, MP and flat Damage it does not wear.
CHARACTERISTIC_EFFECTS = {118: 'buff_str', 119: 'buff_agi', 123: 'buff_cha',
                          126: 'buff_int', 125: 'buff_vit', 138: 'buff_pow'}
ROW_EFFECTS = dict(DAMAGE_EFFECTS)
ROW_EFFECTS.update(CHARACTERISTIC_EFFECTS)

# Two class spells carry characteristic effects the caster does not reliably
# get, and this scraper has no target test at all.
#
# The 1.29 target field (slot 5 of a level) IS a run of two-character codes,
# one per effect line, and the codes align exactly: 56 buff lines, 56 codes, no
# leftovers. But the codes do NOT settle the question. "Resistance Naturelle",
# whose own sentence says it raises the vitality OF SUMMONS, wears the same
# `Pa` as "Chance", which raises the caster's own. Reading the field would have
# looked principled and let both through.
#
# So the exclusion is named, with the sentence Ankama writes, and the generator
# refuses to run if that sentence goes away rather than silently going back to
# crediting the player. Measured 2026-08-27 on the 252 class spells (21 per
# class): 15 carry a buff, 13 of them legitimately.
#
# Neither spell existed in the shipped table before 19b29e9bf, which is the
# commit that added Retro buffs: excluding them restores what the pages had,
# it does not take anything away from a reader.
NOT_A_SELF_BUFF = {
    # Ecaflip, Roulette: ONE random effect among many, on random targets. The
    # data lists the alternatives as four separate lines, so reading them as
    # granted together handed the caster +400 Strength, Chance, Intelligence
    # AND Agility at once, +500 on a critical, at every rank.
    101: 'sur vos adversaires',
    # Osamodas, Resistance Naturelle: the sentence names summons and allies,
    # and never the caster. (Osamodas, not Sadida: checked in
    # chardata/spell_reference/retro.json, whose `name` is a dict of languages.)
    32: 'des invocations',
    # Osamodas, Crocs du Mulou: same sentence as above, and the same spell was
    # already excluded on Touch for the same reason under id 9919.
    29: 'des invocations',
}

# A buff whose sentence names somebody other than the caster and which is NOT
# in the table above has to be settled here, with the words that settle it.
#
# This exists because a hand-written exclusion list goes stale in silence:
# Ankama adds spells, nobody re-derives the list, and the new one is credited
# to the player without a word. So the generator screens every buff it is about
# to keep and stops on anything unaccounted for.
SOMEBODY_ELSE = ('invocation', 'alli', 'adversaire', 'ennemi',
                 'autres personnages')

BUFFS_THE_CASTER_TOO = {
    # Enutrof, Cupidite. "tous les joueurs" is every player, the caster
    # included, so he does receive it -- and refusing a buff the game says he
    # gets would be the opposite error, erasing a real mechanic. Note this is
    # NOT the same call as Touch's spell 52, whose own sentence there reads
    # "la puissance de tous les allies" and names no player: different words,
    # different version, different answer.
    52: 'tous les joueurs',
    # Iop, Puissance. Names the caster first, the ally second.
    153: 'le lanceur ou un alli',
}


def _not_a_self_buff(spell, spell_id):
    """True when this spell's buff rows are not the caster's.

    Checks that Ankama still writes the sentence the exclusion rests on. A
    hand-written list that stops being read is worse than no list: it keeps
    excluding a spell whose meaning has changed, and says nothing about it.
    """
    quote = NOT_A_SELF_BUFF.get(spell_id)
    if quote is None:
        return False
    text = str(spell.get('d') or '')
    if quote.lower() not in text.lower():
        raise SystemExit(
            'retro spell %s no longer says %r; re-read its description before '
            'trusting this exclusion' % (spell_id, quote))
    return True


def _screen_kept_buff(spell, spell_id):
    """Stop the build if a KEPT buff's sentence names somebody else.

    Runs on what the generator is about to write, not on a list someone
    maintains, so a spell Ankama adds tomorrow cannot be credited to the player
    in silence: the run fails and names the spell and the words that flagged it.
    """
    text = str(spell.get('d') or '')
    lowered = text.lower()
    named = [word for word in SOMEBODY_ELSE if word in lowered]
    if not named:
        return
    quote = BUFFS_THE_CASTER_TOO.get(spell_id)
    if quote is None:
        raise SystemExit(
            'retro spell %s (%s) keeps a characteristic buff and its own '
            'description names %s. Settle it in NOT_A_SELF_BUFF or in '
            'BUFFS_THE_CASTER_TOO before regenerating. Ankama wrote: %r'
            % (spell_id, spell.get('n'), '/'.join(named), text[:160]))
    if quote.lower() not in lowered:
        raise SystemExit(
            'retro spell %s no longer says %r; re-read it before trusting that '
            'the caster is among those it buffs' % (spell_id, quote))

# Standard Dofus class id -> Fashionista class name (Retro = the original 12).
CLASS_ID_TO_NAME = {
    1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor', 6: 'Ecaflip',
    7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida', 11: 'Sacrier', 12: 'Pandawa',
}

LEVELS = ('l1', 'l2', 'l3', 'l4', 'l5', 'l6')


def dice_range(d):
    """'1d5+1' -> (2, 6); '0d0+8' -> (8, 8); None for unparseable."""
    m = re.match(r'(\d+)d(\d+)([+-]\d+)?', d or '')
    if not m:
        return None
    x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if y == 0:
        return (z, z)
    return (x + z, x * y + z)


def _collect(effect_list):
    """One effect list -> {row token: (min, max)}.

    Rows are the elemental damage hits plus the characteristic buffs; the token
    is an element name for the first and a 'buff_<stat>' pseudo-element for the
    second. A level can carry several lines of one token (conditional branches,
    damage/steal pairs); the strongest by midpoint wins."""
    out = {}
    for e in (effect_list or []):
        if isinstance(e, list) and len(e) >= 2 and e[-1] in ROW_EFFECTS:
            rng = dice_range(e[0])
            if rng:
                elem = ROW_EFFECTS[e[-1]]
                prev = out.get(elem)
                if prev is None or rng[0] + rng[1] > prev[0] + prev[1]:
                    out[elem] = rng
    return out


def decode_level(level_arr):
    """Spell level array -> {element: (normal_range, crit_range)}.

    The two effect lists are the normal and the critical effects, in no fixed
    order; the crit is the higher roll.
    """
    if not isinstance(level_arr, list) or len(level_arr) < 2:
        return {}
    a, b = _collect(level_arr[-2]), _collect(level_arr[-1])
    result = {}
    # The five elements first, in their historical order, then whatever buff
    # rows the level carries, sorted so the generated module is stable.
    tokens = list(('water', 'earth', 'air', 'fire', 'neutral'))
    tokens += sorted((set(a) | set(b)) - set(tokens))
    for elem in tokens:
        ra, rb = a.get(elem), b.get(elem)
        if not ra and not rb:
            continue
        if ra and rb:
            normal, crit = (rb, ra) if ra[1] >= rb[1] else (ra, rb)
        else:
            normal = crit = (ra or rb)
        result[elem] = (normal, crit)
    return result


# Slots of the 21-wide level array carrying what a cast costs and how often the
# game allows it.
# Slot 15 is the critical hit rate as the X of 1/X, 0 when the spell cannot
# crit: it is the only slot that improves with the rank (151 spells of the 156
# that move it get a smaller X at a higher rank), while slot 14, the critical
# failure, sits at 100 for most spells and barely moves.
CASTING_SLOTS = {'cooldown': 6, 'per_turn': 7, 'per_target': 8, 'ap': 18,
                 'crit': 15}


def decode_casting(level_arr):
    """The cast cost and limits of one spell level."""
    out = {}
    if not isinstance(level_arr, list):
        return out
    for key, index in CASTING_SLOTS.items():
        if index < len(level_arr):
            value = level_arr[index]
            if isinstance(value, int) and not isinstance(value, bool):
                out[key] = value
    return out


def decode_spell(spell, spell_id=None):
    """Retro spell record -> damage-spell dict, or None if it carries no row.

    A spell that only buffs a characteristic and deals no damage is kept: the
    Dofus 2, 3 and Touch tables keep theirs, and a build optimizer needs the
    Iop's "Puissance" even though it hits nobody."""
    drop_buffs = _not_a_self_buff(spell, spell_id)
    per_level = []
    elements = []
    casting_levels = []
    for lv in LEVELS:
        if lv not in spell:
            continue
        decoded = decode_level(spell[lv])
        if drop_buffs:
            decoded = {token: value for token, value in decoded.items()
                       if not token.startswith('buff_')}
        per_level.append(decoded)
        casting_levels.append(decode_casting(spell[lv]))
        for elem in decoded:
            if elem not in elements:
                elements.append(elem)
    if not elements or not per_level:
        return None
    non_crit_ranges, crit_ranges = [], []
    for elem in elements:
        nc, cr = [], []
        for decoded in per_level:
            normal, crit = decoded.get(elem, (None, None))
            nc.append('%d-%d' % normal if normal else '0-0')
            cr.append('%d-%d' % crit if crit else '0-0')
        non_crit_ranges.append(nc)
        crit_ranges.append(cr)
    # An absent limit reads 0 at every level, which would pass for a real one.
    casting = {}
    for key in CASTING_SLOTS:
        values = [level.get(key, 0) for level in casting_levels]
        if any(values):
            casting[key] = values
    return {
        'name': spell.get('n') or '',
        'level_count': len(per_level),
        'elements': elements,
        'non_crit_ranges': non_crit_ranges,
        'crit_ranges': crit_ranges,
        'casting': casting or None,
    }


# Element token -> dofus_constants constant name (NEUTRAL == 'neut', not 'neutral').
ELEMENT_TOKEN_TO_CONST = {
    'earth': 'EARTH', 'fire': 'FIRE', 'water': 'WATER', 'air': 'AIR',
    'neutral': 'NEUTRAL',
}
# Buff rows are written as plain quoted strings, the way the Dofus 2, 3
# and Touch tables write them, not as element constants.
ELEMENT_TOKEN_TO_CONST.update(
    {token: repr(token) for token in CHARACTERISTIC_EFFECTS.values()})


def _level_req(n):
    """Character level per spell rank: rank 6 needs level 100, ranks 1-5 are
    reachable at level 1 (Retro gates ranks by spell points, not level)."""
    if n <= 1:
        return [100]
    return [1] * (n - 1) + [100]


def emit_module(by_class, spell_names, path):
    """Write a Python module defining RETRO_DAMAGE_SPELLS (Spell/Effects objects)
    and RETRO_SPELL_NAMES ({french_name: {lang: localized_name}})."""
    lines = [
        "# AUTO-GENERATED by itemscraper/get_spells_retro.py -- do not edit by hand.",
        "# Dofus Retro (1.29) damage spells per class, decoded from the spell lang.",
        "from .dofus_constants import Spell, Effects, EARTH, FIRE, WATER, AIR, NEUTRAL",
        "",
        "RETRO_DAMAGE_SPELLS = {",
    ]
    for cls, spells in sorted(by_class.items()):
        lines.append("    %s: [" % json.dumps(cls))
        for s in sorted(spells, key=lambda sp: (sp['name'], sp['level_count'])):
            elems = ", ".join(ELEMENT_TOKEN_TO_CONST[e] for e in s['elements'])
            lines.append("        Spell(%s, %s, Effects(" % (
                json.dumps(s['name'], ensure_ascii=False),
                _level_req(s['level_count'])))
            lines.append("            %s," % json.dumps(s['non_crit_ranges']))
            lines.append("            %s," % json.dumps(s['crit_ranges']))
            lines.append("            [%s]," % elems)
            # The id ties the spell to what the game says about it, in
            # chardata/spell_reference/retro.json.
            tail = []
            if s.get('casting'):
                tail.append("casting=%s" % json.dumps(s['casting'],
                                                      sort_keys=True))
            if s.get('id') is not None:
                tail.append("spell_id=%d" % s['id'])
            lines.append("        )%s)," % (', ' + ', '.join(tail) if tail
                                            else ''))
        lines.append("    ],")
    lines.append("    'default': [],")
    lines.append("}")
    lines.append("")
    lines.append("RETRO_SPELL_NAMES = " + json.dumps(spell_names, ensure_ascii=False, indent=1, sort_keys=True))
    Path(path).write_text("\n".join(lines) + "\n", encoding='utf-8')


def build(spells_root, classes_root):
    by_class = {}
    missing_classes = []
    for cid, app_name in CLASS_ID_TO_NAME.items():
        cdata = classes_root.get(str(cid))
        if not isinstance(cdata, dict) or not cdata.get('s'):
            missing_classes.append(app_name)
            continue
        damage_spells = []
        for spell_id in cdata['s']:
            spell = spells_root.get(str(spell_id))
            if not isinstance(spell, dict):
                continue
            decoded = decode_spell(spell, spell_id)
            if decoded and any(str(token).startswith('buff_')
                               for token in decoded.get('elements') or []):
                _screen_kept_buff(spell, spell_id)
            if decoded:
                decoded['id'] = spell_id
                damage_spells.append(decoded)
        by_class[app_name] = damage_spells
    return by_class, missing_classes


def build_spell_names(by_class, names_by_lang):
    """{french_name: {lang: localized_name}}; Spell.name carries the French name."""
    out = {}
    for spells in by_class.values():
        for s in spells:
            sid, fr = str(s.get('id')), s['name']
            names = {'fr': fr}
            for lang, id_to_name in names_by_lang.items():
                names[lang] = id_to_name.get(sid) or fr
            out[fr] = names
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    _here = Path(__file__).resolve().parent  # itemscraper/
    _root = _here.parent                     # repo root
    p.add_argument('--raw-dir', default=str(_here / 'retro_raw'))
    p.add_argument('--out', default=str(_here / 'retro' / 'retro_damage_spells.json'))
    p.add_argument('--module-out',
                   default=str(_root / 'fashionistapulp' / 'fashionistapulp'
                               / 'dofus_constants_retro_spells.py'),
                   help='Path for the generated RETRO_DAMAGE_SPELLS Python module')
    p.add_argument('--lang', default='fr')
    args = p.parse_args(argv)

    raw = Path(args.raw_dir)
    spells_root = json.loads((raw / f'spells_{args.lang}.json').read_text(encoding='utf-8'))['S']
    classes_root = json.loads((raw / f'classes_{args.lang}.json').read_text(encoding='utf-8'))['G']

    by_class, missing = build(spells_root, classes_root)

    # Every language is required: retro_raw is not committed, so run
    # download_retro_langs.py for the missing ones first.
    names_by_lang = {}
    for lang in ('en', 'es', 'pt', 'de'):
        path = raw / f'spells_{lang}.json'
        if not path.exists():
            sys.exit('missing %s: download the spell langs for every '
                     'language before regenerating the module' % path)
        lang_spells = json.loads(path.read_text(encoding='utf-8'))['S']
        names_by_lang[lang] = {k: v.get('n') for k, v in lang_spells.items()
                               if isinstance(v, dict) and v.get('n')}
    spell_names = build_spell_names(by_class, names_by_lang)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(by_class, ensure_ascii=False, indent=1), encoding='utf-8')

    if args.module_out:
        emit_module(by_class, spell_names, args.module_out)

    total = sum(len(v) for v in by_class.values())
    print(f"Wrote {total} damage spells across {len(by_class)} classes to {out_path}")
    if args.module_out:
        print(f"Wrote RETRO_DAMAGE_SPELLS module to {args.module_out}")
    if missing:
        print(f"  classes with no spell data in lang: {', '.join(missing)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
