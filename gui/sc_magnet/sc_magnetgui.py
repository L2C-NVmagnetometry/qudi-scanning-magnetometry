# -*- coding: utf-8 -*-
"""
This file contains the Qudi GUI for controlling a 3D superconducting
magnet.

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
from core.module import Connector
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy import uic


class SCMagnetMainWindow(QtWidgets.QMainWindow):
    """ The main window for the superconducting magnet GUI.
    """
    
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_sc_magnetgui.ui')

        # Load it
        super(SCMagnetMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()
        
class SCMagnetGui(GUIBase):
    """ This is the GUI Class for the superconducting magnet.
    """
    
    _modclass = 'SCMagnetGui'
    _modtype = 'gui'
    
    # declare connectors
    scmagnetlogic = Connector(interface='SuperConductingMagnetLogic')
    
    # declare signals
    sigGetChannelStatus = QtCore.Signal(str)
    sigGetLimits = QtCore.Signal(str)
    sigGetRanges = QtCore.Signal(str)
    sigGetRates = QtCore.Signal(str)
    sigGetSweepMode = QtCore.Signal(str)
    sigRemoteSwitch = QtCore.Signal(str, str)
    sigSetLimits = QtCore.Signal(list, str)
    sigSetRanges = QtCore.Signal(list, str)
    sigSetRates = QtCore.Signal(list, str)
    sigSwitchHeater = QtCore.Signal(str, str)
    sigSetSweepMode = QtCore.Signal(str, bool, str)
    sigSetUnit = QtCore.Signal(str, str)
    sigGoToField = QtCore.Signal(float, float, float)
    
    
    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        
    def on_activate(self):
        """ Definition, configuration and initialisation of the quenching GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        """
        self._magnetlogic = self.scmagnetlogic()
        
        ########################################################################
        #                      General configurations                          #
        ########################################################################
        
        # use the inherited class 'Ui_SCMagnetGuiUI' to create now the GUI element:
        self._mw = SCMagnetMainWindow()
        
        # Fill the comboBoxes for the sweep modes
        self._mw.comboBox_sweep_mode_Bx.addItems(["UP", "DOWN", "ZERO"])
        self._mw.comboBox_sweep_mode_By.addItems(["UP", "DOWN", "ZERO"])
        self._mw.comboBox_sweep_mode_Bz.addItems(["UP", "DOWN", "ZERO"])
        # Fill the comboBoxes for the unit choice
        self._mw.comboBox_unit_Bx.addItems(["kG", "A"])
        self._mw.comboBox_unit_By.addItems(["kG", "A"])
        self._mw.comboBox_unit_Bz.addItems(["kG", "A"])
        # Set initial values for the voltage limits
        self._mw.doubleSpinBox_voltage_Bx.setValue(1)
        self._mw.doubleSpinBox_voltage_By.setValue(1)
        self._mw.doubleSpinBox_voltage_Bz.setValue(5)
        
        ########################################################################
        #                          Connect signals                             #
        ########################################################################
        
        # interaction with user
        self._mw.pushButton_update_status_Bx.clicked.connect(self.ask_Bx_status)
        self._mw.pushButton_update_status_By.clicked.connect(self.ask_By_status)
        self._mw.pushButton_update_status_Bz.clicked.connect(self.ask_Bz_status)
        
        self._mw.pushButton_get_limits_Bx.clicked.connect(self.ask_Bx_limits)
        self._mw.pushButton_get_limits_By.clicked.connect(self.ask_By_limits)
        self._mw.pushButton_get_limits_Bz.clicked.connect(self.ask_Bz_limits)
        
        self._mw.pushButton_get_range_Bx.clicked.connect(self.ask_Bx_ranges)
        self._mw.pushButton_get_range_By.clicked.connect(self.ask_By_ranges)
        self._mw.pushButton_get_range_Bz.clicked.connect(self.ask_Bz_ranges)
        
        self._mw.pushButton_get_rates_Bx.clicked.connect(self.ask_Bx_rates)
        self._mw.pushButton_get_rates_By.clicked.connect(self.ask_By_rates)
        self._mw.pushButton_get_rates_Bz.clicked.connect(self.ask_Bz_rates)
        
        self._mw.pushButton_get_sweep_mode_Bx.clicked.connect(self.ask_Bx_sweep)
        self._mw.pushButton_get_sweep_mode_By.clicked.connect(self.ask_By_sweep)
        self._mw.pushButton_get_sweep_mode_Bz.clicked.connect(self.ask_Bz_sweep)
        
        self._mw.pushButton_remote_Bx.clicked.connect(self.switch_Bx_remote)
        self._mw.pushButton_remote_By.clicked.connect(self.switch_By_remote)
        self._mw.pushButton_remote_Bz.clicked.connect(self.switch_Bz_remote)
        
        self._mw.pushButton_set_limits_Bx.clicked.connect(self.set_limits_Bx)
        self._mw.pushButton_set_limits_By.clicked.connect(self.set_limits_By)
        self._mw.pushButton_set_limits_Bz.clicked.connect(self.set_limits_Bz)
        
        self._mw.pushButton_set_sweep_mode_Bx.clicked.connect(self.set_sweep_mode_Bx)
        self._mw.pushButton_set_sweep_mode_By.clicked.connect(self.set_sweep_mode_By)
        self._mw.pushButton_set_sweep_mode_Bz.clicked.connect(self.set_sweep_mode_Bz)
        
        self._mw.pushButton_pause_sweep_Bx.clicked.connect(self.pause_sweep_Bx)
        self._mw.pushButton_pause_sweep_By.clicked.connect(self.pause_sweep_By)
        self._mw.pushButton_pause_sweep_Bz.clicked.connect(self.pause_sweep_Bz)
        
        self._mw.pushButton_set_range_Bx.clicked.connect(self.set_ranges_Bx)
        self._mw.pushButton_set_range_By.clicked.connect(self.set_ranges_By)
        self._mw.pushButton_set_range_Bz.clicked.connect(self.set_ranges_Bz)
        
        self._mw.pushButton_set_rates_Bx.clicked.connect(self.set_rates_Bx)
        self._mw.pushButton_set_rates_By.clicked.connect(self.set_rates_By)
        self._mw.pushButton_set_rates_Bz.clicked.connect(self.set_rates_Bz)
        
        self._mw.pushButton_heater_on_Bx.clicked.connect(self.heater_on_Bx)
        self._mw.pushButton_heater_on_By.clicked.connect(self.heater_on_By)
        self._mw.pushButton_heater_on_Bz.clicked.connect(self.heater_on_Bz)
        
        self._mw.pushButton_heater_off_Bx.clicked.connect(self.heater_off_Bx)
        self._mw.pushButton_heater_off_By.clicked.connect(self.heater_off_By)
        self._mw.pushButton_heater_off_Bz.clicked.connect(self.heater_off_Bz)
        
        self._mw.pushButton_set_unit_Bx.clicked.connect(self.set_unit_Bx)
        self._mw.pushButton_set_unit_By.clicked.connect(self.set_unit_By)
        self._mw.pushButton_set_unit_Bz.clicked.connect(self.set_unit_Bz)
        
        self._mw.pushButton_convert.clicked.connect(self.convert_xyz)
        self._mw.pushButton_go_to.clicked.connect(self.go_to_field)
        
        # send signals to logic
        self.sigGetChannelStatus.connect(
            self._magnetlogic.query_status, QtCore.Qt.QueuedConnection)
        self.sigGetLimits.connect(
            self._magnetlogic.query_limits, QtCore.Qt.QueuedConnection)
        self.sigGetRanges.connect(
            self._magnetlogic.query_ranges, QtCore.Qt.QueuedConnection)
        self.sigGetRates.connect(
            self._magnetlogic.query_rates, QtCore.Qt.QueuedConnection)
        self.sigGetSweepMode.connect(
            self._magnetlogic.query_sweep_mode, QtCore.Qt.QueuedConnection)
        self.sigRemoteSwitch.connect(
            self._magnetlogic.change_op_mode, QtCore.Qt.QueuedConnection)
        self.sigSetLimits.connect(
            self._magnetlogic.set_limits, QtCore.Qt.QueuedConnection)
        self.sigSetSweepMode.connect(
            self._magnetlogic.set_sweep_mode, QtCore.Qt.QueuedConnection)
        self.sigSetRanges.connect(
            self._magnetlogic.set_ranges, QtCore.Qt.QueuedConnection)
        self.sigSetRates.connect(
            self._magnetlogic.set_rates, QtCore.Qt.QueuedConnection)
        self.sigSwitchHeater.connect(
            self._magnetlogic.switch_heater, QtCore.Qt.QueuedConnection)
        self.sigSetUnit.connect(
            self._magnetlogic.set_unit, QtCore.Qt.QueuedConnection)
        self.sigGoToField.connect(
            self._magnetlogic.go_to_field, QtCore.Qt.QueuedConnection)
        
        # connect to signals from logic
        self._magnetlogic.sigStatusUpdated.connect(self.update_status)
        self._magnetlogic.sigLimitsUpdated.connect(self.update_limits)
        self._magnetlogic.sigRangesUpdated.connect(self.update_ranges)
        self._magnetlogic.sigRatesUpdated.connect(self.update_rates)
        self._magnetlogic.sigSweepModeUpdated.connect(self.update_sweep_mode)
        self._magnetlogic.sigHeaterNotSwitched.connect(self.switch_heater_refused)
        self._magnetlogic.timer.timeout.connect(self.enable_sweep)
        self._magnetlogic.sigFieldSet.connect(self.enable_gui)
        
        # reads all the values on when starting
        for coil in ["x", "y", "z"]:
            self.sigGetChannelStatus.emit(coil)
            self.sigGetLimits.emit(coil)
            self.sigGetRanges.emit(coil)
            self.sigGetRates.emit(coil)
            self.sigGetSweepMode.emit(coil)
            
        self._mw.pushButton_go_to.setEnabled(False)
        return 
    
    
    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        if self._magnetlogic.check_before_closing():
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
    
    def ask_Bx_status(self):
        """ Emits the signal to ask for the coil x status
        """
        self.sigGetChannelStatus.emit("x")
        return
    
    def ask_By_status(self):
        """ Emits the signal to ask for the coil x status
        """
        self.sigGetChannelStatus.emit("y")
        return
    
    def ask_Bz_status(self):
        """ Emits the signal to ask for the coil x status
        """
        self.sigGetChannelStatus.emit("z")
        return
    
    def update_status(self, coilparams, coil):
        """ Refresh the status of the coil.
            @param list coilparams: list containing the parameters describing the 
                                    coil status: [unit, power supply current, coil voltage,
                                                  coil current, power supply voltage,
                                                  heater status].
            @param str coil: "x", "y" or "z".
        """
        if coil == "x":
            self._mw.display_unit_Bx.setText("unit: {:s}".format(coilparams[0]))
            self._mw.display_power_supply_current_Bx.setText(coilparams[1])
            self._mw.display_coil_voltage_Bx.setText(coilparams[2])
            self._mw.display_coil_current_Bx.setText(coilparams[3])
            self._mw.display_power_supply_voltage_Bx.setText(coilparams[4])
            self._mw.display_heater_status_Bx.setText(coilparams[5])
            if coilparams[5] == "OFF":
                self._mw.pushButton_heater_off_Bx.setEnabled(False)
            else:
                self._mw.pushButton_heater_on_Bx.setEnabled(False)
            
        elif coil == "y":
            self._mw.display_unit_By.setText("unit: {:s}".format(coilparams[0]))
            self._mw.display_power_supply_current_By.setText(coilparams[1])
            self._mw.display_coil_voltage_By.setText(coilparams[2])
            self._mw.display_coil_current_By.setText(coilparams[3])
            self._mw.display_power_supply_voltage_By.setText(coilparams[4])
            self._mw.display_heater_status_By.setText(coilparams[5])
            if coilparams[5] == "OFF":
                self._mw.pushButton_heater_off_By.setEnabled(False)
            else:
                self._mw.pushButton_heater_on_By.setEnabled(False)
            
        elif coil == "z":
            self._mw.display_unit_Bz.setText("unit: {:s}".format(coilparams[0]))
            self._mw.display_power_supply_current_Bz.setText(coilparams[1])
            self._mw.display_coil_voltage_Bz.setText(coilparams[2])
            self._mw.display_coil_current_Bz.setText(coilparams[3])
            self._mw.display_power_supply_voltage_Bz.setText(coilparams[4])
            self._mw.display_heater_status_Bz.setText(coilparams[5])
            if coilparams[5] == "OFF":
                self._mw.pushButton_heater_off_Bz.setEnabled(False)
            else:
                self._mw.pushButton_heater_on_Bz.setEnabled(False)
        else:
            self.log.warning(f"Unknown coil {coil}!")
            
        return
    
    def ask_Bx_limits(self):
        """ Emits the signal to ask for the coil x limits
        """
        self.sigGetLimits.emit("x")
        return
    
    def ask_By_limits(self):
        """ Emits the signal to ask for the coil y limits
        """
        self.sigGetLimits.emit("y")
        return
    
    def ask_Bz_limits(self):
        """ Emits the signal to ask for the coil z limits
        """
        self.sigGetLimits.emit("z")
        return

    def update_limits(self, limits, coil):
        """ Refresh the limits of the coil.
            @param list limits: list containing the limits [upper, 
                                lower, voltage]
            @param str coil: "x", "y" or "z".
        """
        if coil == "x":
            self._mw.display_lower_Bx.setText(limits[0])
            self._mw.display_upper_Bx.setText(limits[1])
            self._mw.display_limit_volt_Bx.setText(limits[2])
            
        elif coil == "y":
            self._mw.display_lower_By.setText(limits[0])
            self._mw.display_upper_By.setText(limits[1])
            self._mw.display_limit_volt_By.setText(limits[2])
            
        elif coil == "z":
            self._mw.display_lower_Bz.setText(limits[0])
            self._mw.display_upper_Bz.setText(limits[1])
            self._mw.display_limit_volt_Bz.setText(limits[2])
            
        else:
            self.log.warning(f"Unknown coil {coil}!")
            
        return
    
    def ask_Bx_ranges(self):
        """ Emits the signal to ask for the coil x ranges
        """
        self.sigGetRanges.emit("x")
        return
    
    def ask_By_ranges(self):
        """ Emits the signal to ask for the coil y ranges
        """
        self.sigGetRanges.emit("y")
        return
    
    def ask_Bz_ranges(self):
        """ Emits the signal to ask for the coil z ranges
        """
        self.sigGetRanges.emit("z")
        return

    def update_ranges(self, ranges, coil):
        """ Refresh the ranges of the coil.
            @param list ranges: list containing the ranges
            @param str coil: "x", "y" or "z".
        """
        if coil == "x":
            self._mw.display_range1_Bx.setText(ranges[0] + " A")
            self._mw.display_range2_Bx.setText(ranges[1] + " A")
            self._mw.display_range3_Bx.setText(ranges[2] + " A")
            self._mw.display_range4_Bx.setText(ranges[3] + " A")
   
        elif coil == "y":
            self._mw.display_range1_By.setText(ranges[0] + " A")
            self._mw.display_range2_By.setText(ranges[1] + " A")
            self._mw.display_range3_By.setText(ranges[2] + " A")
            self._mw.display_range4_By.setText(ranges[3] + " A")
    
        elif coil == "z":
            self._mw.display_range1_Bz.setText(ranges[0] + " A")
            self._mw.display_range2_Bz.setText(ranges[1] + " A")
            self._mw.display_range3_Bz.setText(ranges[2] + " A")
            self._mw.display_range4_Bz.setText(ranges[3] + " A")
            
        else:
            self.log.warning(f"Unknown coil {coil}!")
            
        return
    
    def ask_Bx_rates(self):
        """ Emits the signal to ask for the coil x rates
        """
        self.sigGetRates.emit("x")
        return
    
    def ask_By_rates(self):
        """ Emits the signal to ask for the coil y rates
        """
        self.sigGetRates.emit("y")
        return
    
    def ask_Bz_rates(self):
        """ Emits the signal to ask for the coil z rates
        """
        self.sigGetRates.emit("z")
        return

    def update_rates(self, rates, coil):
        """ Refresh the rates of the coil.
            @param list rates: list containing the rates
            @param str coil: "x", "y" or "z".
        """
        if coil == "x":
            self._mw.display_rate1_Bx.setText(rates[0] + " A/s")
            self._mw.display_rate2_Bx.setText(rates[1] + " A/s")
            self._mw.display_rate3_Bx.setText(rates[2] + " A/s")
            self._mw.display_rate4_Bx.setText(rates[3] + " A/s")
            self._mw.display_rate5_Bx.setText(rates[4] + " A/s")
            self._mw.display_fast_rate_Bx.setText(rates[5] + " A/s")
        elif coil == "y":
            self._mw.display_rate1_By.setText(rates[0] + " A/s")
            self._mw.display_rate2_By.setText(rates[1] + " A/s")
            self._mw.display_rate3_By.setText(rates[2] + " A/s")
            self._mw.display_rate4_By.setText(rates[3] + " A/s")
            self._mw.display_rate5_By.setText(rates[4] + " A/s")
            self._mw.display_fast_rate_By.setText(rates[5] + " A/s")
        elif coil == "z":
            self._mw.display_rate1_Bz.setText(rates[0] + " A/s")
            self._mw.display_rate2_Bz.setText(rates[1] + " A/s")
            self._mw.display_rate3_Bz.setText(rates[2] + " A/s")
            self._mw.display_rate4_Bz.setText(rates[3] + " A/s")
            self._mw.display_rate5_Bz.setText(rates[4] + " A/s")
            self._mw.display_fast_rate_Bz.setText(rates[5] + " A/s")
            
        else:
            self.log.warning(f"Unknown coil {coil}!")
            
        return
    
    def ask_Bx_sweep(self):
        """ Emits the signal to ask for the coil x sweep mode
        """
        self.sigGetSweepMode.emit("x")
        return
    
    def ask_By_sweep(self):
        """ Emits the signal to ask for the coil y sweep mode
        """
        self.sigGetSweepMode.emit("y")
        return
    
    def ask_Bz_sweep(self):
        """ Emits the signal to ask for the coil z sweep mode
        """
        self.sigGetSweepMode.emit("z")
        return

    def update_sweep_mode(self, mode, fast, coil):
        """ Refresh the rates of the coil.
            @param str mode: sweep mode "UP", "DOWN", "ZERO", "PAUSED"
            @param bool fast: True if fast, False if slow.
            @param str coil: "x", "y" or "z".
        """
        if coil == "x":
            self._mw.display_sweep_mode_Bx.setText(mode)
            if fast:
                self._mw.display_fast_sweep_Bx.setText("FAST")
            else:
                self._mw.display_fast_sweep_Bx.setText("SLOW")
                
        elif coil == "y":
            self._mw.display_sweep_mode_By.setText(mode)
            if fast:
                self._mw.display_fast_sweep_By.setText("FAST")
            else:
                self._mw.display_fast_sweep_By.setText("SLOW")

        elif coil == "z":
            self._mw.display_sweep_mode_Bz.setText(mode)
            if fast:
                self._mw.display_fast_sweep_Bz.setText("FAST")
            else:
                self._mw.display_fast_sweep_Bz.setText("SLOW")

        else:
            self.log.warning(f"Unknown coil {coil}!")
                
        return
    
    def switch_Bx_remote(self):
        """ Emits the signal to change the op mode of the coil x.
        """
        self.sigRemoteSwitch.emit("remote", "x")
        return
    
    def switch_By_remote(self):
        """ Emits the signal to change the op mode of the coil y.
        """
        self.sigRemoteSwitch.emit("remote", "y")
        return
    
    def switch_Bz_remote(self):
        """ Emits the signal to change the op mode of the coil z.
        """
        self.sigRemoteSwitch.emit("remote", "z")
        return

    def set_limits_Bx(self):
        """ Emits the signal to change the limits of the coil x.
        """
        ul = self._mw.doubleSpinBox_upper_Bx.value()
        ll = self._mw.doubleSpinBox_lower_Bx.value()
        vl = self._mw.doubleSpinBox_voltage_Bx.value()
        changed = False
        
        # test that the values are OK
        ## ll should be lower than ul
        if ul < ll:
            ul = ll
            ll =  self._mw.doubleSpinBox_upper_Bx.value()
            changed  = True
            
        ## we should not exceed the max field
        unit = self._magnetlogic.query_unit("x")
        self.log.info("{}".format(unit))
        if "A" in unit:
            max_val = self._magnetlogic.max_current_x
        elif "kG" in unit:
            # also switch to kG
            max_val = 1e-3*self._magnetlogic.max_field_x
            ul = ul*1e-3
            ll = ll*1e-3
          
        if np.abs(ul) > max_val:
            ul = np.sign(ul)*max_val
            changed = True
        if np.abs(ll) > max_val:
            ll = np.sign(ll)*max_val
            changed = True
            
        if changed:
            if "kG" in unit:
                self._mw.doubleSpinBox_upper_Bx.setValue(ul*1e3)
                self._mw.doubleSpinBox_lower_Bx.setValue(ll*1e3)
            else:
                self._mw.doubleSpinBox_upper_Bx.setValue(ul)
                self._mw.doubleSpinBox_lower_Bx.setValue(ll)
            messagebox = QtGui.QMessageBox()
            messagebox.setText("The limits that you entered were incorrect! \n The values were modified.")
            messagebox.setStandardButtons(QtGui.QMessageBox.Ok)
            messagebox.setWindowTitle("Warning")
            messagebox.exec_()
        limits = [ll, ul, vl]
        self.sigSetLimits.emit(limits, "x")
        return
    
    def set_limits_By(self):
        """ Emits the signal to change the limits of the coil y.
        """
        ul = self._mw.doubleSpinBox_upper_By.value()
        ll = self._mw.doubleSpinBox_lower_By.value()
        vl = self._mw.doubleSpinBox_voltage_By.value()
        changed = False
        
        # test that the values are OK
        ## ll should be lower than ul
        if ul < ll:
            ul = ll
            ll =  self._mw.doubleSpinBox_upper_By.value()
            changed  = True
            
        ## we should not exceed the max field
        unit = self._magnetlogic.query_unit("x")
        if "A" in unit:
            max_val = self._magnetlogic.max_current_y
        elif "kG" in unit:
            # also switch to kG
            max_val = 1e-3*self._magnetlogic.max_field_y
            ul = ul*1e-3
            ll = ll*1e-3
          
        if np.abs(ul) > max_val:
            ul = np.sign(ul)*max_val
            changed = True
        if np.abs(ll) > max_val:
            ll = np.sign(ll)*max_val
            changed = True
            
        if changed:
            if "kG" in unit:
                self._mw.doubleSpinBox_upper_By.setValue(ul*1e3)
                self._mw.doubleSpinBox_lower_By.setValue(ll*1e3)
            else:
                self._mw.doubleSpinBox_upper_By.setValue(ul)
                self._mw.doubleSpinBox_lower_By.setValue(ll)
            messagebox = QtGui.QMessageBox()
            messagebox.setText("The limits that you entered were incorrect! \n The values were modified.")
            messagebox.setStandardButtons(QtGui.QMessageBox.Ok)
            messagebox.setWindowTitle("Warning")
            messagebox.exec_()
        limits = [ll, ul, vl]
        self.sigSetLimits.emit(limits, "y")
        return
    
    def set_limits_Bz(self):
        """ Emits the signal to change the limits of the coil z.
        """
        ul = self._mw.doubleSpinBox_upper_Bz.value()
        ll = self._mw.doubleSpinBox_lower_Bz.value()
        vl = self._mw.doubleSpinBox_voltage_Bz.value()
        changed = False
        
        # test that the values are OK
        ## ll should be lower than ul
        if ul < ll:
            ul = ll
            ll =  self._mw.doubleSpinBox_upper_Bz.value()
            changed  = True
            
        ## we should not exceed the max field
        unit = self._magnetlogic.query_unit("x")
        if "A" in unit:
            max_val = self._magnetlogic.max_current_z
        elif "kG" in unit:
            # also switch to kG
            max_val = 1e-3*self._magnetlogic.max_field_z
            ul = ul*1e-3
            ll = ll*1e-3
          
        if np.abs(ul) > max_val:
            ul = np.sign(ul)*max_val
            changed = True
        if np.abs(ll) > max_val:
            ll = np.sign(ll)*max_val
            changed = True
            
        if changed:
            if "kG" in unit:
                self._mw.doubleSpinBox_upper_Bz.setValue(ul*1e3)
                self._mw.doubleSpinBox_lower_Bz.setValue(ll*1e3)
            else:
                self._mw.doubleSpinBox_upper_Bz.setValue(ul)
                self._mw.doubleSpinBox_lower_Bz.setValue(ll)
            messagebox = QtGui.QMessageBox()
            messagebox.setText("The limits that you entered were incorrect! \n The values were modified.")
            messagebox.setStandardButtons(QtGui.QMessageBox.Ok)
            messagebox.setWindowTitle("Warning")
            messagebox.exec_()
        limits = [ll, ul, vl]
        self.sigSetLimits.emit(limits, "z")
        return
    
    def set_sweep_mode_Bx(self):
        """ Emits the signal to change the sweep mode of the coil x.
        """
        mode = self._mw.comboBox_sweep_mode_Bx.currentText()
        fast = self._mw.checkBox_fast_sweep_Bx.isChecked()
        self.sigSetSweepMode.emit(mode, fast, "x")
        return
    
    def set_sweep_mode_By(self):
        """ Emits the signal to change the sweep mode of the coil y.
        """
        mode = self._mw.comboBox_sweep_mode_By.currentText()
        fast = self._mw.checkBox_fast_sweep_By.isChecked()
        self.sigSetSweepMode.emit(mode, fast, "y")
        return
    
    def set_sweep_mode_Bz(self):
        """ Emits the signal to change the sweep mode of the coil z.
        """
        mode = self._mw.comboBox_sweep_mode_Bz.currentText()
        fast = self._mw.checkBox_fast_sweep_Bz.isChecked()
        self.sigSetSweepMode.emit(mode, fast, "z")
        return
    
    def pause_sweep_Bx(self):
        """ Emits the signal to change the sweep mode of the coil x.
        """
        self.sigSetSweepMode.emit("PAUSE", False, "x")
        return
    
    def pause_sweep_By(self):
        """ Emits the signal to change the sweep mode of the coil y.
        """
        self.sigSetSweepMode.emit("PAUSE", False, "y")
        return
    
    def pause_sweep_Bz(self):
        """ Emits the signal to change the sweep mode of the coil z.
        """
        self.sigSetSweepMode.emit("PAUSE", False, "z")
        return
    
    def set_ranges_Bx(self):
        """ Emits the signal to change the ranges of the coil x.
        """
        ranges = []
        ranges.append(self._mw.doubleSpinBox_range1_Bx.value())
        ranges.append(self._mw.doubleSpinBox_range2_Bx.value())
        ranges.append(self._mw.doubleSpinBox_range3_Bx.value())
        ranges.append(self._mw.doubleSpinBox_range4_Bx.value())
        
        self.sigSetRanges.emit(ranges, "x")
        return
    
    def set_ranges_By(self):
        """ Emits the signal to change the ranges of the coil y.
        """
        ranges = []
        ranges.append(self._mw.doubleSpinBox_range1_By.value())
        ranges.append(self._mw.doubleSpinBox_range2_By.value())
        ranges.append(self._mw.doubleSpinBox_range3_By.value())
        ranges.append(self._mw.doubleSpinBox_range4_By.value())
        
        self.sigSetRanges.emit(ranges, "y")
        return
    
    def set_ranges_Bz(self):
        """ Emits the signal to change the ranges of the coil z.
        """
        ranges = []
        ranges.append(self._mw.doubleSpinBox_range1_Bz.value())
        ranges.append(self._mw.doubleSpinBox_range2_Bz.value())
        ranges.append(self._mw.doubleSpinBox_range3_Bz.value())
        ranges.append(self._mw.doubleSpinBox_range4_Bz.value())
        
        self.sigSetRanges.emit(ranges, "z")
        return
    
    def set_rates_Bx(self):
        """ Emits the signal to change the rates of the coil x.
        """
        rates = []
        rates.append(self._mw.doubleSpinBox_rate1_Bx.value())
        rates.append(self._mw.doubleSpinBox_rate2_Bx.value())
        rates.append(self._mw.doubleSpinBox_rate3_Bx.value())
        rates.append(self._mw.doubleSpinBox_rate4_Bx.value())
        rates.append(self._mw.doubleSpinBox_rate5_Bx.value())
        rates.append(self._mw.doubleSpinBox_fast_rate_Bx.value())
        
        self.sigSetRates.emit(rates, "x")
        return
    
    def set_rates_By(self):
        """ Emits the signal to change the rates of the coil y.
        """
        rates = []
        rates.append(self._mw.doubleSpinBox_rate1_By.value())
        rates.append(self._mw.doubleSpinBox_rate2_By.value())
        rates.append(self._mw.doubleSpinBox_rate3_By.value())
        rates.append(self._mw.doubleSpinBox_rate4_By.value())
        rates.append(self._mw.doubleSpinBox_rate5_By.value())
        rates.append(self._mw.doubleSpinBox_fast_rate_By.value())
        
        self.sigSetRates.emit(rates, "y")
        return
    
    def set_rates_Bz(self):
        """ Emits the signal to change the rates of the coil z.
        """
        rates = []
        rates.append(self._mw.doubleSpinBox_rate1_Bz.value())
        rates.append(self._mw.doubleSpinBox_rate2_Bz.value())
        rates.append(self._mw.doubleSpinBox_rate3_Bz.value())
        rates.append(self._mw.doubleSpinBox_rate4_Bz.value())
        rates.append(self._mw.doubleSpinBox_rate5_Bz.value())
        rates.append(self._mw.doubleSpinBox_fast_rate_Bz.value())
        self.sigSetRates.emit(rates, "z")
        return

    def set_unit_Bx(self):
        """ Emits the signal to change the unit of the coil x.
        """
        unit = self._mw.comboBox_unit_Bx.currentText()
        self.sigSetUnit.emit(unit, "x")
        return
    
    def set_unit_By(self):
        """ Emits the signal to change the unit of the coil y.
        """
        unit = self._mw.comboBox_unit_By.currentText()
        self.sigSetUnit.emit(unit, "y")
        return
    
    def set_unit_Bz(self):
        """ Emits the signal to change the unit of the coil z.
        """
        unit = self._mw.comboBox_unit_Bz.currentText()
        self.sigSetUnit.emit(unit, "z")
        return
    
    def heater_on_Bx(self):
        """ Emits the signal to turn on the Bx heater.
        """
        self._mw.pushButton_heater_on_Bx.setEnabled(False) # cannot turn it on twice
        self._mw.pushButton_set_sweep_mode_Bx.setEnabled(False) # we have to wait a few s before sweeping
        self._mw.pushButton_pause_sweep_Bx.setEnabled(False) # we have to wait a few s before sweeping
        self.sigSwitchHeater.emit("ON", "x")
        return
    
    def heater_on_By(self):
        """ Emits the signal to turn on the By heater.
        """
        self._mw.pushButton_heater_on_By.setEnabled(False) # cannot turn it on twice
        self._mw.pushButton_set_sweep_mode_By.setEnabled(False) # we have to wait a few s before sweeping
        self._mw.pushButton_pause_sweep_By.setEnabled(False) # we have to wait a few s before sweeping
        self.sigSwitchHeater.emit("ON", "y")
        return
    
    def heater_on_Bz(self):
        """ Emits the signal to turn on the Bz heater.
        """
        self._mw.pushButton_heater_on_Bz.setEnabled(False) # cannot turn it on twice
        self._mw.pushButton_set_sweep_mode_Bz.setEnabled(False) # we have to wait a few s before sweeping
        self._mw.pushButton_pause_sweep_Bz.setEnabled(False) # we have to wait a few s before sweeping
        self.sigSwitchHeater.emit("ON", "z")
        return
    
    def heater_off_Bx(self):
        """ Emits the signal to turn off the Bx heater.
        """
        self._mw.pushButton_heater_off_Bx.setEnabled(False) # cannot turn it on twice
        self._mw.pushButton_set_sweep_mode_Bx.setEnabled(False) # we have to wait a few s before sweeping
        self._mw.pushButton_pause_sweep_Bx.setEnabled(False) # we have to wait a few s before sweeping
        self.sigSwitchHeater.emit("OFF", "x")
        return
    
    def heater_off_By(self):
        """ Emits the signal to turn off the By heater.
        """
        self._mw.pushButton_heater_off_By.setEnabled(False) # cannot turn it on twice
        self._mw.pushButton_set_sweep_mode_By.setEnabled(False) # we have to wait a few s before sweeping
        self._mw.pushButton_pause_sweep_By.setEnabled(False) # we have to wait a few s before sweeping
        self.sigSwitchHeater.emit("OFF", "y")
        return
    
    def heater_off_Bz(self):
        """ Emits the signal to turn off the Bz heater.
        """
        self._mw.pushButton_heater_off_Bz.setEnabled(False) # cannot turn it on twice
        self._mw.pushButton_set_sweep_mode_Bz.setEnabled(False) # we have to wait a few s before sweeping
        self._mw.pushButton_pause_sweep_Bz.setEnabled(False) # we have to wait a few s before sweeping
        self.sigSwitchHeater.emit("OFF", "z")
        return
    
    def switch_heater_refused(self):
        """ In the case where the heater could not switched because the conditions
            were not met, we re-enable the disabled buttons.
        """
        coil = self._magnetlogic.current_coil_heater
        status = self._magnetlogic.current_coil_state
        # re enable the sweep and the disabled button
        if coil == "x":
            self._mw.pushButton_set_sweep_mode_Bx.setEnabled(True)
            self._mw.pushButton_pause_sweep_Bx.setEnabled(True)
            if status == "ON":
                self._mw.pushButton_heater_on_Bx.setEnabled(True)
            else:
                self._mw.pushButton_heater_off_Bx.setEnabled(True)
        if coil == "y":
            self._mw.pushButton_set_sweep_mode_By.setEnabled(True)
            self._mw.pushButton_pause_sweep_By.setEnabled(True)
            if status == "ON":
                self._mw.pushButton_heater_on_By.setEnabled(True)
            else:
                self._mw.pushButton_heater_off_By.setEnabled(True)
        if coil == "z":
            self._mw.pushButton_set_sweep_mode_Bz.setEnabled(True) 
            self._mw.pushButton_pause_sweep_Bz.setEnabled(True)
            if status == "ON":
                self._mw.pushButton_heater_on_Bz.setEnabled(True)
            else:
                self._mw.pushButton_heater_off_Bz.setEnabled(True)
        messagebox = QtGui.QMessageBox()
        messagebox.setText("The heater was not switched. Make sure that the coil\n and the power supply fields are the same and that\n you are not sweeping.")
        messagebox.setStandardButtons(QtGui.QMessageBox.Ok)
        messagebox.setWindowTitle("Warning")
        messagebox.exec_()
        return
    
    def enable_sweep(self):
        """ Once the heater was switched, after waiting some time, we allow
            to sweep or to switch again.
        """
        coil = self._magnetlogic.current_coil_heater
        status = self._magnetlogic.current_coil_state
        # re enable the sweep and the disabled button
        if coil == "x":
            self._mw.pushButton_set_sweep_mode_Bx.setEnabled(True)
            self._mw.pushButton_pause_sweep_Bx.setEnabled(True)
            if status == "ON":
                self._mw.pushButton_heater_off_Bx.setEnabled(True)
            else:
                self._mw.pushButton_heater_on_Bx.setEnabled(True)
        if coil == "y":
            self._mw.pushButton_set_sweep_mode_By.setEnabled(True)
            self._mw.pushButton_pause_sweep_By.setEnabled(True)
            if status == "ON":
                self._mw.pushButton_heater_off_By.setEnabled(True)
            else:
                self._mw.pushButton_heater_on_By.setEnabled(True)
        if coil == "z":
            self._mw.pushButton_set_sweep_mode_Bz.setEnabled(True) 
            self._mw.pushButton_pause_sweep_Bz.setEnabled(True)
            if status == "ON":
                self._mw.pushButton_heater_off_Bz.setEnabled(True)
            else:
                self._mw.pushButton_heater_on_Bz.setEnabled(True)
        return
    
    def convert_xyz(self):
        """ Converts the field in spherical coords to cartesian coords.
        """
        mag = self._mw.doubleSpinBox_magnitude.value()
        theta = self._mw.doubleSpinBox_theta.value()*np.pi/180
        phi = self._mw.doubleSpinBox_phi.value()*np.pi/180
        
        self.Bx = np.round(mag*np.sin(theta)*np.cos(phi), decimals=3)
        self.By = np.round(mag*np.sin(theta)*np.sin(phi), decimals=3)
        self.Bz = np.round(mag*np.cos(theta), decimals=3)
        
        self._mw.display_x.setText("{:.3f} kG".format(self.Bx))
        self._mw.display_y.setText("{:.3f} kG".format(self.By))
        self._mw.display_z.setText("{:.3f} kG".format(self.Bz))
        self._mw.pushButton_go_to.setEnabled(True)
        return
    
    def go_to_field(self):
        """ Sends the signal with the three field values x, y, z and 
            disable the GUI buttons.
        """
        self._mw.pushButton_set_limits_Bx.setEnabled(False)
        self._mw.pushButton_set_limits_By.setEnabled(False)
        self._mw.pushButton_set_limits_Bz.setEnabled(False)
        
        self._mw.pushButton_set_range_Bx.setEnabled(False)
        self._mw.pushButton_set_range_By.setEnabled(False)
        self._mw.pushButton_set_range_Bz.setEnabled(False)
        
        self._mw.pushButton_set_rates_Bx.setEnabled(False)
        self._mw.pushButton_set_rates_By.setEnabled(False)
        self._mw.pushButton_set_rates_Bz.setEnabled(False)
        
        self._mw.pushButton_set_sweep_mode_Bx.setEnabled(False)
        self._mw.pushButton_set_sweep_mode_By.setEnabled(False)
        self._mw.pushButton_set_sweep_mode_Bz.setEnabled(False)
        
        self._mw.pushButton_pause_sweep_Bx.setEnabled(False)
        self._mw.pushButton_pause_sweep_By.setEnabled(False)
        self._mw.pushButton_pause_sweep_Bz.setEnabled(False)
        
        self._mw.pushButton_set_unit_Bx.setEnabled(False)
        self._mw.pushButton_set_unit_By.setEnabled(False)
        self._mw.pushButton_set_unit_Bz.setEnabled(False)
       
        self._mw.pushButton_heater_on_Bx.setEnabled(False)
        self._mw.pushButton_heater_on_By.setEnabled(False)
        self._mw.pushButton_heater_on_Bz.setEnabled(False)
        
        self._mw.pushButton_heater_off_Bx.setEnabled(False)
        self._mw.pushButton_heater_off_By.setEnabled(False)
        self._mw.pushButton_heater_off_Bz.setEnabled(False)
        
        self._mw.pushButton_convert.setEnabled(False)
        self._mw.pushButton_go_to.setEnabled(False)

        self.sigGoToField.emit(self.Bx, self.By, self.Bz)
        return
    
    def enable_gui(self):
        """Enables all the buttons again once the field is set.
        """
        self._mw.pushButton_set_limits_Bx.setEnabled(True)
        self._mw.pushButton_set_limits_By.setEnabled(True)
        self._mw.pushButton_set_limits_Bz.setEnabled(True)
        
        self._mw.pushButton_set_range_Bx.setEnabled(True)
        self._mw.pushButton_set_range_By.setEnabled(True)
        self._mw.pushButton_set_range_Bz.setEnabled(True)
        
        self._mw.pushButton_set_rates_Bx.setEnabled(True)
        self._mw.pushButton_set_rates_By.setEnabled(True)
        self._mw.pushButton_set_rates_Bz.setEnabled(True)
        
        self._mw.pushButton_set_sweep_mode_Bx.setEnabled(True)
        self._mw.pushButton_set_sweep_mode_By.setEnabled(True)
        self._mw.pushButton_set_sweep_mode_Bz.setEnabled(True)
        
        self._mw.pushButton_pause_sweep_Bx.setEnabled(True)
        self._mw.pushButton_pause_sweep_By.setEnabled(True)
        self._mw.pushButton_pause_sweep_Bz.setEnabled(True)
        
        self._mw.pushButton_set_unit_Bx.setEnabled(True)
        self._mw.pushButton_set_unit_By.setEnabled(True)
        self._mw.pushButton_set_unit_Bz.setEnabled(True)
       
        self._mw.pushButton_heater_on_Bx.setEnabled(True)
        self._mw.pushButton_heater_on_By.setEnabled(True)
        self._mw.pushButton_heater_on_Bz.setEnabled(True)
        
        self._mw.pushButton_heater_off_Bx.setEnabled(True)
        self._mw.pushButton_heater_off_By.setEnabled(True)
        self._mw.pushButton_heater_off_Bz.setEnabled(True)
        
        self._mw.pushButton_convert.setEnabled(True)
        self._mw.pushButton_go_to.setEnabled(True)
        
        return
