"""

Hardware module to interface a Cryomagnetics LM510 lHe levelmeter

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
from interface.cryo_levelmeter_interface import CryoLevelMeterInterface
import time

class LevelMeter(Base, CryoLevelMeterInterface):
    
    _modclass = 'LevelMeter'
    _modtype = 'hardware'

    _address = ConfigOption('address', missing='error')
    _model = None
    
    
    def on_activate(self):
        """ Startup the module. """

        rm = visa.ResourceManager()
        try:
            self._inst = rm.open_resource(self._address)
        except visa.VisaIOError:
            self.log.error("Could not connect to hardware. Please check the wires and the address.")

        self._model = self.query('*IDN?')[:-1] 
        self._mode = "OFF"
        self.log.info('Connected to {}'.format(self._model))


    def on_deactivate(self):
        """ Stops the module. """
        self._inst.close()

    def query(self, msg):
        """ Specific query function because the hardware sends the command back before answering."""
        self._inst.write(msg)
        time.sleep(0.2)
        self._inst.read()
        time.sleep(0.2)
        rep = self._inst.read()
        time.sleep(0.2)
        self._inst.read()
        return rep 
    
    def write(self, msg):
        """ Specific query function because the hardware sends the command back."""
        self._inst.write(msg)
        time.sleep(0.2)
        self._inst.read()
        time.sleep(0.2)
        self._inst.read()
        return
        
    # interface functions
        
    def getChannel(self):
        """
        Read the channel number. 
        @return int channel number.
        """
        ch = int(self.query("CHAN?")) 
        return ch


    def setChannel(self, ch):
        """
        Select the channel to use.
        @param int channel number.
        """
        if not ch in (1, 2):
            self.log.warning("Wrong channel number!")
            return
        else:
            rep = self.write(f"CHAN {ch}")
            return

        
    def setRemote(self):
        """ Switch to remote mode. """
        rep = self.write("REMOTE")
        return


    def setLocal(self):
        """ Switch to local mode. """
        rep = self.write("LOCAL")
        return


    def getMeasurementMode(self):
        """ 
        Read measurement mode.
        @return string "Continuous" or "Sample/Hold" or "OFF"
        """
        mode = self.query("MODE?") # MIGHT NEED TO FORMAT BETTER
        self._mode = mode
        return mode

    
    def setMeasurementMode(self, mode):
        """ 
        Set measurement mode.
        @param string "C" for continuous or "S" for sample/hold or "0" for off.
        """
        if not mode in ("S", "C", "0"):
            self.log.warning("Wrong selected mode!")
            return
        else:
            rep = self.write(f"MODE {mode}")
            self.getMeasurementMode()
            return


    def getLevel(self):
        """ 
        Measure the cryo level
        @return float measured value
        @return string unit
        """
        if self._mode is not "Continuous":
            self.write("MEAS")
        rep = self.query("MEAS?")
        #print("query line", rep)
        rep = rep.split(' ') # MIGHT NEED TO FORMAT BETTER
        val = float(rep[0])
        unit = rep[1]
        return val, rep
