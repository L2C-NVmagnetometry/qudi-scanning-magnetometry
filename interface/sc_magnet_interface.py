# -*- coding: utf-8 -*-
"""
This file contains the Qudi Interface file to control a superconducting magnet.

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

import abc
from core.util.interfaces import InterfaceMetaclass

class SuperConductingMagnetInterface(metaclass=InterfaceMetaclass):
    """ This is the Interface class to define the controls for the devices
        controlling the magnetic field.
    """
    
    _modtype = 'SuperConductingMagnetInterface'
    _modclass = 'interface'
    
    @abc.abstractmethod
    def get_limits(self, axis):
        """
        Read lower/upped sweep limit and voltage limit (5 for z, 1 for x and y)
        @param adress of the desired magnet
        
        @return float [llim, ulim, vlim]
        """
        pass
    
    @abc.abstractmethod
    def start_remote_mode(self, axis):
        """
        Select remote operation
        """
        pass
    
    @abc.abstractmethod
    def channel_select(self, axis, n_channel):
        """
        Select module for subsequent commands
        @param int: wanted channel
        
        @return int: selected channel
        """
        pass
    
    @abc.abstractmethod
    def get_active_coil_status(self, axis, mode):
        """
        Query current coil and power supply caracteristics
        
        @return array
        """
        pass
    
    @abc.abstractmethod
    def get_rates(self, axis):
        """
        Query sweep rates for selected sweep range
        
        @return array
        """
        pass
    
    @abc.abstractmethod
    def read_sweep_mode(self, axis):
        """
        Query sweep mode
        
        @return str
        """
        pass
    
    @abc.abstractmethod
    def get_ranges(self, axis):
        """
        Query range limit for sweep rate boundary
        
        @return str
        """
        pass
    
    @abc.abstractmethod
    def get_mode(self, axis):
        """
        Query selected operating mode
        
        @return str
        """
        pass
    
    @abc.abstractmethod
    def get_units(self, axis):
        """
        Query selected units
        
        @return str
        """
        pass
    
    @abc.abstractmethod
    def set_switch_heater(self, axis, mode='OFF'):
        """
        Control persistent switch heater
        @param USB adress
        @param string: ON or OFF to set the switch heater on or off
        """
        pass
    
    @abc.abstractmethod
    def set_units(self, axis, units='G'):
        """
        Select Units
        @param string: A or G
        
        @return string: selected units
        """
        pass
    
    @abc.abstractmethod
    def set_sweep_mode(self, axis, mode):
        """
        Start output current sweep
        @param str: sweep mode
        
        @return str
        """
        pass
    
    @abc.abstractmethod
    def set_limits(self, axis, ll=None, ul=None, vl=None):
        """
        Set current and voltage sweep limits
        @param float: lower current sweep limit
        @param float: upper current sweep limit
        @param float: voltage sweep limit
        
        @return array
        """
        pass
    
    @abc.abstractmethod
    def set_ranges(self, axis, ranges):
        """
        Set range limit for sweep rate boundary
        @param array: range values
        
        @return array
        """
        pass
    
    @abc.abstractmethod
    def set_rates(self, axis, rates):
        """
        Set sweep rates for selected sweep range
        @param array: range values
        
        @return array
        """
        pass
    
    @abc.abstractmethod
    def self_test_query(self, axis):
        """
        Self test query
        
        @return bool
        """
        pass
