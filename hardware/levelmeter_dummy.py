"""

Hardware module to interface a dummy lHe levelmeter

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
from interface.cryo_levelmeter_interface import CryoLevelMeterInterface
import datetime
import numpy as np

class LevelMeterDummy(Base, CryoLevelMeterInterface):
    
    _modclass = 'LevelMeter'
    _modtype = 'hardware'

    _model = None
    
    
    def on_activate(self):
        """ Startup the module. """

        self._model = "Dummy instrument"
        self._mode = "OFF"
        self.log.info('Connected to {}'.format(self._model))
        self.ch = 1
        self.op_mode = "remote"
        self.last_val = 100
        self.last_time = datetime.datetime.now()

    def on_deactivate(self):
        """ Stops the module. """
        return
        
    # interface functions
        
    def getChannel(self):
        """
        Read the channel number. 
        @return int channel number.
        """
        return self.ch


    def setChannel(self, ch):
        """
        Select the channel to use.
        @param int channel number.
        """
        if not ch in (1, 2):
            self.log.warning("Wrong channel number!")
            return
        else:
            self.ch = ch
            return

        
    def setRemote(self):
        """ Switch to remote mode. """
        self.op_mode = "REMOTE"
        return


    def setLocal(self):
        """ Switch to local mode. """
        self.op_mode = "LOCAL"
        return


    def getMeasurementMode(self):
        """ 
        Read measurement mode.
        @return string "Continuous" or "Sample/Hold" or "OFF"
        """
        return self._mode

    
    def setMeasurementMode(self, mode):
        """ 
        Set measurement mode.
        @param string "C" for continuous or "S" for sample/hold or "0" for off.
        """
        if not mode in ("S", "C", "0"):
            self.log.warning("Wrong selected mode!")
            return
        else:
            if mode == "C":
                self._mode = "continuous"
            elif mode == "S":
                self._mode =  "sample/hold"
            else:
                self._mode = "OFF"
        return


    def getLevel(self):
        """ 
        Measure the cryo level
        @return float measured value
        @return string unit
        """
        now = datetime.datetime.now()
        interval = now - self.last_time
        val = np.max(self.last_val - interval.total_seconds()*1e-2/3600, 0)
        unit = "%"
        self.last_time = now
        self.last_val = val
        return val, unit
