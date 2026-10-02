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
from pulp import (LpVariable, LpInteger, LpProblem, LpMaximize, LpMinimize, LpStatus,
                  LpStatusOptimal, LpSolution, LpSolutionOptimal, value)
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

# Confirm which solver is being used
if hasattr(SOLVER, 'path'):
    logger.debug('Using CBC solver at: %s', SOLVER.path)
else:
    logger.debug('Using default PuLP solver configuration')

_PARTIAL_SEARCH = re.compile(r'best objective (\S+) \(best possible (\S+)\)')
_SUMMARY_OBJECTIVE = re.compile(r'^Objective value:\s+(\S+)', re.M)
_SUMMARY_BOUND = re.compile(r'^(?:Upper|Lower) bound:\s+(\S+)', re.M)
_START_TAKEN = re.compile(r'MIPStart provided solution with cost')


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
    return None


def _solver_for_run(warm_start, seed=None):
    """A copy of SOLVER writing CBC's log to a file of its own, reading a start and seeding if asked."""
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


def _sum_or_zero(terms):
    return pulp.lpSum(terms) if terms else 0


class LpProblem2:
    
    def __init__(self):
        self.pulp_vars = {}
        #self.model_output = open('model.txt', 'w')
        self.pulp_lp = LpProblem("The Whiskas Problem", LpMaximize)
        self.objective_value = None
        self.best_bound = None
        self.start_objective = None
        self.start_accepted = None

    def run(self, warm_start=None, seed=None):
        """Solve; warm_start is {variable name: value} of a set to start from, zero elsewhere, and seed a positive int for another search path."""
        problem_name = '/tmp/problem_%s' % str(uuid.uuid4())
        self.pulp_lp.name = problem_name
        solver = _solver_for_run(warm_start is not None, seed)
        objective = self.pulp_lp.objective
        self.objective_value = self.best_bound = self.start_objective = None
        self.start_accepted = None
        if warm_start is not None:
            for variable in self.pulp_lp.variables():
                variable.varValue = warm_start.get(variable.name, 0)
            self.start_objective = value(objective)
            # CBC 2.10 prices a mipstart in the wrong sign under "max"
            self.pulp_lp.sense = LpMinimize
            self.pulp_lp.objective = -objective
        try:
            self.pulp_lp.solve(solver)
        finally:
            if warm_start is not None:
                self.pulp_lp.sense = LpMaximize
                self.pulp_lp.objective = objective
            log_text = _read_and_remove(solver.optionsDict['logPath'])
        if warm_start is not None:
            self.start_accepted = bool(_START_TAKEN.search(log_text))
        if self.pulp_lp.status == LpStatusOptimal:
            self.objective_value = value(objective)
            if not self.solution_is_proven() and self.objective_value is not None:
                self.best_bound = read_best_bound(log_text, self.objective_value)
        logger.debug('Status: %s, Z = %s', LpStatus[self.pulp_lp.status], self.objective_value)

        tmpMps = os.path.join('%s-pulp.mps' % problem_name)
        tmpSol = os.path.join('%s-pulp.sol' % problem_name)
        try: os.remove(tmpMps)
        except: logger.debug('could not remove file %s', tmpMps)
        try: os.remove(tmpSol)
        except: logger.debug('could not remove file %s', tmpSol)

    def get_result(self):
        return {v.name: v.varValue for v in self.pulp_lp.variables()}

    def setup_variable(self, category, id, min_bound, max_bound):
        sanitized_id = str(id).replace(' ', '_').replace('-', '_')
        name = '%s_%s' % (category, sanitized_id)
        pulpVar = LpVariable(name, min_bound, max_bound, LpInteger)
        self.pulp_vars[name] = pulpVar

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
        self.pulp_lp.objective = _sum_or_zero([value * self.pulp_vars[key] for key, value in
                         self.obj_vars.items() if key in self.pulp_vars])
        
    def restriction_lt_eq(self, max_bound, parcels):
        restriction = _sum_or_zero([parcel[0] * self.pulp_vars['%s_%s' % (parcel[1], str(parcel[2]).replace(' ', '_').replace('-', '_'))] 
                            for parcel in parcels]) <= max_bound
        self.pulp_lp += restriction
        return restriction
        

    def restriction_eq(self, max_bound, parcels):
        restriction = _sum_or_zero([parcel[0] * self.pulp_vars['%s_%s' % (parcel[1], str(parcel[2]).replace(' ', '_').replace('-', '_'))] 
                            for parcel in parcels]) == max_bound
        self.pulp_lp += restriction
        return restriction
        
    def get_status(self):
        return LpStatus[self.pulp_lp.status]

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
        return LpSolution[self.pulp_lp.sol_status]

    def solution_is_proven(self):
        """True only when the solver closed the gap. See get_solution_status."""
        return self.pulp_lp.sol_status == LpSolutionOptimal

    def get_search_state(self):
        """The last run's objective, best bound (None once proven or unread), start objective, whether CBC took the start, and non-zero values."""
        return {'objective': self.objective_value,
                'bound': self.best_bound,
                'start_objective': self.start_objective,
                'start_accepted': self.start_accepted,
                'values': {name: number for name, number in self.get_result().items()
                           if number}}
