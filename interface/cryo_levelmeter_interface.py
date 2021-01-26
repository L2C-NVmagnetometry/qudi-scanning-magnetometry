# -*- coding: utf-8 -*-
"""
This file contains the Qudi Interface file to control a cryo level meter.

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


class CryoLevelMeterInterface(metaclass=InterfaceMetaclass):
    """ This is the Interface class to define the controls for the cryo level meter.
    """

    _modtype = 'CryoLevelMeterInterface'
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
    def getMeasurementMode(self):
        """ 
        Read measurement mode.
        @return string "continuous" or "hold"
        """
        pass

    
    @abc.abstractmethod
    def setMeasurementMode(self, mode):
        """ 
        Set measurement mode.
        @param string "continuous" or "hold"
        """
        pass

    
    @abc.abstractmethod
    def getLevel(self):
        """ 
        Measure the cryo level
        @return float measured value
        @return string unit
        """
        pass

    

    
