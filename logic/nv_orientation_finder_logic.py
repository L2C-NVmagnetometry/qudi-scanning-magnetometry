# -*- coding: utf-8 -*-
""" 
This module combines magnet control and ODMR logics.

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
from interface.microwave_interface import MicrowaveMode
import time
import datetime
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.module import Connector, ConfigOption, StatusVar
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge

def B_NV(B, theta, phi, theta_tip, phi_tip):
    return B*np.abs((np.cos(theta)*np.cos(theta_tip) + np.sin(theta)*np.sin(theta_tip)*np.cos(phi-phi_tip)))

class NVOrientationFinderLogic(GenericLogic):
    """ This is the logic class to find the NV orientation using a 3D magnet.
    """
    
    _modclass = 'nvorientationlogic'
    _modtype = 'logic'

    _magnet_type = ConfigOption("magnet_type", "coil") # otherwise "supra"
    
    # declare connectors
    microwave1 = Connector(interface='mwsourceinterface')
    savelogic = Connector(interface='SaveLogic')
    odmrlogic1 = Connector(interface='ODMRLogic')
    scmagnetlogic = Connector(interface='SuperConductingMagnetLogic')
    coilmagnetlogic = Connector(interface='CoilMagnetLogic')
    
    # Internal signals
    sigNextField = QtCore.Signal()
    sigContinueThetaPhi = QtCore.Signal()
    
    # Update signals, e.g. for GUI module
    sigUpdateCurrentField = QtCore.Signal(float, float, float)
    sigUpdateNextField = QtCore.Signal(float, float, float)
    sigUpdatePlotPhi = QtCore.Signal()
    sigUpdatePlotTheta = QtCore.Signal()
    sigUpdatePlotESR = QtCore.Signal()
    sigUpdateTimeESR = QtCore.Signal()
    sigUpdateSweepAngles = QtCore.Signal(str)
    sigSweepStarted = QtCore.Signal()
    sigSweepStopped = QtCore.Signal()
    
    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()
        
    def on_activate(self):
        """
        Initialisation performed during activation of the module.
        """
        # Get connectors
        self._mw_device = self.microwave1()
        self._save_logic = self.savelogic()
        self._odmr_logic = self.odmrlogic1()
        if self._magnet_type == "supra":
            self._magnet_logic = self.scmagnetlogic()
        else:
            self._magnet_logic = self.coilmagnetlogic()
        
        self.user_save_path = self._save_logic.get_path_for_module('NVorientation')

        self.stop_measurement = False
        self.pause_measurement = False
        self.theta_sweep_remaining = False
        self.theta_phi_measurement = False
        
        # ODMR parameters
        self.rf_power = 0 # in dBm
        self.av_time = 10 # in s, time per odmr scan
        self.start_freq = 2850e6 # in Hz
        self.stop_freq = 2890e6 # in Hz
        self.freq_step = 2e6 # in Hz

        self.init_start_freq = self.start_freq
        self.init_stop_freq = self.stop_freq
        
        self.tracked_resonance = "lower" # "lower" or "upper"

        self.field_ampl = 0 # in G
        self.nb_pts = 20
        self.field_list = np.arange(self.nb_pts)
        self.sweep_counter = -1

         # Data arrays for the ESR line
        self.freq_esr_range = np.arange(self.start_freq, self.stop_freq + self.freq_step, self.freq_step)
        self.pl_esr = np.zeros(len(self.freq_esr_range))
        self.freq_esr_range_fit = np.zeros(len(self.freq_esr_range))
        self.pl_esr_fit = np.zeros(len(self.freq_esr_range_fit))
        self.fit_esr_params = None
        
        # Data arrays for the phi sweep
        self.phi_sweep_index = np.linspace(0, 90, self.nb_pts)
        self.phi_sweep_freq = np.nan*np.ones(self.nb_pts)
        self.phi_sweep_freq_error = np.zeros(self.nb_pts)
        self.phi_sweep_fit = np.zeros(self.nb_pts)
        self.phi_sweep_full_data = np.zeros((self.nb_pts, 2*len(self.freq_esr_range)+1))

        # Data arrays for the theta sweep
        self.theta_sweep_index = np.linspace(0, 90, self.nb_pts)
        self.theta_sweep_freq = np.nan*np.ones(self.nb_pts)
        self.theta_sweep_freq_error = np.zeros(self.nb_pts)
        self.theta_sweep_fit = np.zeros(self.nb_pts)
        self.theta_sweep_full_data = np.zeros((self.nb_pts, 2*len(self.freq_esr_range)+1))

        self.theta_for_phi = 90 # value of theta during the phi sweep
        self.phi_for_theta = 0 # value of phi during the theta sweep

        self.fit_theta = None
        self.fit_phi = None
        self.phi0_phi_sweep = np.pi/4
        self.theta0_phi_sweep = np.pi/3
        self.phi0_theta_sweep = np.pi/4
        self.theta0_theta_sweep = np.pi/3
        self.use_guess_phi = False
        self.use_guess_theta = False

        
        self.sweep_angle = "theta" # or "phi"

        # connect signals
        self.sigNextField.connect(self.change_field)
        self.sigContinueThetaPhi.connect(self.continue_theta_phi)
        self._magnet_logic.sigFieldSet.connect(self.start_odmr_measurement)
        self._odmr_logic.sigOdmrElapsedTimeUpdated.connect(self.change_odmr_elapsed_time)
        self._odmr_logic.sigOdmrPlotsUpdated.connect(self.change_odmr_data)
        self._odmr_logic.sigOdmrFitUpdated.connect(self.get_odmr_fit)
        
        return 0
    
    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        # Stop measurement if it is still running
        if self.module_state() == 'locked':
            self.stop_measurement()
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
        
        # Disconnect signals
        return 0

    def update_pts_nb(self, nb, sweep="both"):
        """ Change the array sizes when updating the number of points 
        """
        self.nb_pts = nb
        if sweep == "both" or sweep == "phi":
            self.phi_sweep_index = np.linspace(0, 90, self.nb_pts)
            self.phi_sweep_freq = np.nan*np.ones(self.nb_pts)
            self.phi_sweep_freq_error = np.zeros(self.nb_pts)
            self.phi_sweep_fit = np.zeros(self.nb_pts)
            self.phi_sweep_full_data = np.zeros((self.nb_pts, 2*len(self.freq_esr_range)+1))
            self.fit_phi = None
        if sweep == "both" or sweep == "theta":
            self.theta_sweep_index = np.linspace(0, 90, self.nb_pts)
            self.theta_sweep_freq = np.nan*np.ones(self.nb_pts)
            self.theta_sweep_freq_error = np.zeros(self.nb_pts)
            self.theta_sweep_fit = np.zeros(self.nb_pts)
            self.theta_sweep_full_data = np.zeros((self.nb_pts, 2*len(self.freq_esr_range)+1))
            self.fit_theta = None
        return

    def B_from_theta_phi(self, theta, phi, ampl):
        """ From spherical to cartesian coords, ampl in G, theta, phi in deg. 
        """
        Bx = ampl*np.sin(theta*np.pi/180)*np.cos(phi*np.pi/180)
        By = ampl*np.sin(theta*np.pi/180)*np.sin(phi*np.pi/180)
        Bz = ampl*np.cos(theta*np.pi/180)
        return Bx, By, Bz

    def compute_field_list_phi_sweep(self):
        """ Computes the values of Bx, By, Bz to use during a phi sweep.
        """
        Bx, By, Bz = self.B_from_theta_phi(self.theta_for_phi*np.ones(self.nb_pts),
                                           self.phi_sweep_index, self.field_ampl)
        self.field_list_Bx = Bx
        self.field_list_By = By
        self.field_list_Bz = Bz
        return

    def compute_field_list_theta_sweep(self):
        """ Computes the values of Bx, By, Bz to use during a phi sweep.
        """
        Bx, By, Bz = self.B_from_theta_phi(self.theta_sweep_index, self.phi_for_theta*np.ones(self.nb_pts),
                                           self.field_ampl)
        self.field_list_Bx = Bx
        self.field_list_By = By
        self.field_list_Bz = Bz
        return

    def start_phi_sweep(self):
        """ Starts a phi sweep.
        """
        self.sigSweepStarted.emit()
        self.stop_measurement = False
        self.start_measurement = True
        self.update_pts_nb(self.nb_pts, sweep="phi")
        self.log.info("Start a phi sweep")
        self.sweep_angle = "phi"
        self.sweep_counter = -1
        self.freq_esr_range = np.arange(self.start_freq, self.stop_freq + self.freq_step, self.freq_step)
        self.phi_sweep_full_data = np.zeros((self.nb_pts, 2*len(self.freq_esr_range)+1))
        #print("start phi sweep", np.shape(self.freq_esr_range), np.shape(self.phi_sweep_full_data))
        self.phi_sweep_index = np.linspace(0, 90, self.nb_pts)
        self.compute_field_list_phi_sweep()
        self.change_field()
        return

    def start_theta_sweep(self):
        """ Starts a theta sweep.
        """
        self.sigSweepStarted.emit()
        self.stop_measurement = False
        self.start_measurement = True
        self.update_pts_nb(self.nb_pts, sweep="theta")
        self.log.info("Start a theta sweep")
        self.sweep_angle = "theta"
        self.sweep_counter = -1
        self.start_freq = self.init_start_freq
        self.stop_freq = self.init_stop_freq
        self.freq_esr_range = np.arange(self.start_freq, self.stop_freq + self.freq_step, self.freq_step)
        self.theta_sweep_full_data = np.zeros((self.nb_pts, 2*len(self.freq_esr_range)+1))
        self.theta_sweep_index = np.linspace(0, 90, self.nb_pts)
        self.compute_field_list_theta_sweep()
        self.change_field()
        return

    def find_theta_phi(self):
        """ Starts a full phi and theta sweep.
        """
        self.theta_sweep_remaining = True
        self.theta_phi_measurement = True
        self.theta_for_phi = 90
        self.init_start_freq = self.start_freq
        self.init_stop_freq = self.stop_freq
        self.update_pts_nb(self.nb_pts)
        self.sigUpdateSweepAngles.emit("theta")
        self.start_phi_sweep()
        return
    
    def continue_theta_phi(self):
        """ Starts the theta sweep for the theta phi routine
        """
        # self.sigSweepStarted.emit()
        self.theta_sweep_remaining = False
        
        if np.abs(self.fit_phi["phi_tip"]) <= 90:
            self.phi_for_theta = self.fit_phi["phi_tip"]
        else:
            div = np.floor(np.abs(self.fit_phi["phi_tip"])/180)
            self.phi_for_theta = self.fit_phi["phi_tip"] - np.sign(self.fit_phi["phi_tip"])*div*180
            if self.phi_for_theta > 90:
                self.phi_for_theta = self.phi_for_theta - 180
            elif self.phi_for_theta < 90:
                self.phi_for_theta = self.phi_for_theta + 180

        self.sigUpdateSweepAngles.emit("phi")
        self.start_theta_sweep()
        return
    
    def stop_sweep(self):
        """ Stops the sweep.
        """
        self.stop_measurement = True
        self._odmr_logic.stopRequested = True
        return
    

    def apply_field(self, theta, phi, ampl):
        """ Apply a magnetic field
        """
        self.stop_measurement = True
        self.start_measurement = False
        Bx, By, Bz = self.B_from_theta_phi(theta, phi, ampl)
        self._magnet_logic.go_to_field(Bx, By, Bz)
        self.sigUpdateCurrentField.emit(Bx, By, Bz)
        return 0
    
    def change_field(self):
        """ Calls the magnet to change the field.
        """
        # checks if we reached the end of the sweep
        end = False
        if self.sweep_counter >= len(self.field_list_Bx)-1 or self.stop_measurement:
            # sweep over, go to zero field
            if not self.stop_measurement:
                end = True
                self.stop_measurement = True
            self.log.info("Ending the sweep.")
            self._magnet_logic.go_to_field(0, 0, 0)
            if self.theta_sweep_remaining and end and not self.pause_measurement:
                self.sigContinueThetaPhi.emit()
        elif self.pause_measurement:
            return
        else:
            # go to next field
            self.sweep_counter = self.sweep_counter + 1
            self._magnet_logic.go_to_field(self.field_list_Bx[self.sweep_counter],
                                           self.field_list_By[self.sweep_counter],
                                           self.field_list_Bz[self.sweep_counter])
        return

    def start_odmr_measurement(self):
        """ Calls the odmr logic to record a spectrum.
        """
        if not self.stop_measurement:
            self.sigUpdateCurrentField.emit(self.field_list_Bx[self.sweep_counter],
                                            self.field_list_By[self.sweep_counter],
                                            self.field_list_Bz[self.sweep_counter])
            if self.sweep_counter == len(self.field_list_Bx)-1:
                self.sigUpdateNextField.emit(0, 0, 0)
            else:             
                self.sigUpdateNextField.emit(self.field_list_Bx[self.sweep_counter+1],
                                             self.field_list_By[self.sweep_counter+1],
                                             self.field_list_Bz[self.sweep_counter+1])
                
            #self.update_freq_params()
            #self.log.info("Update frequency window")
            self._odmr_logic.set_runtime(self.av_time)
            
            test = np.arange(self.start_freq, self.stop_freq + self.freq_step, self.freq_step)
            if 2*len(test)+1 > np.size(self.freq_esr_range):
                self.stop_freq = self.stop_freq-1
            test = np.arange(self.start_freq, self.stop_freq + self.freq_step, self.freq_step)
            if 2*len(test)+1 < np.size(self.freq_esr_range):
                self.stop_freq = self.stop_freq+1
                
            self._odmr_logic.set_sweep_parameters(self.start_freq, self.stop_freq,
                                                  self.freq_step, self.rf_power)
            
            self._odmr_logic.start_odmr_scan()

        else:
            self.sigSweepStopped.emit()
            if self.start_measurement:
                self.sigUpdateCurrentField.emit(0, 0, 0)
                self.sigUpdateNextField.emit(np.nan, np.nan, np.nan)
        return

    def change_odmr_elapsed_time(self, elapsed_time, nb_sweeps):
        """ Change display of odmr elapsed time.
        """
        self.odmr_elapsed_time = elapsed_time
        self.sigUpdateTimeESR.emit()
        return

    def change_odmr_data(self, odmr_plot_x, odmr_plot_y, odmr_plot_xy):
        """ Update the odmr data and does the fit.
        """
        self.freq_esr_range = odmr_plot_x
        self.pl_esr = odmr_plot_y[0].flatten()
        self._odmr_logic.do_fit(fit_function="Lorentzian dip",
                                x_data=self.freq_esr_range,
                                y_data=self.pl_esr)
        return

    def get_odmr_fit(self, odmr_fit_x, odmr_fit_y, result, current_fit):
        """ Gets the fitting parameters and updates the sweep data.
        """
        self.freq_esr_range_fit = odmr_fit_x
        self.pl_esr_fit = odmr_fit_y
        self.fit_esr_params = result
        self.sigUpdatePlotESR.emit()
        
        # check if the ODMR measurement is over, if yes, save the data point and update the sweep plot
        if self.odmr_elapsed_time - self.av_time >= 0:
            #self.log.info("rem time {}".format(self.odmr_elapsed_time - self.av_time))
            if self.sweep_angle == "phi":
                phi = self.phi_sweep_index[self.sweep_counter]
                #print("store data phi", np.shape(self.phi_sweep_full_data), len(self.freq_esr_range)*2+1)
                self.phi_sweep_full_data[self.sweep_counter, :] = np.concatenate((np.array([phi]),
                                                                                  self.freq_esr_range,
                                                                                 self.pl_esr))
                self.phi_sweep_freq[self.sweep_counter] = self.fit_esr_params["Position"]['value']
                self.phi_sweep_freq_error[self.sweep_counter] = self.fit_esr_params["FWHM"]['value']
                
                if self.sweep_counter>=4: # if we have several points, we can try to fit
                    self.fit_phi_sweep()
                self.sigUpdatePlotPhi.emit()
            else:
                theta = self.theta_sweep_index[self.sweep_counter]
                self.theta_sweep_full_data[self.sweep_counter, :] = np.concatenate((np.array([theta]),
                                                                                    self.freq_esr_range,
                                                                                    self.pl_esr))
                #print("store data theta", np.shape(self.theta_sweep_full_data[self.sweep_counter, :]),
                #np.shape(np.concatenate((np.array([theta]), self.freq_esr_range, self.pl_esr))))
                self.theta_sweep_freq[self.sweep_counter] = self.fit_esr_params["Position"]['value']
                self.theta_sweep_freq_error[self.sweep_counter] = self.fit_esr_params["FWHM"]['value']
                
                if self.sweep_counter>=4: # if we have several points, we can try to fit
                    self.fit_theta_sweep()
                self.sigUpdatePlotTheta.emit()
            self.sigNextField.emit()
        return

    def fit_phi_sweep(self):
        """ Fits the current phi sweep to get the tip angles
        """
        phi_list = self.phi_sweep_index[:self.sweep_counter]
        freq_list = self.phi_sweep_freq[:self.sweep_counter]
        freq_err = self.phi_sweep_freq_error[:self.sweep_counter]
        func = lambda phi, B, theta_tip, phi_tip : B_NV(B, self.theta_for_phi*np.pi/180, phi,
                                                                theta_tip, phi_tip)+2.87e9
        try:
            if self.use_guess_phi:
                p0 = [np.max(freq_list)-np.min(freq_list), self.theta0_phi_sweep,
                      self.phi0_phi_sweep]
            else:
                p0 = [np.max(freq_list)-np.min(freq_list), np.pi/3, np.pi/3]
            popt, pcov = curve_fit(func, phi_list*np.pi/180, freq_list, p0=p0, sigma=freq_err)
            perr = np.sqrt(np.diag(pcov))
        
        
            self.phi_sweep_fit = func(self.phi_sweep_index*np.pi/180, *popt)
            self.fit_phi = {}
            self.fit_phi["f_ampl"] = popt[0]
            self.fit_phi["f_ampl_error"] = perr[0]
            self.fit_phi["theta_tip"] = popt[1]*180/np.pi
            self.fit_phi["theta_tip_error"] = perr[1]*180/np.pi
            self.fit_phi["phi_tip"] = popt[2]*180/np.pi
            self.fit_phi["phi_tip_error"] = perr[2]*180/np.pi
        except:
            self.log.info("Fit failed")
        return

    def fit_theta_sweep(self):
        """ Fits the current theta sweep to get the tip angles
        """
        theta_list = self.theta_sweep_index[:self.sweep_counter]
        freq_list = self.theta_sweep_freq[:self.sweep_counter]
        freq_err = self.theta_sweep_freq_error[:self.sweep_counter]
        self.fit_theta = {}
        print("theta_phi_measurement", self.theta_phi_measurement)
        if self.theta_phi_measurement:
            try:
                func = lambda theta, B, theta_tip : B_NV(B, theta, self.phi_for_theta*np.pi/180,
                                                             theta_tip, self.phi_for_theta*np.pi/180)+2.87e9
                if self.use_guess_theta:
                    p0 = [np.max(freq_list)-np.min(freq_list), self.theta0_theta_sweep]
                else:
                    p0 = [np.max(freq_list)-np.min(freq_list), np.pi/3]

                popt, pcov = curve_fit(func, theta_list, freq_list, p0=p0, sigma=freq_err)
                perr = np.sqrt(np.diag(pcov))
                self.fit_theta["phi_tip"] = self.phi_for_theta
                self.fit_theta["phi_tip_error"] = self.fit_phi["phi_tip_error"]
            except:
                self.log.info("Fit failed")
        else:
            try:
                func = lambda theta, B, theta_tip, phi_tip : B_NV(B, theta,
                                                                 self.phi_for_theta*np.pi/180,
                                                                 theta_tip, phi_tip)+2.87e9
                if self.use_guess_theta:
                    p0 = [np.max(freq_list)-np.min(freq_list), self.theta0_theta_sweep,
                          self.phi0_theta_sweep]
                else:
                    p0 = [np.max(freq_list)-np.min(freq_list), np.pi/3, np.pi/3]
                popt, pcov = curve_fit(func, theta_list*np.pi/180, freq_list, p0=p0, sigma=freq_err)
                perr = np.sqrt(np.diag(pcov))
                self.fit_theta["phi_tip"] = popt[2]*180/np.pi
                self.fit_theta["phi_tip_error"] = perr[2]*180/np.pi
                self.fit_theta["offset"] = popt[3]
            except:
                self.log.info("Fit failed")

        try:
            self.theta_sweep_fit = func(self.theta_sweep_index*np.pi/180, *popt)
            self.fit_theta["f_ampl"] = popt[0]
            self.fit_theta["f_ampl_error"] = perr[0]
            self.fit_theta["theta_tip"] = popt[1]*180/np.pi
            self.fit_theta["theta_tip_error"] = perr[1]*180/np.pi
        except:
            pass
        return

    def update_freq_params(self):
        """ Shifts the frequency window to keep the resonance in the center. 
        """
        if self.sweep_counter > 0:
            center = 0.5*(self.stop_freq - self.start_freq) + self.start_freq
            if self.sweep_angle == "phi":
                try:
                    peak_pos = self.phi_sweep_freq[self.sweep_counter-1]
                    shift = peak_pos-center
                except:
                    shift = 0                 
            else:
                try:
                    peak_pos = self.theta_sweep_freq[self.sweep_counter-1]
                    shift = peak_pos-center
                except:
                    shift = 0
        else:
            shift=0
        self.start_freq = self.start_freq + shift
        self.stop_freq = self.stop_freq + shift
        return

    def draw_figure(self, sweeped_angle):
        """ Prepares the plot for saving.
        """
        # Prepare the figure to save as a "data thumbnail"
        plt.style.use(self._save_logic.mpl_qd_style)

        # extract the possible colors from the colorscheme:
        prop_cycle = self._save_logic.mpl_qd_style['axes.prop_cycle']
        colors = {}
        for i, color_setting in enumerate(prop_cycle):
            colors[i] = color_setting['color']

        if sweeped_angle == "phi":
            x_to_plot = self.phi_sweep_index
            data_to_plot = self.phi_sweep_freq*1e-6
            fit_to_plot = self.phi_sweep_fit*1e-6
            err_to_plot = self.phi_sweep_freq_error*1e-6
            xlabel = "phi (°)"
            fit_res = self.fit_phi["phi_tip"]
        else:
            x_to_plot = self.theta_sweep_index
            data_to_plot = self.theta_sweep_freq*1e-6
            fit_to_plot = self.theta_sweep_fit*1e-6
            err_to_plot = self.theta_sweep_freq_error*1e-6
            xlabel = "theta (°)"
            fit_res = self.fit_phi["theta_tip"]
            
        fig, ax = plt.subplots()
        ax.errorbar(x=x_to_plot, y=data_to_plot, yerr=err_to_plot, fmt='-o',
                    linestyle=':', linewidth=0.5, color=colors[0], ecolor=colors[1], capsize=3,
                    capthick=0.9, elinewidth=1.2, label='data')
        ax.plot(x_to_plot, fit_to_plot, color=colors[2], marker='None', linewidth=1.5,
                label='fit, {:s} tip = {:f} °'.format(sweeped_angle, fit_res))
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Frequency (MHz)")
        fig.tight_layout()
        ax.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, ncol=2,
                   mode="expand", borderaxespad=0.)
        
        return fig
    
    def save_data(self, file_tag, comment):
        """ Save the current data to several files. One file for the PL vs phi and the PL vs theta data,
        one file for the full phi sweep data with ESR spectra, idem for a theta sweep. Also saves a figure
        with the two plots for the theta and phi sweeps.  
        """
        filepath = self._save_logic.get_path_for_module('NVorientation')
        timestamp =  datetime.datetime.now()
        # Prepare the metadata parameters (common to all saved files):
        parameters = OrderedDict()

        parameters["Field amplitude (G)"] = self.field_ampl
        parameters["Number of field values per sweep"] = self.nb_pts
        parameters["Resonance tracked"] = self.tracked_resonance
        parameters["Phi value during theta sweep (deg)"] = self.phi_for_theta
        parameters["Theta value during phi sweep (deg)"] = self.theta_for_phi
        parameters["RF power (dBm)"] = self.rf_power
        parameters["RF frequency step (MHz)"] = self.freq_step*1e-6
        parameters["RF initial start frequency (MHz)"] = self.start_freq*1e-6
        parameters["RF initial stop frequency (MHz)"] = self.stop_freq*1e-6
        parameters["ODMR averaging time (s)"] = self.av_time
        parameters["Comment"] = comment

        figphi = self.draw_figure("phi")
        figtheta = self.draw_figure("theta")

        phi_sweep_data = OrderedDict()
        phi_sweep_data["phi angle (deg)"] = self.phi_sweep_index
        phi_sweep_data["resonance frequency (Hz)"] = self.phi_sweep_freq
        phi_sweep_data["resonance frequency error (Hz)"] = self.phi_sweep_freq_error
        filelabel = file_tag + "_analyzed_phi_sweep"
        
        self._save_logic.save_data(phi_sweep_data, filepath=filepath,
                                   timestamp=timestamp, parameters=parameters,
                                   filelabel=filelabel, fmt="%d", delimiter="\t",
                                   plotfig=figphi)

        theta_sweep_data = OrderedDict()
        theta_sweep_data["theta angle (deg)"] = self.theta_sweep_index
        theta_sweep_data["resonance frequency (Hz)"] = self.theta_sweep_freq
        theta_sweep_data["resonance frequency error (Hz)"] = self.theta_sweep_freq_error
        filelabel = file_tag + "_analyzed_theta_sweep"
        
        self._save_logic.save_data(theta_sweep_data, filepath=filepath, timestamp=timestamp,
                                   parameters=parameters, filelabel=filelabel, fmt="%d",
                                   delimiter="\t", plotfig=figtheta)

        raw_data_phi = OrderedDict()
        raw_data_phi["Raw data phi sweep (phi(deg) frequencies(Hz) PLcounts)"] = self.phi_sweep_full_data
        filelabel = file_tag + "_raw_phi_sweep"
        self._save_logic.save_data(raw_data_phi, filepath=filepath, timestamp=timestamp,
                                   parameters=parameters, filelabel=filelabel, fmt="%d",
                                   delimiter="\t")

        raw_data_theta = OrderedDict()
        raw_data_theta["Raw data theta sweep (theta(deg) frequencies(Hz) PLcounts)"] = self.theta_sweep_full_data
        filelabel = file_tag + "_raw_theta_sweep"
        self._save_logic.save_data(raw_data_theta, filepath=filepath, timestamp=timestamp,
                                   parameters=parameters, filelabel=filelabel, fmt="%d",
                                   delimiter="\t")
        
        return
