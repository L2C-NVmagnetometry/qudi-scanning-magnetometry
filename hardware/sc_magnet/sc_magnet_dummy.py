# -*- coding: utf-8 -*-
"""
This file contains the dummy for a superconducting magnet interface.

QuDi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

QuDi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with QuDi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import time
import numpy as np

from core.module import Base, ConfigOption
from interface.sc_magnet_interface import SuperConductingMagnetInterface

class SuperConductingMagnetDummy(Base, SuperConductingMagnetInterface):
    """ Magnet positioning software for attocube's superconducting magnet.

    Enables precise positioning of the magnetic field in spherical coordinates
    with the angle theta, phi and the radius rho.
    The superconducting magnet has three coils, one in x, y and z direction respectively.
    The current through these coils is used to compute theta, phi and rho.

    Example config for copy-paste:

    sc_magnet_dummy:
        module.Class: 'sc_magnet.sc_magnet_dummy.SuperConductingMagnetDummy'
        max_field_z: 5000
        max_field_x: 5000
        max_field_y: 5000
        max_current_z: 15.72
        max_current_x: 39.67
        max_current_y: 47.73
    """
    
    _modclass = 'SuperConductingMagnetDummy'
    _modtype = 'hardware'
    _max_field_z = ConfigOption('max_field_z', missing='error')
    _max_field_x = ConfigOption('max_field_x', missing='error')
    _max_field_y = ConfigOption('max_field_y', missing='error')
    _max_current_z = ConfigOption('max_current_z', missing='error')
    _max_current_x = ConfigOption('max_current_x', missing='error')
    _max_current_y = ConfigOption('max_current_y', missing='error')


    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        self.xy_magnet = {}
        self.xy_magnet["x"] = {"ll":0, "ul":0.5, "vl":1, "op_mode":"remote", 
                               "iout":0, "vout":0, "imag":0, "vmag":0,
                               "pshtr":"OFF", "ranges":[0.25,0.5,0.75,1,2],
                               "rates":[0.5, 0.5, 0.25, 0.25, 0.15, 1],
                               "sweep": "sweep paused.", "mode":"manual", "unit":"G"}
        self.xy_magnet["y"] = {"ll":0, "ul":0.5, "vl":1, "op_mode":"remote", 
                               "iout":0, "vout":0, "imag":0, "vmag":0,
                               "pshtr":"OFF", "ranges":[0.25,0.5,0.75,1,2],
                               "rates":[0.5, 0.5, 0.25, 0.25, 0.15, 1],
                               "sweep": "sweep paused.", "mode":"manual", "unit":"G"}
        self.z_magnet = {"ll":0, "ul":0.5, "vl":1, "op_mode":"remote", 
                               "iout":0, "vout":0, "imag":0, "vmag":0,
                               "pshtr":"OFF", "ranges":[0.25,0.5,0.75,1,2],
                               "rates":[0.5, 0.5, 0.25, 0.25, 0.15, 1],
                               "sweep": "sweep paused.", "mode":"manual", "unit":"G"}
        self.current_channel = "x"
        self.test_str = "Dummy superconducting magnet"
        return
    
    def on_deactivate(self):
        """ Cleanup performed during deactivation of the module. """
        pass
    
    def get_limits(self, axis):
        """
        Read lower/upped sweep limit and voltage limit (5 for z, 1 for x and y)
        @param adress of the desired magnet
        
        @return float [llim, ulim, vlim]
        """
        if "x" in axis.keys(): 
            lim = [str(axis[self.current_channel]["ll"]) + " " + axis[self.current_channel]["unit"],
                   str(axis[self.current_channel]["ul"]) + " " + axis[self.current_channel]["unit"],
                   str(axis[self.current_channel]["vl"]) + " V"]
        else:
            lim = [str(axis["ll"]) + " " + axis["unit"],
                   str(axis["ul"]) + " " + axis["unit"],
                   str(axis["vl"]) + " V"]

        return lim

    
    def start_remote_mode(self, axis):
        """
        Select remote operation
        """
        if "x" in axis.keys(): 
            axis[self.current_channel]["op_mode"] = "remote"
        else:
            axis["op_mode"] = "remote"

        return
    
    def start_local_mode(self, axis):
        """
        Select local operation
        """
        if "x" in axis.keys(): 
            axis[self.current_channel]["op_mode"] = "remote"
        else:
            axis["op_mode"] = "remote"

        return
    
    def channel_select(self, axis, n_channel):
        """
        Select module for subsequent commands
        @param int: wanted channel
        
        @return int: selected channel
        """
        if n_channel == 1:
            self.current_channel = "x"
        else:
            self.current_channel = "y"
        
        return n_channel
    
    def get_active_coil_status(self, axis, mode):
        """
        Query current coil and power supply caracteristics
        
        @return array
        """
        if "x" in axis.keys(): 
            rep = [str(axis[self.current_channel]["iout"]) + " " + axis[self.current_channel]["unit"],
                   str(axis[self.current_channel]["vout"]) + " V",
                   str(axis[self.current_channel]["imag"]) + " " + axis[self.current_channel]["unit"],
                   str(axis[self.current_channel]["vmag"]) + " V", 
                   str(axis[self.current_channel]["pshtr"])]
        else:
            rep = [str(axis["iout"]*1e3) + " " + axis["unit"],
                   str(axis["vmag"]) + " V",
                   str(axis["imag"]*1e3) + " " + axis["unit"],
                   str(axis["vout"]) + " V",
                   str(axis["pshtr"])]
        
        return rep
    
    def get_rates(self, axis):
        """
        Query sweep rates for selected sweep range
        
        @return array
        """
        if "x" in axis.keys(): 
            self.current_rates = [str(r) for r in axis[self.current_channel]["rates"]]
        else:
            self.current_rates = [str(r) for r in axis["rates"]]
            
        return self.current_rates
    
    def read_sweep_mode(self, axis):
        """
        Query sweep mode
        
        @return str
        """
        if "x" in axis.keys(): 
            self.sweep_mode = axis[self.current_channel]["sweep"]
        else:
            self.sweep_mode = axis["sweep"]
        
        return self.sweep_mode
    
    def get_ranges(self, axis):
        """
        Query range limit for sweep rate boundary
        
        @return str
        """
        if "x" in axis.keys(): 
            self.current_ranges = [str(r) for r in axis[self.current_channel]["ranges"]]
        else:
            self.current_ranges = [str(r) for r in axis["ranges"]]
            
        return self.current_ranges
    
    def get_mode(self, axis):
        """
        Query selected operating mode
        
        @return str
        """
        if "x" in axis.keys(): 
            self.current_mode = axis[self.current_channel]["mode"]
        else:
            self.current_mode = axis["mode"]
        
        return self.current_mode
    
    def get_units(self, axis):
        """
        Query selected units
        
        @return str
        """
        if "x" in axis.keys(): 
            self.unit = axis[self.current_channel]["unit"]
        else:
            self.unit = axis["unit"]
        
        return self.unit
    
    def set_switch_heater(self, axis, mode='OFF'):
        """
        Control persistent switch heater
        @param USB adress
        @param string: ON or OFF to set the switch heater on or off
        """
        if "x" in axis.keys(): 
            axis[self.current_channel]["pshtr"] = mode
        else:
            axis["pshtr"] = mode
        self.sh_mode = mode
        
        return mode
    
    def set_units(self, axis, units='G'):
        """
        Select Units
        @param string: A or G
        
        @return string: selected units
        """
        if "x" in axis.keys(): 
            axis[self.current_channel]["unit"] = units
        else:
            axis["unit"] = units
        
        self.current_units = units
        
        return units

    def set_sweep_mode(self, axis, mode):
        """
        Start output current sweep
        @param str: sweep mode
        
        @return str
        """
        modes = {"UP": "sweep up", "DOWN": "sweep down", "ZERO": "zeroing",
                 "PAUSE": "sweep paused", "UP FAST": "sweep up fast", 
                 "DOWN FAST": "sweep down fast", "ZERO FAST": "zeroing fast", 
                 "UP SLOW": "sweep up slow", "DOWN SLOW": "sweep down slow",
                 "ZERO SLOW": "zeroing slow"}
        if "x" in axis.keys(): 
            dico = axis[self.current_channel]
        else:
            dico = axis

        dico["sweep"] = modes[mode]
        
        time.sleep(2)
        
        if "UP" in mode:
            dico["iout"] = dico["ul"]
            if dico["pshtr"] == "ON":
                dico["imag"] = dico["ul"]
        elif "DOWN" in mode:
            dico["iout"] = dico["ll"]
            if dico["pshtr"] == "ON":
                dico["imag"] = dico["ll"]
        elif "ZERO" in mode:
            dico["iout"] = 0
            if dico["pshtr"] == "ON":
                dico["imag"] = 0
        
        return mode
    
    def set_limits(self, axis, ll=None, ul=None, vl=None):
        """
        Set current and voltage sweep limits
        @param float: lower current sweep limit
        @param float: upper current sweep limit
        @param float: voltage sweep limit
        
        @return array
        """
        if "x" in axis.keys(): 
            axis[self.current_channel]["ll"] = ll
            axis[self.current_channel]["ul"] = ul
            axis[self.current_channel]["vl"] = vl
        else:
            axis["ll"] = ll
            axis["ul"] = ul
            axis["vl"] = vl
        
        return [ll, ul, vl]
    
    def set_ranges(self, axis, ranges):
        """
        Set range limit for sweep rate boundary
        @param array: range values
        
        @return array
        """
        if len(ranges) != 5:
            self.log.warning('Not enough ranges ({} instead of 5)'.format(len(ranges)))
            return
        
        if "x" in axis.keys(): 
            axis[self.current_channel]["ranges"] = ranges
        else:
            axis["ranges"] = ranges
        
        return ranges
    
    def set_rates(self, axis, rates):
        """
        Set sweep rates for selected sweep range
        @param array: range values
        
        @return array
        """
        if len(rates) != 6:
            self.log.warning('not enough rates ({} instead of 6)'.format(len(rates)))
            return
        
        if "x" in axis.keys(): 
            axis[self.current_channel]["rates"] = rates
        else:
            axis["rates"] = rates
        
        return rates
    
    def self_test_query(self, axis):
        """
        Self test query
        
        @return bool
        """
        
        return self.test_str
 
