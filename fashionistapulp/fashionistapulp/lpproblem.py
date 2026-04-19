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
from pulp import LpVariable, LpInteger, LpProblem, LpMaximize, LpStatus, value
import pulp
import os
import uuid
import platform

# Print debug information to confirm platform details
print(f"System: {platform.system()}")
print(f"Machine: {platform.machine()}")

# Initialize solver variable
SOLVER = None

# Handle different platforms
if platform.system() == 'Windows':
    # Windows implementation
    print("Detected Windows system. Looking for CBC solver...")
    
    # Check user home directory for .pulp/pulp.cfg which might contain solver path
    pulp_cfg = os.path.join(os.path.expanduser("~"), ".pulp", "pulp.cfg")
    if os.path.exists(pulp_cfg):
        print(f"Found PuLP configuration at {pulp_cfg}")
        # Use the default solver configured in the .pulp/pulp.cfg file
        try:
            SOLVER = pulp.PULP_CBC_CMD(msg=False, timeLimit=90)
            print("Using CBC solver from configuration")
        except Exception as e:
            print(f"Error loading solver from config: {e}")
    
    # Try to find CBC in the project directory
    if SOLVER is None:
        try:
            cbc_path = os.path.join(get_fashionista_path(), 'solvers', 'cbc', 'bin', 'cbc.exe')
            if os.path.isfile(cbc_path):
                print(f"Found CBC at {cbc_path}")
                SOLVER = pulp.COIN_CMD(path=cbc_path, timeLimit=90)
            else:
                print(f"CBC not found at {cbc_path}")
                # Fall back to default solver
                SOLVER = pulp.PULP_CBC_CMD(msg=False, timeLimit=90)
                print("Using default PuLP solver")
        except Exception as e:
            print(f"Error setting up solver: {e}")
            # Last resort - use default solver with no specific configuration
            SOLVER = pulp.CBC()
            print("Using minimal CBC solver")

elif platform.system() == 'Linux' and ('arm' in platform.machine() or 'aarch64' in platform.machine()):
    # On Raspberry Pi (ARM architecture, both 32-bit and 64-bit)
    cbc_path = '/usr/bin/cbc'
    print(f"Detected ARM architecture. Using system-installed CBC at: {cbc_path}")
    if not os.path.isfile(cbc_path):
        raise FileNotFoundError(f"CBC binary not found at {cbc_path}")
    SOLVER = pulp.COIN_CMD(path=cbc_path, timeLimit=90)
else:
    # On AWS or other x86_64 systems
    cbc_path = os.path.join(get_fashionista_path(), 'fashionistapulp', 'fashionistapulp', 'cbc')
    print(f"Detected non-ARM Linux system. Using project-specific CBC at: {cbc_path}")
    if not os.path.isfile(cbc_path):
        raise FileNotFoundError(f"CBC binary not found at {cbc_path}")
    SOLVER = pulp.COIN_CMD(path=cbc_path, timeLimit=90)

# Confirm which solver is being used
if hasattr(SOLVER, 'path'):
    print(f"Using CBC solver at: {SOLVER.path}")
else:
    print("Using default PuLP solver configuration")

class LpProblem2:
    
    def __init__(self):
        self.pulp_vars = {}
        #self.model_output = open('model.txt', 'w')
        self.pulp_lp = LpProblem("The Whiskas Problem", LpMaximize)
        
    def run(self):
        problem_name = '/tmp/problem_%s' % str(uuid.uuid4())
        self.pulp_lp.name = problem_name
        self.pulp_lp.solve(SOLVER)
        print('Status: %s, Z = %g' % (LpStatus[self.pulp_lp.status], value(self.pulp_lp.objective)))
        
        tmpMps = os.path.join('%s-pulp.mps' % problem_name)
        tmpSol = os.path.join('%s-pulp.sol' % problem_name)
        try: os.remove(tmpMps)
        except: print('could not remove file %s' % tmpMps)
        try: os.remove(tmpSol)
        except: print('could not remove file %s' % tmpSol)

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
        self.pulp_lp.objective = sum([value * self.pulp_vars[key] for key, value in
                         self.obj_vars.items() if key in self.pulp_vars])
        
    def restriction_lt_eq(self, max_bound, parcels):
        restriction = sum([parcel[0] * self.pulp_vars['%s_%s' % (parcel[1], str(parcel[2]).replace(' ', '_').replace('-', '_'))] 
                            for parcel in parcels]) <= max_bound
        self.pulp_lp += restriction
        return restriction
        

    def restriction_eq(self, max_bound, parcels):
        restriction = sum([parcel[0] * self.pulp_vars['%s_%s' % (parcel[1], str(parcel[2]).replace(' ', '_').replace('-', '_'))] 
                            for parcel in parcels]) == max_bound
        self.pulp_lp += restriction
        return restriction
        
    def get_status(self):
        return LpStatus[self.pulp_lp.status]
