# -*- coding: utf-8 -*-
""" 
This module is used for monitoring the lHe level and the temperature in a cryo.

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

import numpy as np
import time
import datetime

from core.module import Connector
from logic.generic_logic import GenericLogic
from qtpy import QtCore
from core.util.mutex import Mutex
from gui.guiutils import timestamp
from threading import Thread
from collections import deque, OrderedDict
from itertools import islice

class CryoMonitoringLogic(GenericLogic):
    """ 
    Logic class to monitor the cryo.
    """

    _modclass = 'cryomonitoringlogic'
    _modtype = 'logic'

    # declare connectors
    savelogic = Connector(interface="SaveLogic")
    levelmeter = Connector(interface="CryoLevelMeterInterface")
    tempcontroller = Connector(interface="TempControllerInterface")

    # Update signals for GUI module
    sigUpdatelHePlot = QtCore.Signal()
    sigUpdateTempPlot = QtCore.Signal()
    sigNewlHeValue = QtCore.Signal(int, float)
    sigNewTempValue = QtCore.Signal(int, float, float)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()
        return
    
    def on_activate(self):
        """
        Initialisation performed during activation of the module.
        """
        
        # connect to hardware
        self._lHe_meter = self.levelmeter()
        self._thermometer = self.tempcontroller()
        self._save_logic = self.savelogic()
        
        # parameters
        self.saving = False
        self.temp_unit = "K"
        self.max_time_window = 24*3600 # 1 day, in seconds
        self.max_memory = 10000
        self.meas_lHe = False
        self.monitoring = False
        self.levelmeter_mode = "OFF"
        self.lHe_meas_interval = 60 # default 1 min
        self.temp_meas_interval = 2 # default 2 seconds
        self.temp_channel = "A"
        self.user_comment = ""
        self.recording = False
        self.temp_ref_time = timestamp()
        self.lHe_ref_time = timestamp()
        
        # initialize data arrays
        # arrays to store the data, arrays corresponding to the plot window
        # and arrays for saving
        # time is stored as an int for plots and as a string for saving
        self.lHe_time = deque(maxlen=self.max_memory)
        self.lHe_level = deque(maxlen=self.max_memory)
        self.lHe_time_for_plot = deque()
        self.lHe_level_for_plot = deque()
        self.lHe_time_to_save = deque()
        self.lHe_level_to_save = deque()

        self.temp_time = deque(maxlen=self.max_memory)
        self.temp_valuesA = deque(maxlen=self.max_memory)
        self.temp_valuesB = deque(maxlen=self.max_memory)
        self.temp_time_for_plot = deque()
        self.temp_valuesA_for_plot = deque()
        self.temp_valuesB_for_plot = deque()
        self.temp_time_to_save = deque()
        self.temp_valuesA_to_save = deque()
        self.temp_valuesB_to_save = deque()

        # connect internal signals
        self.sigNewlHeValue.connect(self.fill_lHe_data_arrays)
        self.sigNewTempValue.connect(self.fill_temp_data_arrays)
        
    def on_deactivate(self):
        """
        Stops the module.
        """
        self.stop_monitoring()
        return


    def change_lHe_meas_mode(self):
        """
        Tells the levelmeter to change the mode.
        """
        if self.levelmeter_mode == "Continuous":
            msg = "C"
        elif self.levelmeter_mode == "Sample/Hold":
            msg = "S"
        else:
            msg = "0"
        self._lHe_meter.setMeasurementMode(msg)
        return
    
    def start_monitoring(self):
        """
        Launch the monitoring process.
        """
        self.monitoring =  True
        if self.meas_lHe:
            self.launch_lHe_thread()
        self.temp_ref_time = timestamp()
        t = Thread(target=self.temp_meas_loop)
        t.start()
        self.log.info("Started temp measuring loop.")
        return

    
    def launch_lHe_thread(self):
        """
        If we were not measuring lHe but already monitoring the temp.
        """
        if self.monitoring and self.meas_lHe:
            self.lHe_ref_time = timestamp()
            l = Thread(target=self.lHe_meas_loop)
            l.start()
            self.log.info("Started lHe measuring loop.")
        return

    
    def stop_monitoring(self):
        """
        Stops the monitoring process.
        """
        self.monitoring = False
        return
    
    
    def plot_window_changed(self):
        """
        Updates the plotted time window.
        """
        # lHe 
        if self.meas_lHe:
            try:
                lindex = int(np.argmin(np.abs(np.array(self.lHe_time)-self.max_time_window)))
                self.lHe_time_for_plot = deque(islice(self.lHe_time, lindex, None))
                self.lHe_level_for_plot = deque(islice(self.lHe_level, lindex, None))
                self.sigUpdatelHePlot.emit()
            except Exception as e:
                print(e)
                self.log.warning("Could not change plotted time window for lHe")
                
        # temp
        try:
            tindex = int(np.argmin(np.abs(np.array(self.temp_time)-self.max_time_window)))
            self.temp_time_for_plot = deque(islice(self.temp_time, tindex, None))
            self.temp_valuesA_for_plot = deque(islice(self.temp_valuesA, tindex, None))
            self.temp_valuesB_for_plot = deque(islice(self.temp_valuesB, tindex, None))
            self.sigUpdateTempPlot.emit()
        except  Exception as e:
            print(e)
            self.log.warning("Could not change plotted time window for temp")

        return
    

    def fill_lHe_data_arrays(self, meastime, lHe):
        """
        Puts the data from the measurement threads in the corresponding arrays.
        """
        
        self.lHe_time.append(meastime)
        self.lHe_level.append(lHe)

        if len(self.lHe_time_for_plot)>0:
            if self.max_time_window < meastime - self.lHe_time_for_plot[0]:
                self.lHe_time_for_plot.popleft()
                self.lHe_level_for_plot.popleft()
        self.lHe_time_for_plot.append(meastime)
        self.lHe_level_for_plot.append(lHe)
        self.sigUpdatelHePlot.emit()

        if self.recording:
            stringmeastime = datetime.datetime.fromtimestamp(meastime).strftime("%d/%m/%y %H:%M:%S")
            self.lHe_time_to_save.append(stringmeastime)
            self.lHe_level_to_save.append(lHe)
            if len(self.lHe_time_to_save) > 5000:
                self.save_routine()
        
        return        

    
    def fill_temp_data_arrays(self, meastime, tempA, tempB):
        """
        Puts the data from the measurement threads in the corresponding arrays.
        """
        
        self.temp_time.append(meastime)
        self.temp_valuesA.append(tempA)
        self.temp_valuesB.append(tempB)

        if len(self.temp_time_for_plot)>0:
            if self.max_time_window < meastime - self.temp_time_for_plot[0]:
                self.temp_time_for_plot.popleft()
                self.temp_valuesA_for_plot.popleft()
                self.temp_valuesB_for_plot.popleft()
        self.temp_time_for_plot.append(meastime)
        self.temp_valuesA_for_plot.append(tempA)
        self.temp_valuesB_for_plot.append(tempB)
        self.sigUpdateTempPlot.emit()

        if self.recording:
            stringmeastime = datetime.datetime.fromtimestamp(meastime).strftime("%d/%m/%y %H:%M:%S")
            self.temp_time_to_save.append(stringmeastime)
            self.temp_valuesA_to_save.append(tempA)
            self.temp_valuesB_to_save.append(tempB)
            if len(self.temp_time_to_save) > 5000:
                self.save_routine()
        return

    
    def lHe_meas_loop(self):
        """
        Measurement loop for lHe.
        """
        while self.monitoring and self.meas_lHe:
            meastime = timestamp()
            if meastime-self.lHe_ref_time > self.lHe_meas_interval:
                val, unit = self._lHe_meter.getLevel()
                self.fill_lHe_data_arrays(meastime, val)
                self.lHe_ref_time = meastime
            time.sleep(4)
        return

    def temp_meas_loop(self):
        """
        Measurement loop for temp.
        """
        while self.monitoring:
            meastime = timestamp()
            if meastime-self.temp_ref_time > self.temp_meas_interval:
                self._thermometer.setChannel("A")
                valA, unit = self._thermometer.getTemp()
                self._thermometer.setChannel("B")
                valB, unit = self._thermometer.getTemp()
                self.fill_temp_data_arrays(meastime, valA, valB)
                self.temp_ref_time = meastime
            time.sleep(1)
        return

    def start_recording(self):
        """
        Starts filling the _to_save arrays.
        """
        self.recording = True
        self.log.info("Start recording.")
        return


    def stop_recording(self):
        """
        Save the _to_save arrays and empty them.
        """
        self.recording = False
        self.log.info("Stopped recording, saving.")
        # call savelogic and empty the arrays
        self.save_routine()
        return

    
    def save_routine(self):
        """
        Calls savelogic.
        TODO
        """
        # save
        filepath = self._save_logic.get_path_for_module('CryoMonitoring')
        filetimestamp = datetime.datetime.now()
        parameters = OrderedDict()
        parameters["Comment"] = self.user_comment
        
        lHe_save_data = OrderedDict()
        lHe_save_data["Time"] = np.array(self.lHe_time_to_save)
        lHe_save_data["lHe level (%)"] = np.array(self.lHe_level_to_save)

        filelabel = "lHe_level"
        self._save_logic.save_data(lHe_save_data, filepath=filepath, timestamp=filetimestamp,
                                   parameters=parameters, filelabel=filelabel, fmt=["%s", "%.2f"],
                                   delimiter="\t")


        temp_save_data = OrderedDict()
        temp_save_data["Time"] = np.array(self.temp_time_to_save)
        temp_save_data["Temp A (K)"] = np.array(self.temp_valuesA_to_save)
        temp_save_data["Temp B (K)"] = np.array(self.temp_valuesA_to_save)

        filelabel = "temperature"
        self._save_logic.save_data(temp_save_data, filepath=filepath, timestamp=filetimestamp,
                                   parameters=parameters, filelabel=filelabel,
                                   fmt=["%s", "%.3f", "%.3f"], delimiter="\t")
        
        # empty the arrays
        self.lHe_time_to_save.clear()
        self.lHe_level_to_save.clear()
        self.temp_time_to_save.clear()
        self.temp_valuesA_to_save.clear()
        self.temp_valuesB_to_save.clear()
        return
    
