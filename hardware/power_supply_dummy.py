"""

Dummy hardware module.

This file is adapted from the pi3diamond project distributed under GPL V3 licence.
Created by Helmut Fedder <helmut@fedder.net>. Adapted by someone else.

---

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

from core.module import Base, ConfigOption
from interface.process_control_interface import ProcessControlInterface


class PowerSupplyDummy(Base, ProcessControlInterface):

    _voltage_max_1 = ConfigOption('voltage_max_1', 32)
    _current_max_1 = ConfigOption('current_max_1', 5)
    _voltage_max_2 = ConfigOption('voltage_max_2', 32)
    _current_max_2 = ConfigOption('current_max_2', 5)
    _voltage_max_3 = ConfigOption('voltage_max_3', 32)
    _current_max_3 = ConfigOption('current_max_3', 5)

    _model = None
    _inst = None

    def on_activate(self):
        """ Startup the module """
        self.channel = 1
        self.voltage = {1: 0, 2: 0, 3: 0}
        self.current = {1: 0, 2: 0, 3: 0}
        return

    def on_deactivate(self):
        """ Stops the module """
        return
    
    def _set_channel(self, channel):
        """sets the channel 1, 2 or 3"""
        if channel in [1, 2, 3]:
            self.channel = channel
        else:
            self.log.error('Wrong channel number. Chose 1, 2 or 3.')
    
    def _get_channel(self):
        """ query the selected channel"""
        return self.channel
    
    def _get_status_channel(self, channel):
        """ Gets the current status of the selected channel (CC or CV)"""
        return "I am a dummy."
    
    def _set_voltage(self, value, channel=None):
        """ Sets the voltage to the desired value"""
        if channel is not None:
            self._set_channel(channel)
        mini, maxi = self.get_control_limit(channel=self.channel)
        if mini <= value <= maxi:
            self.voltage[self.channel] = value
        else:
            self.log.error('Voltage value {} out of range'.format(value))
    
    def _get_voltage(self, channel=None):
        """ Get the measured the voltage """
        if channel is not None:
            self._set_channel(channel)
        return self.voltage[self.channel]
        
    def _set_current(self, value, channel=None):
        """ Sets the current to the desired value """
        if channel is not None:
            self._set_channel(channel)
        mini, maxi = self._get_control_limit_current(channel=self.channel)
        if mini <= value <= maxi:
            self.current[self.channel] = value
        else:
            self.log.error('Current value {} out of range'.format(value))
    
    def _get_current(self, channel=None):
        """ Get the measured the current  """
        if channel is not None:
            self._set_channel(channel)
        return self.current[self.channel]
    
    def _set_on(self, channel=None):
        """ Turns the output from the chosen channel on """
        if channel is not None:
            self._set_channel(channel)
        return

    def _set_off(self, channel=None):
        """ Turns the output from the chosen channel off """
        if channel is not None:
            self._set_channel(channel)
        return
            
    def _set_all_off(self):
        """ Stops the output of all channels """
        return
    
    def _reset(self):
        """ Reset the whole system"""
        self.channel = 1
        self.voltage = {1: 0, 2: 0, 3: 0}
        self.current = {1: 0, 2: 0, 3: 0}
        
    def _beep(self):
        """ gives an acoustical signal from the device """
        return
        
    def _error_list(self):
        """ Get all errors from the error register """
        return

    def _set_over_voltage(self, maxi, channel=None):
        """ Sets the over voltage protection for a selected channel"""
        if channel is not None:
            self._set_channel(channel)
        return

    def _set_over_current(self, maxi, channel=None):
        """ Sets the over current protection for a selected channel"""
        if channel is not None:
            self._set_channel(channel)
        return
    
# Interface methods

    def setControlValue(self, value, channel=1, ctrparam="VOLT"):
        """ Set control value

            @param (float) value: control value
            @param (int) channel: channel to control
            @param (str) ctrparam: control parameter ("VOLT" or "CURR")
        """
        if channel is not None:
            self._set_channel(channel)
        mini, maxi = self.getControlLimits(channel, ctrparam)
        if mini <= value <= maxi:
            if ctrparam == "CURR":
                self.current[self.channel] = value
            else:
                self.voltage[self.channel] = value
        else:
            self.log.error('Control value {} out of range'.format(value))

    def getControlValue(self, ctrparam="VOLT"):
        """ Get current control value, here heating power

            @param (str) ctrparam: control parameter ("VOLT" or "CURR")
            @return float: current control value
        """
        if ctrparam == "CURR":
            rep = self.current[self.channel]
        else:
            rep = self.voltage[self.channel]
        return rep

    def getControlUnit(self, ctrparam="VOLT"):
        """ Get unit of control value.

            @param (str) ctrparam: control parameter ("VOLT" or "CURR")
            @return tuple(str): short and text unit of control value
        """
        if ctrparam == "VOLT":
            return 'V', 'Volt'
        else:
            return 'A', 'Ampere'

    def getControlLimits(self, channel=None, ctrparam="VOLT"):
        """ Get minimum and maximum of control value.

            @param (str) ctrparam: control parameter ("VOLT" or "CURR")
            @return tuple(float, float): minimum and maximum of control value
        """
        if channel is None:
            channel = self._get_channel()
        maxi = 0
        if ctrparam == "VOLT":
            maxi = self._voltage_max_1 if channel == 1 else maxi
            maxi = self._voltage_max_2 if channel == 2 else maxi
            maxi = self._voltage_max_3 if channel == 3 else maxi
        else:
            maxi = self._current_max_1 if channel == 1 else maxi
            maxi = self._current_max_2 if channel == 2 else maxi
            maxi = self._current_max_3 if channel == 3 else maxi
        return 0, maxi

    def processControlSupportsMultipleChannels(self):
        """ Function to test if hardware support multiple channels """
        return True

    def processControlGetNumberChannels(self):
        """ Function to get the number of channels available for control """
        return 3
