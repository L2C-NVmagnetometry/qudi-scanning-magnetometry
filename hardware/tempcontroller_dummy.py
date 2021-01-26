"""

Hardware module to interface a dummy temperature controller.

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
from interface.temp_controller_interface import TempControllerInterface
import numpy as np

class TempControllerDummy(Base, TempControllerInterface):

    _modclass = 'TempControllerDummy'
    _modtype = 'hardware'

    _model = None
    
    
    def on_activate(self):
        """ Startup the module. """

        self._model = "Dummy instrument"
        self.log.info('Connected to {}.'.format(self._model))
        self.channel = "a" # default value
        self.unit = "K" # default value
        self.mode = "remote"
        self.trenda = 1
        self.tempa = 295
        self.trendb = 1
        self.tempb = 290 


    def on_deactivate(self):
        """ Stops the module. """
        return

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
        self.mode = "remote"
        return


    def setLocal(self):
        """ Switch to local mode. """
        self.mode = "local"
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
        test_trend = np.random.rand()
        if test_trend < 0.1:
            if self.channel == "a":
                self.trenda = - self.trenda
            else:
                self.trendb = - self.trendb
        var = 0.1*np.random.rand() # max variation 100 mK between 2 points
        if self.channel == "a":
            val = self.tempa + self.trenda*var
            self.tempa = val
        else:
            val = self.tempb + self.trendb*var
            self.tempb = val
            
        if self.unit == "C":
            val = val - 273.15

        return val, self.unit
