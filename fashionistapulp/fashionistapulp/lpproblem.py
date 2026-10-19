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

from .fashionista_config import get_fashionista_path
from collections import namedtuple
from pulp import (LpVariable, LpInteger, LpContinuous, LpProblem, LpMaximize, LpMinimize,
                  LpStatusOptimal, LpStatusInfeasible, LpStatusNotSolved, LpStatusUnbounded,
                  LpStatusUndefined, LpSolution, LpSolutionOptimal, value)
import copy
import logging
import pulp
import os
import re
import uuid
import platform

logger = logging.getLogger(__name__)

#: Seconds CBC is given before it hands back the best set it has found. Written
#: once because the solution page quotes it to the reader: a second copy would
#: let the page promise a limit the solver no longer uses.
TIME_LIMIT_SECONDS = 90

# Log platform details to confirm solver detection at import time
logger.debug('System: %s', platform.system())
logger.debug('Machine: %s', platform.machine())

# Initialize solver variable
SOLVER = None

# Handle different platforms
if platform.system() == 'Windows':
    # Windows implementation
    logger.debug('Detected Windows system. Looking for CBC solver...')

    # Check user home directory for .pulp/pulp.cfg which might contain solver path
    pulp_cfg = os.path.join(os.path.expanduser("~"), ".pulp", "pulp.cfg")
    if os.path.exists(pulp_cfg):
        logger.debug('Found PuLP configuration at %s', pulp_cfg)
        # Use the default solver configured in the .pulp/pulp.cfg file
        try:
            SOLVER = pulp.PULP_CBC_CMD(msg=False, timeLimit=TIME_LIMIT_SECONDS)
            logger.debug('Using CBC solver from configuration')
        except Exception as e:
            logger.warning('Error loading solver from config: %s', e)

    # Try to find CBC in the project directory
    if SOLVER is None:
        try:
            cbc_path = os.path.join(get_fashionista_path(), 'solvers', 'cbc', 'bin', 'cbc.exe')
            if os.path.isfile(cbc_path):
                logger.debug('Found CBC at %s', cbc_path)
                SOLVER = pulp.COIN_CMD(path=cbc_path, timeLimit=TIME_LIMIT_SECONDS)
            else:
                logger.debug('CBC not found at %s', cbc_path)
                # Fall back to default solver
                SOLVER = pulp.PULP_CBC_CMD(msg=False, timeLimit=TIME_LIMIT_SECONDS)
                logger.debug('Using default PuLP solver')
        except Exception as e:
            logger.warning('Error setting up solver: %s', e)
            # Last resort - use default solver with no specific configuration
            SOLVER = pulp.PULP_CBC_CMD(msg=False, timeLimit=TIME_LIMIT_SECONDS)
            logger.warning('Using minimal CBC solver')

elif platform.system() == 'Linux' and ('arm' in platform.machine() or 'aarch64' in platform.machine()):
    # On Raspberry Pi (ARM architecture, both 32-bit and 64-bit)
    cbc_path = '/usr/bin/cbc'
    logger.debug('Detected ARM architecture. Using system-installed CBC at: %s', cbc_path)
    if not os.path.isfile(cbc_path):
        raise FileNotFoundError(f"CBC binary not found at {cbc_path}")
    SOLVER = pulp.COIN_CMD(path=cbc_path, timeLimit=TIME_LIMIT_SECONDS)
else:
    # On AWS / other x86_64 Linux. The vendored CBC binary aborts
    # ("terminate called after throwing an instance of 'CoinError'") on some
    # Retro models; PuLP's bundled CBC matches the MPS PuLP writes.
    bundled_solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=TIME_LIMIT_SECONDS)
    if bundled_solver.available():
        SOLVER = bundled_solver
        logger.debug("Detected non-ARM Linux system. Using PuLP's bundled CBC.")
    else:
        cbc_path = os.path.join(get_fashionista_path(), 'fashionistapulp', 'fashionistapulp', 'cbc')
        logger.debug('Detected non-ARM Linux system. Using project-specific CBC at: %s', cbc_path)
        if not os.path.isfile(cbc_path):
            raise FileNotFoundError(f"CBC binary not found at {cbc_path}")
        SOLVER = pulp.COIN_CMD(path=cbc_path, timeLimit=TIME_LIMIT_SECONDS)

CBC_SETTING_NAME = 'FASHIONISTA_CBC'


def solver_from_setting(setting, time_limit=TIME_LIMIT_SECONDS):
    """The solver the FASHIONISTA_CBC value names, None when it is empty."""
    setting = (setting or '').strip()
    if not setting:
        return None
    if setting == 'cbcbox':
        if int(pulp.__version__.split('.')[0]) < 4:
            raise RuntimeError('%s=cbcbox needs PuLP 4 or later, PuLP %s cannot drive that binary'
                               % (CBC_SETTING_NAME, pulp.__version__))
        import cbcbox
        return pulp.COIN_CMD(path=cbcbox.cbc_bin_path(), msg=False, timeLimit=time_limit)
    if not os.path.isfile(setting):
        raise FileNotFoundError('%s names no cbc binary: %s' % (CBC_SETTING_NAME, setting))
    return pulp.COIN_CMD(path=setting, msg=False, timeLimit=time_limit)


SOLVER_TAG = (os.environ.get(CBC_SETTING_NAME) or '').strip()
_SOLVER_FROM_SETTING = solver_from_setting(SOLVER_TAG)
if _SOLVER_FROM_SETTING is not None:
    SOLVER = _SOLVER_FROM_SETTING

# Confirm which solver is being used
if hasattr(SOLVER, 'path'):
    logger.debug('Using CBC solver at: %s', SOLVER.path)
else:
    logger.debug('Using default PuLP solver configuration')

_PARTIAL_SEARCH = re.compile(r'best objective (\S+) \(best possible (\S+)\)')
_SUMMARY_OBJECTIVE = re.compile(r'^Objective value:\s+(\S+)', re.M)
_SUMMARY_BOUND = re.compile(r'^(?:Upper|Lower) bound:\s+(\S+)', re.M)
_START_TAKEN = re.compile(r'MIPStart provided solution with cost')
_GAP_EXIT = re.compile(r'Exiting as integer gap of (\S+)')


def read_best_bound(log_text, objective):
    """The best bound a CBC log gives for a maximised objective that stopped at objective, or None."""
    pairs = _PARTIAL_SEARCH.findall(log_text)[-1:]
    summary_objective = _SUMMARY_OBJECTIVE.search(log_text)
    summary_bound = _SUMMARY_BOUND.search(log_text)
    if summary_objective and summary_bound:
        pairs.append((summary_objective.group(1), summary_bound.group(1)))
    for printed_objective, printed_bound in pairs:
        try:
            printed_objective, bound = float(printed_objective), float(printed_bound)
        except ValueError:
            continue
        if abs(printed_objective + objective) < abs(printed_objective - objective):
            bound = -bound
        if bound >= objective - 1e-6 * max(1.0, abs(objective)):
            return max(bound, objective)
    for printed_gap in _GAP_EXIT.findall(log_text)[-1:]:
        try:
            return objective + abs(float(printed_gap))
        except ValueError:
            continue
    return None


def _solver_for_run(warm_start, seed=None, gap=0):
    """A copy of SOLVER writing CBC's log to a file of its own, reading a start, seeding and stopping within a relative gap if asked."""
    solver = copy.copy(SOLVER)
    solver.msg = False
    if seed is not None:
        solver.options = list(SOLVER.options) + ['randomSeed %d' % seed,
                                                 'randomCbcSeed %d' % seed]
    if warm_start and platform.system() == 'Windows':
        drive, path = os.path.splitdrive(solver.tmpDir)
        # CBC 2.10 opens "mips C:\..." under its own directory, but reads a path from the drive root
        if drive and drive.lower() == os.path.splitdrive(os.getcwd())[0].lower():
            solver.tmpDir = path
    solver.optionsDict = dict(SOLVER.optionsDict, warmStart=bool(warm_start),
                              logPath=os.path.join(solver.tmpDir,
                                                   'cbc-%s.log' % uuid.uuid4().hex))
    if gap:
        solver.optionsDict['gapRel'] = gap
    return solver


def _read_and_remove(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as log_file:
            return log_file.read()
    except OSError:
        return ''
    finally:
        try:
            os.remove(path)
        except OSError:
            logger.debug('could not remove file %s', path)


def solver_tag():
    """What the cache keys add for the chosen CBC binary, empty for today's."""
    return SOLVER_TAG


SolveOutcome = namedtuple('SolveOutcome', 'status finished')

_SITE_STATUS = {LpStatusOptimal: 'Optimal',
                LpStatusInfeasible: 'Infeasible',
                LpStatusNotSolved: 'Not Solved',
                LpStatusUnbounded: 'Unbounded',
                LpStatusUndefined: 'Undefined'}


def read_outcome(status, sol_status):
    """The status string the site compares and whether the solver ended the search itself.

    CBC stopped on its time limit with a set in hand reads as Optimal with a
    sol_status of Integer feasible, so only the pair says the search finished.
    A stop within a relative gap reads as a finished search too: the caller
    knows the gap it gave, see LpProblem2.solution_is_proven.
    """
    return SolveOutcome(_SITE_STATUS.get(status, 'Undefined'),
                        status == LpStatusOptimal and sol_status == LpSolutionOptimal)


def _sum_or_zero(terms):
    return pulp.lpSum(terms) if terms else 0


class RowHandle:
    """A row the site owns: terms as (coefficient, variable name), a sense and a right-hand side.

    The row table of LpProblem2 holds the same object, so a change made here is
    the change the next solve sees. Reading and writing go by name; no solver
    object is kept outside the problem.
    """

    __slots__ = ('_problem', 'name', 'terms', 'sense', 'rhs', 'auto', '_constraint')

    def __init__(self, problem, name, terms, sense, rhs, auto):
        self._problem = problem
        self.name = name
        self.terms = terms
        self.sense = sense
        self.rhs = rhs
        self.auto = auto
        self._constraint = None

    @property
    def constant(self):
        """The row written as terms + constant (sense) 0, so the right-hand side negated."""
        return -self.rhs

    def changeRHS(self, value):
        """Sets the right-hand side; nothing happens when it already is value."""
        if value == self.rhs:
            return
        self.rhs = value
        self._problem._row_changed(self)

    def __repr__(self):
        return 'RowHandle(%r, %s %r)' % (self.name, self.sense, self.rhs)


_SENSES = ('<=', '>=', '==')


class LpProblem2:
    """The model the solver is given: variables by name, rows as handles, and one objective.

    The rows and the objective are data held here. The solver library's problem
    is built from them, with columns only for the variables a row or the
    objective names, and is brought up to date on first use after a change: a
    row added is appended, a right-hand side changed is written through, and
    any other change (a row removed or moved) builds the problem again from the
    table.
    """

    WRITE_THROUGH = True

    def __init__(self):
        self.objective_value = None
        self.best_bound = None
        self.start_objective = None
        self.start_accepted = None
        self.gap = 0
        self._lp = LpProblem("The Whiskas Problem", LpMaximize)
        self._specs = {}
        self._built = {}
        self._built_specs = {}
        self._rows = {}
        self._live = []
        self._removed = {}
        self._last_unused = 0
        self._rows_changed = False
        self._force_rebuild = False
        self._objective_terms = ()
        self._objective_changed = False

    @property
    def pulp_lp(self):
        """The library's problem, up to date with the rows and the objective."""
        self._sync()
        return self._lp

    def new_variable(self, name, min_bound, max_bound, integer=True):
        """A column of the library's problem, the one place its variable is built."""
        return LpVariable(name, min_bound, max_bound, LpInteger if integer else LpContinuous)

    def declare_variable(self, name, min_bound, max_bound, integer=True):
        """Registers a column by name; it is built when a row or the objective first names it."""
        spec = (min_bound, max_bound, bool(integer))
        if self._built_specs.get(name, spec) != spec:
            self._force_rebuild = True
        self._specs[name] = spec

    def forget_variables(self, names):
        """Takes columns out of the registry; the rows that name them must go too."""
        for name in names:
            self._specs.pop(name, None)

    def has_variable(self, name):
        return name in self._specs

    def variable_names(self):
        return list(self._specs)

    def variable_spec(self, name):
        """(lowest, highest, integer) of a registered column, KeyError when none is."""
        return self._specs[name]

    def column_names(self):
        """The columns the solver is given: those a row or the objective names."""
        return [column.name for column in self.pulp_lp.variables()]

    def variable(self, name):
        """The column of the current library problem named name, KeyError when none is registered."""
        self._sync()
        return self._column(name)

    def value(self, name):
        """The value the last solve gave the column, None when it has none."""
        column = self._built.get(name)
        return None if column is None else column.varValue

    def _column(self, name):
        column = self._built.get(name)
        if column is None:
            spec = self._specs[name]
            column = self._built[name] = self.new_variable(name, spec[0], spec[1], spec[2])
            self._built_specs[name] = spec
        return column

    def _expression(self, terms):
        return _sum_or_zero([coefficient * self._column(name) for coefficient, name in terms])

    def _sync(self):
        if self._rows_changed or self._force_rebuild:
            table = list(self._rows.values())
            live = self._live
            if (self._force_rebuild or len(live) > len(table)
                    or any(held is not wanted for held, wanted in zip(live, table))):
                self._rebuild()
            else:
                for row in table[len(live):]:
                    self._attach(row)
            self._rows_changed = False
            self._removed.clear()
        if self._objective_changed:
            self._apply_objective()

    def _rebuild(self):
        if self._force_rebuild:
            for row in self._live:
                row._constraint = None
            self._built = {}
            self._built_specs = {}
        else:
            kept = {id(row) for row in self._rows.values()}
            for row in self._live:
                if id(row) not in kept:
                    row._constraint = None
        self._lp = LpProblem(self._lp.name, LpMaximize)
        self._live = []
        self._force_rebuild = False
        for row in self._rows.values():
            if row._constraint is None:
                self._attach(row)
            else:
                self._lp.addConstraint(row._constraint, row.name)
                self._live.append(row)
        self._objective_changed = True

    def _attach(self, row):
        expression = self._expression(row.terms)
        if row.sense == '<=':
            constraint = expression <= row.rhs
        elif row.sense == '>=':
            constraint = expression >= row.rhs
        else:
            constraint = expression == row.rhs
        self._lp.addConstraint(constraint, row.name)
        row._constraint = constraint
        self._live.append(row)

    def _apply_objective(self):
        self._lp.objective = self._expression(self._objective_terms)
        self._objective_changed = False

    def _row_changed(self, row):
        if self.WRITE_THROUGH and row._constraint is not None:
            row._constraint.changeRHS(row.rhs)

    def _unused_row_name(self):
        self._last_unused += 1
        while '_C%d' % self._last_unused in self._rows:
            self._last_unused += 1
        return '_C%d' % self._last_unused

    def add_row(self, terms, sense, rhs, name=None):
        """Adds terms (sense) rhs as a row and returns its handle.

        terms is [(coefficient, variable name)]. A row name is unique, and a row
        given none is named _C1, _C2 and so on, as the library names them. A row
        with no terms needs no column and is held by its handle alone; one that
        cannot hold is refused.
        """
        if sense not in _SENSES:
            raise ValueError('a row is <=, >= or ==, not %r' % (sense,))
        terms = tuple((coefficient, variable) for coefficient, variable in terms)
        for _coefficient, variable in terms:
            if variable not in self._specs:
                raise KeyError(variable)
        if not terms:
            holds = {'<=': 0 <= rhs, '>=': 0 >= rhs, '==': 0 == rhs}[sense]
            if not holds:
                raise TypeError('A False object cannot be passed as a constraint')
            return RowHandle(self, name, terms, sense, rhs, name is None)
        if name is not None and name in self._rows:
            raise ValueError('overlapping constraint names: %s' % name)
        removed = self._removed.pop(name, None)
        if (removed is not None and removed.terms == terms and removed.sense == sense
                and removed.rhs == rhs):
            self._rows[name] = removed
            self._rows_changed = True
            return removed
        auto = name is None
        if auto:
            name = self._unused_row_name()
        row = RowHandle(self, name, terms, sense, rhs, auto)
        self._rows[name] = row
        self._rows_changed = True
        return row

    def row(self, name):
        return self._rows.get(name)

    def row_names(self):
        return list(self._rows)

    def rows(self):
        return list(self._rows.values())

    def objective_terms(self):
        return list(self._objective_terms)

    def remove_rows(self, names):
        """Takes the rows named out of the table; added again they sit after the others."""
        for name in names:
            row = self._rows.pop(name, None)
            if row is not None:
                self._removed[name] = row
                self._rows_changed = True

    def set_objective(self, terms):
        """The objective to maximise, [(coefficient, variable name)]."""
        self._objective_terms = tuple((coefficient, variable) for coefficient, variable in terms)
        self._objective_changed = True

    def run(self, warm_start=None, seed=None, gap=0):
        """Solve; warm_start is {variable name: value} of a set to start from, zero elsewhere, seed a positive int for another search path, and gap the relative distance from the best bound CBC may stop at."""
        problem_name = '/tmp/problem_%s' % str(uuid.uuid4())
        lp = self.pulp_lp
        lp.name = problem_name
        self.gap = gap or 0
        solver = _solver_for_run(warm_start is not None, seed, self.gap)
        objective = lp.objective
        self.objective_value = self.best_bound = self.start_objective = None
        self.start_accepted = None
        if warm_start is not None:
            for variable in lp.variables():
                variable.varValue = warm_start.get(variable.name, 0)
            self.start_objective = value(objective)
            # CBC 2.10 prices a mipstart in the wrong sign under "max"
            lp.sense = LpMinimize
            lp.objective = -objective
        try:
            lp.solve(solver)
        finally:
            if warm_start is not None:
                lp.sense = LpMaximize
                lp.objective = objective
            log_text = _read_and_remove(solver.optionsDict['logPath'])
        if warm_start is not None:
            self.start_accepted = bool(_START_TAKEN.search(log_text))
        if self.get_status() == 'Optimal':
            self.objective_value = value(objective)
            if not self.solution_is_proven() and self.objective_value is not None:
                self.best_bound = read_best_bound(log_text, self.objective_value)
        logger.debug('Status: %s, Z = %s', self.get_status(), self.objective_value)

        tmpMps = os.path.join('%s-pulp.mps' % problem_name)
        tmpSol = os.path.join('%s-pulp.sol' % problem_name)
        try: os.remove(tmpMps)
        except: logger.debug('could not remove file %s', tmpMps)
        try: os.remove(tmpSol)
        except: logger.debug('could not remove file %s', tmpSol)

    def get_result(self):
        return {v.name: v.varValue for v in self._lp.variables()}

    def setup_variable(self, category, id, min_bound, max_bound):
        sanitized_id = str(id).replace(' ', '_').replace('-', '_')
        self.declare_variable('%s_%s' % (category, sanitized_id), min_bound, max_bound)

    def init_objective_function(self):
        self.obj_vars = {}

    def add_to_of(self, category, id, weight):
        sanitized_id = str(id).replace(' ', '_').replace('-', '_')
        var_name = '%s_%s' % (category, sanitized_id)
        if self.obj_vars.get(var_name) == None:
            self.obj_vars[var_name] = weight
        else:
            self.obj_vars[var_name] += weight

    def finish_objective_function(self):
        self.set_objective([(value, key) for key, value in self.obj_vars.items()
                            if key in self._specs])

    @staticmethod
    def _parcel_terms(parcels):
        return [(parcel[0], '%s_%s' % (parcel[1], str(parcel[2]).replace(' ', '_').replace('-', '_')))
                for parcel in parcels]

    def restriction_lt_eq(self, max_bound, parcels):
        return self.add_row(self._parcel_terms(parcels), '<=', max_bound)

    def restriction_eq(self, max_bound, parcels):
        return self.add_row(self._parcel_terms(parcels), '==', max_bound)

    def _outcome(self):
        return read_outcome(self._lp.status, self._lp.sol_status)

    def get_status(self):
        return self._outcome().status

    def get_solution_status(self):
        """Did the solver PROVE this is the best set, or only find it?

        `get_status` cannot answer that, and reading it as if it could is the
        trap: PuLP maps a CBC run stopped by its own time limit back onto
        LpStatusOptimal. In pulp/apis/coin_api.py, when CBC writes
        "Stopped on time - objective value X", get_status turns
        LpStatusNotSolved into LpStatusOptimal and files the truth in
        `sol_status` instead. So `get_status() == 'Optimal'` is true both for a
        closed gap and for the best set found before the clock ran out.

        This returns the field that keeps them apart: "Optimal Solution Found"
        when CBC closed the gap, "Solution Found" when it timed out holding an
        incumbent. Every solver here runs with TIME_LIMIT_SECONDS, so the second case
        is reachable on a hard search.
        """
        return LpSolution[self._lp.sol_status]

    def solution_is_proven(self):
        """True only when the solver closed the gap, never after a run given a gap. See get_solution_status."""
        return self.search_finished() and not getattr(self, 'gap', 0)

    def search_finished(self):
        """True when CBC ended the search itself, on a proof or within the gap it was given, not on its time limit.

        CBC writes "Optimal" in its solution file when it stops within a
        relative gap, so PuLP sets sol_status to LpSolutionOptimal for that
        stop as for a proof.
        """
        return self._outcome().finished

    def get_search_state(self):
        """The last run's objective, best bound (None once proven or unread), start objective, whether CBC took the start, and non-zero values."""
        return {'objective': self.objective_value,
                'bound': self.best_bound,
                'start_objective': self.start_objective,
                'start_accepted': self.start_accepted,
                'values': {name: number for name, number in self.get_result().items()
                           if number}}
