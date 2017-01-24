from __future__ import print_function, division

import os
import sys

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
    QComboBox,
)

from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib
from operator import itemgetter

import logging
if not logging.getLogger().handlers:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s %(levelname)-6s [%(name)s]: %(message)s'
    )
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


supported_classes = [
    matplotlib.lines.Line2D,
    matplotlib.axes.Axes,
    matplotlib.axis.Axis,
    matplotlib.figure.Figure,
]

from collections import OrderedDict

linestyle_dict =  OrderedDict([
    ('solid line', '-'),
    ('dashed line', '--'),
    ('dash-dotted line', '-.'),
    ('dotted line', ':'),
    ('draw nothing', 'None'),
])

from matplotlib.markers import MarkerStyle
markernames_inverted = {
    "{} ('{}')".format(v,k): k for (k, v) in MarkerStyle.markers.iteritems()
}
markernames_inverted['nothing'] = 'None'  

def left_partial(fn, *partial_args, **kwargs):
    def inner(*call_args):
        return fn(*(call_args + partial_args), **kwargs)
    return inner

property_2_widget_factory = {
    'alpha': lambda obj: slider_for_object(
        obj, 'Alpha', 0, 1,
        getter=lambda: 1 if obj.get_alpha() is None else obj.get_alpha()
    ),
    'linewidth' : lambda obj: slider_for_object(obj, 'Line width', 0, 10),
    'label': lambda obj: text_for_object(obj, 'Label'),
    'title': lambda obj: text_for_object(obj, 'Title'),
    'linestyle': lambda obj: choice_combobox(obj, 'Line style', linestyle_dict),
    'drawstyle': lambda obj: choice_combobox(obj, 'Draw style', obj.drawStyleKeys),
    'markersize': lambda obj: slider_for_object(obj, 'Marker size', 0, 16),
    'marker': lambda obj: choice_combobox(obj, 'Marker', markernames_inverted),
    'figheight': lambda obj: slider_for_object(obj, 'Figure height', 1, 40,
                                               prop='figheight'),
    'dpi': lambda obj: slider_for_object(obj, 'Dots-per-inch', 1, 240,
                                         prop='dpi')
}
property_order = [
    'label',
    'title',
    'linewidth',
    'linestyle',
    'marker',
    'markersize',
    'drawstyle',
    'figheight',
    'dpi',
    'alpha',
    ]

if len(property_2_widget_factory) != len(property_order):
    raise AssertionError('forgot to add to property_order?')


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
    tree = Tree()
    tree.new_tree({
        'hej':ax.figure,
        'toplevel_dt': datetime.utcnow(),
        'dic': {'hej': datetime.utcnow(),
                'yo': 'tjataj',
                'sub': {'hej': datetime.utcnow(), 'yo': 'tjataj'}
            },
    })
    return tree, ax

class Tree(QWidget):
    def __init__(self):
        super(Tree, self).__init__()
        self.tw = QTreeWidget()
        self.last_selected = None
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.tw)
        self.show()

    def new_tree(self, obj):
        def add_top_level_item(tree_widget, item_obj, name):
            top_item = QTreeWidgetItem()
            top_item.target_obj = item_obj
            tree_widget.addTopLevelItem(top_item)
            logger.debug('Adding top level item: %s : %s', name, item_obj)
            populate_tree_item(
                top_item,
                item_obj,
                prefix='<b>{}</b> : '.format(name),
                expand_n_levels=1
            )

        if isinstance(obj, dict):
            for key, val in obj.iteritems():
                add_top_level_item(self.tw, val, key)
        else:
            for attrname in dir(obj):
                if attrname.startswith('_'):
                    continue
                else:
                    add_top_level_item(tw, getattr(obj, attrname), attrname)

        self.tw.itemDoubleClicked.connect(expand_tree_item)
        self.tw.itemSelectionChanged.connect(self.tree_item_selected)

    def tree_item_selected(self):
        if hasattr(self.last_selected, 'prop_widget'):
            self.last_selected.prop_widget.hide()
        selected = self.tw.selectedItems()
        logger.debug('Selected %s', selected)
        if len(selected) > 1:
            logger.debug('multiple items selected - no action')
            return
        else:
            selected = selected[0]
        if hasattr(selected, 'prop_widget'):
            self.last_selected = selected
            selected.prop_widget.show()
        else:
            maybe_widget = create_prop_widgets(selected.target_obj)
            if maybe_widget is not None:
                selected.prop_widget = maybe_widget
                self.layout().addWidget(selected.prop_widget)
            else:
                return


def expand_tree_item(item, col):
    if hasattr(item, 'target_obj'):
        obj = item.target_obj
    else:
        logging.debug('obj does not have target_obj attr: %s', obj)
        return
    if item.childCount() > 0:
        logger.debug('Item is already expanded {}'.format(str(obj)[:100]))
    else:
        logger.debug('Expanding %s on tree item %s', obj, item)
#         for attrname in dir(obj):
#             if attrname.startswith('_'):
#                 continue
        populate_tree_item(
            item,
            item.target_obj,
            text_already_set=True,
            expand_n_levels=1,
        )


def create_prop_widgets(obj):
    # Add property-widget children if supported class
    if type(obj) not in supported_classes:
        return None
    container_widget = QFrame()
    container_widget.setLayout( QVBoxLayout() )
    for propname, factory in property_2_widget_factory.iteritems():
        if hasattr(obj, 'get_' + propname):
            container_widget.layout().addWidget(factory(obj))
        else:
            continue
            
    return container_widget


def populate_tree_item(tree_item, obj, prefix='', text_already_set=False,
                       expand_n_levels=1, curr_depth=0):
    logger.debug('Populating from obj: %s', obj)
    if not text_already_set:
        text = format_obj(obj, prefix)
        tree_item.treeWidget().setItemWidget(tree_item, 0, QLabel(text))
        logger.debug('Setting text label: %s', text)

    if curr_depth >= expand_n_levels:
        logger.debug('Not expanding further/deeper')
        return
    elif isinstance(obj, (tuple, list, dict)):
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
                               expand_n_levels=expand_n_levels)
    elif expand_n_levels > 0:
        logger.debug('%s: recursing into %s', tree_item.target_obj, obj)
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
                expand_n_levels=expand_n_levels,
                curr_depth=curr_depth + 1
            )
    else:
        child_item = QTreeWidgetItem()
        child_item.target_obj = obj
        tree_item.addChild(child_item)


def deduce_getter_setter(obj, text, prop, getter, setter):
    if prop is None:
        prop = text.replace(' ', '').lower()
    getter = getter or getattr(obj, 'get_' + prop)
    setter = setter or getattr(obj, 'set_' + prop)
    return getter, setter


def redraw_canvas_through_object(obj):
    if hasattr(obj, 'canvas'):
        canvas = obj.canvas
    elif hasattr(obj, 'axes'):
        canvas = obj.axes.figure.canvas
    elif hasattr(obj, 'figure'):
        canvas = obj.figure.canvas
    else:
        logging.warning('Could not find canvas through obj. '
                        'Using gcf() to get figure canvas '
                        '(might not be correct)')
        canvas = plt.gcf().canvas
    canvas.draw_idle()


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
        redraw_canvas_through_object(obj)

    lineedit.textChanged.connect(update)
    return obj_widget


def slider_for_object(obj, text, min, max, prop=None, getter=None, setter=None):
    getter, setter = deduce_getter_setter(obj, text, prop, getter, setter)
    label, slider, value_edit, hbox_layout = new_slider(text)
    obj_widget = QFrame()
    obj_widget.setLayout(hbox_layout)

    def update(value):
        setter(value / 100)
        redraw_canvas_through_object(obj)
    slider.setValue(getter() * 100)
    slider.setMinimum(min * 100)
    slider.setMaximum(max * 100)
    slider.valueChanged.connect(update)

    return obj_widget


def choice_combobox(obj, text, choices, prop=None, getter=None, setter=None):
    getter, setter = deduce_getter_setter(obj, text, prop, getter, setter)
    obj_widget = QFrame()
    hbox = QHBoxLayout()
    obj_widget.setLayout(hbox)
    hbox.addWidget(QLabel(text))
    combobox = QComboBox()
    hbox.addWidget(combobox)
    if not isinstance(choices, dict):
        choices = OrderedDict(zip(choices, choices))
    choice_list = choices.keys()
    combobox.addItems(choice_list)
    current_choice = getter()
    combobox.setCurrentIndex(choices.values().index(current_choice))
    def update(_placeholder):
        new_choice = str(combobox.currentText())
        if new_choice not in choices:
            logging.error('Could not find among choices: %s (%s)',
                          new_choice,
                          choices)
            return
        setter(choices[new_choice])
        redraw_canvas_through_object(obj)

    combobox.currentIndexChanged.connect(update)
    return obj_widget


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

    value_edit = QLineEdit('0')
    value_edit.setMinimumSize(QtCore.QSize(20, 0))
    value_edit.setAlignment(
        QtCore.Qt.AlignRight |
        QtCore.Qt.AlignTrailing |
        QtCore.Qt.AlignVCenter)

    hbox_layout.addWidget(label)
    hbox_layout.addWidget(slider)
    hbox_layout.addWidget(value_edit)

    def on_slider_changed(val):
        text = "%.2f" % (val / 100)
        if str(value_edit.text()) != text:
            logger.debug('not equal text %s %s', value_edit.text(), text)
            value_edit.setText(text)

    def on_box_changed():
        text = value_edit.text()
        try:
            value = float(text) * 100
        except ValueError as ve:
            logger.error('Could not convert argument to flaot %s', text)
            return
        logger.debug('updating slider %s', text)
        if value > slider.maximum():
            slider.setMaximum(value)
        slider.setValue(value)

    slider.valueChanged.connect(on_slider_changed)
    value_edit.editingFinished.connect(on_box_changed)

    return label, slider, value_edit, hbox_layout



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

