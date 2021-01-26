# -*- coding: utf-8 -*-

"""
This file contains the Qudi cryomonitoring gui.

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
import os
import pyqtgraph as pg

from core.module import Connector
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from gui.guiutils import TimeAxisItem, timestamp
from qtpy import QtCore, QtGui
from qtpy import QtWidgets
from qtpy import uic


class CryomonitoringMainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self, **kwargs):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_cryomonitoring.ui')

        # Load it
        super().__init__(**kwargs)
        uic.loadUi(ui_file, self)
        self.show()

class CryomonitoringGui(GUIBase):
    """ GUI to display the lHe level and the temperature of the cryo. """

    _modclass = 'CryomonitoringGui'
    _modtype = 'gui'

    # declare connectors
    cryomonitoringlogic = Connector(interface='CyromonitoringLogic')

    # declare signals
    sigTimeWindowChanged = QtCore.Signal()
    sigStartMonitoring = QtCore.Signal()
    sigStopMonitoring = QtCore.Signal()
    sigStartRecording = QtCore.Signal()
    sigStopRecording = QtCore.Signal()
    sigLaunchlHeMeas = QtCore.Signal()
    sigChangelHeMeasMode = QtCore.Signal()
    
    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition, configuration and initialisation of the nv orientation finder GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        """

        self._cryologic = self.cryomonitoringlogic()

        ########################################################################
        #                      General configurations                          #
        ########################################################################
        
        # use the inherited class 'Ui_CryoMonitoringGuiUI' to create now the GUI element:
        self._mw = CryomonitoringMainWindow()

        ########################################################################
        #                          Connect signals                             #
        ########################################################################
        
        # interaction with user
        self._mw.spinBox_time_lHe.valueChanged.connect(self.set_lHe_meas_interval)
        self._mw.pushButton_lHe.clicked.connect(self.set_lHe_meas_mode)
        self._mw.radioButton_lHe_no_measure.toggled.connect(self.set_lHe_meas_interval)
        self._mw.radioButton_lHe_measure_every.toggled.connect(self.set_lHe_meas_interval)
        self._mw.spinBox_time_temp.valueChanged.connect(self.set_temp_meas_interval)
        self._mw.checkBox_temp_channelA.stateChanged.connect(self.set_temp_channels)
        self._mw.checkBox_temp_channelB.stateChanged.connect(self.set_temp_channels)
        self._mw.comment_lineEdit.editingFinished.connect(self.set_comment)

        self._mw.actionTimeWindow.triggered.connect(self.set_time_window)
        self._mw.actionStartMonitoring.triggered.connect(self.start_stop_monitoring)
        self._mw.actionRecordData.triggered.connect(self.start_stop_recording)

        # signals from logic
        self._cryologic.sigUpdatelHePlot.connect(self.refresh_lHe_plot, QtCore.Qt.QueuedConnection)
        self._cryologic.sigUpdateTempPlot.connect(self.refresh_temp_plot, QtCore.Qt.QueuedConnection)

        # Signals to logic
        self.sigTimeWindowChanged.connect(self._cryologic.plot_window_changed)
        self.sigStartMonitoring.connect(self._cryologic.start_monitoring)
        self.sigStopMonitoring.connect(self._cryologic.stop_monitoring)
        self.sigStartRecording.connect(self._cryologic.start_recording)
        self.sigStopRecording.connect(self._cryologic.stop_recording)
        self.sigLaunchlHeMeas.connect(self._cryologic.launch_lHe_thread)
        self.sigChangelHeMeasMode.connect(self._cryologic.change_lHe_meas_mode)

        ########################################################################
        #                          Load displays                               #
        ########################################################################
        self._mw.checkBox_temp_channelA.setChecked(True)
        self._mw.checkBox_temp_channelB.setChecked(False)
        self._mw.radioButton_lHe_no_measure.setChecked(True)
        self._mw.radioButton_lHe_measure_every.setChecked(False)
        
        # set device IDs
        self._mw.label_lHemeter_status.setText(self._cryologic._lHe_meter._model)
        self._mw.label_temp_status.setText(self._cryologic._thermometer._model)

        # initialize the plots
        axis_lHe = TimeAxisItem(orientation="bottom")
        self.lHe_plot = pg.PlotDataItem(np.array([timestamp()]), np.zeros(1),
                                        pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                        symbol='o',
                                        symbolPen=palette.c1,
                                        symbolBrush=palette.c1,
                                        symbolSize=3)
        self._mw.lHe_level_ViewWidget.addItem(self.lHe_plot)
        self._mw.lHe_level_ViewWidget.setLabel("bottom", "Time")
        self._mw.lHe_level_ViewWidget.setLabel("left", "lHe level", unit="%")
        axis_lHe.attachToPlotItem(self._mw.lHe_level_ViewWidget.getPlotItem())

        axis_temp = TimeAxisItem(orientation="bottom")
        self.temp_plotA = pg.PlotDataItem(np.array([timestamp()]), np.zeros(1),
                                          pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                          symbol='o',
                                          symbolPen=palette.c1,
                                          symbolBrush=palette.c1,
                                          symbolSize=3)
        self._mw.temp_ViewWidget.addItem(self.temp_plotA)
        self.temp_plotB = pg.PlotDataItem(np.array([timestamp()]), np.ones(1),
                                          pen=pg.mkPen(palette.c2, style=QtCore.Qt.DotLine),
                                          symbol='o',
                                          symbolPen=palette.c2,
                                          symbolBrush=palette.c2,
                                          symbolSize=3)
        self._mw.temp_ViewWidget.addItem(self.temp_plotB)
        self._mw.temp_ViewWidget.setLabel("bottom", "Time")
        self._mw.temp_ViewWidget.setLabel("left", "Temperature", unit="K")
        axis_temp.attachToPlotItem(self._mw.temp_ViewWidget.getPlotItem())
        legend = pg.LegendItem()
        legend.addItem(self.temp_plotA, name="  Channel A")
        legend.addItem(self.temp_plotB, name="  Channel B")
        legend.setParentItem(self._mw.temp_ViewWidget.getPlotItem())
        legend.setPos(75, 25)

        # show the main window
        self.show()

        return

                
    def on_deactivate(self):
        """ 
        Reverse steps of activation.
        """
        self._cryologic.sigUpdatelHePlot.disconnect()
        self._cryologic.sigUpdateTempPlot.disconnect()
        self._mw.close()
        
        
    def show(self):
        """ Make window visible and put it above all other windows. 
        """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()
        
        return

        
    def set_lHe_meas_interval(self):
        """ 
        Set the time between two measurements (in hold mode) , and if we should measure at all.
        In continous mode, we take the value every 5 seconds.
        """
        already_running = False
        if self._cryologic.meas_lHe == True and self._cryologic.monitoring:
            already_running = True
        if self._mw.radioButton_lHe_no_measure.isChecked():
            self._cryologic.lHe_meas_interval = np.nan
            self._cryologic.meas_lHe = False
        elif self._mw.radioButton_lHe_measure_every.isChecked():
            self._cryologic.lHe_meas_interval = self._mw.spinBox_time_lHe.value()*60
            self._cryologic.meas_lHe = True
        # override if Continous mode
        if self._cryologic.levelmeter_mode == "Continuous":
            self._cryologic.lHe_meas_interval = 5
            self._cryologic.meas_lHe = True
        if self._cryologic.meas_lHe and self._cryologic.monitoring and not already_running:
            self.sigLaunchlHeMeas.emit()

    
    def set_lHe_meas_mode(self):
        """
        Choose between hold and continuous, updates the button and the measurement interval.
        """
        if self._mw.pushButton_lHe.text() == "Continuous":
            self._cryologic.levelmeter_mode = "Continuous"
            self._mw.pushButton_lHe.setText("Hold")
            self.log.info("Switching to continuous mode.")
        else:
            self._cryologic.levelmeter_mode = "Sample/Hold"
            self._mw.pushButton_lHe.setText("Continuous")
            self.log.info("Switching to hold mode.")
        self.sigChangelHeMeasMode.emit()
        self.set_lHe_meas_interval()
        return


    def set_temp_meas_interval(self):
        """ 
        Set the time between two temperature reading, minimum 2 seconds.
        """
        self._cryologic.temp_meas_interval = self._mw.spinBox_time_temp.value()
        return

    
    def set_temp_channels(self):
        """
        Selection of the channels to read on the Lakeshore.
        """
        if self._mw.checkBox_temp_channelA.isChecked() and\
           self._mw.checkBox_temp_channelB.isChecked():
            self._cryologic.temp_channel = ["A", "B"]
        elif self._mw.checkBox_temp_channelA.isChecked():
            self._cryologic.temp_channel = "A"
        elif self._mw.checkBox_temp_channelB.isChecked():
            self._cryologic.temp_channel = "B"

            
    def set_time_window(self):
        """
        Opens a dialog to set the max displayed time window (in seconds).
        """
        dialog = QtGui.QInputDialog()
        value, ok = dialog.getInt(self._mw, "Time window",
                                  "New maximum time window displayed, in minutes:",
                                  int(self._cryologic.max_time_window/60), 1, 1000000, 1)
        if value and ok:
            self._cryologic.max_time_window = 60*value # in seconds
            self.log.info("Changed display time window.")
            self.sigTimeWindowChanged.emit()
        return

    
    def start_stop_monitoring(self):
        """
        Start or stop the monitoring and update the buttons accordingly. 
        """
        if self._mw.actionStartMonitoring.text() == "Start monitoring":
            self.sigStartMonitoring.emit()
            self._mw.actionStartMonitoring.setText("Stop monitoring")
        elif self._mw.actionStartMonitoring.text() == "Stop monitoring":
            self.sigStopMonitoring.emit()
            self._mw.actionStartMonitoring.setText("Start monitoring")
        return

    def start_stop_recording(self):
        """
        Start or stop recording the data. When recording, the data is saved every 5000 points.
        """
        if self._mw.actionRecordData.text() == "Record data":
            self.sigStartRecording.emit()
            self._mw.actionRecordData.setText("Stop recording")
        elif self._mw.actionRecordData.text() == "Stop recording":
            self.sigStopRecording.emit()
            self._mw.actionRecordData.setText("Record data")
        return

    def refresh_lHe_plot(self):
        """
        Update the lHe level plot.
        """
        self.lHe_plot.setData(x=np.array(self._cryologic.lHe_time_for_plot, dtype=np.int64),
                              y=np.array(self._cryologic.lHe_level_for_plot, dtype=np.float64))
        return
        

    def refresh_temp_plot(self):
        """
        Update the temperature plot.
        """
        if "A" in self._cryologic.temp_channel:
            self.temp_plotA.setData(x=np.array(self._cryologic.temp_time_for_plot, dtype=np.int64),
                                y=np.array(self._cryologic.temp_valuesA_for_plot, dtype=np.float64))
        if "B" in self._cryologic.temp_channel:
            self.temp_plotB.setData(x=np.array(self._cryologic.temp_time_for_plot, dtype=np.int64),
                                y=np.array(self._cryologic.temp_valuesB_for_plot, dtype=np.float64))
        if not "A" in self._cryologic.temp_channel:
            self.temp_plotA.setData(x=np.nan*np.ones(2), y=np.nan*np.ones(2))
        elif not "B" in self._cryologic.temp_channel:
            self.temp_plotB.setData(x=np.nan*np.ones(2), y=np.nan*np.ones(2))
        return

    def set_comment(self):
        """
        Sets the user comment for saving.
        """
        self._cryologic.user_comment = self._mw.comment_lineEdit.text()
        return
