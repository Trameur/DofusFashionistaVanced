# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Split a Barlow woff2 into a latin file and an ext file, keeping layout features, hinting and names.

Usage: py scripts/make_atelier_font_subsets.py Barlow-Regular.woff2 OUT_DIR
       py scripts/make_atelier_font_subsets.py BarlowSemiCondensed-Bold.woff2 OUT_DIR num
Prints the unicode-range of each file for the @font-face of modern.css. The IM Fell file is never split: its
Reserved Font Name may not stay on a modified file. With num, one file holds the digits and the signs a number
is written with, and only the figure features.
"""
import os
import subprocess
import sys

from fontTools.ttLib import TTFont

LATIN = [(0x0000, 0x00FF), (0x0131, 0x0131), (0x0152, 0x0153), (0x02BB, 0x02BC), (0x02C6, 0x02C6), (0x02DA, 0x02DA),
         (0x02DC, 0x02DC), (0x0304, 0x0304), (0x0308, 0x0308), (0x0329, 0x0329), (0x2000, 0x206F), (0x20AC, 0x20AC),
         (0x2122, 0x2122), (0x2191, 0x2191), (0x2193, 0x2193), (0x2212, 0x2212), (0x2215, 0x2215), (0xFEFF, 0xFEFF),
         (0xFFFD, 0xFFFD)]
NUMBERS = [(0x0020, 0x003F), (0x00A0, 0x00A0), (0x00B1, 0x00B1), (0x00D7, 0x00D7), (0x2212, 0x2212)]


def ranges(codepoints):
    found, start = [], codepoints[0]
    for before, after in zip(codepoints, codepoints[1:] + [None]):
        if after != before + 1:
            found.append((start, before))
            start = after
    return ', '.join('U+%04X' % low if low == high else 'U+%04X-%04X' % (low, high) for low, high in found)


source, out = sys.argv[1], sys.argv[2]
every = sorted(TTFont(source).getBestCmap())
in_latin = [c for c in every if any(low <= c <= high for low, high in LATIN)]
if sys.argv[3:] == ['num']:
    features = 'tnum,lnum,pnum,kern'
    cuts = (('num', [c for c in every if any(low <= c <= high for low, high in NUMBERS)]),)
else:
    features = '*'
    cuts = (('latin', in_latin), ('ext', [c for c in every if c not in in_latin]))
for tag, chosen in cuts:
    target = os.path.join(out, '%s-%s.woff2' % (os.path.basename(source)[:-6], tag))
    subprocess.check_call([sys.executable, '-m', 'fontTools.subset', source, '--unicodes=' + ','.join('%04X' % c for c in chosen),
                           '--layout-features=' + features, '--name-IDs=*', '--name-legacy', '--name-languages=*', '--notdef-glyph',
                           '--notdef-outline', '--recommended-glyphs', '--hinting', '--flavor=woff2', '--output-file=' + target])
    print(os.path.basename(target), os.path.getsize(target), ranges(chosen))
