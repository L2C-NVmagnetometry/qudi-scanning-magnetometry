# -*- coding: utf-8 -*-

"""
This file contains the Qudi GUI module utility classes.

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

import pyqtgraph as pg
import numpy as np
from qtpy import QtCore
import numpy as np
import datetime
import time

## ColorBar things
class ColorBar(pg.GraphicsObject):
    """ Create a ColorBar according to a previously defined color map.

    @param object pyqtgraph.ColorMap cmap: a defined colormap
    @param float width: width of the colorbar in x direction, starting from
                        the origin.
    @param numpy.array ticks: optional, definition of the relative ticks marks
    """

    def __init__(self, cmap, width, cb_min, cb_max):

        pg.GraphicsObject.__init__(self)

        # handle the passed arguments:
        self.stops, self.colors = cmap.getStops('float')
        self.stops = (self.stops - self.stops.min())/self.stops.ptp()
        self.width = width

        # Constructs an empty picture which can be altered by QPainter
        # commands. The picture is a serialization of painter commands to an IO
        # device in a platform-independent format.
        self.pic = pg.QtGui.QPicture()

        self.refresh_colorbar(cb_min, cb_max)

    def refresh_colorbar(self, cb_min, cb_max, cmap=None, width=None, 
                         height=None, xMin=None, yMin=None):
        """ Refresh the appearance of the colorbar for a changed count range.

        @param float cb_min: The minimal count value should be passed here.
        @param float cb_max: The maximal count value should be passed here.
        @param object pyqtgraph.ColorMap cmap: optional, a new colormap.
        @param float width: optional, with that you can change the width of the
                            colorbar in the display.
        """

        if width is None:
            width = self.width
        else:
            self.width = width
            
        if cmap is not None:
            # update colors if needed
            self.stops, self.colors = cmap.getStops('float')
            self.stops = (self.stops - self.stops.min())/self.stops.ptp()

#       FIXME: Until now, if you want to refresh the colorbar, a new QPainter
#              object has been created, but I think that it is not necassary.
#              I have to figure out how to use the created object properly.
        p = pg.QtGui.QPainter(self.pic)
        p.drawRect(self.boundingRect())
        p.setPen(pg.mkPen('k'))
        grad = pg.QtGui.QLinearGradient(width/2.0, cb_min*1.0, width/2.0, cb_max*1.0)
        for stop, color in zip(self.stops, self.colors):
            grad.setColorAt(1.0 - stop, pg.QtGui.QColor(*[255*c for c in color]))
        p.setBrush(pg.QtGui.QBrush(grad))
        if xMin is None:
            p.drawRect(pg.QtCore.QRectF(0, cb_min, width, cb_max-cb_min))
        else:
            # If this picture whants to be set in a plot, which is going to be
            # saved:
            p.drawRect(pg.QtCore.QRectF(xMin, yMin, width, height))
        p.end()

        vb = self.getViewBox()
        # check whether a viewbox is already created for this object. If yes,
        # then it should be adjusted according to the full screen.
        if vb is not None:
            vb.updateAutoRange()
            vb.enableAutoRange()

    def paint(self, p, *args):
        """ Overwrite the paint method from GraphicsObject.

        @param object p: a pyqtgraph.QtGui.QPainter object, which is used to
                         set the color of the pen.

        Since this colorbar object is in the end a GraphicsObject, it will
        drop an implementation error, since you have to write your own paint
        function for the created GraphicsObject.
        """
        # paint colorbar
        p.drawPicture(0, 0, self.pic)

    def boundingRect(self):
        """ Overwrite the paint method from GraphicsObject.

        Get the position, width and hight of the displayed object.
        """
        return pg.QtCore.QRectF(self.pic.boundingRect())
  
    
### ROI things    
class CrossROI(pg.ROI):
    """ Create a Region of interest, which is a zoomable rectangular.

    @param float pos: optional parameter to set the position
    @param float size: optional parameter to set the size of the roi

    Have a look at:
    http://www.pyqtgraph.org/documentation/graphicsItems/roi.html
    """
    sigUserRegionUpdate = QtCore.Signal(object)
    sigMachineRegionUpdate = QtCore.Signal(object)

    def __init__(self, pos, size, **args):
        """Create a ROI with a central handle."""
        self.userDrag = False
        pg.ROI.__init__(self, pos, size, **args)
        # That is a relative position of the small box inside the region of
        # interest, where 0 is the lowest value and 1 is the higherst:
        center = [0.5, 0.5]
        # Translate the center to the intersection point of the crosshair.
        self.addTranslateHandle(center)

        self.sigRegionChangeStarted.connect(self.startUserDrag)
        self.sigRegionChangeFinished.connect(self.stopUserDrag)
        self.sigRegionChanged.connect(self.regionUpdateInfo)

    def setPos(self, pos, update=True, finish=False):
        """Sets the position of the ROI.

        @param bool update: whether to update the display for this call of setPos
        @param bool finish: whether to emit sigRegionChangeFinished

        Changed finish from parent class implementation to not disrupt user dragging detection.
        """
        super().setPos(pos, update=update, finish=finish)

    def setSize(self, size, update=True, finish=True):
        """
        Sets the size of the ROI
        @param bool update: whether to update the display for this call of setPos
        @param bool finish: whether to emit sigRegionChangeFinished
        """
        super().setSize(size, update=update, finish=finish)

    def handleMoveStarted(self):
        """ Handles should always be moved by user."""
        super().handleMoveStarted()
        self.userDrag = True

    def startUserDrag(self, roi):
        """ROI has started being dragged by user."""
        self.userDrag = True

    def stopUserDrag(self, roi):
        """ROI has stopped being dragged by user"""
        self.userDrag = False

    def regionUpdateInfo(self, roi):
        """When the region is being dragged by the user, emit the corresponding signal."""
        if self.userDrag:
            self.sigUserRegionUpdate.emit(roi)
        else:
            self.sigMachineRegionUpdate.emit(roi)
            
    def update_roi(self, x=None, y=None):
        """ Adjust the xy ROI position if the value has changed.
        @param float: real value of the current x position
        @param float: real value of the current y position
        
        Since the origin of the region of interest (ROI) is not the crosshair
        point but the lowest left point of the square, you have to shift the
        origin according to that. Therefore the position of the ROI is not
        the actual position!
        """
        roi_x = self.pos()[0]
        roi_y = self.pos()[1]
        
        if x is not None:
            roi_x = x - self.size()[0] * 0.5
        if y is not None:
            roi_y = y - self.size()[1] * 0.5

        self.setPos([roi_x, roi_y])
            
        return self.pos()
    
    def update_roi_from_user(self, max_scanner):
        """The user manually moved the ROI, adjust all other GUI elements accordingly

        @params object: PyQtGraph ROI object
        """
        h_pos = self.pos()[0] + 0.5 * self.size()[0]
        v_pos = self.pos()[1] + 0.5 * self.size()[1]
        
        h_pos = np.clip(h_pos, 0 + self.size()[0] * 0.5, max_scanner - self.size()[0] * 0.5)
        v_pos = np.clip(v_pos, 0 + self.size()[1] * 0.5, max_scanner - self.size()[1] * 0.5)
        
        return h_pos, v_pos
    
    def update_roi_from_input(self, x=None, y=None):
        """ The user pressed a key to move the crosshair, adjust all GUI elements.

        @param float: new x position in m
        @param float: new y position in m
        """
        if x is not None:
            self.update_roi(x=x)
        if y is not None:
            self.update_roi(y=y)
            
        return 0
    
    def roi_bounds_check(self, max_scanner):
        """ Check if the focus cursor is outside the allowed range after drag
        and set its position to the limit
            
        @param object: PyQtGraph ROI object
        """
        
        h_pos = self.pos()[0] + self.size()[0] * 0.5
        v_pos = self.pos()[1] + self.size()[1] * 0.5
        
        h_pos_temp = np.clip(h_pos, 0 + self.size()[0] * 0.5, max_scanner - self.size()[0] * 0.5)
        v_pos_temp = np.clip(v_pos, 0 + self.size()[1] * 0.5, max_scanner - self.size()[1] * 0.5)
        
        if h_pos_temp != h_pos or v_pos_temp != v_pos:
            self.update_roi(h_pos_temp, v_pos_temp)
            
        return 0
    
    
    def update_roi_size(self, range_scan, max_scanner):
        """ Update the roi size.
        
        @param 2*2 array: [[xmin, xmax], [ymin, ymax]]
        """
        hsize = range_scan[1] - range_scan[0]
        vsize = range_scan[3] - range_scan[2]
        hpos = self.pos()[0] + self.size()[0] * 0.5
        vpos = self.pos()[1] + self.size()[1] * 0.5
        
        hsize = np.clip(hsize, 0, max_scanner)
        vsize = np.clip(vsize, 0, max_scanner) 
        
        self.setSize([hsize, vsize])
        self.setPos([hpos, vpos])
        
        return 0



class CrossLine(pg.InfiniteLine):
    """ Construct one line for the Crosshair in the plot.

    @param float pos: optional parameter to set the position
    @param float angle: optional parameter to set the angle of the line
    @param dict pen: Configure the pen.

    For additional options consider the documentation of pyqtgraph.InfiniteLine
    """

    def __init__(self, **args):
        pg.InfiniteLine.__init__(self, **args)
#        self.setPen(QtGui.QPen(QtGui.QColor(255, 0, 255),0.5))

    def adjust(self, extroi):
        """
        Run this function to adjust the position of the Crosshair-Line

        @param object extroi: external roi object from pyqtgraph
        """
        if self.angle == 0:
            self.setValue(extroi.pos()[1] + extroi.size()[1] * 0.5)
        if self.angle == 90:
            self.setValue(extroi.pos()[0] + extroi.size()[0] * 0.5)


### TimeAxis things
# from https://gist.github.com/iverasp/9349dffa42aeffb32e48a0868edfa32d
# and https://gist.github.com/cpascual/cdcead6c166e63de2981bc23f5840a98
def timestamp():
    return int(time.mktime(datetime.datetime.now().timetuple()))


class TimeAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setLabel(text='Time', units=None)
        self.enableAutoSIPrefix(False)

    def tickStrings(self, values, scale, spacing):
        return [datetime.datetime.fromtimestamp(value).strftime("%H:%M:%S") for value in values]
    
    def attachToPlotItem(self, plotItem):
        """Add this axis to the given PlotItem
        @params plotItem: (PlotItem)
        """
        self.setParentItem(plotItem)
        viewBox = plotItem.getViewBox()
        self.linkToView(viewBox)
        self._oldAxis = plotItem.axes[self.orientation]['item']
        self._oldAxis.hide()
        plotItem.axes[self.orientation]['item'] = self
        pos = plotItem.axes[self.orientation]['pos']
        plotItem.layout.addItem(self, *pos)
        self.setZValue(-1000)
