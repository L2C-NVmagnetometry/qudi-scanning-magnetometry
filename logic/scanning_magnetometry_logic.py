# -*- coding: utf-8 -*-
""" 
This module is a logic for a scanning NV magnetometer.

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

from qtpy import QtCore
from collections import OrderedDict
from interface.microwave_interface import MicrowaveMode, TriggerEdge
from copy import copy
from threading import Thread
import time
import datetime
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy.optimize import leastsq
import tempfile
from timeit import default_timer as timer

from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.module import Connector, ConfigOption, StatusVar

class MagnetometerLogic(GenericLogic):
    
    _modclass = 'magnetometerlogic'
    _modtype = 'logic'

    # declare connectors
    confocalscanner1 = Connector(interface='ConfocalScannerInterface')
    #odmrcounter = Connector(interface='ODMRCounterInterface')
    microwave1 = Connector(interface='mwsourceinterface')
    odmrlogic1 = Connector(interface='ODMRLogic')
    savelogic = Connector(interface='SaveLogic')

     # config options
    clock_frequency = StatusVar('clock_frequency', 10)
    return_slowness = StatusVar(default=50e-9)
    z_scanner_range = ConfigOption('z_scanner_range', 3e-6)
    z_scanner_max_voltage = ConfigOption('z_scanner_max_voltage', 4)
    mw_scanmode = ConfigOption('scanmode', 'SWEEP', missing='warn',
                               converter=lambda x: MicrowaveMode[x.upper()])
    sweep_mw_power = StatusVar('sweep_mw_power', -30)
    mw_start = StatusVar('mw_start', 2870e6)
    mw_stop = StatusVar('mw_stop', 2900e6)
    mw_step = StatusVar('mw_step', 30e6)
    mw_step_hf = StatusVar('mw_step', 60e6)
    run_time = StatusVar('run_time', 60)
    min_fullb = StatusVar('min_fullb', 2800e6)
    max_fullb = StatusVar('max_fullb', 2940e6)
    number_sweeps = StatusVar('number_sweeps', 1)
    threshold = StatusVar('threshold', 2920e6)
    resonance_frequency = StatusVar('resonance_frequency', 2870e6)

    # signals
    sigNextLine = QtCore.Signal()
    sigParamUpdated = QtCore.Signal(dict) # connected in GUI
    sigMovetoEnded = QtCore.Signal(bool) # connected in GUI
    sigPlotsUpdated = QtCore.Signal(np.ndarray, np.ndarray, np.ndarray) # connected in GUI
    sigStartScan = QtCore.Signal()
    sigStopScan = QtCore.Signal(bool) # connected in GUI
    sigResumeScan = QtCore.Signal()
    sigUpdateDuration = QtCore.Signal(str) # connected in GUI
    sigUpdateRemTime = QtCore.Signal(str) # connected in GUI
    sigScanPixelOver = QtCore.Signal(np.ndarray, np.ndarray)
    sigFinishedDataTreatment = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()


    def on_activate(self):
        """ Initialization performed during activation of the module.
        """ 
        # Get connectors
        self._scanning_device = self.confocalscanner1()
        #self._odmr_counter = self.odmrcounter()
        self._mw_device = self.microwave1()
        self._odmr_logic = self.odmrlogic1()
        self._save_logic = self.savelogic()

         ########### Set mw parameters ###########
        
        # Get hardware constraints
        limits = self.get_hw_constraints()
    
        # Set/recall microwave source parameters
        self._odmr_logic.sweep_mw_power = limits.power_in_range(self.sweep_mw_power)
        self._odmr_logic.mw_start = limits.frequency_in_range(self.mw_start)
        self._odmr_logic.mw_stop = limits.frequency_in_range(self.mw_stop)
        self.min_fullb = limits.frequency_in_range(self.min_fullb)
        self.max_fullb = limits.frequency_in_range(self.max_fullb)
        self.threshold = limits.frequency_in_range(self.threshold)
        self._odmr_logic.mw_step = limits.list_step_in_range(self.mw_step)
        self.mw_step_hf = limits.list_step_in_range(self.mw_step_hf)
        self._odmr_logic.mw_scanmode = self.mw_scanmode
        self._odmr_logic.clock_frequency = self.clock_frequency
        self.freq1 = self._odmr_logic.mw_start
        self.freq2 = self._odmr_logic.mw_stop


        # Set the trigger polarity (RISING/FALLING) of the mw-source input trigger
        # theoretically this can be changed, but the current counting scheme will not support that
        self._odmr_logic.mw_trigger_pol = TriggerEdge.RISING
        self.set_trigger(self._odmr_logic.mw_trigger_pol, self._odmr_logic.clock_frequency)

        # Switch off microwave and set CW frequency and power
        self.mw_off()

        # Raw data array (isob params)
        # get the number of data points the same way as odmr_logic
        self.line_number = 2
        self.odmr_raw_data = np.zeros((len(self.get_odmr_channels()), self.line_number))
        self.esr_line = np.zeros(np.shape(self.odmr_raw_data))
        
        ########### Set scanning parameters ###########

        # coeff to convert the measured voltage in topo
        self.coeff_topo = self.z_scanner_range/self.z_scanner_max_voltage
        
        # sets scanning variables
        self.line_position = [0,0]
        self.range = self._scanning_device.get_position_range()[0:2]

        ## default values for the resolution of the scan
        self.resolution = [100, 100]
        
        # gets current position of the scanner
        self.current_position = self._scanning_device.get_scanner_position()[:2]
        self.center_position = [self.range[0][1]/2, self.range[1][1]/2]
        
        # default comments
        self.user_comment = ""
        self.user_save_tag = ""

        # stopping the measurement
        self.stopRequested = False
        
        # scan mode
        self.scan_mode = "_hpix"
        self.meas_mode = "quenching"
        self.incr = 2
        self.image_size = 5 # default quenching when starting
        self.scanline_size = 4 # default quenching when starting
        self.corr_fct = "plane_fit"

        ########### Connect signals ################
        self.sigNextLine.connect(self._scan_line, QtCore.Qt.QueuedConnection)
        self.sigStartScan.connect(self.start_scanner, QtCore.Qt.QueuedConnection)
        self.sigResumeScan.connect(self.resume_scanner, QtCore.Qt.QueuedConnection)
        self.sigScanPixelOver.connect(self.treat_data, QtCore.Qt.QueuedConnection)
        self.sigFinishedDataTreatment.connect(self.move_after_scan_pixel, QtCore.Qt.QueuedConnection)

        # Create a new temporary file to stock ESR data
        self.temp = tempfile.TemporaryFile(mode='w+t')

        return


    def on_deactivate(self):
        """ Deinitialization performed during deactivation of the module.
        """
        # Stop measurement if it is still running
        if self.module_state() == 'locked':
            self.stop_odmr_scan()
        timeout = 30.0
        start_time = time.time()
        while self.module_state() == 'locked':
            time.sleep(0.5)
            timeout -= (time.time() - start_time)
            if timeout <= 0.0:
                self.log.error('Failed to properly deactivate odmr logic. Odmr scan is still '
                               'running but can not be stopped after 30 sec.')
                break
        # Switch off microwave source (also if CW mode is active or module is still locked)
        self._mw_device.off()
        #self._scanning_device.reset_hardware()

        self.sigNextLine.disconnect()
        self.sigStartScan.disconnect()
        self.sigResumeScan.disconnect()
        self.sigPlotsUpdated.disconnect()
        self.sigUpdateDuration.disconnect()
        self.sigUpdateRemTime.disconnect()
        self.sigMovetoEnded.disconnect()
        self.sigParamUpdated.disconnect()
        self.sigStopScan.disconnect()
        return


    def set_trigger(self, trigger_pol, frequency):
        """
        Set trigger polarity of external microwave trigger (for list and sweep mode).

        @param object trigger_pol: one of [TriggerEdge.RISING, TriggerEdge.FALLING]
        @param float frequency: trigger frequency during ODMR scan

        @return object: actually set trigger polarity returned from hardware
        """
        if frequency == 0 or not isinstance(frequency, (int, float)):
            frequency = 1.0

        self.log.info("Setting MW trigger")
        return self._odmr_logic.set_trigger(trigger_pol, frequency)


    def set_runtime(self, runtime):
        """
        Sets the runtime for ODMR measurement

        @param float runtime: desired runtime in seconds

        @return float: actually set runtime in seconds
        """
        self.log.info("Setting ODMR runtime")
        return self._odmr_logic.set_runtime(runtime)


    def set_sweep_parameters_isob(self, freq1, freq2):
        """ Set the desired frequency parameters for list and sweep mode

        @param float start: start frequency to set in Hz
        @param float stop: stop frequency to set in Hz
        @param float step: step frequency to set in Hz

        @return float, float, float: current start_freq, current stop_freq,
                                            current freq_step
        """
        self.log.info("Setting iso-B parameters")
        limits = self.get_hw_constraints()
        if isinstance(freq1, (int, float)) and isinstance(freq2, (int, float)):
            if freq2 <= freq1:
                freq2, freq1 = freq1, freq2
            self._odmr_logic.mw_stop = limits.frequency_in_range(freq2)
            self._odmr_logic.mw_start = limits.frequency_in_range(freq1)
            self._odmr_logic.mw_step = limits.sweep_step_in_range(freq2 - freq1)
            
        self.freq1 = self._odmr_logic.mw_start
        self.freq2 = self._odmr_logic.mw_stop
        self.line_number = 2

        param_dict = {'freq1': self.freq1,
                      'freq2': self.freq2}
        self.sigParamUpdated.emit(param_dict)
        
        return [self._odmr_logic.mw_start, self._odmr_logic.mw_stop,
                self._odmr_logic.mw_step]


    def set_sweep_parameters_fullb(self, start, stop, min_fullb, max_fullb, step, mw_step_hf, number_sweeps, threshold):
        """ Set the desired frequency parameters for list and sweep mode

        @param float start: start frequency to set in Hz
        @param float stop: stop frequency to set in Hz
        @param float min_fullb: lower bound frequency to set in Hz
        @param float max_fullb: upper bound frequency to set in Hz
        @param float step: step frequency to set in Hz
        @param float mw_step_hf: step frequency in high fields to set in Hz
        @param float threshold: high field threshold frequency to set in Hz

        @return float, float, float, float, float, float, float: current start_freq, 
        current stop_freq, current min_fullb, current max_fullb, current freq_step, 
        current freq_step_hf, current threshold
        """
        self.log.info("Setting full-B parameters")
        limits = self.get_hw_constraints()
        if isinstance(stop, (int, float)) and isinstance(start, (int, float)):
            if stop <= start:
                stop, start = start, stop
        self._odmr_logic.mw_stop = limits.frequency_in_range(stop)
        self._odmr_logic.mw_start = limits.frequency_in_range(start)
        self._odmr_logic.mw_step = limits.frequency_in_range(step)
        self.mw_start = self._odmr_logic.mw_start
        self.mw_step = self._odmr_logic.mw_step
        self.mw_stop = self._odmr_logic.mw_stop
        self.line_number = int(np.rint((self._odmr_logic.mw_stop - self._odmr_logic.mw_start) \
                                       / self._odmr_logic.mw_step))+1
                                          
        self.min_fullb = limits.frequency_in_range(min_fullb)
        self.max_fullb = limits.frequency_in_range(max_fullb)
        self.threshold = limits.frequency_in_range(threshold)
        self.mw_step_hf = limits.list_step_in_range(mw_step_hf)
        self.number_sweeps = number_sweeps
        
        self.odmr_raw_data = np.zeros([len(self.get_odmr_channels()), self.line_number])

        param_dict = {'mw_start': self._odmr_logic.mw_start,
                      'mw_stop': self._odmr_logic.mw_stop,
                      'min_fullb': self.min_fullb,
                      'max_fullb': self.max_fullb,
                      'mw_step': self._odmr_logic.mw_step,
                      'mw_step_hf': self.mw_step_hf,
                      'number_sweeps': self.number_sweeps,
                      'threshold': self.threshold
                      }
        self.sigParamUpdated.emit(param_dict)
        
        return [self._odmr_logic.mw_start, self._odmr_logic.mw_stop, self.min_fullb, 
                self.max_fullb, self._odmr_logic.mw_step, self.mw_step_hf, self.number_sweeps, self.threshold]


    def set_power(self, power):
        """ Set the desired RF power for list and sweep mode

        @param float: RF power in dBm      
        @return float: current power
        """
        self.log.info("Setting RF power")
        limits = self.get_hw_constraints()
        if isinstance(power, (int, float)):
            self._odmr_logic.sweep_mw_power = limits.power_in_range(power)
        param_dict = {'sweep_mw_power': self._odmr_logic.sweep_mw_power}
        self.sigParamUpdated.emit(param_dict)
        return self._odmr_logic.sweep_mw_power


    def mw_sweep_on(self):
        """
        Switching on the mw source in list/sweep mode.

        @return str, bool: active mode ['cw', 'list', 'sweep'], is_running
        """
        self.log.info("Turning on the MW sweep")
        return self._odmr_logic.mw_sweep_on()


    def start_odmr_counter(self):
        """
        Starting the ODMR counter and setting up the corresponding clock.

        @return int: error code (0:OK, -1:error)
        """
        self.log.info("Starting ODMR counter")
        return self._odmr_logic._start_odmr_counter()


    def stop_odmr_counter(self):
        """
        Stopping the ODMR counter.

        @return int: error code (0:OK, -1:error)
        """
        self.log.info("Stopping ODMR counter")
        return self._odmr_logic._stop_odmr_counter()


    def reset_sweep(self):
        """
        Resets the list/sweep mode of the microwave source to the first frequency step.
        """
        #self.log.info("Resetting the MW sweep.")
        return self._odmr_logic.reset_sweep()


    def mw_off(self):
        """ Switching off the MW source.

        @return str, bool: active mode ['cw', 'list', 'sweep'], is_running
        """
        self.log.info("Turning off the MW.")
        return self._odmr_logic.mw_off()


    def scan_odmr_line(self):
        """ Scans one ODMR line
        (from mw_start to mw_stop in steps of mw_step)
        """
        self.reset_sweep()
        
        if self.meas_mode == "fullb":
            # sets the new sweep frequencies
            self._odmr_logic.mw_sweep_on()
            self._odmr_logic._initialize_odmr_plots()

        # Acquire count data
        new_counts = self._odmr_logic.get_odmr_counts(self.line_number)
        if self.number_sweeps>1:
            for i in range(self.number_sweeps-1):
                new_counts += self._odmr_logic.get_odmr_counts(self.line_number)
        if new_counts[0, 0] == -1:
            self.stopRequested = True
            return

        self.odmr_raw_data = new_counts/self.number_sweeps
        
        return self.odmr_raw_data


    def get_odmr_channels(self):
        return self._odmr_logic.get_odmr_channels()


    def get_hw_constraints(self):
        """ Return the names of all configured fit functions.
        @return object: Hardware constraints object
        """
        return self._odmr_logic.get_hw_constraints()
    

    def set_clock_frequency(self, time_clock):
        """ Sets the frequency of the clock

        @param float: time for a measurement

        @return int: clock frequency
        """

        if self.module_state() == 'locked' or not isinstance(time_clock, (int,float)):
            self.log.warning('set_clock_frequency failed. Logic is locked or input value is '
                             'no integer or float.')
        else:        
            self.clock_frequency = 1/time_clock
            self._odmr_logic.clock_frequency = self.clock_frequency
            
            update_dict = {'clock_frequency' : self.clock_frequency}
            self.sigParamUpdated.emit(update_dict)
            dur_str = self.compute_scan_duration()
            self.sigUpdateDuration.emit(dur_str)
            self.sigUpdateRemTime.emit(dur_str)
                
        return self.clock_frequency
    

    def set_range(self, range_scan):
        """ Sets the range for the scan
        
        @param array 2*2: [[xmin, xmax],[ymin, ymax]]
        
        @return array 2*2: [[xmin, xmax],[ymin, ymax]]
        """
        # checks if scanner is still running
        if self.module_state() == 'locked':
            self.log.warning('set_range failed, logic is locked.')
        else:    
            self.range = [range_scan[0:2],range_scan[2:4]]
            update_dict = {'x_range' : self.range[0], 'y_range' : self.range[1]}
            self.sigParamUpdated.emit(update_dict)
            dur_str = self.compute_scan_duration()
            self.sigUpdateDuration.emit(dur_str)
            self.sigUpdateRemTime.emit(dur_str)
        
        return self.range
    

    def set_resolution(self, x_res, y_res):
        """ Sets the resolution for the scan
        
        @param int: desired x resolution
        @param int: desired y resolution
        
        @return array: self.resolution
        """
         # checks if scanner is still running
        if self.module_state() == 'locked':
            self.log.warning('set_resolution failed, logic is locked.')
        else:
            #The scan from NI card hardware need at least a 2 pixels scan. 
            #We have to check if our number of pixel is odd or even
            if x_res%2 == 1:
                x_res -= 1
            if y_res%2 == 1:
                y_res -= 1
            self.resolution = [x_res, y_res]
            
            update_dict = {'x_resolution' : self.resolution[0],
                           'y_resolution' : self.resolution[1]}
            self.sigParamUpdated.emit(update_dict)
            dur_str = self.compute_scan_duration()
            self.sigUpdateDuration.emit(dur_str)
            self.sigUpdateRemTime.emit(dur_str)
        
        return self.resolution
    

    def set_return_slowness(self, rs):
        """ Sets the return speed

        @param int: desired return speed

        @return int: return speed
        """
         # checks if scanner is still running
        if self.module_state() == 'locked':
            self.log.warning('set_return_slowness failed, logic is locked.')
        else:
            self.return_slowness = rs
            update_dict = {'return_slowness' : self.return_slowness}
            self.sigParamUpdated.emit(update_dict)
            dur_str = self.compute_scan_duration()
            self.sigUpdateDuration.emit(dur_str)
            self.sigUpdateRemTime.emit(dur_str)
        return self.return_slowness
    

    def shift_indices(self):
        """ Bring back the indices to the correct position at the end of the scan.

        @return int: error code (0:OK, -1:error)
        """ 
        # at the end, the indices go too far, shift them
        if self.line_position[1] == np.size(self.pl_image, axis=0):
            self.line_position[1] = self.line_position[1] -1
        if self.line_position[0] == np.size(self.pl_image, axis=1):
            self.line_position[0] = self.line_position[0] -1
        # recall last position
        self.current_position[0] = self.pl_image[self.line_position[1], self.line_position[0], 0]
        self.current_position[1] = self.pl_image[self.line_position[1], self.line_position[0], 1]
        
        return


    def initialize_image(self, image_size, scanline_size):
        """ Initialization of the image [x, y, topo, pl1, pl2, ...] where the number of slides is
        defined by the size parameter. Note: the check of the aspect ratio is now done in the GUI.

        @param int: nb of layers in the image (X, Y, topo, PL, freq, etc...)-2
        @param int: nb of scanline*2
        @return int: error code (0:OK, -1:error)
        """ 
        self.log.info("Image initialization")
        # Creates an image centered on the current position        
        h_range = self.range[0][1] - self.range[0][0]
        v_range = self.range[1][1] - self.range[1][0]
        x = [self.center_position[0] - h_range * 0.5, self.center_position[0] + h_range * 0.5]
        y = [self.center_position[1] - v_range * 0.5, self.center_position[1] + v_range * 0.5]
        # Checks if the x-start and x-end values are ok
        if x[1] < x[0]:
            self.log.error(
                'x[0] must be smaller than x[1], but they are '
                '({0:.3f},{1:.3f}).'.format(x[0], x[1]))
            return -1

        # Checks if the y-start and y-end value are ok
        if y[1] < y[0]:
            self.log.error(
                'y[0] must be smaller than y[1], but they are '
                '({0:.3f},{1:.3f}).'.format(y[0], y[1]))
            return -1

        self._X = np.linspace(x[0], x[1], num=int(self.resolution[0]))
        self._Y = np.linspace(y[0], y[1], num=int(self.resolution[1]))
        
        # Arrays for retrace line
        
        self._return_X = np.arange(self._X[0], self._X[-1], self.return_slowness)
        self._return_X = self._return_X[::-1]
        self._return_Y = np.arange(self._Y[0], self._Y[-1], self.return_slowness)
        self._return_Y = self._return_Y[::-1]

        # creates an image where each pixel will be [x,y,topo,counts, etc]
        self.pl_image = np.zeros((len(self._Y), len(self._X), image_size))
        self.pl_image[:, :, 0] = np.full((len(self._Y), len(self._X)), self._X)
        y_value_matrix = np.full((len(self._X), len(self._Y)), self._Y)
        self.pl_image[:, :, 1] = y_value_matrix.transpose()
        self.topo_corr = np.zeros((len(self._Y), len(self._X)))
        
        
        # creates scanlines 
        # Careful: It depends on the scanmode !!!
        if self.scan_mode == "_vpix":
            self.scanline = np.zeros((len(self._Y), scanline_size))
            self.mean_pl = np.zeros((len(self._Y), int(scanline_size/2)))
        elif self.scan_mode == "_hpix":
            self.scanline = np.zeros((len(self._X), self.scanline_size))
            self.mean_pl = np.zeros((len(self._X), int(scanline_size/2)))
            
        return 0


    def set_meas_mode(self, mode):
        """ Switches between quenching, isob and fullb.
            @param: str, mode, "quenching", "isob" or "fullb" 
        """
#        try:
#            if self.meas_mode != "quenching":
#                self._odmr_logic._stop_odmr_counter()
#            #self._scanning_device.reset_hardware()
#        except:
#            pass
        self.meas_mode = mode
        print(mode)
        if mode == "quenching":
            self.image_size = 5 # x, y, raw topo, pl, corrected topo
            self.scanline_size = 4 # 2*topo + 2*pl
            self.incr = 2
        elif mode == "isob":
            self.incr = 1
            self.image_size = 7 # x, y, raw topo, pldiff, pl1, pl2, corrected topo
            self.scanline_size = 8 # 2*topo, 2*pldiff, 2*pl1, 2*pl2
            # get the number of data points the same way as odmr_logic
            self.line_number = 2
            self.odmr_raw_data = np.zeros((len(self.get_odmr_channels()), self.line_number))
        else: # fullb
            self.incr = 1
            self.image_size = 8 # x, y, raw topo, freq, pldiff, pl1, pl2, corrected topo
            self.scanline_size = 10 # 2*topo + 2*freq + 2*pldiff + 2*pl1 + 2*pl2
            # get the number of data points the same way as odmr_logic
            self.line_number = int(np.rint((self._odmr_logic.mw_stop - self._odmr_logic.mw_start) \
                                           / self._odmr_logic.mw_step)) + 1
            self.odmr_raw_data = np.zeros([len(self.get_odmr_channels()), self.line_number])
            self.esr_line = np.zeros((self.line_number,2))
            
        self.initialize_image(self.image_size, self.scanline_size)
        return
    

    def start_scanner(self):
        """ Setting up the scanner device and starts the scanning procedure

        @return int: error code (0:OK, -1:error)
        """ 
        self.log.info("Starting the scanner")
        
        self.stopRequested = False
        
        with self.threadlock:
            if self.module_state() == 'locked':
                self.log.error('Cannot start a scan. Logic is already locked.')
                return -1
            self.module_state.lock()

            if self.meas_mode == "fullb":
                self.line_number = int(np.rint((self._odmr_logic.mw_stop - self._odmr_logic.mw_start) \
                        / self._odmr_logic.mw_step)) + 1
                self._normal_mw_step = self._odmr_logic.mw_step
                #self.image_size =  7 # x, y, topo, freq, pldiff, pl1, pl2
            
            # the following test is important, it initializes the image
            if self.initialize_image(self.image_size, self.scanline_size) < 0: 
                self.module_state.unlock()
                return -1
    
            clock_status = self._scanning_device.set_up_scanner_clock(
                clock_frequency=self.clock_frequency)
    
            if clock_status < 0:
                #self._scanning_device.module_state.unlock()
                self.module_state.unlock()
                self.set_position()
                return -1
    
            scanner_status = self._scanning_device.set_up_scanner(scanner_ao_channels=
                                                                  self._scanning_device._scanner_ao_channels)
    
            if scanner_status < 0:
                self._scanning_device.close_scanner_clock()
                #self._scanning_device.module_state.unlock()
                self.module_state.unlock()
                self.set_position()
                return -1   
            
            if self.meas_mode != "quenching":
                self.set_trigger(self._odmr_logic.mw_trigger_pol, self._odmr_logic.clock_frequency)
                self.odmr_raw_data = np.zeros([self.line_number, len(self.get_odmr_channels())])
                
                odmr_status = self.start_odmr_counter()
                if odmr_status < 0:
                    self.module_state.unlock()
                    mode, is_running = self._mw_device.get_status()
                    return -1
    
                mode, is_running = self.mw_sweep_on()
                if not is_running:
                    self.module_state.unlock()
                    self.stop_odmr_counter()
                    return -1
                
        self.sigNextLine.emit()

        return 0


    def resume_scanner(self):
        """ Continue the scanning procedure

        @return int: error code (0:OK, -1:error)
        """ 
        self.log.info("Resuming the scanner")
        self.set_trigger(self._odmr_logic.mw_trigger_pol, self._odmr_logic.clock_frequency)
        self.stopRequested = False
        
        with self.threadlock:
            if self.module_state() == 'locked':
                self.log.error('Can not start again the scan. Logic is already locked.')
                return -1
            self.module_state.lock()
    
            if self.meas_mode != "quenching":
                odmr_status = self.start_odmr_counter()
                if odmr_status < 0:
                    self.module_state.unlock()
                    mode, is_running = self._mw_device.get_status()
                    self.module_state.unlock()
                    return -1
    
                mode, is_running = self.mw_sweep_on()
                if not is_running:
                    self.stop_odmr_counter()
                    self.module_state.unlock()
                    return -1
            
            clock_status = self._scanning_device.set_up_scanner_clock(
                clock_frequency=self.clock_frequency)
    
            if clock_status < 0:
                self.module_state.unlock()
                self.set_position()
                
                return -1
    
            scanner_status = self._scanning_device.set_up_scanner(scanner_ao_channels=
                                                                  self._scanning_device._scanner_ao_channels)
    
            if scanner_status < 0:
                if self._scanning_device._scanner_clock_daq_task is not None:
                    self._scanning_device.close_scanner_clock()
                self.module_state.unlock()
                self.set_position()
                
                return -1
            
        self.sigNextLine.emit()
        return 0


    def kill_scanner(self):
        """ Closing the scanner device.

        @return int: error code (0:OK, -1:error)
        """ 
        self.log.info("Killing the scanner")
        try:
            self.module_state.unlock()
        except Exception as e:
            self.log.exception('Could not unlock the toolbox.')
        try:
            self._scanning_device.close_scanner()
        except Exception as e:
            self.log.exception('Could not close the scanner.')
        try:
            self._scanning_device.close_scanner_clock()
        except Exception as e:
            self.log.exception('Could not close the scanner clock.')

        if self.meas_mode != "quenching":
            self.mw_off()
            self.stop_odmr_counter()
        
        return 0


    def set_position(self, x=None, y=None):
        """ Forwarding the desired new position from the GUI to the scanning device.

        @param float: if defined, changes to position in x-direction (microns)
        @param float: if defined, changes to position in y-direction (microns)

        @return int: error code (0:OK, -1:error)
        """ 
        # Changes the respective value
        if self._scanning_device.module_state() == 'locked':
            self.log.warning("Cannot set the position while measuring")
            return -1
        else:
            if x is not None and y is not None:
                self.current_position[0:2] = [float(x), float(y)]
                self.change_position()
            return 0


    def change_position(self):
        """ Threaded method to change the hardware position.

        @return array: [x, y]
        """ 
        ch_array = ['x', 'y', 'z', 'a']
        try:
            pos_array = self.current_position
        except:
            pos_array = self.current_position[0:2]
        pos_dict = {}

        for i, ch in enumerate(self.get_scanner_axes()):
            pos_dict[ch_array[i]] = pos_array[i]
        self._scanning_device.scanner_set_position(**pos_dict)
        return 0


    def moveto(self, x, y):
        """ Action when the MoveTo button is pushed.
        """
        rs = self.return_slowness
        lsx = np.arange(min(self.current_position[0], x),
                        max(self.current_position[0], x)+rs, rs)
        if len(lsx) == 0:
            lsx = [x]
        lsy = np.arange(min(self.current_position[1], y + rs),
                                    max(self.current_position[1], y + rs), rs)
        if len(lsy) == 0:
            lsy = [y]

        if lsx[0] != self.current_position[0]:
            lsx = lsx[::-1]
        if lsy[0] != self.current_position[1]:
            lsy = lsy[::-1]
            
        lsx_temp = np.pad(lsx, (0, np.abs(len(lsx)-max(len(lsx), len(lsy)))),
                     'constant', constant_values=(0, lsx[-1]))
        lsy = np.pad(lsy, (0, np.abs(len(lsy)-max(len(lsx), len(lsy)))),
                     'constant', constant_values=(0, lsy[-1]))
        lsx = lsx_temp
            
        # need a thread here to avoid that python freezes
        f = Thread(target=self.moveto_loop, args=(lsx, lsy))
        f.start()


    def moveto_loop(self, lsx, lsy):
        """ Loop for the moveto thread.
        """
        nb_axes = len(self.get_scanner_axes())
        ch_array = ['x', 'y', 'z', 'a']
        
        i=0
        while i<len(lsx):
            self.current_position[0] = lsx[i]
            self.current_position[1] = lsy[i]
            #print(self.current_position)
            pos_dict = {}
            try:
                pos_array = self.current_position
            except:
                pos_array = self.current_position[0:2]
            j=0
            while j<nb_axes:
                pos_dict[ch_array[j]] = pos_array[j]
                j+=1
            self._scanning_device.scanner_set_position(**pos_dict)
            time.sleep(1/self.clock_frequency)
            update_dict = {'x' : self.current_position[0],
                           'y' : self.current_position[1]}
            self.sigParamUpdated.emit(update_dict)
            i+=1
            
        self.sigMovetoEnded.emit(True)


    def get_position(self):
        """ Get position from scanning device.

        @return list: with three entries x, y and z denoting the current
                      position in meters
        """ 
        return self._scanning_device.get_scanner_position()


    def get_scanner_axes(self):
        """ Get axes from scanning device.
        
        @return list(str): names of scanner axes
        """ 
        return self._scanning_device.get_scanner_axes()


    def get_scanner_count_channels(self):
        """ Get list of counting channels from scanning device.
        
        @return list(str): names of counter channels
        """ 
        return self._scanning_device.get_scanner_count_channels()


    def reset_position(self):
        """ Bring the scanner back to the initial position
        """       
        try:
            image = self.pl_image
            rs = self.return_slowness
                
            if self.line_position[0] == 0 and self.line_position[1] == 0:
                # make a line from the current cursor position to
                # the starting position of the first scan line of the scan
                self.scanline = self.scanline*0.0
                if self.current_position[:2] != [image[0, 0, 0], image[0, 0, 1]]:
                    lsx = np.arange(min(self.current_position[0], image[0, 0, 0]),
                                    max(self.current_position[0], image[0, 0, 0]), rs)
                    if len(lsx) == 0:
                        lsx = [image[0,0,0]]
                    lsy = np.arange(min(self.current_position[1], image[0, 0, 1]),
                                    max(self.current_position[1], image[0, 0, 1]), rs)
                    if len(lsy) == 0:
                        lsy = [image[0,0,1]]

                    if lsx[0] != self.current_position[0]:
                        lsx = lsx[::-1]
                    if lsy[0] != self.current_position[1]:
                        lsy = lsy[::-1]
                                   
                    lsx_temp = np.pad(lsx, (0, np.abs(len(lsx)-max(len(lsx), len(lsy)))),
                                      'constant', constant_values=(0, lsx[-1]))
                    lsy = np.pad(lsy, (0, np.abs(len(lsy)-max(len(lsx), len(lsy)))),
                                 'constant', constant_values=(0, lsy[-1]))
                    lsx = lsx_temp
                    start_line = np.vstack([lsx, lsy])
                    #print(start_line)
                   
                # move to the initial position of the scan, counts are thrown away
                start_line_counts = self._scanning_device.scan_line(start_line)
                if np.any(start_line_counts == -1):
                    self.stopRequested = True
                    self.sigNextLine.emit()
                    return 0
                self.log.info("Bringing the scanner back to initial position")
      
        except Exception as e:
            print(e)
            return -1
        
        return 0


    def start_scanning(self):
        """ Starts scanning.
        """
        self.log.info("Starting a scan.")
        self.line_position = [0, 0]
        if self.meas_mode == "fullb":
            # Suppress temporary file
            self.temp.close()
            # Create a new temporary file to stock ESR data
            self.temp = tempfile.TemporaryFile(mode='w+t')
        self.sigStartScan.emit()
        dur_str = self.compute_scan_duration()
        self.sigUpdateDuration.emit(dur_str)
        self.sigUpdateRemTime.emit(dur_str)
        self.start_time = timer()
        return


    def resume_scanning(self):
        """ Continue scanning
        """
        self.log.info("Resuming the scan.")
        self.sigResumeScan.emit()
        return


    def stop_scanning(self, end=False):
        """ Stops the scan.
        """ 
        self.log.info("Stopping the scan.")
        with self.threadlock:
            if self.module_state() == 'locked':
                self.stopRequested = True
        # at the end, the indices go too far, shift them
        self.shift_indices()
        self.sigStopScan.emit(end)
        return
    

    def _scan_line(self):
        """ Scanning an image by calling a function which defines the scanning mode      
        @param string: define the scanning mode
        """ 
        now = timer()
        rem_time = self.duration - (now - self.start_time)
        self.sigUpdateRemTime.emit(self.format_time(rem_time))
        
        # stops scanning if requested
        if self.stopRequested:
            with self.threadlock:
                self.kill_scanner()
                self.stopRequested = False
                #self.module_state.unlock()
                self.sigPlotsUpdated.emit(self.pl_image, self.scanline, self.esr_line)
                self.set_position()
                return 0
            
        # prepares the function to call
        function_name = getattr(self, self.scan_mode, None)
        
        try:
            if self.reset_position()<0:
                self.log.exception('Resetting position failed. The scan went wrong, killing the scanner.')
                self.stop_scanning()
                self.sigNextLine.emit()

            # return the scanner to the start of the next line
            if self.scan_mode == "_hpix":
                if self.move_hpix() < 0:
                    return -1
            else:
                if self.move_vpix() < 0:
                    return -1
                
            if function_name() is None: # important test, does the scanning
                self.log.exception('Scanning failed. The scan went wrong, killing the scanner.')
                self.stop_scanning()
                self.sigNextLine.emit()                
                
        except Exception as e:
            self.log.exception('The scan went wrong, killing the scanner.')
            self.stop_scanning()
            self.sigNextLine.emit() # ???
            return -1
    

    def return_h(self):
        """ Return the scanner to the begining of the next line, in horizontal mode
        """
        # return the scanner to the start of the next line
        lsx = self._return_X
        lsy = np.linspace(self.pl_image[self.line_position[1], self.line_position[0]-1, 1],
                self.pl_image[self.line_position[1], 0, 1],len(lsx))
        lsx_temp = np.pad(lsx, (0, np.abs(len(lsx)-max(len(lsx), len(lsy)))),
                          'constant', constant_values=(0, lsx[-1]))
        lsy = np.pad(lsy, (0, np.abs(len(lsy)-max(len(lsx), len(lsy)))),
                     'constant', constant_values=(0, lsy[-1]))
        lsx = lsx_temp
        return_line = np.vstack([lsx, lsy])
        print(return_line)
        return_line_counts = self._scanning_device.scan_line(return_line)
        
        return return_line_counts


    def return_v(self):
        """ Return the scanner to the begining of the next line, in vertical mode
        """        
        # return the scanner to the start of the next line
        lsy = self._return_Y
        lsx = np.linspace(self.pl_image[self.line_position[1]-1, self.line_position[0], 0],
                self.pl_image[0, self.line_position[0], 0], len(lsy))
        lsx_temp = np.pad(lsx, (0, np.abs(len(lsx)-max(len(lsx), len(lsy)))),
                                'constant', constant_values=(0, lsx[-1]))
        lsy = np.pad(lsy, (0, np.abs(len(lsy)-max(len(lsx), len(lsy)))),
                     'constant', constant_values=(0, lsx[-1]))
        lsx = lsx_temp
        return_line = np.vstack([lsx, lsy])
        print(return_line)
        return_line_counts = self._scanning_device.scan_line(return_line)
        
        return return_line_counts


    def move_hpix(self):
        """ Move the scanner to the next pixel, in horizontal mode
        """ 
        # write the next positions
        self.current_position[0] = self.pl_image[self.line_position[1], self.line_position[0], 0]
        self.current_position[1] = self.pl_image[self.line_position[1], self.line_position[0], 1]
        print("move_hpix", self.current_position)
            
        position = np.vstack(self.current_position)
        print(position)
        # send the position to the hardware
        try:
            self._scanning_device._write_scanner_ao(
                    voltages=self._scanning_device._scanner_position_to_volt(position),
                    start=True)
        except:
            return -1

        return 0
    

    def move_vpix(self):
        """ Move the scanner to the next pixel, in horizontal mode
        """ 
        # write the next positions
        self.current_position[0] = self.pl_image[self.line_position[1], self.line_position[0], 0]
        self.current_position[1] = self.pl_image[self.line_position[1], self.line_position[0], 1]
            
        position = np.vstack(self.current_position)
        print(position)
        # send the position to the hardware
        try:
            self._scanning_device._write_scanner_ao(
                    voltages=self._scanning_device._scanner_position_to_volt(position),
                    start=True)
        except:
            return -1
        
        return 0
    
    
    def threaded_treat_data(self, data, data_isob=None):
        """
        Thread for treat data to avoid freezing during fullB
        """
        f = Thread(target=self.treat_data, args=(data, data_isob))
        f.start()
        return

    def treat_data(self, data, data_isob):
        """ Stores the data nicely.
        """
        if self.meas_mode == "quenching":
            if self.scan_mode == "_hpix":
                # write the raw topography counts
                self.pl_image[self.line_position[1],
                              self.line_position[0]:self.line_position[0]+2,
                              4] = self.z_scanner_range - self.coeff_topo*data[:,1]
                # write the corrected topography counts
                self.pl_image[self.line_position[1],
                              self.line_position[0]:self.line_position[0]+2,
                              2] += self.z_scanner_range - self.coeff_topo*data[:,1]-self.topo_corr[self.line_position[1],
                              self.line_position[0]:self.line_position[0]+2]
                # write the pl counts
                self.pl_image[self.line_position[1],
                              self.line_position[0]:self.line_position[0]+2,
                              3] = data[:,0]
            else:
                # write the raw topography counts
                self.pl_image[self.line_position[1]:self.line_position[1]+2,
                              self.line_position[0],
                              4] = self.z_scanner_range - self.coeff_topo*data[:,1]
                # write the corrected topography counts
                self.pl_image[self.line_position[1]:self.line_position[1]+2,
                              self.line_position[0],
                              2] += self.z_scanner_range - self.coeff_topo*data[:,1]-self.topo_corr[self.line_position[1]:self.line_position[1]+2,
                              self.line_position[0]]
                # write the pl counts
                self.pl_image[self.line_position[1]:self.line_position[1]+2,
                              self.line_position[0],
                              3] = data[:,0]

        elif self.meas_mode == "isob":
            # write the raw topography counts
            self.pl_image[self.line_position[1], self.line_position[0],
                          6] = self.z_scanner_range - self.coeff_topo*np.mean(data[1])
            # write the corrected topography counts
            self.pl_image[self.line_position[1], self.line_position[0],
                          2] += self.z_scanner_range - self.coeff_topo*np.mean(data[1])-self.topo_corr[self.line_position[1], self.line_position[0]]
            # write the pldiff counts
            self.pl_image[self.line_position[1], self.line_position[0],
                          3] = data[0][0] - data[0][1]
            # write counts for the two frequencies
            self.pl_image[self.line_position[1], self.line_position[0],
                          4:6] = data[0]

        else:
            num_steps = int(np.rint((
                self.mw_stop - self.mw_start)/self.mw_step
                ))
            end_freq = self.mw_start + num_steps * self.mw_step
            self.freq_list = np.linspace(self.mw_start, end_freq, num_steps + 1)
            
            N = len(self.freq_list) #nb of freq points
            self.esr_line = np.zeros((N, 2))
            self.esr_line[:,0] = self.freq_list
            self.esr_line[:,1] = data[0]
            indmin = np.argmin(data[0])
            

            # write the raw topography counts
            self.pl_image[self.line_position[1], self.line_position[0],
                          7] = self.z_scanner_range - self.coeff_topo*np.mean(data[1])
            # write the corrected topography counts
            self.pl_image[self.line_position[1], self.line_position[0],
                          2] += self.z_scanner_range - self.coeff_topo*np.mean(data[1])-self.topo_corr[self.line_position[1], self.line_position[0]]

            # write ESR's min frequency
            self.pl_image[self.line_position[1], self.line_position[0], 3] = self.freq_list[indmin]
            # save the ESR temporarily
            x = self.pl_image[self.line_position[1], self.line_position[0], 0]
            y = self.pl_image[self.line_position[1], self.line_position[0], 0]
            freq_esr_list = np.append([x,y], self.freq_list)
            freq_esr_list = np.reshape(np.append(freq_esr_list, data[0]), (1, len(freq_esr_list)+len(data[0])))
            np.savetxt(self.temp, freq_esr_list)

            # write the pldiff counts
            self.pl_image[self.line_position[1], self.line_position[0],
                          4] = data_isob[0][0] - data_isob[0][1]
            # write counts for pl1
            self.pl_image[self.line_position[1], self.line_position[0],
                          5] = data_isob[0][0]
            # write counts for pl1
            self.pl_image[self.line_position[1], self.line_position[0],
                          6] = data_isob[0][1]
       
            # select the ESR's minimum
            freq_min = self.freq_list[indmin]
            minfield = self.min_fullb
            maxfield = self.max_fullb

            if freq_min <= minfield or freq_min >= maxfield:
                # only keep values in the right interval and select the minimum
                indices = [i for i in range(len(self.freq_list))
                           if self.freq_list[i] <= maxfield and self.freq_list[i] >=minfield]
                esr_interval = np.array([data[0][i] for i in indices])
                freq_min = self.freq_list[indices[np.argmin(esr_interval)]] 
            
            #track the minimum
            self.mw_start = freq_min - (self.freq_list[-1] - self.freq_list[0])/2
            self.mw_stop = freq_min + (self.freq_list[-1] - self.freq_list[0])/2
            
            # we do the updates manually, otherwise too many signals and it freezes
            self._odmr_logic.mw_start = self.mw_start
            self._odmr_logic.mw_stop = self.mw_stop
            
            if self.resonance_frequency -  freq_min < self.threshold:
                self._odmr_logic.mw_step = self.mw_step
            else:
                self._odmr_logic.mw_step = self.mw_step_hf
                
            self.line_number = int(np.rint((self._odmr_logic.mw_stop - self._odmr_logic.mw_start) \
                                       / self._odmr_logic.mw_step))+1
            self.odmr_raw_data = np.zeros([len(self.get_odmr_channels()), self.line_number])    
                                           
        self.sigFinishedDataTreatment.emit()
        return
    
    
    def move_after_scan_pixel(self):
        """
        Launched at the end of treat_data, moves to next pixel.
        """
        if self.scan_mode == "_hpix":
            f = Thread(target=self._hpix_end)
            f.start()
        else:
            f = Thread(target=self._vpix_end)
            f.start()               
        return
            

    def scan_pixel(self):
        """ Scan the current pixel
        """
        if self.meas_mode == "quenching":
            if self.scan_mode == "_hpix":
                lsx = self.pl_image[self.line_position[1], self.line_position[0]:self.line_position[0]+2, 0]
                lsy = self.pl_image[self.line_position[1], self.line_position[0]:self.line_position[0]+2, 1]
            else:
                lsx = self.pl_image[self.line_position[1]:self.line_position[1]+2, self.line_position[0], 0]
                lsy = self.pl_image[self.line_position[1]:self.line_position[1]+2, self.line_position[0], 1]
            line = np.vstack([lsx, lsy])
            # get the data from counter
            # we do not use a line, we scan 2px per 2px
            # print("pl_image_x", self.pl_image[:,:,0])
            # print("pl_image_y", self.pl_image[:,:,1])
            # print("line", self.line_position, line)
            data = self._scanning_device.scan_line(line, pixel_clock=True)
            data_isob = np.zeros(1)
            
        elif self.meas_mode == "isob":
            # data[0] is the PL, data[1] is the topo (one topo pt for each freq)
            # we go px per px, we do not care about horizontal or vertical
            data = self.scan_odmr_line()
            data_isob = np.zeros(1)
                      
        else: # fullb
            self.line_number = int(np.rint((self._odmr_logic.mw_stop - self._odmr_logic.mw_start) \
                                       / self._odmr_logic.mw_step))+1
            data = self.scan_odmr_line()
            if len(data[0]) == 2:
                self.set_sweep_parameters_fullb(self.mw_start, self.mw_stop, self.min_fullb, 
                                           self.max_fullb, self.mw_step, self.mw_step_hf, self.threshold)
                data = self.scan_odmr_line()
            # do an iso-B scan
            self.line_number = 2
            self._odmr_logic.mw_stop = self.freq2
            self._odmr_logic.mw_start = self.freq1
            self._odmr_logic.mw_step = self.freq2 - self.freq1
            data_isob = self.scan_odmr_line()
            # sets back the correct settings
            self._odmr_logic.mw_start = self.mw_start
            self._odmr_logic.mw_step = self.mw_step
            self._odmr_logic.mw_stop = self.mw_stop

        self.sigScanPixelOver.emit(data, data_isob)
        return 

    def _hpix(self):
        """ Scanning pixel per pixel horizontally
        """ 
        try:
             # need a thread here to avoid that python freezes
            f = Thread(target=self.scan_pixel)
            f.start()
        except:
            self.log.exception('The scan went wrong, killing the scanner.')
            self.stop_scanning()
            self.sigNextLine.emit()
        return  0
        
    def _hpix_end(self):
        """ Scanning pixel per pixel horizontally.
        """
        try:
            # prepare the scanline
            n = int(self.scanline_size/2)
            for i in range(n):
                    self.scanline[:, 2*i:2*(i+1)] = self.pl_image[self.line_position[1], :, 0:3+i:2+i]
                    np.place(self.scanline[:,2*i+1], self.scanline[:,2*i+1]==0, self.mean_pl[:, i])
                
                
            self.sigPlotsUpdated.emit(self.pl_image, self.scanline, self.esr_line)
            
            # return scanner to the start of the next line or stop the scan if we reach the limit
            self.line_position[0] += self.incr # quenching +2, others +1
            if self.line_position[0] >= np.size(self._X):
                # end of line
                self.line_position[0] = 0
                self.line_position[1] += 1 
                # we reach the limits, stop the scan
                if self.line_position[1] >= np.size(self._Y):
                    
                    self.stop_scanning(end=True)
                    self.log.info("Reached end of scan")
                    self.line_position = [0, 0]
                    self.sigNextLine.emit()
                    return 0
                self.return_h()
                
                for i in range(n):
                    # save the mean value for the next line
                    self.mean_pl[:, i] = np.mean(self.scanline[:,2*i+1])
   
            self.sigNextLine.emit()
                
        except:
            self.log.exception('The scan went wrong, killing the scanner.')
            self.stop_scanning()
            self.sigNextLine.emit()
            
        return 0


    def _vpix(self):
        """ Scanning pixel per pixel vertically
        """ 
        try:
             # need a thread here to avoid that python freezes
            f = Thread(target=self.scan_pixel)
            f.start()
        except:
            self.log.exception('The scan went wrong, killing the scanner.')
            self.stop_scanning()
            self.sigNextLine.emit()
        return  0
    
    def _vpix_end(self):
        """ Scanning pixel per pixel vertically
        """ 
        try:    
            # prepare the scanline
            n = int(self.scanline_size/2)
            for i in range(n):
                self.scanline[:, 2*i:2*(i+1)] = self.pl_image[:, self.line_position[0], 1:3+i:1+i]
                np.place(self.scanline[:,2*i+1], self.scanline[:,2*i+1]==0, self.mean_pl[:, i])

            self.sigPlotsUpdated.emit(self.pl_image, self.scanline, self.esr_line) 
        
            # return scanner to the start of the next line or stop the scan if we reach the limit
            self.line_position[1] += self.incr # +2 for quenching, +1 for others
            
            if self.line_position[1] >= np.size(self._Y):
                self.line_position[1] = 0
                self.line_position[0] += 1
                
                # we reach the limits, stop the scan
                if self.line_position[0] >= np.size(self._X):
                    self.stop_scanning(end=True)
                    self.line_position = [0, 0]
                    self.sigNextLine.emit()
                    return 0
                self.return_v()
                for i in range(n):
                    self.mean_pl[:, i] = np.mean(self.scanline[:,2*i+1])
   
            self.sigNextLine.emit()
                
        except:
            self.log.exception('The scan went wrong, killing the scanner.')
            self.stop_scanning()
            self.sigNextLine.emit()
            
        return 0
    
    
    def compute_scan_duration(self):
        """ Evaluate the duration of a scan to display it.

        @return str: the str to display the duration 
        """
        if self.meas_mode == "quenching":
            fwd = self.resolution[0]*self.resolution[1]/self.clock_frequency
        elif self.meas_mode == "isob":
            fwd = 2*self.resolution[0]*self.resolution[1]/self.clock_frequency
        else:
            fwd = (2+self.line_number)*self.resolution[0]*self.resolution[1]/self.clock_frequency

        if self.scan_mode == "_hpix":
            hrange = self.range[0][1] - self.range[0][0]
            bwd = self.resolution[1]*(hrange/self.return_slowness)/self.clock_frequency
        else:
            vrange = self.range[1][1] - self.range[1][0]
            bwd = self.resolution[0]*(vrange/self.return_slowness)/self.clock_frequency
            
        self.duration = 1.8*(fwd+bwd) # empirical factor, might need to be changed    
        displaystr = self.format_time(self.duration)
        return displaystr    
    

    def format_time(self, duration):
        """ Convert a nb a seconds in a nice str to display """
        minutes = int(duration/60)
        if minutes == 0:
            displaystr = "{:d} s".format(int(duration))
        else:
            hours = int(minutes/60)
            if hours == 0:
                displaystr = "{:d} min, {:d} s".format(minutes, int(np.round(duration-minutes*60)))
            else:
                displaystr = "{:d} h, {:d} min, {:d} s".format(hours, minutes-hours*60,
                                                               int(round(duration-minutes*60-hours*60)))
        return displaystr
    
    # Equation of a plane from 2 array of coordinates x,y
    def plane(self, x, y, a, b, c):
        return a*x+b*y+c


    # Compute the difference between a 2D array zz and the plane
    # with parameters a, b, c in params
    def errorfunc_plane(self, params, *args):
        zz = args[0]
        xx = args[1]
        yy = args[2]
        out = zz-self.plane(xx, yy, *params)
        return out.flatten()


    def plane_fit(self):
        """
        Data correction function. Fits a plane to the data and subtracts it.
        ----
        Input parameters:
        ----
        array: the 2D-ndarray to correct
        ----
        Output:
        ----
        array, after subtraction of the fitted plane
        """
        # pb with incomplete pictures,
        # we need to fit only the part containing data.
        
        if self.scan_mode == "_hpix":
            topo = self.pl_image[:self.line_position[1]-1,:,2]
            print('line pos', format(self.line_position[1]))
            print('topo shape', np.shape(topo))
        else:
            topo = self.pl_image[:,:self.line_position[0]-1,2]
            print('line pos', format(self.line_position[0]))
            print('topo shape', np.shape(topo))

        N = np.size(topo, axis=0)
        M = np.size(topo, axis=1)
        xx, yy = np.meshgrid(np.arange(M), np.arange(N))
        result = leastsq(self.errorfunc_plane, [1, 1, 1], args=(topo, xx, yy))
        pfit = result[0]
        
        # substract the fitted plane to all the topo        
        xx, yy = np.meshgrid(np.arange(self.resolution[0]), np.arange(self.resolution[1]))
        topo_corr = self.plane(xx, yy, *pfit)

        return topo_corr

    def correct_topo(self, corr_fc):
        """ Apply a plane fit correction to the topo"""
        self.corr_fct = corr_fc
        function_name = getattr(self, self.corr_fct, None)
        self.topo_corr = function_name()
        
        self.pl_image[:,:,2] -= self.topo_corr
        
        if self.scan_mode == "_hpix":
            self.pl_image[self.line_position[1]+1:,:,2]=0
            self.pl_image[self.line_position[1]:,self.line_position[0],2]=0
        else:
            self.pl_image[:,self.line_position[0]+1:,2]=0
            self.pl_image[self.line_position[1]:,self.line_position[0],2]=0
        
        

        self.sigPlotsUpdated.emit(self.pl_image, self.scanline, self.esr_line)
        return 0


    def save_data(self, colorscale_ranges=None):
        """ Save the current data to file.

        Two files are created for each channel, except full B.  The first is the imagedata,
        which has a text-matrix of count values corresponding to the pixel matrix of the image.
        Only count-values are saved here.

        The second file saves the full raw data with x, y, and counts at every pixel.

        A figure is also saved.

        @param: dict colorscale_ranges (optional) A dict of ranges [min, max] of the display
        colour scale (for the figure), with the keys "Topo", "PL", "PL1", "PL2", "PLdiff" and
        "Freq" depending on the scanning mode.
        """
        if self.meas_mode == "quenching":
            saved_scans = ["Topo", "PL", "RawTopo"]
        elif self.meas_mode == "isob":
            saved_scans = ["Topo", "PLdiff", "PL1", "PL2", "RawTopo"]
        else:
            saved_scans = ["Topo", "Freq", "PLdiff", "PL1", "PL2", "RawTopo"]
        
        timestamp = datetime.datetime.now()
        # Prepare the metadata parameters (common to all saved files):
        parameters = OrderedDict()
        
        parameters['Comment'] = self.user_comment

        parameters['X center position (m)'] = self.center_position[0]
        parameters['X image range (m)'] = self.range[0][1] - self.range[0][0]

        parameters['Y center position (m)'] = self.center_position[0]
        parameters['Y image range (m)'] = self.range[1][1] - self.range[1][0]

        parameters['X resolution (px)'] = self.resolution[0]
        parameters['Y resolution (px)'] = self.resolution[1]

        parameters['Measurement time (s)'] = 1.0/self.clock_frequency
        parameters['Return Slowness (Step size during retrace line)'] = self.return_slowness
        
        if self.scan_mode == "_hpix": 
            parameters['Scan mode'] = "Horizontal"
        else:
            parameters['Scan mode'] = "Vertical"
        
        if self.meas_mode == "isob":
            parameters['RF power (dBm)'] = self._odmr_logic.sweep_mw_power 
            parameters['IsoB frequency 1 (MHz)'] = 1e-6*self.freq1
            parameters['IsoB frequency 2 (MHz)'] = 1e-6*self.freq2
            
        elif self.meas_mode == "fullb":
            parameters['RF power (dBm)'] = self._odmr_logic.sweep_mw_power 
            parameters['IsoB frequency 1 (MHz)'] = 1e-6*self.freq1
            parameters['IsoB frequency 2 (MHz)'] = 1e-6*self.freq2
            parameters['Full B start frequency (MHz)'] = 1e6*self._odmr_logic.mw_start
            parameters['Full B stop frequency (MHz)'] = 1e6*self._odmr_logic.mw_stop
            parameters['Full B step frequency (MHz)'] = 1e6*self._odmr_logic.mw_step
            parameters['Number of sweeps'] = self.number_sweeps
       
        # Prepare a figure to be saved
        image_extent = [self.range[0][0],
                        self.range[0][1],
                        self.range[1][0],
                        self.range[1][1]]
        axes = ['X', 'Y']
        
        figs = {}
        for n in range(len(saved_scans)):
            ch = saved_scans[n]
            figs[ch]=self.draw_figure(data=self.pl_image[:, :, 2 + n],
                                     image_extent=image_extent,
                                     data_type=ch,
                                     scan_axis=axes)
            ch = saved_scans[n]
            # data for the text-array "image":
            image_data = OrderedDict()
            image_data["2D image"] = self.pl_image[:, :, 2 + n]

            filelabel = '{}_image_{}'.format(self.meas_mode, ch.replace('/', ''))
            # if the user entered a tag, adds it
            if self.user_save_tag != "":
                filelabel = filelabel + "_" + self.user_save_tag
            self._save_logic.save_data(image_data,
                                       filepath=None,
                                       timestamp=timestamp,
                                       parameters=parameters,
                                       filelabel=filelabel,
                                       fmt='%.6e',
                                       delimiter='\t',
                                       plotfig=figs[ch])


        # prepare the full raw data in an OrderedDict:
        data = OrderedDict()
        data['x position (m)'] = self.pl_image[:, :, 0].flatten()
        data['y position (m)'] = self.pl_image[:, :, 1].flatten()

        for n in range(len(saved_scans)):
            ch = saved_scans[n]
            data['value {0}'.format(ch)] = self.pl_image[:, :, 2 + n].flatten()

        # Save the raw data to file
        filelabel = '{}_data'.format(self.meas_mode)
        # if the user entered a tag, adds it
        if self.user_save_tag != "":
            filelabel = filelabel + "_" + self.user_save_tag
        self._save_logic.save_data(data,
                                   filepath=None,
                                   timestamp=timestamp,
                                   parameters=parameters,
                                   filelabel=filelabel,
                                   fmt='%.6e',
                                   delimiter='\t')

        # if fullB, save the spectra
        if self.meas_mode == "fullb":
            self.temp.seek(0)
            spdat=[x.split() for x in self.temp.readlines()]
            spdat = np.asarray(spdat)
            spdat = spdat.astype(np.float)
            #spdat = np.loadtxt(self.temp)
#            nb_pts = np.size(self.pl_image, axis=2)-7
#            spdat = np.zeros((len(data["x position (m)"]), 2+nb_pts))
#            spdat[:, 0] = data["x position (m)"]
#            spdat[:, 1] = data["y position (m)"]
#            for i in range(nb_pts):
#                spdat[:, i+2] = self.pl_image[:, :, i+7].flatten()
            spectra = {"x position (m), y position (m), spectra (freq in Hz, PL in counts/s)": spdat}
            filelabel = 'fullB_spectra'
            # if the user entered a tag, adds it
            if self.user_save_tag != "":
                filelabel = filelabel + "_" + self.user_save_tag
            self._save_logic.save_data(spectra,
                                   filepath=None,
                                   timestamp=timestamp,
                                   parameters=parameters,
                                   filelabel=filelabel,
                                   fmt='%.6e',
                                   delimiter='\t')
        
        self.log.info('Data saved.')
        
        return


    def draw_figure(self, data, image_extent, data_type, scan_axis=None, cbar_range=None):
        """ Create a 2-D color map figure of the scan image.

        @param: array data: The NxM array of count values from a scan with NxM pixels.

        @param: list image_extent: The scan range in the form [hor_min, hor_max, ver_min, ver_max]

        @param: str: "Topo" or "PL" or "PL1" or "PL2" or "PLdiff" or "Freq", to adjust the label

        @param: list axes: Names of the horizontal and vertical axes in the image

        @param: list cbar_range: (optional) [color_scale_min, color_scale_max].
        If not supplied then a default of data_min to data_max will be used.

        @return: fig fig: a matplotlib figure object to be saved to file.
        """
        if scan_axis is None:
            scan_axis = ['X', 'Y']

        # If no colorbar range was given, take full range of data
        if cbar_range is None:
            cbar_range = [np.min(data), np.max(data)]

        if data_type == "Topo" or data_type == "RawTopo":
            # Scale color values using SI prefix
            prefix = ['', 'm', 'µ', 'n', 'p', 'f']
            prefix_count = 0
            image_data = data
            draw_cb_range = np.array(cbar_range)
            image_dimension = image_extent.copy()

            while draw_cb_range[1] < 1000:
                image_data = image_data*1000
                draw_cb_range = draw_cb_range*1000
                prefix_count = prefix_count + 1

            c_prefix = prefix[prefix_count]
            c_map = "gray"
            colorbar_label = 'Topography (' + c_prefix + 'm)'

        else:
            # Scale color values using SI prefix
            prefix = ['', 'k', 'M', 'G']
            prefix_count = 0
            image_data = data
            draw_cb_range = np.array(cbar_range)
            image_dimension = image_extent.copy()

            while draw_cb_range[1] > 1000:
                image_data = image_data/1000
                draw_cb_range = draw_cb_range/1000
                prefix_count = prefix_count + 1

            c_prefix = prefix[prefix_count]
            
            if data_type in ["PL", "PL1", "PL2"]:
                c_map = "copper"
                colorbar_label = 'PL (' + c_prefix + 'counts/s)'
                
            elif data_type == "PLdiff":
                c_map = "bwr"
                colorbar_label = 'PLdiff (' + c_prefix + 'counts/s)'
                
            elif data_type == "Freq":
                c_map = "viridis"
                colorbar_label = 'Freq (' + c_prefix + 'Hz)'

        # Scale axes values using SI prefix
        axes_prefix = ['', 'm', r'$\mathrm{\mu}$', 'n']
        x_prefix_count = 0
        y_prefix_count = 0

        while np.abs(image_dimension[1]-image_dimension[0]) < 1:
            image_dimension[0] = image_dimension[0] * 1000.
            image_dimension[1] = image_dimension[1] * 1000.
            x_prefix_count = x_prefix_count + 1

        while np.abs(image_dimension[3] - image_dimension[2]) < 1:
            image_dimension[2] = image_dimension[2] * 1000.
            image_dimension[3] = image_dimension[3] * 1000.
            y_prefix_count = y_prefix_count + 1

        x_prefix = axes_prefix[x_prefix_count]
        y_prefix = axes_prefix[y_prefix_count]

        # Use qudi style
        plt.style.use(self._save_logic.mpl_qd_style)

        # Create figure
        fig, ax = plt.subplots()

        # Create image plot
        cfimage = ax.imshow(image_data,
                            cmap=c_map,
                            origin="lower",
                            vmin=draw_cb_range[0],
                            vmax=draw_cb_range[1],
                            interpolation='none',
                            extent=image_dimension
                            )

        ax.set_aspect(1)
        ax.set_xlabel(scan_axis[0] + ' position (' + x_prefix + 'm)')
        ax.set_ylabel(scan_axis[1] + ' position (' + y_prefix + 'm)')
        ax.spines['bottom'].set_position(('outward', 10))
        ax.spines['left'].set_position(('outward', 10))
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.get_xaxis().tick_bottom()
        ax.get_yaxis().tick_left()

        # Draw the colorbar
        cbar = plt.colorbar(cfimage, shrink=0.8)#, fraction=0.046, pad=0.08, shrink=0.75)
        cbar.set_label(colorbar_label)

        # remove ticks from colorbar for cleaner image
        cbar.ax.tick_params(which=u'both', length=0)

        return fig
