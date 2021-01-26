# -*- coding: utf-8 -*-
""" 
This module operates a superconducting 3D magnet.

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
#import matplotlib as mpl
#import matplotlib.pyplot as plt
#from timeit import default_timer as timer
#from io import BytesIO

from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.module import Connector, ConfigOption, StatusVar

class SuperConductingMagnetLogic(GenericLogic):
    
    _modclass = 'scmagnetlogic'
    _modtype = 'logic'
    
    # declare connectors
    scmagnet = Connector(interface='SuperConductingMagnetInterface')
    
    # Internal signals
    
    # Update signals, e.g. for GUI module
    sigStatusUpdated = QtCore.Signal(list, str)
    sigLimitsUpdated = QtCore.Signal(list, str)
    sigRangesUpdated = QtCore.Signal(list, str)
    sigRatesUpdated = QtCore.Signal(list, str)
    sigSweepModeUpdated = QtCore.Signal(str, bool, str)
    sigHeaterNotSwitched = QtCore.Signal()
    sigFieldSet = QtCore.Signal()
    
    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()
        
    
    def on_activate(self):
       """ Initialisation performed during activation of the module. """
       # connectors
       self._magnet = self.scmagnet()
       
       self.max_field_x = self._magnet._max_field_x # in G
       self.max_field_y = self._magnet._max_field_y # in G
       self.max_field_z = self._magnet._max_field_z # in G
       
       self.max_current_x = self._magnet._max_current_x # in A
       self.max_current_y = self._magnet._max_current_y # in A
       self.max_current_z = self._magnet._max_current_z # in A
       
       self.ch = {"x":1, "y":2}
       
       self.timer = QtCore.QTimer()
       self.timer.setSingleShot(True)
       
       return 0
   
    def on_deactivate(self):
       """ Cleanup performed during deactivation of the module. """
       return
   
    def get_axis(self, coil):
        """ Return the axis with which we want to communicate.
        """
        if coil == "z":
           axis = self._magnet.z_magnet
        else:
           axis = self._magnet.xy_magnet
           n = self._magnet.channel_select(axis, self.ch[coil])
        return axis
   
    def query_status(self, coil):
       """ Asks for the status of the coil.
           @param str coil "x", "y" or "z".
       """
       axis = self.get_axis(coil)
           
       status = self._magnet.get_active_coil_status(axis, 4)
       unit = self._magnet.get_units(axis)
       coilparams = [unit]+ status
       
       
       self.sigStatusUpdated.emit(coilparams, coil)
       return
   
    def query_unit(self, coil):
       """ Asks for the selected unit of the coil.
           @param str coil "x", "y" or "z".
       """
       axis = self.get_axis(coil)
       unit = self._magnet.get_units(axis)
       
       return unit
   
    def query_limits(self, coil):
       """ Asks for the status of the coil.
           @param str coil "x", "y" or "z".
       """
       axis = self.get_axis(coil)    
       limits = self._magnet.get_limits(axis) # values given in kG or A
       unit = self.query_unit(coil)
       if unit == "G":
           vl = limits[2]
           limits =[str(1e3*float(l[:-2]))+ " G" for l in limits[:2]] + [vl] # convert in G
       
       self.sigLimitsUpdated.emit(limits, coil)
       return
   
    def query_ranges(self, coil):
       """ Asks for the ranges of the coil.
           @param str coil "x", "y" or "z".
       """
       axis = self.get_axis(coil)    
       ranges = self._magnet.get_ranges(axis)
           
       self.sigRangesUpdated.emit(ranges[:-1], coil)
       return
   
    def query_rates(self, coil):
       """ Asks for the rates of the coil.
           @param str coil "x", "y" or "z".
       """
       axis = self.get_axis(coil)    
       rates = self._magnet.get_rates(axis)
       
       self.sigRatesUpdated.emit(rates, coil)
       return
   
    def query_sweep_mode(self, coil):
       """ Asks for the sweep mode of the coil.
           @param str coil "x", "y" or "z".
       """
       axis = self.get_axis(coil)
       sweep = self._magnet.read_sweep_mode(axis).split(" ")
       if sweep[-1] == "fast":
           fast = True
       else:
           fast = False
       if sweep[0] == "sweep":
           mode = sweep[1][:-2].upper()
       else:
           mode = sweep[0][:-2].upper()
       
       self.sigSweepModeUpdated.emit(mode, fast, coil)
       return mode

    def change_op_mode(self, mode, coil):
        """ Changes the operating mode of the coil (local
            or remote).
            @param str mode: "local" or "remote".
            @param str coil: "x", "y", "z".
        """
        axis = self.get_axis(coil)
        if mode == "remote":
            self._magnet.start_remote_mode(axis)
        elif mode == "local":
            self._magnet.start_local_mode(axis)
            
        return
    
    def set_limits(self, limits, coil):
        """ Changes the limits of the coil.
            @param list limits: [upper, lower, voltage]
            @param str coil: "x", "y", "z".
        """
        axis = self.get_axis(coil)
        self.log.info("Settings limits for coil {}, lower {}G, upper {}G, voltage {}V".format(coil,
                      limits[0], limits[1],limits[2]))
        self._magnet.set_limits(axis, ll=limits[0], ul=limits[1],
                                vl = limits[2])
        return
    
    def set_sweep_mode(self, mode, fast, coil):
        """ Changes the limits of the coil.
            @param str mode: "UP", "DOWN", "ZERO", "PAUSE".
            @param bool fast: True if fast sweep, False if slow.
            @param str coil: "x", "y", "z".
        """
        axis = self.get_axis(coil)
        if mode == "PAUSE":
            command = mode
        elif fast:
            command = mode + " FAST"
        else:
            command = mode + " SLOW"
        self._magnet.set_sweep_mode(axis, command)
        return
    
    def set_ranges(self, ranges, coil):
        """ Changes the ranges of the coil.
            @param list ranges
            @param str coil: "x", "y", "z".
        """
        axis = self.get_axis(coil)
        if coil == "x":
            ranges.append(self.max_current_x)
        elif coil == "y":
            ranges.append(self.max_current_y)
        elif coil == "z":
            ranges.append(self.max_current_z)
        self._magnet.set_ranges(axis, ranges)
        return
    
    def set_rates(self, rates, coil):
        """ Changes the rates of the coil.
            @param list rates
            @param str coil: "x", "y", "z".
        """
        axis = self.get_axis(coil)
        self._magnet.set_rates(axis, rates)
        return
    
    def switch_heater(self, state, coil):
        """ Switches the heater of the coil.
            @param str state: "ON" or "OFF"
        """
        test = self.check_heater(coil)
        self.current_coil_heater = coil
        self.current_coil_state = state
        if test:
            axis = self.get_axis(coil)
            self._magnet.set_switch_heater(axis, mode=state)
            self.timer.start(5000) # wait 5s before
        else:
            self.sigHeaterNotSwitched.emit()
        return
    
    def set_unit(self, unit, coil):
        """ Changes the unit of the coil.
            @param str unit: "A" or "G".
            @param str coil: "x", "y", "z".
        """
        axis = self.get_axis(coil)
        self._magnet.set_units(axis, unit)
        return
    
    def check_before_closing(self):
        """ Check that we can safely turn off the program, the heaters 
        should be off and the fields should be zero
            @return bool test: True if we can turn off, False otherwise.
        """
        test = True
        for coil in ["x", "y", "z"]:
            axis = self.get_axis(coil)
            status = self._magnet.get_active_coil_status(axis, 4)
            if np.abs(float(status[0][:-2])) > 0.1 or np.abs(float(status[2][:-2])) > 0.1:
                test = False
            if not status[4] == "OFF":
                test = False
        return test
    
    def check_heater(self, coil):
        """ Check that the conditions are met to turn the heater on.
        """
        axis = self.get_axis(coil)
        mode = self.query_sweep_mode(coil)
        if mode not in ["PAUSE", "STANDBY"]:
            self.log.warning("Do not switch the heater during a sweep!")
            test = False
        else:
            status = self._magnet.get_active_coil_status(axis, 4)
            # check that iout and imag are close enough
            if "G" in status[0]:
                margin = 0.1 ### ASSUME THAT THE VALUES ARE IN G
                ### WE HAVE TO CHECK THAT THEY ARE NOT IN kG
            else:
                margin = 0.05
            if np.abs(float(status[0][:-2])-float(status[2][:-2])) > margin:
               self.log.warning("The fields of the coil and of the power supply are not the same!")
               test = False
            else:
                test = True
        return test
    
    def wait_sweep_and_pause(self, axis, target, coil):
        """ Checks every 2s if the sweep is over. When it is the case, pause.
        """
        cur_stat = self._magnet.get_active_coil_status(axis, 4)
        self.sigStatusUpdated.emit(["G"] + cur_stat, coil)
        while np.abs(target-float(cur_stat[0][:-2])) > 0.0001:
            # check every 2s if the value is reached
            time.sleep(2)
            cur_stat = self._magnet.get_active_coil_status(axis, 4)
            self.sigStatusUpdated.emit(["kG"] + cur_stat, coil)
        self._magnet.set_sweep_mode(axis, "PAUSE")
        return
        
    
    def set_field_coil(self, B, coil, status):
        """ Bring a coil to field B and the power supply back to zero.
        """
        axis = self.get_axis(coil)
        # First check the units, we need to be in G
        self._magnet.set_units(axis, "G")
        # Then check if we are already at the desired field or not
        currentB = float(status[2][:-2])
        powersupply = float(status[0][:-2])
        self.log.info("Current field value {}".format(currentB))
        if np.abs(currentB-B) < 0.0001:
            self.log.info(f"Coil {coil} already at the desired value.")
        else:
            # check if the magnet field and the power supply field are the same
            # if not, we have to change the power supply field
            if np.abs(currentB-powersupply) > 0.0001:
                
                if currentB > powersupply:
                    # imag > iout, we go up
                    l = self._magnet.set_limits(axis, ul=currentB) # in kG
                    self._magnet.set_sweep_mode(axis, "UP FAST")
                    self.log.info(f"Sweeping coil {coil} up fast")
                    self.wait_sweep_and_pause(axis, currentB, coil)
                
                else:
                    # imag < iout, we go down
                    l = self._magnet.set_limits(axis, ll=currentB) # in kG
                    self._magnet.set_sweep_mode(axis, "DOWN FAST")
                    self.log.info(f"Sweeping coil {coil} down fast")
                    self.wait_sweep_and_pause(axis, currentB, coil)

            # now we have imag = iout, select the sweep direction
            if currentB < B:
                # imag > B, we go up
                l = self._magnet.set_limits(axis, ul=B) # in kG
                direction = "UP"
                self.log.info("We need to sweep up")
            else:
                # imag < B, we go down
                l = self._magnet.set_limits(axis, ll=B) # in kG
                direction = "DOWN"
                self.log.info("We need to sweep down")
                
            time.sleep(1)   
            # heater on
            self._magnet.set_switch_heater(axis, mode="ON")
            self.log.info(f"Heater {coil} ON, waiting 5 s")
            time.sleep(5)
            # sweep
            self._magnet.set_sweep_mode(axis, direction+" SLOW")
            self.log.info("Sweeping...")
            self.wait_sweep_and_pause(axis, B, coil)
            self.log.info("Sweep finished")
            # heater off
            self._magnet.set_switch_heater(axis, mode="OFF")
            self.log.info(f"Heater {coil} OFF, waiting 5 s")
            time.sleep(5)
            # zeroing
            self._magnet.set_sweep_mode(axis, "ZERO FAST")
            self.log.info("Zeroing...")
            self.wait_sweep_and_pause(axis, 0, coil)
            self.log.info(f"Field set for coil {coil}.")
                
        return
    
    def go_to_field(self, Bx, By, Bz):
        """ Routine doing the full work to set a field value.
        """    
        test = True
        status = {}
        # we do not do anything if a heater is ON or a magnet sweeping
        for coil in ["x", "y", "z"]:
            axis = self.get_axis(coil) 
            mode = self.query_sweep_mode(coil)
            
            if not mode in ["PAUSE", "STANDBY"]:
                self.log.warning("Do not try to change the field during a sweep!")
                test = False
            status[coil] = self._magnet.get_active_coil_status(axis, 4)
            if status[coil][-1] == "ON":
                self.log.warning("Do not try to change the field with a heater on!")
                test = False               
        if test:
            self.set_field_coil(Bx, "x", status["x"])
            self.set_field_coil(By, "y", status["y"])
            self.set_field_coil(Bz, "z", status["z"])
        self.sigFieldSet.emit()
        return
