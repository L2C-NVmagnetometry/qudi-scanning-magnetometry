# -*- coding: utf-8 -*-
"""
This file contains the Qudi Interface file for a temperature controller.

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


class TempControllerInterface(metaclass=InterfaceMetaclass):
    """ This is the Interface class to define the controls for the temperature controller.
        At the moment, it is only coded for use as a thermometer.
        The needed functions to use the heater are missing.
    """

    _modtype = 'TempControllerInterface'
    _modclass = 'interface'

    @abc.abstractmethod
    def getChannel(self):
        """ 
        Read channel number.
        @return int channel number
        """
        pass


    @abc.abstractmethod
    def setChannel(self, ch):
        """ 
        Select the channel to use.
        @param int channel number
        """
        pass


    @abc.abstractmethod
    def setRemote(self):
        """ 
        Switch to remote mode.
        """
        pass

    @abc.abstractmethod
    def setLocal(self):
        """ 
        Switch to local mode.
        """
        pass

    @abc.abstractmethod
    def setUnit(self, unit):
        """ 
        Set the measurement unit to Celsius "C" or Kelvin "K".
        @params string unit "C" or "K"
        """
        pass
    
    @abc.abstractmethod
    def getTemp(self):
        """ 
        Measure the temperature
        @return float measured value
        @return string unit
        """
        pass


    

    
