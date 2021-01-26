# -*- coding: utf-8 -*-
""" 
This module operates a 3D coil magnet using a HMP3020 power supply.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
""" 

from qtpy import QtCore
from collections import OrderedDict
from copy import copy
import time
import datetime
import numpy as np

from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.module import Connector, ConfigOption, StatusVar

class CoilMagnetLogic(GenericLogic):
    
    _modclass = 'coilmagnetlogic'
    _modtype = 'logic'

    _coeff_x = ConfigOption('coeff_x', 10.50) #G/A
    _coeff_y = ConfigOption('coeff_y', 10.50) #G/A
    _coeff_z = ConfigOption('coeff_z', 42.00) #G/A

    # declare connectors
    powersupply = Connector(interface='ProcessControlInterface')
    
    # Internal signals
    
    # Update signals, e.g. for GUI module
    sigFieldSet = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
       """ Initialisation performed during activation of the module. """
       # connectors
       self._power_supply = self.powersupply()
       
       self.max_voltage_x = self._power_supply._voltage_max_1 # in V
       self.max_voltage_y = self._power_supply._voltage_max_2 # in V
       self.max_voltage_z = self._power_supply._voltage_max_3 # in V
       
       self.max_current_x = self._power_supply._current_max_1 # in A
       self.max_current_y = self._power_supply._current_max_2 # in A
       self.max_current_z = self._power_supply._current_max_3 # in A
       
       return 0

    def on_deactivate(self):
       """ Cleanup performed during deactivation of the module. """
       return

    def _set_field_coil(self, B, coil):
       """ Set the field for one coil. 
       B in G, coil is a str, "x", "y" or "z" .
       """

       if coil == "x":
           current = B/self._coeff_x
           # print(current)
           ch = 1
       elif coil == "y":
           current = B/self._coeff_y
           # print(current)
           ch = 2
       elif coil == "z":
           current = B/self._coeff_z
           # print(current)
           ch = 3
       if current < 1e-4: # then we just turn off the channel
           self._power_supply._set_off(ch)
           self._power_supply.setControlValue(0, ch)
           self._power_supply.setControlValue(0, ch, ctrparam="CURR")
           self.log.info("Turned off channel {}.".format(ch))
       else:
           # first voltage to 32 V (copied from the old labview program)
           self._power_supply.setControlValue(30, ch)
           # then sets the current
           self._power_supply.setControlValue(current, ch, ctrparam="CURR")
           self._power_supply._set_on(ch)
           self.log.info("Current set in channel {}.".format(ch))
       return

    def go_to_field(self, Bx, By, Bz):
       """ Routine doing the full work to set a field value, B in G.
       """
       self._set_field_coil(Bx, "x")
       time.sleep(1)
       self._set_field_coil(By, "y")
       time.sleep(1)
       self._set_field_coil(Bz, "z")
       time.sleep(1)
       self.sigFieldSet.emit()
       return

    def check_before_closing(self):
        return