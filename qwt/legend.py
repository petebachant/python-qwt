# -*- coding: utf-8 -*-
#
# Licensed under the terms of the Qwt License
# Copyright (c) 2002 Uwe Rathmann, for the original C++ code
# Copyright (c) 2015 Pierre Raybaut, for the Python translation/optimization
# (see LICENSE file for more details)

from qwt.legend_data import QwtLegendData
from qwt.dyngrid_layout import QwtDynGridLayout
from qwt.painter import QwtPainter
from qwt.legend_label import QwtLegendLabel

from qwt.qt.QtGui import (QFrame, QScrollArea, QWidget, QVBoxLayout, QPalette,
                          QApplication)
from qwt.qt.QtCore import Signal, QEvent, QSize, Qt, QRect, QRectF

import numpy as np


class QwtAbstractLegend(QFrame):
    def __init__(self, parent):
        QFrame.__init__(self, parent)
        
    def renderLegend(self, painter, rect, fillBackground):
        raise NotImplementedError
    
    def isEmpty(self):
        return 0
        
    def scrollExtent(self, orientation):
        return 0
    
    def updateLegend(self, itemInfo, data):
        raise NotImplementedError        


class Entry(object):
    def __init__(self):
        self.itemInfo = None
        self.widgets = []

class QwtLegendMap(object):
    def __init__(self):
        self.__entries = []
    
    def isEmpty(self):
        return len(self.__entries) == 0
    
    def insert(self, itemInfo, widgets):
        for entry in self.__entries:
            if entry.itemInfo == itemInfo:
                entry.widgets = widgets
                return
        newEntry = Entry()
        newEntry.itemInfo = itemInfo
        newEntry.widgets = widgets
        self.__entries += [newEntry]
        
    def remove(self, itemInfo):
        for entry in self.__entries[:]:
            if entry.itemInfo == itemInfo:
                self.__entries.remove(entry)
                return
    
    def removeWidget(self, widget):
        for entry in self.__entries:
            while widget in entry.widgets:
                entry.widgets.remove(widget)
    
    def itemInfo(self, widget):
        if widget is not None:
            for entry in self.__entries:
                if widget in entry.widgets:
                    return entry.itemInfo
    
    def legendWidgets(self, itemInfo):
        if itemInfo is not None:
            for entry in self.__entries:
                if entry.itemInfo == itemInfo:
                    return entry.widgets
        return []
    

class LegendView(QScrollArea):
    def __init__(self, parent):
        QScrollArea.__init__(self, parent)
        self.gridLayout = None
        self.contentsWidget = QWidget(self)
        self.contentsWidget.setObjectName("QwtLegendViewContents")
        self.setWidget(self.contentsWidget)
        self.setWidgetResizable(False)
        self.viewport().setObjectName("QwtLegendViewport")
        self.contentsWidget.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
    
    def event(self, event):
        if event.type() == QEvent.PolishRequest:
            self.setFocusPolicy(Qt.NoFocus)
        if event.type() == QEvent.Resize:
            cr = self.contentsRect()
            w = cr.width()
            h = self.contentsWidget.heightForWidth(cr.width())
            if h > w:
                w -= self.verticalScrollBar().sizeHint().width()
                h = self.contentsWidget.heightForWidth(w)
            self.contentsWidget.resize(w, h)
        return QScrollArea.event(self, event)
    
    def viewportEvent(self, event):
        ok = QScrollArea.viewportEvent(self, event)
        if event.type() == QEvent.Resize:
            self.layoutContents()
        return ok
    
    def viewportSize(self, w, h):
        sbHeight = self.horizontalScrollBar().sizeHint().height()
        sbWidth = self.verticalScrollBar().sizeHint().width()
        cw = self.contentsRect().width()
        ch = self.contentsRect().height()
        vw = cw
        vh = ch
        if w > vw:
            vh -= sbHeight
        if h > vh:
            vw -= sbWidth
            if w > vw and vh == ch:
                vh -= sbHeight
        return QSize(vw, vh)
    
    def layoutContents(self):
        tl = self.gridLayout
        if tl is None:
            return
        visibleSize = self.viewport().contentsRect().size()
        margins = tl.contentsMargins()
        margin_w = margins.left() + margins.right()
        minW = int(tl.maxItemWidth()+margin_w)
        w = max([visibleSize.width(), minW])
        h = max([tl.heightForWidth(w), visibleSize.height()])
        vpWidth = self.viewportSize(w, h).width()
        if w > vpWidth:
            w = max([vpWidth, minW])
            h = max([tl.heightForWidth(w), visibleSize.height()])
        self.contentsWidget.resize(w, h)
        

class QwtLegend_PrivateData(object):
    def __init__(self):
        self.itemMode = QwtLegendData.ReadOnly
        self.view = None
        self.itemMap = QwtLegendMap()    

class QwtLegend(QwtAbstractLegend):
    SIG_CLICKED = Signal("PyQt_PyObject", int)
    SIG_CHECKED = Signal("PyQt_PyObject", bool, int)
    
    def __init__(self, parent=None):
        QwtAbstractLegend.__init__(self, parent)
        self.setFrameStyle(QFrame.NoFrame)
        self.__data = QwtLegend_PrivateData()
        self.__data.view = LegendView(self)
        self.__data.view.setObjectName("QwtLegendView")
        self.__data.view.setFrameStyle(QFrame.NoFrame)
        gridLayout = QwtDynGridLayout(self.__data.view.contentsWidget)
        gridLayout.setAlignment(Qt.AlignHCenter|Qt.AlignTop)
        self.__data.view.gridLayout = gridLayout
        self.__data.view.contentsWidget.installEventFilter(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__data.view)
    
    def setMaxColumns(self, numColumns):
        tl = self.__data.view.gridLayout
        if tl is not None:
            tl.setMaxColumns(numColumns)
    
    def maxColumns(self):
        tl = self.__data.view.gridLayout
        if tl is not None:
            return tl.maxColumns()
        return 0
    
    def setDefaultItemMode(self, mode):
        self.__data.itemMode = mode
    
    def defaultItemMode(self):
        return self.__data.itemMode
        
    def contentsWidget(self):
        return self.__data.view.contentsWidget
    
    def horizontalScrollBar(self):
        return self.__data.view.horizontalScrollBar()
    
    def verticalScrollBar(self):
        return self.__data.view.verticalScrollBar()
    
    def updateLegend(self, itemInfo, data):
        widgetList = self.legendWidgets(itemInfo)
        if len(widgetList) != len(data):
            contentsLayout = self.__data.view.gridLayout
            while len(widgetList) > len(data):
                w = widgetList.pop(-1)
                contentsLayout.removeWidget(w)
                w.hide()
                w.deleteLater()
            for i in range(len(widgetList), len(data)):
                widget = self.createWidget(data[i])
                if contentsLayout is not None:
                    contentsLayout.addWidget(widget)
                if self.isVisible():
                    widget.setVisible(True)
                widgetList.append(widget)
            if not widgetList:
                self.__data.itemMap.remove(itemInfo)
            else:
                self.__data.itemMap.insert(itemInfo, widgetList)
            self.updateTabOrder()
        for i in range(len(data)):
            self.updateWidget(widgetList[i], data[i])
    
    def createWidget(self, data):
        label = QwtLegendLabel()
        label.setItemMode(self.defaultItemMode())
        label.SIG_CLICKED.connect(lambda: self.itemClicked(label))
        label.SIG_CHECKED.connect(lambda state: self.itemChecked(state, label))
        return label
    
    def updateWidget(self, widget, data):
        label = widget #TODO: cast to QwtLegendLabel!
        if label is not None:
            label.setData(data)
            if data.value(QwtLegendData.ModeRole) is None:
                label.setItemMode(self.defaultItemMode())
    
    def updateTabOrder(self):
        contentsLayout = self.__data.view.gridLayout
        if contentsLayout is not None:
            w = None
            for i in range(contentsLayout.count()):
                item = contentsLayout.itemAt(i)
                if w is not None and item.widget():
                    QWidget.setTabOrder(w, item.widget())
                w = item.widget()
    
    def sizeHint(self):
        hint = self.__data.view.contentsWidget.sizeHint()
        hint += QSize(2*self.frameWidth(), 2*self.frameWidth())
        return hint
        
    def heightForWidth(self, width):
        width -= 2*self.frameWidth()
        h = self.__data.view.contentsWidget.heightForWidth(width)
        if h >= 0:
            h += 2*self.frameWidth()
        return h
    
    def eventFilter(self, object_, event):
        if object_ is self.__data.view.contentsWidget:
            if event.type() == QEvent.ChildRemoved:
                ce = event  #TODO: cast to QChildEvent
                if ce.child().isWidgetType():
                    w = ce.child()  #TODO: cast to QWidget
                    self.__data.itemMap.removeWidget(w)
            elif event.type() == QEvent.LayoutRequest:
                self.__data.view.layoutContents()
                if self.parentWidget() and self.parentWidget().layout() is None:
                    QApplication.postEvent(self.parentWidget(),
                                           QEvent(QEvent.LayoutRequest))
        return QwtAbstractLegend.eventFilter(self, object_, event)
        
    def itemClicked(self, widget):
#        w = self.sender()  #TODO: cast to QWidget
        w = widget
        if w is not None:
            itemInfo = self.__data.itemMap.itemInfo(w)
            if itemInfo is not None:
                widgetList = self.__data.itemMap.legendWidgets(itemInfo)
                if w in widgetList:
                    index = widgetList.index(w)
                    self.SIG_CLICKED.emit(itemInfo, index)
    
    def itemChecked(self, on, widget):
#        w = self.sender()  #TODO: cast to QWidget
        w = widget
        if w is not None:
            itemInfo = self.__data.itemMap.itemInfo(w)
            if itemInfo is not None:
                widgetList = self.__data.itemMap.legendWidgets(itemInfo)
                if w in widgetList:
                    index = widgetList.index(w)
                    self.SIG_CHECKED.emit(itemInfo, on, index)
    
    def renderLegend(self, painter, rect, fillBackground):
        if self.__data.itemMap.isEmpty():
            return
        if fillBackground:
            if self.autoFillBackground() or\
               self.testAttribute(Qt.WA_StyledBackground):
                QwtPainter.drawBackground(painter, rect, self)
#    const QwtDynGridLayout *legendLayout = 
#        qobject_cast<QwtDynGridLayout *>( contentsWidget()->layout() );
        #TODO: not the exact same implementation
        legendLayout = self.__data.view.contentsWidget.layout()
        if legendLayout is None:
            return
        left, right, top, bottom = self.getContentsMargins()
        layoutRect = QRect()
        layoutRect.setLeft(np.ceil(rect.left())+left)
        layoutRect.setTop(np.ceil(rect.top())+top)
        layoutRect.setRight(np.ceil(rect.right())-right)
        layoutRect.setBottom(np.ceil(rect.bottom())-bottom)
        numCols = legendLayout.columnsForWidth(layoutRect.width())
        itemRects = legendLayout.layoutItems(layoutRect, numCols)
        index = 0
        for i in range(legendLayout.count()):
            item = legendLayout.itemAt(i)
            w = item.widget()
            if w is not None:
                painter.save()
                painter.setClipRect(itemRects[index], Qt.IntersectClip)
                self.renderItem(painter, w, itemRects[index], fillBackground)
                index += 1
                painter.restore()
                
    def renderItem(self, painter, widget, rect, fillBackground):
        if fillBackground:
            if widget.autoFillBackground() or\
               widget.testAttribute(Qt.WA_StyledBackground):
                QwtPainter.drawBackground(painter, rect, widget)
        label = widget  #TODO: cast to QwtLegendLabel
        if label is not None:
            icon = label.data().icon()
            sz = icon.defaultSize()
            iconRect = QRectF(rect.x()+label.margin(),
                              rect.center().y()-.5*sz.height(),
                              sz.width(), sz.height())
            icon.render(painter, iconRect, Qt.KeepAspectRatio)
            titleRect = QRectF(rect)
            titleRect.setX(iconRect.right()+2*label.spacing())
            painter.setFont(label.font())
            painter.setPen(label.palette().color(QPalette.Text))
            label.drawText(painter, titleRect)  #TODO: cast label to QwtLegendLabel
            
    def legendWidgets(self, itemInfo):
        return self.__data.itemMap.legendWidgets(itemInfo)
    
    def legendWidget(self, itemInfo):
        list_ = self.__data.itemMap.legendWidgets(itemInfo)
        if list_:
            return list_[0]
    
    def itemInfo(self, widget):
        return self.__data.itemMap.itemInfo(widget)
    
    def isEmpty(self):
        return self.__data.itemMap.isEmpty()
