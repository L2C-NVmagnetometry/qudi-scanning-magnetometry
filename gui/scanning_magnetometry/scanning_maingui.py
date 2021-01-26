# -*- coding: utf-8 -*-
"""
This file contains the Qudi GUI for scanning NV magnetometry.

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
#import time
import pickle

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

class NVScanningMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_scanning_magnetometry_maingui.ui')

        # Load it
        super(NVScanningMainWindow, self).__init__()

        uic.loadUi(ui_file, self)
        self.show()

        
class ParametersTab(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_scanning_parameters.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)

        
class ScanningTab(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_scanning_window.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)


class NVScanningGui(GUIBase):
    """ This is the GUI Class for scanning NV magnetometry.
    """

    _modclass = 'NVScanningGui'
    _modtype = 'gui'

    # declare connectors
    magnetometerlogic1 = Connector(interface='MagnetometerLogic')
    odmrlogic1 = Connector(interface='OdmrLogic')

    # declare signals
    sigStartScan = QtCore.Signal()
    sigResumeScan = QtCore.Signal()
    sigStopScan = QtCore.Signal()
    sigRangeChanged = QtCore.Signal(np.ndarray)
    sigResChanged = QtCore.Signal(float, float)
    sigClockChanged = QtCore.Signal(float)
    sigRsChanged = QtCore.Signal(float)
    sigMeasModeChanged = QtCore.Signal(str)
    sigIsobChanged = QtCore.Signal(float, float)
    sigFullbChanged = QtCore.Signal(float, float, float, float, float, float, int, float)
    sigPowerChanged = QtCore.Signal(float)
    sigUpdateRoiSize = QtCore.Signal(np.ndarray, float)
    sigUpdateRoiFromInput = QtCore.Signal(float, float)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition, configuration and initialization of the magnetometer
        GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        """

        # connect to logic
        self._magneto_logic = self.magnetometerlogic1()
        self._odmr_logic = self.odmrlogic1()

        # create the main window and insert the tabs
        self._mw = NVScanningMainWindow()
        self._pa = ParametersTab()
        self._sc = ScanningTab()
        self._mw.tabWidget.addTab(self._pa, 'Scanning parameters')
        self._mw.tabWidget.addTab(self._sc, 'Scanning window')

        # init file storage
        self.init_file_path = "magnetometry_init.pickle"
        
        # Send signals to logic
        self.sigStartScan.connect(self._magneto_logic.start_scanning, QtCore.Qt.QueuedConnection)
        self.sigStopScan.connect(self._magneto_logic.stop_scanning, QtCore.Qt.QueuedConnection)
        self.sigResumeScan.connect(self._magneto_logic.resume_scanning, QtCore.Qt.QueuedConnection)
        self.sigRangeChanged.connect(self._magneto_logic.set_range, QtCore.Qt.QueuedConnection)
        self.sigResChanged.connect(self._magneto_logic.set_resolution, QtCore.Qt.QueuedConnection)
        self.sigClockChanged.connect(self._magneto_logic.set_clock_frequency, QtCore.Qt.QueuedConnection)
        self.sigRsChanged.connect(self._magneto_logic.set_return_slowness, QtCore.Qt.QueuedConnection)
        self.sigMeasModeChanged.connect(self._magneto_logic.set_meas_mode, QtCore.Qt.QueuedConnection)
        self.sigFullbChanged.connect(self._magneto_logic.set_sweep_parameters_fullb,
                                     QtCore.Qt.QueuedConnection)
        self.sigIsobChanged.connect(self._magneto_logic.set_sweep_parameters_isob, QtCore.Qt.QueuedConnection)
        self.sigPowerChanged.connect(self._magneto_logic.set_power, QtCore.Qt.QueuedConnection)

        # Connect logic
        self._magneto_logic.sigParamUpdated.connect(self.update_parameters, QtCore.Qt.QueuedConnection)
        self._magneto_logic.sigMovetoEnded.connect(self.enable_disable_moveto, QtCore.Qt.QueuedConnection)
        self._magneto_logic.sigPlotsUpdated.connect(self.update_plots, QtCore.Qt.QueuedConnection)
        self._magneto_logic.sigStopScan.connect(self.enable_action, QtCore.Qt.QueuedConnection)
        self._magneto_logic.sigUpdateDuration.connect(self.update_duration, QtCore.Qt.QueuedConnection)
        self._magneto_logic.sigUpdateRemTime.connect(self.update_rem_time, QtCore.Qt.QueuedConnection)

        # Internal signals
        self._mw.actionStart.triggered.connect(self.start_scanning)
        self._mw.actionPause.triggered.connect(self.pause_scanning)
        self._mw.actionResume.triggered.connect(self.resume_scanning)
        self._mw.actionSave.triggered.connect(self.save_routine)

        self._step_state = False
        self.activate_params_tab()
        self.activate_scanning_tab()

        self.disable_action()
        self.enable_action()

        self.change_range_params()
        self.check_scanner_position()
        self.check_scan_range()
        
        self._mw.actionResume.setEnabled(False)

        # Show the main window
        self.show()


    def on_deactivate(self):
        """ Reverse steps of activation.
        """
        # save the params
        info_dict = self.gather_info_dict()
        with open(self.init_file_path, "wb") as f:
            pickle.dump(info_dict, f)
            
        # go to (0,0)
        self._magneto_logic.moveto(0, 0)
        self._pa.moveto_pushButton.clicked.disconnect()
        self.sigUpdateRoiSize.disconnect()
        self.sigUpdateRoiFromInput.disconnect()
        self.sigStartScan.disconnect()
        self.sigResumeScan.disconnect()
        self.sigStopScan.disconnect()
        self.sigRangeChanged.disconnect()
        self.sigResChanged.disconnect()
        self.sigClockChanged.disconnect()
        self.sigRsChanged.disconnect()
        self.sigIsobChanged.disconnect()
        self.sigFullbChanged.disconnect()
        self.sigPowerChanged.disconnect()
        
        self._mw.close()
        return 0

    
    def show(self):
        """ Make window visible and put it above all other windows. 
        """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()
        
        return
    
    
    def activate_params_tab(self):
        """
        Activation part for the params tab.
        """
        # auto save on
        self._pa.auto_save_checkBox.setChecked(True)

        # max scanner value
        self.max_scanner = 30e-6
        self._pa.x_position_DoubleSpinBox.setMaximum(self.max_scanner)
        self._pa.x_position_DoubleSpinBox.setMinimum(0)
        self._pa.y_position_DoubleSpinBox.setMaximum(self.max_scanner)
        self._pa.y_position_DoubleSpinBox.setMinimum(0)

        self._pa.x_res_SpinBox.setMinimum(2)
        self._pa.y_res_SpinBox.setMinimum(2)
        self._pa.rs_SpinBox.setMinimum(10e-9)
        self._pa.time_DoubleSpinBox.setMinimum(30e-3)
        
        # set max rf spinboxes values
        self._pa.mw_start_DoubleSpinBox.setMaximum(30e9)
        self._pa.mw_stop_DoubleSpinBox.setMaximum(30e9)
        self._pa.step_DoubleSpinBox.setMaximum(30e9)
        self._pa.step_hf_DoubleSpinBox.setMaximum(30e9)
        self._pa.min_fullb_DoubleSpinBox.setMaximum(30e9)
        self._pa.max_fullb_DoubleSpinBox.setMaximum(30e9)
        self._pa.number_sweeps_SpinBox.setMaximum(100)
        self._pa.number_sweeps_SpinBox.setMinimum(1)
        self._pa.threshold_DoubleSpinBox.setMaximum(30e9)
        self._pa.freq1_DoubleSpinBox.setMaximum(30e9)
        self._pa.freq2_DoubleSpinBox.setMaximum(30e9)
                
        # recall previously used values if existing
        try:
            self.recall_info_dict()
            h_range = self._pa.width_DoubleSpinBox.value()
            v_range = self._pa.height_DoubleSpinBox.value()
            self._pa.quenching_radioButton.setChecked(True)
            self.measmode = "quenching"
        except:
            # Get spinboxes values from logic
            h_range = self._magneto_logic.range[0][1] - self._magneto_logic.range[0][0]
            v_range = self._magneto_logic.range[1][1] - self._magneto_logic.range[1][0]
            self._pa.width_DoubleSpinBox.setValue(h_range)
            self._pa.height_DoubleSpinBox.setValue(v_range)            
            self._pa.x_position_DoubleSpinBox.setValue(self._magneto_logic.current_position[0])
            self._pa.y_position_DoubleSpinBox.setValue(self._magneto_logic.current_position[1])
            self._pa.x_res_SpinBox.setValue(self._magneto_logic.resolution[0])
            self._pa.y_res_SpinBox.setValue(self._magneto_logic.resolution[1])
            self._pa.time_DoubleSpinBox.setValue(1.0/self._magneto_logic.clock_frequency)
            self._pa.rs_SpinBox.setValue(self._magneto_logic.return_slowness)
            self._pa.quenching_radioButton.setChecked(True)
            self.measmode = "quenching"
            self._pa.hscan_radioButton.setChecked(True)
            self.scanmode = "_hpix"

        # center of the scan
        self._magneto_logic.center_position = [self._pa.x_position_DoubleSpinBox.value(),
                                               self._pa.y_position_DoubleSpinBox.value()]
        
        self._pa.scanner_pos_label.setText("{:.3f} µm, {:.3f} µm".format(
            self._magneto_logic.current_position[0]*1e6,
            self._magneto_logic.current_position[1]*1e6))
        
        # Connect buttons and spinboxes
        self._pa.moveto_pushButton.clicked.connect(self.moveto)
        self._pa.scanner_range_pushButton.clicked.connect(self.change_max_scanner)
        self._pa.quenching_radioButton.clicked.connect(self.measmode_changed)
        self._pa.fullb_radioButton.clicked.connect(self.measmode_changed)
        self._pa.isob_radioButton.clicked.connect(self.measmode_changed)
        self._pa.x_position_DoubleSpinBox.editingFinished.connect(self.check_scanner_position)
        self._pa.y_position_DoubleSpinBox.editingFinished.connect(self.check_scanner_position)  
        self._pa.width_DoubleSpinBox.editingFinished.connect(self.change_range_params)
        self._pa.height_DoubleSpinBox.editingFinished.connect(self.change_range_params)
        self._pa.x_res_SpinBox.editingFinished.connect(self.change_resolution_params)
        self._pa.y_res_SpinBox.editingFinished.connect(self.change_resolution_params)
        self._pa.time_DoubleSpinBox.editingFinished.connect(self.change_time_params)
        self._pa.rs_SpinBox.editingFinished.connect(self.change_rs_params)
        self._pa.hscan_radioButton.clicked.connect(self.scanmode_changed)
        self._pa.vscan_radioButton.clicked.connect(self.scanmode_changed)
        self._pa.sweep_power_DoubleSpinBox.editingFinished.connect(self.change_power_params)
        self._pa.mw_start_DoubleSpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.mw_stop_DoubleSpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.min_fullb_DoubleSpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.max_fullb_DoubleSpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.step_DoubleSpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.step_hf_DoubleSpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.number_sweeps_SpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.threshold_DoubleSpinBox.editingFinished.connect(self.change_fullb_params)
        self._pa.freq1_DoubleSpinBox.editingFinished.connect(self.change_isob_params)
        self._pa.freq2_DoubleSpinBox.editingFinished.connect(self.change_isob_params)
        
        self._magneto_logic.initialize_image(4, 4) # default quenching on start
        

    def activate_scanning_tab(self):
        """ Activate the scanning part.
        """
        # User input changed signals
        self._sc.pl_cb_min_DoubleSpinBox.valueChanged.connect(self.refresh_pl_image)
        self._sc.pl_cb_max_DoubleSpinBox.valueChanged.connect(self.refresh_pl_image)
        self._sc.pl_cb_ComboBox.currentIndexChanged.connect(self.refresh_pl_image)
        self._sc.topo_cb_min_DoubleSpinBox.valueChanged.connect(self.refresh_topo_image)
        self._sc.topo_cb_max_DoubleSpinBox.valueChanged.connect(self.refresh_topo_image)
        self._sc.topo_cb_ComboBox.currentIndexChanged.connect(self.refresh_topo_image)
        self._sc.pfcorrection_Button.clicked.connect(lambda: self.correct_topo('plane_fit'))
        
        # Internal signals
        self._sc.topo_manual_checkBox.toggled.connect(self.refresh_topo_image)
        self._sc.pl_manual_checkBox.toggled.connect(self.refresh_pl_image)

        # Set manual/auto colorbar button
        self._sc.topo_manual_checkBox.setChecked(False)
        self._sc.pl_manual_checkBox.setChecked(False)
    
        # Initialize the ComboBoxes for the colormap choice
        self.cdict = cdef.colordict
        self._sc.pl_cb_ComboBox.addItems(self.cdict.keys())
        self._sc.topo_cb_ComboBox.addItems(self.cdict.keys())

        self.recall_info_dict() # we cannot get the right colors otherwise
        if self._sc.pl_cb_ComboBox.currentText() == "":
            index_combobox = self._sc.pl_cb_ComboBox.findText("Inferno")
            self._sc.pl_cb_ComboBox.setCurrentIndex(index_combobox)
        if self._sc.topo_cb_ComboBox.currentText() == "":
            index_combobox = self._sc.topo_cb_ComboBox.findText("Gray")
            self._sc.topo_cb_ComboBox.setCurrentIndex(index_combobox)

        # Initialize the ComboBoxes for the plot choice
        self.set_comboBoxes()

        ## Load displays
        # Get images from the logic and load it in the displays
        topo_raw_data = self._magneto_logic.pl_image[:, :, 2]
        self.image_pl_plot = self._magneto_logic.pl_image[:, :, 3]
        h_range = self._pa.width_DoubleSpinBox.value()
        v_range = self._pa.height_DoubleSpinBox.value()

        # Update x and y axis
        self.pl_image = pg.ImageItem(image=self.image_pl_plot, axisOrder='row-major')
        self.pl_image.setRect(QtCore.QRectF(
            self._magneto_logic.current_position[0] - h_range * 0.5,
            self._magneto_logic.current_position[1] - v_range * 0.5,
            h_range,
            v_range
            ))
        self.topo_image = pg.ImageItem(image=topo_raw_data, axisOrder='row-major')
        self.topo_image.setRect(QtCore.QRectF(
            self._magneto_logic.current_position[0] - h_range * 0.5,
            self._magneto_logic.current_position[1] - v_range * 0.5,
            h_range,
            v_range
            ))
    
        self._sc.pl_ViewWidget.addItem(self.pl_image)
        self._sc.pl_ViewWidget.setAspectLocked(True) # for rectangular scans
        self._sc.topo_ViewWidget.addItem(self.topo_image)
        self._sc.topo_ViewWidget.setAspectLocked(True) # for rectangular scans
    
        # Label the axes:
        self._sc.pl_ViewWidget.setLabel('bottom', 'X position', units='m')
        self._sc.pl_ViewWidget.setLabel('left', 'Y position', units='m')
        self._sc.topo_ViewWidget.setLabel('bottom', 'X position', units='m')
        self._sc.topo_ViewWidget.setLabel('left', 'Y position', units='m')
    
        # Set colorscales
        self.my_colors_pl = self.cdict[self._sc.pl_cb_ComboBox.currentText()]()
        self.pl_image.setLookupTable(self.my_colors_pl.lut)
    
        self.my_colors_topo = self.cdict[self._sc.topo_cb_ComboBox.currentText()]()
        self.topo_image.setLookupTable(self.my_colors_topo.lut)

        # Set colorbar and add it to ViewWidget
        cb_range = [0, 1e6]
        self.pl_cb = ColorBar(self.my_colors_pl.cmap_normed, 100, cb_range[0], cb_range[1])
    
        self._sc.pl_cb_ViewWidget.addItem(self.pl_cb)
        self._sc.pl_cb_ViewWidget.hideAxis('bottom')
        self._sc.pl_cb_ViewWidget.hideAxis('left')
        if self.measmode == "quenching":
            self.pl_plot_text = "PL"
        else:
            self.pl_plot_text = "PL1"
        self.pl_plot_unit = "counts/s"
        self._sc.pl_cb_ViewWidget.setLabel('right', self.pl_plot_text, units=self.pl_plot_unit)
        self._sc.pl_cb_ViewWidget.setMouseEnabled(x=False, y=False)
    
        cb_range = [-10e-6, 10e-6]
        self.topo_cb = ColorBar(self.my_colors_topo.cmap_normed, 100, cb_range[0], cb_range[1])
    
        self._sc.topo_cb_ViewWidget.addItem(self.topo_cb)
        self._sc.topo_cb_ViewWidget.hideAxis('bottom')
        self._sc.topo_cb_ViewWidget.hideAxis('left')
        self._sc.topo_cb_ViewWidget.setLabel('right', 'Z', units='m')
        self._sc.topo_cb_ViewWidget.setMouseEnabled(x=False, y=False)

        # Create ROI for pl image and add it to pl image viewwidget
        roi_x_size = h_range
        roi_y_size = v_range
        self.roi_pl = CrossROI(
            [
                    self._magneto_logic.current_position[0] - roi_x_size * 0.5, 
                    self._magneto_logic.current_position[1] - roi_y_size * 0.5
            ],
            [roi_x_size, roi_y_size], pen={'color': "F0F", 'width': 1},
            removable=True)
    
        self._sc.pl_ViewWidget.addItem(self.roi_pl)
        
        # create horizontal and vertical line as a crosshair in xy image:
        self.hline_pl = CrossLine(pos=self.roi_pl.pos() + self.roi_pl.size() * 0.5,
                                  angle=0, pen={'color': palette.green, 'width': 1})
        self.vline_pl = CrossLine(pos=self.roi_pl.pos() + self.roi_pl.size() * 0.5,
                                  angle=90, pen={'color': palette.green, 'width': 1})
    
        self._sc.pl_ViewWidget.addItem(self.hline_pl)
        self._sc.pl_ViewWidget.addItem(self.vline_pl)
    
        # connect the change of a region with the adjustment of the crosshair:
        self.roi_pl.sigRegionChanged.connect(self.hline_pl.adjust)
        self.roi_pl.sigRegionChanged.connect(self.vline_pl.adjust)
        self.roi_pl.sigUserRegionUpdate.connect(self.update_roi_from_user)
        self.roi_pl.sigRegionChangeFinished.connect(self.roi_bounds_check)
        # connect the change of size with the ROI
        self.sigUpdateRoiSize.connect(self.roi_pl.update_roi_size)
        self.sigUpdateRoiFromInput.connect(self.roi_pl.update_roi_from_input)
        

        # Get topo and pl scanlines and load it in the displays
        current_line = self._magneto_logic.line_position[1]
        
        data = self._magneto_logic.pl_image[current_line, :, 0:3:2]
        self.topo_scanline = pg.PlotDataItem(data, pen=pg.mkPen(palette.c1))
        self._sc.topo_scanline_ViewWidget.addItem(self.topo_scanline)
        if self._magneto_logic.scan_mode == "_hpix":
            self._sc.topo_scanline_ViewWidget.setLabel('bottom', 'X position', units='m')
        else: 
            self._sc.topo_scanline_ViewWidget.setLabel('bottom', 'Y position', units='m')
        self._sc.topo_scanline_ViewWidget.setLabel('left', 'Z', units='m')
        
        data = self._magneto_logic.pl_image[current_line, :, 0:4:3]
        self.pl_scanline = pg.PlotDataItem(data, pen=pg.mkPen(palette.c1))
        self._sc.pl_scanline_ViewWidget.addItem(self.pl_scanline)
        self._sc.pl_scanline_ViewWidget.setLabel('left', 'PL1', units='cts/s')
        if self._magneto_logic.scan_mode == "_hpix":
            self._sc.pl_scanline_ViewWidget.setLabel('bottom', 'X position', units='m')
        else: 
            self._sc.pl_scanline_ViewWidget.setLabel('bottom', 'Y position', units='m')
        
        return


    def set_comboBoxes(self):
        """ Enable/disable and changes the items of the plot comboBoxes depending
        on the measurement mode.
        """
        if self.measmode == "quenching":
            self._sc.image_disp_comboBox.setEnabled(False)
            self._sc.line_disp_comboBox.setEnabled(False)  
        elif self.measmode == "isob":
            self._sc.image_disp_comboBox.clear()
            self._sc.image_disp_comboBox.addItems(["PL1", "PL2", "PL diff"])
            self._sc.image_disp_comboBox.setCurrentIndex(0)
            self._sc.image_disp_comboBox.setEnabled(True)
            self._sc.line_disp_comboBox.setEnabled(False)
        else:
            self._sc.image_disp_comboBox.clear()
            self._sc.image_disp_comboBox.addItems(["PL1", "PL2", "PL diff", "Freq"])
            self._sc.image_disp_comboBox.setCurrentIndex(0)
            self._sc.line_disp_comboBox.clear()
            self._sc.line_disp_comboBox.addItems(["Scanline", "ESR spectrum"])
            self._sc.line_disp_comboBox.setCurrentIndex(0)
            self._sc.image_disp_comboBox.setEnabled(True)
            self._sc.line_disp_comboBox.setEnabled(True)
        return
    

    def disable_action(self, lock_odmr=False):
        """ Disable all the possible actions while scanning.
        @params: lock_odmr, bool, True if we are just disabling
        the RF buttons because we use quenching.
        """
        if not lock_odmr :
            # do not allow restart a scan
            self._mw.actionSave.setEnabled(True)
            self._mw.actionStart.setEnabled(False)
            self._mw.actionPause.setEnabled(True)
            self._mw.actionResume.setEnabled(False)
            # do not allow param change
            self._pa.x_position_DoubleSpinBox.setEnabled(False)
            self._pa.y_position_DoubleSpinBox.setEnabled(False)
            self._pa.width_DoubleSpinBox.setEnabled(False)
            self._pa.height_DoubleSpinBox.setEnabled(False)
            self._pa.x_res_SpinBox.setEnabled(False)
            self._pa.y_res_SpinBox.setEnabled(False)
            self._pa.time_DoubleSpinBox.setEnabled(False)
            self._pa.rs_SpinBox.setEnabled(False)
            self._pa.moveto_pushButton.setEnabled(False)
            self._pa.hscan_radioButton.setEnabled(False)
            self._pa.vscan_radioButton.setEnabled(False)
            
        self._pa.sweep_power_DoubleSpinBox.setEnabled(False)
        self._pa.mw_start_DoubleSpinBox.setEnabled(False)      
        self._pa.mw_stop_DoubleSpinBox.setEnabled(False)
        self._pa.step_DoubleSpinBox.setEnabled(False)
        self._step_state = False
        self._pa.freq1_DoubleSpinBox.setEnabled(False)
        self._pa.freq2_DoubleSpinBox.setEnabled(False)
        self._pa.step_hf_DoubleSpinBox.setEnabled(False)
        self._pa.min_fullb_DoubleSpinBox.setEnabled(False)
        self._pa.max_fullb_DoubleSpinBox.setEnabled(False)
        self._pa.number_sweeps_SpinBox.setEnabled(False)
        self._pa.threshold_DoubleSpinBox.setEnabled(False)


    def enable_action(self, end=False):
        """ Enable all the possible actions if we are not scanning. 
        If the quenching mode is selected, we do not enable the RF buttons.
        @params: end, bool, True if we reached the end of the scan.
        """
        # Re-allow restart a scan
        self._mw.actionSave.setEnabled(True)
        self._mw.actionStart.setEnabled(True)
        self._mw.actionPause.setEnabled(False)
        self._mw.actionResume.setEnabled(True)
        # Re-allow the change of parameters       
        self._pa.x_position_DoubleSpinBox.setEnabled(True)
        self._pa.y_position_DoubleSpinBox.setEnabled(True)
        self._pa.width_DoubleSpinBox.setEnabled(True)
        self._pa.height_DoubleSpinBox.setEnabled(True)
        self._pa.x_res_SpinBox.setEnabled(True)
        self._pa.y_res_SpinBox.setEnabled(True)
        self._pa.time_DoubleSpinBox.setEnabled(True)
        self._pa.rs_SpinBox.setEnabled(True)
        self._pa.moveto_pushButton.setEnabled(True)
        self._pa.hscan_radioButton.setEnabled(True)
        self._pa.vscan_radioButton.setEnabled(True)
        if self.measmode != "quenching":
            self._pa.sweep_power_DoubleSpinBox.setEnabled(True)
            self._pa.mw_start_DoubleSpinBox.setEnabled(True)      
            self._pa.mw_stop_DoubleSpinBox.setEnabled(True)
            self._pa.step_DoubleSpinBox.setEnabled(True)
            self._step_state = True
            self._pa.freq1_DoubleSpinBox.setEnabled(True)
            self._pa.freq2_DoubleSpinBox.setEnabled(True)
            self._pa.step_hf_DoubleSpinBox.setEnabled(True)
            self._pa.min_fullb_DoubleSpinBox.setEnabled(True)
            self._pa.max_fullb_DoubleSpinBox.setEnabled(True)
            self._pa.number_sweeps_SpinBox.setEnabled(True)
            self._pa.threshold_DoubleSpinBox.setEnabled(True)

        # Display scanner position
        self._pa.scanner_pos_label.setText("{:.3f} µm, {:.3f} µm".format(
            self._magneto_logic.current_position[0]*1e6,
            self._magneto_logic.current_position[1]*1e6))

        # if auto save, save
        if end:
            self._mw.actionResume.setEnabled(False)
            if self._pa.auto_save_checkBox.isChecked():
               self.save_routine()


    def start_scanning(self):
        """ Prepare the GUI for the scan.
        """
        test = self.check_aspect_ratio()
        if test:
            self.disable_action()
            x = self._pa.x_position_DoubleSpinBox.value()
            y = self._pa.y_position_DoubleSpinBox.value()
            self.roi_pl.update_roi_from_input(x, y)
            if self.measmode == "fullb":
                self.change_fullb_params()
            elif self.measmode == "isob":
                self.change_isob_params()
            self.sigStartScan.emit()
            self._pa.scanner_pos_label.setText("scanning...")
            self.log.info("Scanning...")
        else:
            self.log.warning("Did not start scanning. Change the scan range or the resolution.")
        return


    def pause_scanning(self):
        """ Stop the scan.
        """
        self.enable_action()
        self.sigStopScan.emit()
        self._mw.actionResume.setEnabled(True)
        self.log.info("Scanning stopped.")
        return


    def resume_scanning(self):
        """ Prepare the GUI for the scan.
        """
        self.disable_action()
        x = self._pa.x_position_DoubleSpinBox.value()
        y = self._pa.y_position_DoubleSpinBox.value()
        self.roi_pl.update_roi_from_input(x, y)
        self.sigResumeScan.emit()
        self._pa.scanner_pos_label.setText("scanning...")
        self.log.info("Scanning...")
        return
               

    def change_range_params(self, init=False):
        """ Change range using the SpinBox values.

        @param: init, bool, True during the init when recalling the data
        from previous session.
        """
        self.log.info("Changing the scan range")
        range_scan = np.zeros(4)
        h_range = self._pa.width_DoubleSpinBox.value()
        v_range = self._pa.height_DoubleSpinBox.value()

        range_scan[0] = self._magneto_logic.center_position[0] - 0.5*h_range
        range_scan[1] = self._magneto_logic.center_position[0] + 0.5*h_range
        range_scan[2] = self._magneto_logic.center_position[1] - 0.5*v_range
        range_scan[3] = self._magneto_logic.center_position[1] + 0.5*v_range

        test = self.check_scan_range()
        self.sigRangeChanged.emit(range_scan)
        
        if not init:
            self.sigUpdateRoiSize.emit(range_scan, self.max_scanner)
        if test:
            self.log.info("Successfully changed the scan range")
        return
        

    def check_scan_range(self):
        """ Checks if we are going out of the range of the scanner.
        If we do, do not allow to start scanning.
        """
        range_scan = np.zeros(4)
        h_range = self._pa.width_DoubleSpinBox.value()
        v_range = self._pa.height_DoubleSpinBox.value()

        range_scan[0] = self._magneto_logic.center_position[0] - 0.5*h_range
        range_scan[1] = self._magneto_logic.center_position[0] + 0.5*h_range
        range_scan[2] = self._magneto_logic.center_position[1] - 0.5*v_range
        range_scan[3] = self._magneto_logic.center_position[1] + 0.5*v_range

        if range_scan[0] < 0 or range_scan[1] > self.max_scanner\
           or range_scan[2] < 0 or range_scan[3] > self.max_scanner:
            self.log.warning('Scanning region is out of range, please change your range.')
            self._mw.actionStart.setEnabled(False)
            self._mw.actionResume.setEnabled(False)
            result = False
        else:
            self._mw.actionStart.setEnabled(True)
            result = True
            self.log.info("Scan range OK.")

        return result


    def check_scanner_position(self):
        """ Compare if the scanner is at the position given by the spin boxes. 
        If not, does not allow to start scanning. Also changes the position of
        the cursor.
        """
        x = self._pa.x_position_DoubleSpinBox.value()
        y = self._pa.y_position_DoubleSpinBox.value()
        self._magneto_logic.center_position = [x, y]
        if np.abs(x- self._magneto_logic.current_position[0])>self._magneto_logic.return_slowness\
            or np.abs(y- self._magneto_logic.current_position[1])>self._magneto_logic.return_slowness:
            self.log.info("Scanner not yet at the desired position.")
            self._mw.actionStart.setEnabled(False)
            result = False
        else:
            self._mw.actionStart.setEnabled(True)
            result = True
            self.log.info("Scanner at the desired position.")
            
        self.sigUpdateRoiFromInput.emit(x, y)
        
        return result
    

    def check_aspect_ratio(self):
        """Check before starting the scan if the settings correspond to square pixels.
        If not, the resolution will be decreased to reach a correct aspect ratio.
        """
        x_range = self._pa.width_DoubleSpinBox.value()
        y_range = self._pa.height_DoubleSpinBox.value()
        px_x = self._pa.x_res_SpinBox.value()
        px_y = self._pa.y_res_SpinBox.value()

        scan_ratio = x_range/y_range
        res_ratio = px_x/px_y
        
        if np.abs(scan_ratio-res_ratio)>5e-2:    
            new_x_res = px_x
            new_y_res = int(np.ceil(px_x/scan_ratio))
            messagebox = QtGui.QMessageBox()
            messagebox.setText("Your pixels are not square. Choose cancel if you do not care."
                               +"If you choose OK, the "
                               +"resolution will be modified to {:d}x{:d}px.".format(
                                       new_x_res, new_y_res))
            messagebox.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
            messagebox.setWindowTitle("Warning")
            answer = messagebox.exec_()
            if answer == QtGui.QMessageBox.Ok:
                self._pa.x_res_SpinBox.setValue(new_x_res)
                self._pa.y_res_SpinBox.setValue(new_y_res)
                self.change_resolution_params()
                
        return True


    def change_resolution_params(self):
        """ Change resolution using the SpinBox values.
        """
        x_res = int(self._pa.x_res_SpinBox.value())
        y_res = int(self._pa.y_res_SpinBox.value())
    
        self.sigResChanged.emit(x_res, y_res)
        self.log.info("Changed pixel resolution.")
        return


    def change_time_params(self):
        """ Change time using the SpinBox value.
        """
        time_clock = self._pa.time_DoubleSpinBox.value()
        self.sigClockChanged.emit(time_clock)
        self.log.info("Changed time per pixel.")
        return 


    def change_rs_params(self):
        """ Change return slowness using the SpinBox value.
        """
        rs = self._pa.rs_SpinBox.value()
        self.sigRsChanged.emit(rs)
        self.log.info("Changed return slowness.")
        return


    def change_isob_params(self):
        """ Change frequencies using the SpinBox values.
        """
        freq1 = self._pa.freq1_DoubleSpinBox.value()
        freq2 = self._pa.freq2_DoubleSpinBox.value()
        self.sigIsobChanged.emit(freq1, freq2)
        self.log.info("Changed iso-B frequencies.")
        return
    

    def change_fullb_params(self):
        """ Change full-B parameters using the from SpinBox values.
        """
        start = self._pa.mw_start_DoubleSpinBox.value()
        stop = self._pa.mw_stop_DoubleSpinBox.value()
        min_fullb = self._pa.min_fullb_DoubleSpinBox.value()
        max_fullb = self._pa.max_fullb_DoubleSpinBox.value()
        step = self._pa.step_DoubleSpinBox.value()
        step_hf = self._pa.step_hf_DoubleSpinBox.value()
        number_sweeps = self._pa.number_sweeps_SpinBox.value()
        threshold = self._pa.threshold_DoubleSpinBox.value()
        self.sigFullbChanged.emit(start, stop, min_fullb, max_fullb, step, step_hf, number_sweeps, threshold)
        self.log.info("Changed full-B frequency parameters.")
        return
    

    def change_power_params(self):
        """ Change RF power using the SpinBox value.
        """
        power = self._pa.sweep_power_DoubleSpinBox.value()
        self.sigPowerChanged.emit(power)
        self.log.info("Changed RF power.")
        return


    def update_parameters(self, param_dict):
        """ Update the parameter display in the GUI.

        @param param_dict:
        Any change event from the logic should call this update function.
        The update will block the GUI signals from emitting a change back to the
        logic.
        """
        param = param_dict.get('clock_frequency')
        if param is not None:
            self._pa.time_DoubleSpinBox.blockSignals(True)
            self._pa.time_DoubleSpinBox.setValue(1.0/param)
            self._pa.time_DoubleSpinBox.blockSignals(False)
        
        param = param_dict.get('x_range')
        if param is not None:
            self._pa.width_DoubleSpinBox.blockSignals(True)
            self._pa.width_DoubleSpinBox.setValue(param[1]-param[0])
            self._pa.width_DoubleSpinBox.blockSignals(False)

        param = param_dict.get('y_range')
        if param is not None:
            self._pa.height_DoubleSpinBox.blockSignals(True)
            self._pa.height_DoubleSpinBox.setValue(param[1]-param[0])
            self._pa.height_DoubleSpinBox.blockSignals(False)
            
        param = param_dict.get('x_resolution')
        if param is not None:
            self._pa.x_res_SpinBox.blockSignals(True)
            self._pa.x_res_SpinBox.setValue(param)
            self._pa.x_res_SpinBox.blockSignals(False)
            
        param = param_dict.get('y_resolution')
        if param is not None:
            self._pa.y_res_SpinBox.blockSignals(True)
            self._pa.y_res_SpinBox.setValue(param)
            self._pa.y_res_SpinBox.blockSignals(False)
            
        param = param_dict.get('return_slowness')
        if param is not None:
            self._pa.rs_SpinBox.blockSignals(True)
            self._pa.rs_SpinBox.setValue(param)
            self._pa.rs_SpinBox.blockSignals(False)
            
        param = param_dict.get('sweep_mw_power')
        if param is not None:
            self._pa.sweep_power_DoubleSpinBox.blockSignals(True)
            self._pa.sweep_power_DoubleSpinBox.setValue(param)
            self._pa.sweep_power_DoubleSpinBox.blockSignals(False)
            
        param = param_dict.get('mw_start')
        if param is not None:
            self._pa.mw_start_DoubleSpinBox.blockSignals(True)
            self._pa.mw_start_DoubleSpinBox.setValue(param)
            self._pa.mw_start_DoubleSpinBox.blockSignals(False)
            
        param = param_dict.get('mw_stop')
        if param is not None:
            self._pa.mw_stop_DoubleSpinBox.blockSignals(True)
            self._pa.mw_stop_DoubleSpinBox.setValue(param)
            self._pa.mw_stop_DoubleSpinBox.blockSignals(False)
            
        param = param_dict.get('mw_step')
        if param is not None and self._step_state:
            self._pa.step_DoubleSpinBox.blockSignals(True)
            self._pa.step_DoubleSpinBox.setValue(param)
            self._pa.step_DoubleSpinBox.blockSignals(False)
            
        param = param_dict.get('number_sweeps')
        if param is not None:
            self._pa.number_sweeps_SpinBox.blockSignals(True)
            self._pa.number_sweeps_SpinBox.setValue(param)
            self._pa.number_sweeps_SpinBox.blockSignals(False)
            
        param = param_dict.get('freq1')
        if param is not None:
            self._pa.freq1_DoubleSpinBox.blockSignals(True)
            self._pa.freq1_DoubleSpinBox.setValue(param)
            self._pa.freq1_DoubleSpinBox.blockSignals(False)
            
        param = param_dict.get('freq2')
        if param is not None:
            self._pa.freq2_DoubleSpinBox.blockSignals(True)
            self._pa.freq2_DoubleSpinBox.setValue(param)
            self._pa.freq2_DoubleSpinBox.blockSignals(False)
            
        param = param_dict.get('x')
        if param is not None:
            pos_text = "{:.3f} µm, {:.3f} µm".format(param*1e6, param_dict['y']*1e6)
            self._pa.scanner_pos_label.setText(pos_text)

        return 


    def measmode_changed(self):
        """ Update the measurement mode requested from radio buttons.
        @return str: measurement mode
        """
        if self._pa.quenching_radioButton.isChecked():
            self.measmode = "quenching"
            self.disable_action(lock_odmr=True)
        elif self._pa.isob_radioButton.isChecked():
            self.measmode = "isob"
            self.enable_action(end=False)
            self.change_isob_params()
        else:
            self.measmode = "fullb"
            self.enable_action(end=False)
            self.change_fullb_params()
        self.sigMeasModeChanged.emit(self.measmode)
        self.change_range_params()
        self.check_scanner_position()
        self.check_scan_range()
        self.log.info("Changed measurement mode to {}.".format(self.measmode))
        self.set_comboBoxes()
        self._mw.actionResume.setEnabled(False)
        return self.measmode


    def scanmode_changed(self):
        """ Update the scan mode requested from radio buttons.
        @return str: scan mode function
        """
        if self._pa.hscan_radioButton.isChecked():
            scanmode = "_h"
        else:
            scanmode = "_v"
        self.scanmode = scanmode + "pix"
        self._magneto_logic.scan_mode = self.scanmode
        self.log.info("Status: Updated scan mode to {}.".format(self._magneto_logic.scan_mode))
        self.change_resolution_params()
        return self._magneto_logic.scan_mode


    def moveto(self):
        """ Action when the MoveTo button is pushed.
        """
        x = self._pa.x_position_DoubleSpinBox.value()
        y = self._pa.y_position_DoubleSpinBox.value()
        self.sigUpdateRoiFromInput.emit(x, y)
        self._magneto_logic.moveto(x, y)
        self._magneto_logic.sigMovetoEnded.emit(False)
        return


    def enable_disable_moveto(self, status=True):
        """ Enable of disable the move to button.
        """
        self._pa.moveto_pushButton.setEnabled(status)
        if status == True:
            test_range = self.check_scan_range()


    def update_duration(self, duration):
        """ Update the displayed estimation of the scan duration.
        @param str: string to display, showing the estimated time
        """
        self._pa.display_scan_duration.setText(duration)


    def update_rem_time(self, rem_time):
        """ Update the scan remaining time.
        @param str: string to display, showing the estimated time left
        """
        self._pa.display_remaining_time.setText(rem_time)
    

    def change_max_scanner(self):
        """
        Opens a dialog to input a new scanner range.
        """
        dialog = QtGui.QInputDialog()
        value, ok = dialog.getDouble(self._mw,"Scanner range", "New maximum scanner range (in µm):", self.max_scanner*1e6, 0, 100, 3)
        if value and ok:
            self.max_scanner = value*1e-6
            self._pa.x_position_DoubleSpinBox.setMaximum(self.max_scanner)
            self._pa.y_position_DoubleSpinBox.setMaximum(self.max_scanner)
            self._pa.width_DoubleSpinBox.setMaximum(self.max_scanner)
            self._pa.height_DoubleSpinBox.setMaximum(self.max_scanner)
            self.log.info("Changed max scanner range")
        return


    def update_plots(self, pl_image, scanline, esr_line):
        """ Refresh the plot widgets with new data. 
        
        @params np.darray: pl_image [x, y, topo, PL] if quenching,
                                    [x, y, topo, PLdiff, PL1, PL2] if isob,
                                    [x, y, topo, Freq, PLdiff, PL1, PL2] if fullb
        @params np.darray: scanline [x, topo_scanline, PL_scanline] if quenching
                                    [x, topo_scanline, PLdiff_scanline, PL1_scanline, PL2_scanline] if isob
                                    [x, topo_scanline, Freq_scanline, PLdiff_scanline, PL1_scanline, 
                                     PL2_scanline] if fullb 
        @params np.ndarray: esrline, empty array if not in fullb mode, [freq, PL]
        """
        topo_image = pl_image[:, :, 2]
        topo_scanline = scanline[:, 0:2]
        cb_range = self.get_cb_range(topo_image, "topo")
        
        self.topo_image.setImage(image=topo_image, levels=(cb_range[0], cb_range[1]))
        self.topo_scanline.setData(topo_scanline)
        if self.scanmode == "_hpix":
            self._sc.topo_scanline_ViewWidget.setLabel('bottom', 'X position', units='m')
        else: 
            self._sc.topo_scanline_ViewWidget.setLabel('bottom', 'Y position', units='m')        
        self.refresh_colorbar('topo')

        image_temp, scanline_temp = self.get_data_to_plot(pl_image, scanline, esr_line)
        cb_range = self.get_cb_range(image_temp, "pl")
        self.pl_image.setImage(image=image_temp, levels=(cb_range[0], cb_range[1]))
        self.pl_scanline.setData(scanline_temp)
        if self._sc.image_disp_comboBox.currentText() == "Freq":
            self._sc.pl_scanline_ViewWidget.setLabel('left', 'Frequency', units='Hz')
        if self._sc.line_disp_comboBox.currentText() == "ESR spectrum":
            self._sc.pl_scanline_ViewWidget.setLabel('bottom', 'Frequency', units='Hz')
            self._sc.pl_scanline_ViewWidget.setLabel('left', 'PL', units='counts/s')
        elif self.scanmode == "_hpix":
            self._sc.pl_scanline_ViewWidget.setLabel('bottom', 'X position', units='m')
        else: 
            self._sc.pl_scanline_ViewWidget.setLabel('bottom', 'Y position', units='m')
        self.refresh_colorbar('pl')

        # update x and y axis
        h_range = self._pa.width_DoubleSpinBox.value()
        v_range = self._pa.height_DoubleSpinBox.value()
        self.pl_image.setRect(QtCore.QRectF(
                self._pa.x_position_DoubleSpinBox.value() - h_range * 0.5,
                self._pa.y_position_DoubleSpinBox.value() - v_range * 0.5,
                h_range,
                v_range
                ))
        self.topo_image.setRect(QtCore.QRectF(
                self._pa.x_position_DoubleSpinBox.value() - h_range * 0.5,
                self._pa.y_position_DoubleSpinBox.value() - v_range * 0.5,
                h_range,
                v_range
                ))
        return
        
    
    def get_data_to_plot(self, pl_image, scanline, esr_line):
        """ From the measurement mode and the desired display, selects the correct data to plot.
        @params np.darray: pl_image [x, y, topo, PL] if quenching,
                                    [x, y, topo, PLdiff, PL1, PL2] if isob,
                                    [x, y, topo, Freq, PLdiff, PL1, PL2, Freq*N, PLFreq*N] if fullb
        @params np.darray: scanline [x, topo_scanline, x, PL_scanline] if quenching
                                    [x, topo_scanline, x, PLdiff_scanline, x, PL1_scanline, x, PL2_scanline]
                                     if isob
                                    [x, topo_scanline, Freq_scanline, PLdiff_scanline, PL1_scanline, 
                                     PL2_scanline] if fullb 
        @params np.ndarray: esr_line, empty array if not in fullb mode, [freq, PL]
        @return np.ndarray: self.image_pl_plot
        @return np.ndarray: scanline_temp
        """
        if self.measmode == "quenching":
            self.image_pl_plot = pl_image[:, :, 3]
            scanline_temp = scanline[:, 2:4]
            self.pl_plot_text = "PL"
            self.pl_plot_unit = "counts/s"
            
        elif self.measmode == "isob":
            self.pl_plot_unit = "counts/s"
            if self._sc.image_disp_comboBox.currentText() == "PL diff":
                self.image_pl_plot = pl_image[:, :, 3]
                scanline_temp = scanline[:, 2:4]
                self.pl_plot_text = "PL diff"
            elif self._sc.image_disp_comboBox.currentText() == "PL1":
                self.image_pl_plot = pl_image[:, :, 4]
                scanline_temp = scanline[:, 4:6]
                self.pl_plot_text = "PL1"
            elif self._sc.image_disp_comboBox.currentText() == "PL2":
                self.image_pl_plot = pl_image[:, :, 5]
                scanline_temp = scanline[:, 6:8]
                self.pl_plot_text = "PL2"
        else:
            if self._sc.image_disp_comboBox.currentText() == "Freq":
                self.image_pl_plot = pl_image[:, :, 3]
                scanline_temp = scanline[:, 2:4]
                self.pl_plot_text = "Freq shift"
                self.pl_plot_unit = "Hz"
                self._sc.pl_cb_min_DoubleSpinBox.setSuffix("Hz")
                self._sc.pl_cb_max_DoubleSpinBox.setSuffix("Hz")
            elif self._sc.image_disp_comboBox.currentText() == "PL diff":
                self.image_pl_plot = pl_image[:, :, 4]
                scanline_temp = scanline[:, 4:6]
                self.pl_plot_text = "PL diff"
                self.pl_plot_unit = "counts/s"
                self._sc.pl_cb_min_DoubleSpinBox.setSuffix("c")
                self._sc.pl_cb_max_DoubleSpinBox.setSuffix("c")
            elif self._sc.image_disp_comboBox.currentText() == "PL1":
                self.image_pl_plot = pl_image[:, :, 5]
                scanline_temp = scanline[:, 6:8]
                self.pl_plot_text = "PL1"
                self.pl_plot_unit = "counts/s"
                self._sc.pl_cb_min_DoubleSpinBox.setSuffix("c")
                self._sc.pl_cb_max_DoubleSpinBox.setSuffix("c")
            elif self._sc.image_disp_comboBox.currentText() == "PL2":
                self.image_pl_plot = pl_image[:, :, 6]
                scanline_temp = scanline[:, 8:10]
                self.pl_plot_text = "PL2"
                self.pl_plot_unit = "counts/s"
            if self._sc.line_disp_comboBox.currentText() == "ESR spectrum":
                scanline_temp = esr_line
      
        return self.image_pl_plot, scanline_temp
        

    def refresh_pl_image(self):
        """ Update the pl image when the cb manually changes.
        """
        try: #we get troubles at the init when pl_image is not defined
            cb_range = self.get_cb_range(self.image_pl_plot, 'pl')
            # change colors
            self.my_colors_pl = self.cdict[self._sc.pl_cb_ComboBox.currentText()]()
            self.pl_image.setLookupTable(self.my_colors_pl.lut)
        
            # change image
            self.pl_image.setImage(image=self.image_pl_plot, levels=(cb_range[0], cb_range[1]))
        
            # change colorbar
            self.refresh_colorbar("pl")
        except:
            self.log.warning('Could not refresh the image.')
        return


    def refresh_topo_image(self):
        """ Update the topo image when the cb manually changes.
        """
        
        try: #we get troubles at the init when topo_image is not defined
            image_temp = self._magneto_logic.pl_image[:, :, 2]
            cb_range = self.get_cb_range(image_temp, 'topo')
            # change colors
            self.my_colors_topo = self.cdict[self._sc.topo_cb_ComboBox.currentText()]()
            self.topo_image.setLookupTable(self.my_colors_topo.lut)
        
            # change image
            self.topo_image.setImage(image=image_temp, levels=(cb_range[0], cb_range[1]))
        
            # change colorbar
            self.refresh_colorbar("topo")
        except:
            self.log.warning('Could not refresh the topo image.')
        return
    
    def correct_topo(self, corr_fct):
        """ Correct the topography in the scan
        """
        self._magneto_logic.correct_topo(corr_fct)
        return 0

    def refresh_colorbar(self, mode):
        """ Adjust the colorbar.

        Calls the refresh method from colorbar, which takes either the lowest
        and higherst value in the image or predefined ranges. Note that you can
        invert the colorbar if the lower border is bigger then the higher one.
        Remarks: values below one or above 1e9 are creating troubles. Therefore,
        in this case, the cb_range is modified here to fit between these limits
        and the ticks are rewritten.

        @params str: "pl" or "topo"
        """
        if mode == "topo":
            cb_range = self.get_cb_range(self._magneto_logic.pl_image[:, :, 2], mode)
        else:
            cb_range = self.get_cb_range(self.image_pl_plot, mode)

        # check values, change if needed
        if cb_range[1] < 1:
            # too small
            change_ticks = True
            try:
                coeff = 10**(int(np.log10(1/(cb_range[0]+1e-20)))+5)
            except:
                coeff = 1e5
            cb_range_bar = [coeff*cb_range[0], coeff*cb_range[1]]
            
        elif cb_range[0] > 1e8:
            # too large
            change_ticks = True
            coeff = 10**(-int(np.log10(cb_range[1]/1e8))-5)
            cb_range_bar = [coeff*cb_range[0], coeff*cb_range[1]]
        else:
            cb_range_bar = cb_range
            change_ticks = False

        if mode == 'topo':
            self.topo_cb.refresh_colorbar(cb_range_bar[0], cb_range_bar[1],
                                          cmap=self.my_colors_topo.cmap_normed)
            self._sc.topo_cb_ViewWidget.setLabel('right', 'Z', units='m')
             # in case we need to change the labels
            ax = self._sc.topo_cb_ViewWidget.getAxis('right')
            unit = "m"
            text = "Z"
        else:
            self.pl_cb.refresh_colorbar(cb_range_bar[0], cb_range_bar[1], cmap=self.my_colors_pl.cmap_normed)
            self._sc.pl_cb_ViewWidget.setLabel('right', self.pl_plot_text, units=self.pl_plot_unit)
            # in case we need to change the labels
            ax = self._sc.pl_cb_ViewWidget.getAxis('right')
            unit = self.pl_plot_unit
            text = self.pl_plot_text
            
        # rewrite the tick labels if necessary
        if change_ticks:
            scale, prefix = pg.functions.siScale(cb_range[1])
            try: # empty list at the beginning, creates an error
                val = ax.tickValues(cb_range[0], cb_range[1], ax.size().height())
            except:
                val = [(1, [cb_range[0], cb_range[1]])]
            strings = []
            for v in val:
                strings.append(ax.tickStrings(v[1], scale, v[0]))
            
            newt = []
            for j in range(len(val)):
                level = []
                for i, v in enumerate(val[j][1]):
                    level.append((v*coeff, strings[j][i]))
                newt.append(level)
            ax.setTicks(newt)
            ax.setLabel(text=text, units=unit, unitPrefix=prefix)

        return
    

    def get_cb_range(self, image, mode):
        """ Determines the cb_min and cb_max values for the image
        
        @params np.ndarray: image, data to plot
        @params str: 'pl' or 'topo', to indicate which plotwidget needs to be used.
        """
        try:
            nonzero_image = image[np.nonzero(image)] # we do not consider the areas unscanned
            if mode == 'topo':
                if not self._sc.topo_manual_checkBox.isChecked():
                    cb_min = np.min(nonzero_image)
                    cb_max = np.max(image)
                    self._sc.topo_cb_min_DoubleSpinBox.setValue(cb_min)
                    self._sc.topo_cb_max_DoubleSpinBox.setValue(cb_max)
                else:
                    cb_min = self._sc.topo_cb_min_DoubleSpinBox.value()
                    cb_max = self._sc.topo_cb_max_DoubleSpinBox.value()
            else:
                if not self._sc.pl_manual_checkBox.isChecked():
                    cb_min = np.min(nonzero_image)
                    cb_max = np.max(image)
                    self._sc.pl_cb_min_DoubleSpinBox.setValue(cb_min)
                    self._sc.pl_cb_max_DoubleSpinBox.setValue(cb_max)
                else:
                    cb_min = self._sc.pl_cb_min_DoubleSpinBox.value()
                    cb_max = self._sc.pl_cb_max_DoubleSpinBox.value()
            
            cb_range = [cb_min, cb_max]
            return cb_range
        
        except:
            if mode == 'topo':
                if not self._sc.topo_manual_checkBox.isChecked():
                    cb_min = np.min(image)
                    cb_max = np.max(image)
                else:
                    cb_min = self._sc.topo_cb_min_DoubleSpinBox.value()
                    cb_max = self._sc.topo_cb_max_DoubleSpinBox.value()
            else:
                if not self._sc.pl_manual_checkBox.isChecked():
                    cb_min = np.min(image)
                    cb_max = np.max(image)
                else:
                    cb_min = self._sc.pl_cb_min_DoubleSpinBox.value()
                    cb_max = self._sc.pl_cb_max_DoubleSpinBox.value()
            cb_range = [cb_min, cb_max]
            return cb_range


    def update_roi_from_user(self, roi):
        """The user manually moved the ROI, adjust all other GUI elements accordingly

        @params object: PyQtGraph ROI object
        """
        h_pos, v_pos = roi.update_roi_from_user(self.max_scanner)
        
        self._pa.x_position_DoubleSpinBox.setValue(h_pos)
        self._pa.y_position_DoubleSpinBox.setValue(v_pos)
        self._magneto_logic.center_position = [h_pos, v_pos]
        return


    def roi_bounds_check(self, roi):
        """ Check if the focus cursor is outside the allowed range after drag
        and set its position to the limit
            
        @param object: PyQtGraph ROI object
        """
        roi.roi_bounds_check(self.max_scanner)
            
        return 0 
        

    def gather_info_dict(self):
        """Creates a dict with the info to store in the init file for the next session.
        """
        self.log.info("Gathering dict with parameters for storage.")
        info_dict = {}
        info_dict["x center position"] = self._pa.x_position_DoubleSpinBox.value()
        info_dict["y center position"] = self._pa.y_position_DoubleSpinBox.value()
        info_dict["scan width"] = self._pa.width_DoubleSpinBox.value()
        info_dict["scan height"] = self._pa.height_DoubleSpinBox.value()
        info_dict["x resolution"] = self._pa.x_res_SpinBox.value()
        info_dict["y resolution"] = self._pa.y_res_SpinBox.value()
        info_dict["time per pixel"] = self._pa.time_DoubleSpinBox.value()
        info_dict["return slowness"] = self._pa.rs_SpinBox.value()
        info_dict["comment"] = self._pa.Comments_textEdit.toPlainText()
        info_dict["max scanner"] = self.max_scanner
        if self._pa.hscan_radioButton.isChecked():
            info_dict["scan mode"] = "_h"
        else:
            info_dict["scan mode"] = "_v"
        info_dict["sweep_power"] = self._pa.sweep_power_DoubleSpinBox.value()
        info_dict["mw_start"] = self._pa.mw_start_DoubleSpinBox.value()
        info_dict["mw_stop"] = self._pa.mw_stop_DoubleSpinBox.value()
        info_dict["min_fullb"] = self._pa.min_fullb_DoubleSpinBox.value()
        info_dict["max_fullb"] = self._pa.max_fullb_DoubleSpinBox.value()
        info_dict["mw_step"] = self._pa.step_DoubleSpinBox.value()
        info_dict["mw_step_hf"] = self._pa.step_hf_DoubleSpinBox.value()
        info_dict["number_sweeps"] = self._pa.number_sweeps_SpinBox.value()
        info_dict["threshold"] = self._pa.threshold_DoubleSpinBox.value()
        info_dict["freq1"] = self._pa.freq1_DoubleSpinBox.value()
        info_dict["freq2"] = self._pa.freq2_DoubleSpinBox.value()
        info_dict["save tag"] = self._pa.file_tag_lineEdit.text()
        
        info_dict["cmap pl"] = self._sc.pl_cb_ComboBox.currentText()
        info_dict["cmap topo"] = self._sc.topo_cb_ComboBox.currentText()
        
        return info_dict


    def recall_info_dict(self):
        """
        Loads the parameters from the dict contained in the init file
        """
        with open(self.init_file_path, "rb") as f: 
            info_dict = pickle.load(f)
            
        self._pa.x_position_DoubleSpinBox.setValue(info_dict["x center position"])
        self._pa.y_position_DoubleSpinBox.setValue(info_dict["y center position"])
        self._pa.width_DoubleSpinBox.setValue(info_dict["scan width"])
        self._pa.height_DoubleSpinBox.setValue(info_dict["scan height"])
        self.change_range_params(init=True)      
        self._pa.x_res_SpinBox.setValue(info_dict["x resolution"])
        self._pa.y_res_SpinBox.setValue(info_dict["y resolution"])
        self.change_resolution_params()
        
        self._pa.time_DoubleSpinBox.setValue(info_dict["time per pixel"])
        self.change_time_params()
        
        self._pa.rs_SpinBox.setValue(info_dict["return slowness"])
        self.change_rs_params()
        
        self._pa.Comments_textEdit.setText(info_dict["comment"])
       
        if info_dict["scan mode"] == "_h":
            self._pa.hscan_radioButton.setChecked(True)
        else:
            self._pa.vscan_radioButton.setChecked(True)
        self.scanmode_changed()
        
        self._pa.sweep_power_DoubleSpinBox.setValue(info_dict['sweep_power'])
        self.change_power_params()
        
        self._pa.mw_start_DoubleSpinBox.setValue(info_dict['mw_start'])
        self._pa.mw_stop_DoubleSpinBox.setValue(info_dict['mw_stop'])
        self._pa.step_DoubleSpinBox.setValue(info_dict['mw_step'])
        self._pa.min_fullb_DoubleSpinBox.setValue(info_dict['min_fullb'])
        self._pa.max_fullb_DoubleSpinBox.setValue(info_dict['max_fullb'])
        self._pa.number_sweeps_SpinBox.setValue(info_dict['number_sweeps'])
        self._pa.step_hf_DoubleSpinBox.setValue(info_dict['mw_step_hf'])
        self._pa.threshold_DoubleSpinBox.setValue(info_dict['threshold'])
        self.change_fullb_params()
        
        self._pa.freq1_DoubleSpinBox.setValue(info_dict['freq1'])
        self._pa.freq2_DoubleSpinBox.setValue(info_dict['freq2'])
        self.change_isob_params()

        self.max_scanner = info_dict["max scanner"]

        self._pa.file_tag_lineEdit.setText(info_dict["save tag"])
        
        self._sc.pl_cb_ComboBox.setCurrentText(info_dict["cmap pl"])
        self._sc.topo_cb_ComboBox.setCurrentText(info_dict["cmap topo"])
        
        self.log.info("Recalled settings")
        return info_dict

    
    def save_routine(self):
        """ Run the save routine from the logic to save the data.
        """
        self._magneto_logic.user_save_tag = self._pa.file_tag_lineEdit.text()
        self._magneto_logic.user_comment = self._pa.Comments_textEdit.toPlainText()
        self._magneto_logic.save_data()
        self.log.info("Saving data")
        return
