# -*- coding: utf-8 -*-
"""
This file contains the Qudi GUI for iso-b scan.

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
import os

import numpy as np
import pyqtgraph as pg

from core.module import Connector
from gui.guibase import GUIBase
from gui.guiutils import ColorBar, CrossLine, CrossROI
import gui.colordefs as cdef
from gui.colordefs import QudiPalettePale as palette
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy import uic

class NVOrientationFinderMainWindow(QtWidgets.QMainWindow):
    """ The main window for the NV orientation finder.
    """
    
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_nv_orientation_findergui.ui')

        # Load it
        super(NVOrientationFinderMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()
        
class NVOrientationFinderGUI(GUIBase):
    """ This is the GUI class for the NV orientation finder.
    """
    
    _modclass = 'NVOrientationFinderGui'
    _modtype = 'gui'
    
    # declare connectors
    nvorientationfinderlogic = Connector(interface='NVOrientationFinderLogic')
    #odmrlogic1 = Connector(interface='OdmrLogic')
    
    # declare signals
    sigStartPhiSweep = QtCore.Signal()
    sigStartThetaSweep = QtCore.Signal()
    sigFindThetaPhi = QtCore.Signal()
    sigStopSweep = QtCore.Signal()
    sigUpdatePtsNb = QtCore.Signal(int)
    sigResumeMeasurement = QtCore.Signal()
    
    
    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        
    def on_activate(self):
        """ Definition, configuration and initialisation of the nv orientation finder GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        """
        self._orientation_logic = self.nvorientationfinderlogic()
        #self._odmr_logic = self.odmrlogic1()
        
        ########################################################################
        #                      General configurations                          #
        ########################################################################
        
        # use the inherited class 'Ui_CryoMonitoringGuiUI' to create now the GUI element:
        self._mw = NVOrientationFinderMainWindow()

        self._mw.comboBox_lower_upper.addItems(["lower", "upper"])


        ########################################################################
        #                          Connect signals                             #
        ########################################################################
        
        # interaction with user

        self._mw.doubleSpinBox_field_ampl.valueChanged.connect(self.set_field_ampl)
        self._mw.spinBox_nb_pts.valueChanged.connect(self.set_nb_pts)
        
        self._mw.pushButton_find_theta_phi.clicked.connect(self.start_find_theta_phi)
        self._mw.pushButton_sweep_theta.clicked.connect(self.start_sweep_theta)
        self._mw.pushButton_sweep_phi.clicked.connect(self.start_sweep_phi)
        self._mw.pushButton_stop.clicked.connect(self.stop_sweep)

        self._mw.pushButton_apply_field.clicked.connect(self.apply_field)      
        self._mw.pushButton_pause.clicked.connect(self.pause_resume_sweep)


        self._mw.doubleSpinBox_RF_power.valueChanged.connect(self.set_rf_power)
        self._mw.doubleSpinBox_av_time.valueChanged.connect(self.set_averaging_time) # time per pt
        self._mw.doubleSpinBox_start_freq.valueChanged.connect(self.set_start_freq)
        self._mw.doubleSpinBox_stop_freq.valueChanged.connect(self.set_stop_freq)
        self._mw.doubleSpinBox_step_freq.valueChanged.connect(self.set_step_freq)
        self._mw.comboBox_lower_upper.currentIndexChanged.connect(self.change_tracked_resonance)
        
        self._mw.doubleSpinBox_theta_for_phi_sweep.valueChanged.connect(self.set_theta_for_phi_sweep)
        self._mw.doubleSpinBox_phi_for_theta_sweep.valueChanged.connect(self.set_phi_for_theta_sweep)

        self._mw.checkBox_fit_phi_sweep.toggled.connect(self.display_phi_sweep_fit)
        self._mw.checkBox_fit_theta_sweep.toggled.connect(self.display_theta_sweep_fit)

        self._mw.doubleSpinBox_theta0_phi_sweep.valueChanged.connect(self.set_fitting_guess)
        self._mw.doubleSpinBox_theta0_theta_sweep.valueChanged.connect(self.set_fitting_guess)
        self._mw.doubleSpinBox_phi0_phi_sweep.valueChanged.connect(self.set_fitting_guess)
        self._mw.doubleSpinBox_phi0_theta_sweep.valueChanged.connect(self.set_fitting_guess)
        self._mw.checkBox_fit_guess_phi.toggled.connect(self.set_fitting_guess)
        self._mw.checkBox_fit_guess_theta.toggled.connect(self.set_fitting_guess)
                
        self._mw.actionSave.triggered.connect(self.save_routine)

        # signals from logic

        self._orientation_logic.sigUpdateCurrentField.connect(self.update_current_field)
        self._orientation_logic.sigUpdateNextField.connect(self.update_next_field)
        self._orientation_logic.sigUpdatePlotPhi.connect(self.refresh_plot_phi_sweep)
        self._orientation_logic.sigUpdatePlotTheta.connect(self.refresh_plot_theta_sweep)
        self._orientation_logic.sigUpdatePlotESR.connect(self.refresh_plot_esr)
        self._orientation_logic.sigUpdateTimeESR.connect(self.refresh_esr_time)
        self._orientation_logic.sigSweepStarted.connect(self.disable_buttons)
        self._orientation_logic.sigSweepStopped.connect(self.enable_buttons)
        self._orientation_logic.sigUpdateSweepAngles.connect(self.changed_sweep_angle)

        # signals to logic
        self.sigStopSweep.connect(self._orientation_logic.stop_sweep)
        self.sigStartPhiSweep.connect(self._orientation_logic.start_phi_sweep)
        self.sigStartThetaSweep.connect(self._orientation_logic.start_theta_sweep)
        self.sigFindThetaPhi.connect(self._orientation_logic.find_theta_phi)
        self.sigUpdatePtsNb.connect(self._orientation_logic.update_pts_nb)
        self.sigResumeMeasurement.connect(self._orientation_logic.change_field)
        
        ########################################################################
        #                          Load displays                               #
        ########################################################################
        self._mw.spinBox_nb_pts.setValue(20)
        self._mw.doubleSpinBox_theta_for_phi_sweep.setValue(90)
        self._mw.doubleSpinBox_phi_for_theta_sweep.setValue(0)
        
        self.phi_sweep_plot = pg.PlotDataItem(self._orientation_logic.phi_sweep_index,
                                              self._orientation_logic.phi_sweep_freq,
                                              pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                              symbol='o',
                                              symbolPen=palette.c1,
                                              symbolBrush=palette.c1,
                                              symbolSize=7)
        self.phi_sweep_error = pg.ErrorBarItem(x=self._orientation_logic.phi_sweep_index,
                                               y=self._orientation_logic.phi_sweep_freq,
                                               height=self._orientation_logic.phi_sweep_freq_error,
                                               top=0, bottom=0, pen=palette.c1)
        self.phi_sweep_fit_plot = pg.PlotDataItem(self._orientation_logic.phi_sweep_index,
                                                  self._orientation_logic.phi_sweep_fit,
                                                  pen=pg.mkPen(palette.c2))
        self._mw.phi_ViewWidget.addItem(self.phi_sweep_plot)
        self._mw.phi_ViewWidget.addItem(self.phi_sweep_error)
        self._mw.phi_ViewWidget.setLabel('bottom', 'φ', units='°')
        self._mw.phi_ViewWidget.setLabel('left', 'NV Frequency', units='Hz')
        
        self.theta_sweep_plot = pg.PlotDataItem(self._orientation_logic.theta_sweep_index,
                                                self._orientation_logic.theta_sweep_freq,
                                                pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                                symbol='o',
                                                symbolPen=palette.c1,
                                                symbolBrush=palette.c1,
                                                symbolSize=7)
        self.theta_sweep_error = pg.ErrorBarItem(x=self._orientation_logic.theta_sweep_index,
                                                 y=self._orientation_logic.theta_sweep_freq,
                                                 height=self._orientation_logic.theta_sweep_freq_error,
                                                 top=0, bottom=0, pen=palette.c1)
        self.theta_sweep_fit_plot = pg.PlotDataItem(self._orientation_logic.theta_sweep_index,
                                                    self._orientation_logic.theta_sweep_fit,
                                                    pen=pg.mkPen(palette.c2))
        self._mw.theta_ViewWidget.addItem(self.theta_sweep_plot)
        self._mw.theta_ViewWidget.addItem(self.theta_sweep_error)
        self._mw.theta_ViewWidget.setLabel('bottom', 'θ' , units='°')
        self._mw.theta_ViewWidget.setLabel('left', 'NV Frequency', units='Hz')

        self.esr_plot = pg.PlotDataItem(self._orientation_logic.freq_esr_range,
                                        self._orientation_logic.pl_esr,
                                        pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                        symbol='o',
                                        symbolPen=palette.c1,
                                        symbolBrush=palette.c1,
                                        symbolSize=7)
        self.esr_fit_plot = pg.PlotDataItem(self._orientation_logic.freq_esr_range_fit,
                                            self._orientation_logic.pl_esr_fit,
                                            pen=pg.mkPen(palette.c2))
        self._mw.ESR_ViewWidget.addItem(self.esr_plot)
        self._mw.ESR_ViewWidget.addItem(self.esr_fit_plot)
        self._mw.ESR_ViewWidget.setLabel('bottom', 'Frequency', units='Hz')
        self._mw.ESR_ViewWidget.setLabel('left', 'PL', units='counts/s')

        # Show the main window
        self.show()
        
        return
    

    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """    
        if self._orientation_logic._magnet_logic.check_before_closing():
            self._mw.close()
            return 0
        else:
            self.log.warning("Not all the fields are zero or a heater is ON!")
            messagebox = QtGui.QMessageBox()
            messagebox.setText("Not all the fields are zero or a heater is ON!")
            messagebox.setStandardButtons(QtGui.QMessageBox.Ok)
            messagebox.setWindowTitle("Warning")
            messagebox.exec_()
            return -1
    
    
    def show(self):
        """ Make window visible and put it above all other windows. 
        """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()
        
        return


    def start_find_theta_phi(self):
        """ Send a signal to the logic to start the sweeps.
        """
        self._orientation_logic.stop_measurement = False
        self._orientation_logic.pause_measurement = False
        self._mw.pushButton_pause.setText("Pause")
        self._mw.doubleSpinBox_phi0_theta_sweep.setEnabled(False)
        self.sigFindThetaPhi.emit()
        return


    def start_sweep_theta(self):
        """ Send a signal to the logic to start the sweep.
        """
        self._orientation_logic.stop_measurement = False
        self._orientation_logic.pause_measurement = False
        self._orientation_logic.theta_phi_measurement = False
        self._mw.pushButton_pause.setText("Pause")
        self.sigStartThetaSweep.emit()
        return
    

    def start_sweep_phi(self):
        """ Send a signal to the logic to start the sweep.
        """
        self._orientation_logic.stop_measurement = False
        self._orientation_logic.pause_measurement = False
        self._orientation_logic.theta_phi_measurement = False
        self._mw.pushButton_pause.setText("Pause")
        self.sigStartPhiSweep.emit()
        return


    def stop_sweep(self):
        """ Tell the logic to go to zero at the next field change.
        """
        self._orientation_logic.stop_measurement = True
        if self._orientation_logic.pause_measurement:
            self.sigResumeMeasurement.emit() # connected to change field, we go to zero
        return


    def pause_resume_sweep(self):
        """ Tell the logic to pause or to resume a sweep.
        """
        if not self._orientation_logic.pause_measurement:
            self._orientation_logic.pause_measurement = True
            self._mw.pushButton_pause.setText("Resume")
        else:
            self._orientation_logic.pause_measurement = False
            self._mw.pushButton_pause.setText("Pause")
            self.sigResumeMeasurement.emit()
        return

    def disable_buttons(self):
        """ Avoid the user to do annoying things during the sweeps.
        """
        self._mw.pushButton_find_theta_phi.setEnabled(False)
        self._mw.pushButton_sweep_theta.setEnabled(False)
        self._mw.pushButton_sweep_phi.setEnabled(False)
        self._mw.pushButton_stop.setEnabled(True)
        self._mw.pushButton_pause.setEnabled(True)
        self._mw.pushButton_apply_field.setEnabled(False)
        self._mw.doubleSpinBox_RF_power.setEnabled(False)
        self._mw.doubleSpinBox_field_ampl.setEnabled(False)
        self._mw.spinBox_nb_pts.setEnabled(False)
        self._mw.doubleSpinBox_av_time.setEnabled(False)
        self._mw.doubleSpinBox_start_freq.setEnabled(False)
        self._mw.doubleSpinBox_stop_freq.setEnabled(False)
        self._mw.doubleSpinBox_step_freq.setEnabled(False)
        self._mw.comboBox_lower_upper.setEnabled(False)
        self._mw.doubleSpinBox_theta_for_phi_sweep.setEnabled(False)
        self._mw.doubleSpinBox_phi_for_theta_sweep.setEnabled(False)
        self._mw.doubleSpinBox_theta.setEnabled(False)
        self._mw.doubleSpinBox_phi.setEnabled(False)
#        if self._orientation_logic.theta_phi_measurement:
#            self._mw.doubleSpinBox_phi0_theta_sweep.setEnabled(False)
        return


    def enable_buttons(self):
        """ Re-enable the interaction with the user.
        """
        self._mw.pushButton_find_theta_phi.setEnabled(True)
        self._mw.pushButton_sweep_theta.setEnabled(True)
        self._mw.pushButton_sweep_phi.setEnabled(True)
        self._mw.pushButton_stop.setEnabled(False)
        self._mw.pushButton_pause.setEnabled(False)
        self._mw.doubleSpinBox_field_ampl.setEnabled(True)
        self._mw.spinBox_nb_pts.setEnabled(True)
        self._mw.doubleSpinBox_RF_power.setEnabled(True)
        self._mw.doubleSpinBox_av_time.setEnabled(True)
        self._mw.doubleSpinBox_start_freq.setEnabled(True)
        self._mw.doubleSpinBox_stop_freq.setEnabled(True)
        self._mw.doubleSpinBox_step_freq.setEnabled(True)
        self._mw.comboBox_lower_upper.setEnabled(True)
        self._mw.doubleSpinBox_theta_for_phi_sweep.setEnabled(True)
        self._mw.doubleSpinBox_phi_for_theta_sweep.setEnabled(True)
        self._mw.doubleSpinBox_phi0_theta_sweep.setEnabled(True)
        self._mw.doubleSpinBox_theta.setEnabled(True)
        self._mw.doubleSpinBox_phi.setEnabled(True)
        if self._orientation_logic.pause_measurement:
            self._mw.pushButton_apply_field.setEnabled(False)
        else:
            self._mw.pushButton_apply_field.setEnabled(True)
        return
    

    def set_field_ampl(self):
        """ Set the value of the field amplitude in the logic.
        """
        B = self._mw.doubleSpinBox_field_ampl.value()
        self._orientation_logic.field_ampl = B
        self.log.info("NV orientation finder: field amplitude set.")
        return


    def set_nb_pts(self):
        """ Set the value of the number of points in the logic.
        """
        nb = self._mw.spinBox_nb_pts.value()
        self.sigUpdatePtsNb.emit(nb)
        self.log.info("NV orientation finder: number of points set.")
        return


    def set_rf_power(self):
        """ Set the value of the RF power in the logic.
        """
        rf_power = self._mw.doubleSpinBox_RF_power.value()
        self._orientation_logic.rf_power = rf_power
        self.log.info("NV orientation finder: RF power set.")
        return


    def set_averaging_time(self):
        """ Set the value of the averaging time per frequency in the logic.
        """
        av_time = self._mw.doubleSpinBox_av_time.value()
        self._orientation_logic.av_time = av_time
        self.log.info("NV orientation finder: averaging time per frequency set.")
        return


    def set_start_freq(self):
        """ Set the value of the start RF frequency in the logic.
        """
        start_freq = self._mw.doubleSpinBox_start_freq.value()
        self._orientation_logic.start_freq = start_freq
        self._orientation_logic.init_start_freq = start_freq
        self._orientation_logic.freq_esr_range = np.arange(start_freq,
                            self._orientation_logic.stop_freq + self._orientation_logic.freq_step,
                            self._orientation_logic.freq_step)
        self.log.info("NV orientation finder: start frequency set.")        
        return

    def set_stop_freq(self):
        """ Set the value of the stop RF frequency in the logic.
        """
        stop_freq = self._mw.doubleSpinBox_stop_freq.value()
        self._orientation_logic.stop_freq = stop_freq
        self._orientation_logic.init_stop_freq = stop_freq
        self._orientation_logic.freq_esr_range = np.arange(self._orientation_logic.start_freq,
                                                           stop_freq + self._orientation_logic.freq_step,
                                                           self._orientation_logic.freq_step)
        self.log.info("NV orientation finder: stop frequency set.")
        return

    def set_step_freq(self):
        """ Set the value of the RF frequency step in the logic.
        """
        freq_step = self._mw.doubleSpinBox_step_freq.value()
        self._orientation_logic.freq_step = freq_step
        self._orientation_logic.freq_esr_range = np.arange(self._orientation_logic.start_freq,
                                                           self._orientation_logic.stop_freq + freq_step,
                                                           freq_step)
        self.log.info("NV orientation finder: frequency step set.")
        return

    def change_tracked_resonance(self):
        """ Change the tracked resonance in the logic.
        """
        res = self._mw.comboBox_lower_upper.currentText()
        self._orientation_logic.tracked_resonance = res
        self.log.info("NV orientation finder: changed tracked resonance.")
        return
    
    def set_theta_for_phi_sweep(self):
        """ Set the theta angle during the phi sweeps.
        """
        theta_for_phi = self._mw.doubleSpinBox_theta_for_phi_sweep.value()
        self._orientation_logic.theta_for_phi = theta_for_phi
        self.log.info("NV orientation finder: changed theta angle for phi sweeps")
        return

    def set_phi_for_theta_sweep(self):
        """ Set the phi angle during the theta sweeps.
        """
        phi_for_theta = self._mw.doubleSpinBox_phi_for_theta_sweep.value()
        self._orientation_logic.phi_for_theta = phi_for_theta
        self.log.info("NV orientation finder: changed phi angle for theta sweeps")
        return

    def changed_sweep_angle(self, angle):
        """ Displays the theta or phi angle fixed for the sweep if changed by the logic.
        """
        if angle == "phi":
            state = self._mw.doubleSpinBox_phi_for_theta_sweep.isEnabled()
            self._mw.doubleSpinBox_phi_for_theta_sweep.setEnabled(True)
            self._mw.doubleSpinBox_phi_for_theta_sweep.setValue(self._orientation_logic.phi_for_theta)
            self._mw.doubleSpinBox_phi_for_theta_sweep.setEnabled(state)
            self.log.info("Changed phi for theta display")
        else:
            self._mw.doubleSpinBox_theta_for_phi_sweep.setValue(self._orientation_logic.theta_for_phi)
        return

    def set_fitting_guess(self, angle):
        """ Changes the initial guess for the fit
        """
        self._orientation_logic.phi0_phi_sweep = self._mw.doubleSpinBox_phi0_phi_sweep.value()
        self._orientation_logic.theta0_phi_sweep = self._mw.doubleSpinBox_theta0_phi_sweep.value()
        self._orientation_logic.phi0_theta_sweep = self._mw.doubleSpinBox_phi0_theta_sweep.value()
        self._orientation_logic.theta0_theta_sweep = self._mw.doubleSpinBox_theta0_theta_sweep.value()
        self._orientation_logic.use_guess_phi = self._mw.checkBox_fit_guess_phi.isChecked()
        self._orientation_logic.use_guess_theta = self._mw.checkBox_fit_guess_theta.isChecked()
        return
    
    def apply_field(self):
        """ Apply a permanent mag field
        """
        theta = self._mw.doubleSpinBox_theta.value()
        phi = self._mw.doubleSpinBox_phi.value()
        ampl = self._mw.doubleSpinBox_field_ampl.value()
    
        self._orientation_logic.apply_field(theta, phi, ampl)
        
        return 0
    
    def display_phi_sweep_fit(self):
        """ Display (or remove from display) the results of the fit to find phi.
        """
        if self._mw.checkBox_fit_phi_sweep.isChecked():
            if self._orientation_logic.fit_phi is not None:
                self.log.info("Updating phi sweep fit")
                f_fit = self._orientation_logic.fit_phi["f_ampl"]
                f_fit_error = self._orientation_logic.fit_phi["f_ampl_error"]
                phi_tip = self._orientation_logic.fit_phi["phi_tip"]
                phi_tip_error = self._orientation_logic.fit_phi["phi_tip_error"]
                theta_tip = self._orientation_logic.fit_phi["theta_tip"]
                theta_tip_error = self._orientation_logic.fit_phi["theta_tip_error"]
                display_str = "Freq amplitude: {:.1f} ± {:.1f} MHz \n φ tip: {:.1f} ± {:.1f}° \n θ tip: {:.1f} ± {:.1f}°".format(f_fit*1e-6, f_fit_error*1e-6, phi_tip, phi_tip_error, theta_tip, theta_tip_error)
                self.phi_sweep_fit_plot.setData(x=self._orientation_logic.phi_sweep_index,
                                                y=self._orientation_logic.phi_sweep_fit)
                if self.phi_sweep_fit_plot not in self._mw.phi_ViewWidget.listDataItems():
                    self._mw.phi_ViewWidget.addItem(self.phi_sweep_fit_plot)
            else:
                display_str = "No fit."
            self._mw.textBrowser_fit_phi.setText(display_str)

        else:
            if self.phi_sweep_fit_plot in self._mw.phi_ViewWidget.listDataItems():
                self._mw.phi_ViewWidget.removeItem(self.phi_sweep_fit_plot)
            self._mw.textBrowser_fit_phi.setText("")
        return

    def display_theta_sweep_fit(self):
        """ Display (or remove from display) the results of the fit to find theta.
        """
        if self._mw.checkBox_fit_theta_sweep.isChecked():
            if self._orientation_logic.fit_theta is not None:
                self.log.info("Updating theta sweep fit")
                f_fit = self._orientation_logic.fit_theta["f_ampl"]
                f_fit_error = self._orientation_logic.fit_theta["f_ampl_error"]
                phi_tip = self._orientation_logic.fit_theta["phi_tip"]
                phi_tip_error = self._orientation_logic.fit_theta["phi_tip_error"]
                theta_tip = self._orientation_logic.fit_theta["theta_tip"]
                theta_tip_error = self._orientation_logic.fit_theta["theta_tip_error"]
                display_str = "Freq amplitude: {:.1f} ± {:.1f} MHz \n θ tip: {:.1f} ± {:.1f}° \n φ tip: {:.1f} ± {:.1f}°".format(f_fit*1e-6, f_fit_error*1e-6, theta_tip, theta_tip_error, phi_tip, phi_tip_error)
                self.theta_sweep_fit_plot.setData(x=self._orientation_logic.theta_sweep_index,
                                                  y=self._orientation_logic.theta_sweep_fit)
                if self.theta_sweep_fit_plot not in self._mw.theta_ViewWidget.listDataItems():
                    self._mw.theta_ViewWidget.addItem(self.theta_sweep_fit_plot)
            else:
                display_str = "No fit."
            self._mw.textBrowser_fit_theta.setText(display_str)
        else:
            if self.theta_sweep_fit_plot in self._mw.theta_ViewWidget.listDataItems():
                self._mw.theta_ViewWidget.removeItem(self.theta_sweep_fit_plot)
            self._mw.textBrowser_fit_theta.setText("")
        return

    def update_current_field(self, Bx, By, Bz):
        """ Display the value of the current magnetic field.
        """
        if np.isnan(Bx):
            self._mw.display_current_Bx.setText(" ")
        else:
            self._mw.display_current_Bx.setText("{:.3f} G".format(Bx))
            
        if np.isnan(By):
            self._mw.display_current_Bx.setText(" ")
        else:
            self._mw.display_current_By.setText("{:.3f} G".format(By))
            
        if np.isnan(Bz):
            self._mw.display_current_Bz.setText(" ")
        else:
            self._mw.display_current_Bz.setText("{:.3f} G".format(Bz))
        return

    def update_next_field(self, Bx, By, Bz):
        """ Display the value of the next magnetic field.
        """
        if np.isnan(Bx):
            self._mw.display_next_Bx.setText(" ")
        else:
            self._mw.display_next_Bx.setText("{:.3f} G".format(Bx))
            
        if np.isnan(By):
            self._mw.display_next_Bx.setText(" ")
        else:
            self._mw.display_next_By.setText("{:.3f} G".format(By))
            
        if np.isnan(Bz):
            self._mw.display_next_Bz.setText(" ")
        else:
            self._mw.display_next_Bz.setText("{:.3f} G".format(Bz))
        return

        return
    
    def refresh_plot_phi_sweep(self):
        """ Refresh the plot widget with new data.
        """
        self.phi_sweep_plot.setData(x=self._orientation_logic.phi_sweep_index,
                                    y=self._orientation_logic.phi_sweep_freq)
        self.phi_sweep_error.setData(x=self._orientation_logic.phi_sweep_index,
                                     y=self._orientation_logic.phi_sweep_freq,
                                     height=self._orientation_logic.phi_sweep_freq_error)
        self.display_phi_sweep_fit()

        return

    def refresh_plot_theta_sweep(self):
        """ Refresh the plot widget with new data.
        """
        self.theta_sweep_plot.setData(x=self._orientation_logic.theta_sweep_index,
                                      y=self._orientation_logic.theta_sweep_freq)
        self.theta_sweep_error.setData(x=self._orientation_logic.theta_sweep_index,
                                       y=self._orientation_logic.theta_sweep_freq,
                                       height=self._orientation_logic.phi_sweep_freq_error)
        self.display_theta_sweep_fit()
        return

    def refresh_plot_esr(self):
        """ Refresh the plot widget with new data.
        """
        self.esr_plot.setData(x=self._orientation_logic.freq_esr_range,
                              y=self._orientation_logic.pl_esr)
        self.esr_fit_plot.setData(x=self._orientation_logic.freq_esr_range_fit,
                                  y=self._orientation_logic.pl_esr_fit)
        return

    def refresh_esr_time(self):
        """ Change the elapsed time display.
        """
        self._mw.display_elapsed_time.setText("{:.0f} s".format(self._orientation_logic.odmr_elapsed_time))
        return
    
    def save_routine(self):
        """Call save_routine from logic with the file tag.
        """
        file_tag = self._mw.lineEdit_file_tag.text()
        comment = self._mw.textEdit_comment.toPlainText()
        self._orientation_logic.save_data(file_tag, comment)
        return
