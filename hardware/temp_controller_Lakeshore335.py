"""

Hardware module to interface a Lakeshore 335 temperature controller.

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

import visa

from core.module import Base, ConfigOption
from interface.temp_controller_interface import TempControllerInterface

class TempController(Base, TempControllerInterface):

    _modclass = 'TempController'
    _modtype = 'hardware'

    _address = ConfigOption('address', missing='error')
    _model = None
    
    
    def on_activate(self):
        """ Startup the module. """

        rm = visa.ResourceManager()
        try:
            self._inst = rm.open_resource(self._address, baud_rate=57600, data_bits=7,
                                          parity=visa.constants.Parity.odd,
                                          stop_bits=visa.constants.StopBits.one)
        except visa.VisaIOError:
            self.log.error("Could not connect to hardware. Please check the wires and the address.")

        self._model = self._inst.query('*IDN?')[:-1]
        self.log.info('Connected to {}.'.format(self._model))
        self.channel = "a" # default value
        self.unit = "K" # default value


    def on_deactivate(self):
        """ Stops the module. """
        self._inst.close()

    # interface functions
        
    def getChannel(self):
        """
        Return the channel name (A or B). 
        @return string channel name.
        """
        return self.channel.upper()


    def setChannel(self, ch):
        """
        Set the channel to use.
        @param string channel name.
        """
        self.channel = ch.lower()
        return

        
    def setRemote(self):
        """ Switch to remote mode. """
        rep = self._inst.query("MODE 1")
        return


    def setLocal(self):
        """ Switch to local mode. """
        rep = self._inst.query("MODE 0")
        return

    def setUnit(self, unit):
        """ Set the measurement unit to Celsius "C" or Kelvin "K".
        @params string unit "C" or "K"
        """
        self.unit = unit
        return

    def getTemp(self):
        """ 
        Measure the temperature
        @return float measured value
        @return string unit
        """
        if self.unit == "K":
            val = float(self._inst.query(f"KRDG? {self.channel}"))
        elif self.unit == "C":
            val = float(self._inst.query(f"CRDG? {self.channel}"))
        else:
            self.log.error("Unknown temperature unit!")
            return
        return val, self.unit
