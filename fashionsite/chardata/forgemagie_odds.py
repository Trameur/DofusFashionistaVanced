# -*- coding: utf-8 -*-
"""Success odds Ankama published for the 1.27 smithmagic rewrite.

The page tells the reader that Ankama never published the success formula.
For the modern game that is still true. For the Retro line it is not: the game
designer Ooopah described the 1.27 system and put a number on six situations
in a dev post of 18 May 2009, and third-party write-ups of the period quote
the same figures.

Two things keep this honest. These are facts about **1.27**, while the Retro
column of this site targets **1.29**, two versions later -- so they are the
best published anchor, not a measurement of the game as it runs now. And the
post gave outcomes, never the formula behind them, so the per-throw rates the
simulator computes stay estimates either way.
"""

#: The six situations the dev post put a number on, easiest first. Each row is
#: critical success / neutral / critical failure, in percent, and they add to
#: 100 -- a row that does not is a transcription error, which a test checks.
DOCUMENTED_ODDS = (
    {'key': 'remount', 'sc': 66, 'n': 34, 'ec': 0},
    {'key': 'perfect', 'sc': 43, 'n': 50, 'ec': 7},
    {'key': 'remount_hard', 'sc': 15, 'n': 50, 'ec': 35},
    {'key': 'create_best', 'sc': 32, 'n': 50, 'ec': 18},
    {'key': 'create_worst', 'sc': 1, 'n': 22, 'ec': 77},
    {'key': 'create_nosink', 'sc': 1, 'n': 0, 'ec': 99},
)

#: Bounds the same post states in prose. The table above never breaks them,
#: and neither should anything the simulator shows for this ruleset.
NEUTRAL_CEILING = 50
CRITICAL_SUCCESS_FLOOR = 1


def get_odds_ladder(ruleset):
    """The same published rows as fractions, ordered easiest to hardest.

    DOCUMENTED_ODDS keeps the order the dev post used, which is the order the
    page lists them in. A curve needs them monotone in difficulty instead, and
    the critical failure rate is what orders them: 0, 7, 18, 35, 77, 99.

    One source, two views. A ladder written out by hand would drift from the
    table above the first time either was corrected.
    """
    return [{'sc': row['sc'] / 100.0,
             'n': row['n'] / 100.0,
             'ec': row['ec'] / 100.0}
            for row in sorted(get_documented_odds(ruleset),
                              key=lambda row: row['ec'])]


def get_documented_odds(ruleset):
    """The published rows for this ruleset, empty when none were published.

    Only the Retro ruleset has a source. Handing the modern page the 1.27
    numbers would be worse than saying nothing, because they would read as
    measurements of a game they never described.
    """
    return DOCUMENTED_ODDS if ruleset == 'retro' else ()
