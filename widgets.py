from __future__ import print_function, division

from PyQt4 import QtCore
from PyQt4 import QtGui

from PyQt4.QtCore import (
    pyqtSignal,
    Qt,
    QObject,
    pyqtBoundSignal,
    QTimer,
    QSize
)

from PyQt4.QtGui import (
    QAction,
    QLabel,
    QMainWindow,
    QIcon,
    qApp,
    QGridLayout,
    QListView,
    QStandardItem,
    QStandardItemModel,
    QColor,
    QAbstractItemView,
    QWidget,
    QKeySequence,
    QSplitter,
    QHBoxLayout,
    QFrame,
    QTableView,
    QVBoxLayout,
    QHBoxLayout,
    QSpacerItem,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QSlider,
    QLineEdit,
    QCompleter,
)

from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib
from operator import itemgetter


class_properties = {
    matplotlib.lines.Line2D: ['linewidth', 'label']
}

property_2_widget_factory = {
    'linewidth' : lambda obj: slider_for_object(obj, 'Line width', 0, 10),
    'label': lambda obj: text_for_object(obj, 'Label')
}

class Customizer(object):
    def __init__(self):
        self.main_widget = QWidget()
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)
        self.tree = QTreeWidget()
        self.layout.addWidget(self.tree)
        self.prop_frame = QWidget()
        self.layout.addWidget(self.prop_frame)

        self.prop_layout = QVBoxLayout()
        self.prop_frame.setLayout(self.prop_layout)

        self.slider = new_slider('fooval')
        self.frame = QFrame()
        self.frame.setLayout(self.slider[-1])
        self.layout.addWidget(self.frame)


def new_slider(name):
    hbox_layout = QHBoxLayout()
    label = QLabel(name)
    label.setMinimumSize(QtCore.QSize(20, 0))
    label.setAlignment(
        QtCore.Qt.AlignRight |
        QtCore.Qt.AlignTrailing |
        QtCore.Qt.AlignVCenter)

    slider = QSlider()
    slider.setMouseTracking(False)
    slider.setProperty("value", 0)
    slider.setOrientation(QtCore.Qt.Horizontal)
    slider.setInvertedAppearance(False)
    slider.setInvertedControls(False)
    slider.setTickPosition(QSlider.TicksAbove)
    slider.setTickInterval(5)

    value_label = QLabel('0')
    value_label.setMinimumSize(QtCore.QSize(20, 0))
    value_label.setAlignment(
        QtCore.Qt.AlignRight |
        QtCore.Qt.AlignTrailing |
        QtCore.Qt.AlignVCenter)

    hbox_layout.addWidget(label)
    hbox_layout.addWidget(slider)
    hbox_layout.addWidget(value_label)

    def update_text(val):
        value_label.setText("%.2f" % (val / 100))

    slider.valueChanged.connect(update_text)

    return label, slider, value_label, hbox_layout


def new_tree(obj):
    tw = QTreeWidget()

    def add_top_level_item(tree_widget, item_obj, name):
        top_item = QTreeWidgetItem()
        top_item.target_obj = item_obj
        tree_widget.addTopLevelItem(top_item)
        populate_tree_item(
            top_item,
            item_obj,
            prefix='<b>{}</b> : '.format(name)
        )

    if isinstance(obj, dict):
        for key, val in obj.iteritems():
            add_top_level_item(tw, val, key)
    else:
        for attrname in dir(obj):
            if attrname.startswith('_'):
                continue
            else:
                add_top_level_item(tw, getattr(obj, attrname), attrname)
    tw.itemDoubleClicked.connect(expand_tree_item)
    return tw


def expand_tree_item(item, col):
    obj = item.target_obj
    if item.childCount() > 0:
        print('Item is already expanded {}'.format(str(obj)[:100]))
    else:
        print(item, obj)
        for attrname in dir(obj):
            if attrname.startswith('_'):
                continue
            populate_tree_item(
                item,
                getattr(obj, attrname),
                set_text=False,
            )

def populate_tree_item(tree_item, obj, prefix='', set_text=True, recurse=True, curr_depth=0):
    if curr_depth > 3:
        print('hit depth limit')
        return
    elif isinstance(obj, (tuple, list, dict)):
        text = '{pre}{typ} [{len}]'.format(
                pre=prefix,
                typ=type(obj),
                len=len(obj),
            )
        if isinstance(obj, dict):
            item_iter = sorted(obj.items())
        else:
            item_iter = enumerate(obj)

        for key, item in item_iter:
            child_item = QTreeWidgetItem()
            child_item.target_obj = item
            tree_item.addChild(child_item)
            populate_tree_item(child_item,
                               item,
                               prefix='<b>{}</b> : '.format(key),
                               curr_depth=curr_depth + 1,
                               recurse=False)
    elif recurse:
        for attrname in dir(obj):
            if attrname.startswith('_'):
                continue
            child_item = QTreeWidgetItem()
            item = getattr(obj, attrname)
            child_item.target_obj = item
            tree_item.addChild(child_item)
            populate_tree_item(
                child_item,
                item,
                prefix='<b>{}</b> : '.format(attrname),
                recurse=False,
                curr_depth=curr_depth + 1
#                 set_text=False
            )

    if set_text:
        text = format_obj(obj, prefix)
        container_widget = QFrame()
        container_widget.setLayout(
            QVBoxLayout()
        )
        container_widget.layout().addWidget(
            QLabel(text)
        )
        print('setting text label: %s' % text)
        props = class_properties.get(type(obj), [])
        if props:
            widget_factories = itemgetter(*props)(property_2_widget_factory)
            for factory in widget_factories:
                container_widget.layout().addWidget(factory(obj))
        tree_item.treeWidget().setItemWidget(tree_item, 0, container_widget)


def deduce_getter_setter(obj, text, prop, getter, setter):
    if prop is None:
        prop = text.replace(' ', '').lower()
    getter = getter or getattr(obj, 'get_' + prop)
    setter = setter or getattr(obj, 'set_' + prop)
    return getter, setter

def get_axes_from_object(obj):
    if hasattr(obj, 'axes'):
        return obj.axes

def text_for_object(obj, text, prop=None, getter=None, setter=None):
    getter, setter = deduce_getter_setter(obj, text, prop, getter, setter)
    obj_widget = QFrame()
    hbox = QHBoxLayout()
    obj_widget.setLayout(hbox)
    hbox.addWidget(QLabel(text))
    lineedit = QLineEdit()
    hbox.addWidget(lineedit)
    lineedit.setText(getter())
    def update(text):
        setter(text)
        get_axes_from_object(obj).figure.canvas.draw_idle()

    lineedit.textChanged.connect(update)
    return obj_widget



def slider_for_object(obj, text, min, max, prop=None, getter=None, setter=None):
    getter, setter = deduce_getter_setter(obj, text, prop, getter, setter)
    label, slider, value_label, hbox_layout = new_slider(text)
    obj_widget = QFrame()
    obj_widget.setLayout(hbox_layout)

    def update(val):
        setter(val / 100)
        get_axes_from_object(obj).figure.canvas.draw_idle()
    slider.setValue(getter() * 100)
    slider.setMinimum(min * 100)
    slider.setMaximum(max * 100)
    slider.valueChanged.connect(update)

    return obj_widget

def test():
    import pandas as pd
    from datetime import datetime
    series = pd.Series(
        index=map(
            datetime.utcfromtimestamp,
            [ 0,  30,  31,  45,  46, 300]
        ),
        data=[0, 100,  10, 100,  10,  10]
    ).resample('1s').mean().ffill()
    ax = series.plot()
    tw = new_tree({'hej':ax.lines})
    tw.show()
    return tw, ax


def format_obj(obj, prefix):
    if isinstance(obj, (tuple, list, dict)):
        text = '{pre}{typ} [{len}]'.format(
            pre=prefix,
            typ=str( type(obj) )[len("<type '"):-2],
            len=len(obj),
        )
    else:
        obj_str = str(obj)
        obj_str = obj_str[(1 if obj_str.startswith('<') else 0):]
        obj_str = obj_str.replace('bound method', '')
        if ' of ' in obj_str:
            obj_str = obj_str[:obj_str.index(' of ')]
        if ' object at ' in obj_str:
            obj_str = obj_str[:obj_str.index(' object at ')]
        obj_str = obj_str[:100]
        text = '{pre}{obj}'.format(
            pre=prefix,
            obj=obj_str
        )

    return text

