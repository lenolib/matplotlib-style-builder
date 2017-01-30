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
    QFormLayout,
    QScrollArea,
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
    import numpy as np
    from datetime import datetime
    series = pd.Series(
        index=map(
            datetime.utcfromtimestamp,
            [ 0,  30,  31,  45,  46, 300]
        ),
        data=[0, 100,  10, 100,  10,  10]
    ).resample('1s').mean().ffill()

    def my_plot(fig):
        ax = fig.add_subplot(111)
        ret = ax.plot(np.arange(9)**2, label='myline')
        ax=fig.axes[0]
        ax.grid(True)
        ax.legend()
        ax.set_title('The graph title')
        ax.set_xlabel('the xlabel')

    pt = ParamTree(my_plot)
    pt.build_tree()
    return pt

from numbers import Number
def get_rcparams_types(rc, rcfile):
    rc = dict(mpl.rcParams)
    helps = scrape_help_for_param(rcfile)
    for k,v in rc.iteritems():
        if isinstance(v, bool):
            rc[k] = {'type': 'bool', 'default': v}
        elif isinstance(v, Number):
            rc[k] = {'type': 'float', 'default': v}
        elif isinstance(v, basestring):
            rc[k] = {'type': 'colorstring' if 'color' in k else 'string',
                     'default': v,
                     'options': []}
        elif isinstance(v, list):
            list_type = 'float' if (v and isinstance(v[0], Number)) else 'string'
            rc[k] = {'type': 'list', 'list_type': list_type, 'default': v}
        elif v is None:
            rc[k] = {'type': None, 'default': v}
        else:
            rc[k] = {'type': 'string', 'default': v}
        if k in helps:
            rc[k]['help'] = helps[k]
    return rc


from collections import defaultdict, OrderedDict
def categorize_rc_params(rc):
    by_category = defaultdict(OrderedDict)
    for key, val in rc.iteritems():
        by_category[ key.split('.')[0] ][key] = val
    return by_category


def scrape_help_for_param(rcfile):
    with open(rcfile) as fh:
        contents = fh.read()
    wo_comments = re.sub(r'^#[# \n].*', '', contents, flags=re.MULTILINE)
    wo_lead_hash = re.sub(r'^#', r'\n', wo_comments, flags=re.M)
    raw_param_lines = filter(
        None,
        wo_lead_hash.split('\n\n')
    )
    helps = {}
    for line in raw_param_lines:
        parts = filter(None, line.split('#'))
        param = parts[0].split(':')[0].strip()
        if not param:
            print('Empty param: %s' %line.replace('\n', '\\n'))
            continue
        helps[param] = ' '.join(map(str.strip, parts[1:]))
    return helps

import yaml

import matplotlib as mpl
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.backend_bases import key_press_handler

class ParamTree(QWidget):
    def __init__(self, plot_callback=None):
        super(ParamTree, self).__init__()
        self.setMinimumSize(600, 400)
        self.setLayout(QVBoxLayout())
        self.tw = QTreeWidget(self)
        self.last_selected = None
        self.layout().addWidget(self.tw, stretch=2)
        self.show()
        self.changed = {}
        self.plot_callback = plot_callback
        self.fig_widget = QWidget()
        self.fig_widget.setMinimumSize(600, 400)
        self.fig_widget.setLayout(QVBoxLayout())
        self.fig_widget.show()

    def build_tree(self):
        with open('rcParams.yaml') as fh:
            self.params = yaml.safe_load(fh)

        for category, pdict in self.params.items():
            top_item = QTreeWidgetItem()
            self.tw.addTopLevelItem(top_item)
            prop_widget = self.create_prop_widgets(pdict)
            scroll_area = QScrollArea()
            scroll_area.setWidget(prop_widget)
            scroll_area.setWidgetResizable(True)
            top_item.treeWidget().setItemWidget(top_item, 0, QLabel(category))
#             prop_widget.hide()
            scroll_area.hide()
            self.layout().addWidget(scroll_area, stretch=2)
            top_item.prop_widget = prop_widget
            top_item.scroll_area = scroll_area

        self.tw.itemSelectionChanged.connect(self.tree_item_selected)

    def tree_item_selected(self):
        if hasattr(self.last_selected, 'prop_widget'):
#             self.last_selected.prop_widget.hide()
            self.last_selected.scroll_area.hide()
        selected = self.tw.selectedItems()
        logger.debug('Selected %s', selected)
        if len(selected) > 1:
            logger.debug('multiple items selected - no action')
            return
        else:
            selected = selected[0]
        if hasattr(selected, 'prop_widget'):
            self.last_selected = selected
#             selected.prop_widget.show()
            selected.scroll_area.show()
        else:
            raise Exception('no attr')
#             maybe_widget = create_prop_widgets(selected.target_obj)
#             if maybe_widget is not None:
#                 selected.prop_widget = maybe_widget
#                 self.layout().addWidget(selected.prop_widget)
#             else:
#                 return

    def plot_with_changed(self):
        with matplotlib.rc_context(self.changed):
            logger.info('Updating plot')
            self.fig = Figure()
            if hasattr(self, 'fig_canvas'):
                self.fig_widget.layout().removeWidget(self.fig_canvas)
            self.fig_canvas = FigureCanvas(self.fig)
            self.fig_widget.layout().addWidget(self.fig_canvas)
            self.plot_callback(self.fig)

    def value_updated(self, name, value):
        self.changed[name] = value
        self.plot_with_changed()

    def construct_widget(self, name, prop):
        if prop['type'] == 'string':
            if len(prop.get('options', [])) > 0:
                widget = ChoiceParam(name, prop)
            else:
                widget = TextParam(name, prop)
        elif prop['type'] is None:
            widget  = TextParam(name, prop)
        elif prop['type'] == 'float':
            widget = SliderParam(name, prop)
        elif prop['type'] == 'list':
            widget = TextParam(name,
                                prop,
                                default=', '.join(map(str, prop['default'])))
        elif prop['type'] == 'bool':
            widget = ChoiceParam(name, prop)
        elif prop['type'] == 'colorstring':
            widget = ColorParam(name, prop)

        if prop.get('help'):
            help_label = QLabel('<b>Help:</b> ' + prop['help'])
            help_label.setMaximumWidth(400)
            widget.layout().addWidget(help_label)
        widget.sig_param_updated.connect(self.value_updated)
        if hasattr(widget.layout, 'addStretch'):
            widget.layout().addStretch()

        return widget

    def create_prop_widgets(self, props):
        container_widget = QFrame()
        container_widget.setLayout( QFormLayout() )
        container_widget.layout().setFormAlignment(Qt.AlignLeft)
        for name, prop in props.iteritems():
            try:
                widget = self.construct_widget(name, prop)
            except Exception:
                logger.exception('%s %s', name, prop)
                raise
            container_widget.layout().addRow(name, widget)

        return container_widget


def get_reasonable_range_limits(value):
    if value < 0:
        limits = (value * 4, value / 10)
    elif 0 <= value < 1:
        limits = (0, 2)
    elif 1 <= value < 10:
        limits = (0, 20)
    elif value >= 10:
        limits = (value / 10, value * 4)

    return limits


class ParamWidget(QFrame):
    sig_param_updated = pyqtSignal(object, object)

    def __init__(self, name, props):
        super(ParamWidget, self).__init__()
        self.name = name
        self.props = props

    def emit_update(self):
        self.sig_param_updated.emit(self.name, self.get_value())

    def set_value(self, value):
        raise NotImplementedError()

    def get_value(self):
        raise NotImplementedError()


class ChoiceParam(ParamWidget):
    def __init__(self, name, props): # TODO could calculate default index automatically if non-integer supplied
        super(ChoiceParam, self).__init__(name, props)
        self.setLayout( QHBoxLayout() )
        self.combobox = QComboBox()
        self.layout().addWidget(self.combobox)
        options = [False, True] if props['type'] == 'bool' else props['options']
        self.choices = OrderedDict(
            (str(choice), choice) for choice in options
        )
        assert str(props['default']) in self.choices
        self.combobox.addItems(self.choices.keys())
        self.combobox.setCurrentIndex(
            self.choices.keys().index(str(props['default']))
        )
        self.combobox.currentIndexChanged.connect(self.update)

    def set_value(self, value):
        self.combobox.setText(value)

    def get_value(self):
        return self.choices[str(self.combobox.currentText())]

    def update(self, _placeholder):
        new_choice = str(self.combobox.currentText())
        if new_choice not in self.choices:
            logging.error('Could not find among choices: %s (%s)',
                          new_choice,
                          self.choices)
            return
        self.emit_update()


class TextParam(ParamWidget):
    def __init__(self, name, props, default=None):
        super(TextParam, self).__init__(name, props)
        self.setLayout( QHBoxLayout() )
        self.lineedit = QLineEdit()
        self.layout().addWidget(self.lineedit)
        self.set_value(
            default or str(props['default'])  # cast because value could be none
        )
        self.lineedit.editingFinished.connect(self.update)

    def set_value(self, value):
        self.lineedit.setText(value)

    def get_value(self):
        return str(self.lineedit.text())

    def update(self):
        self.emit_update()


from matplotlib.backends.qt_editor.formlayout import ColorLayout, to_qcolor

class ColorLayoutEmitting(ColorLayout):
    sig_color_updated = pyqtSignal()
    def update_text(self, color):
        super(ColorLayoutEmitting, self).update_text(color)
        self.sig_color_updated.emit()


class ColorParam(ParamWidget):
    def __init__(self, name, props):
        super(ColorParam, self).__init__(name, props)
        colorstr = props['default']
        self.setLayout(
            ColorLayoutEmitting(to_qcolor(colorstr))
        )
        self.layout().sig_color_updated.connect(self.emit_update)

    def set_value(self, value):
        self.layout().update_text(to_qcolor(value))
        self.layout().update_color()

    def get_value(self):
        return str(self.layout().text())


class SliderParam(ParamWidget):
    def __init__(self, name, props):
        super(SliderParam, self).__init__(name, props)
        self.setLayout( QHBoxLayout() )
        self.slider = QSlider()
        self.slider.setMouseTracking(False)
        self.slider.setProperty("value", 0)
        self.slider.setOrientation(QtCore.Qt.Horizontal)
        self.slider.setInvertedAppearance(False)
        self.slider.setInvertedControls(False)
        self.slider.setTickPosition(QSlider.TicksAbove)
        self.slider.setTickInterval(5)

        self.value_edit = QLineEdit('0')
        self.value_edit.setMinimumSize(QtCore.QSize(20, 0))
        self.value_edit.setMaximumWidth(100)
        self.value_edit.setAlignment(
            QtCore.Qt.AlignRight |
            QtCore.Qt.AlignTrailing |
            QtCore.Qt.AlignVCenter)

        self.layout().addWidget(self.slider)
        self.layout().addWidget(self.value_edit)

        self.slider.valueChanged.connect(self.on_slider_changed)
        self.value_edit.editingFinished.connect(self.on_box_changed)
        start_value = self.props['default']
        limits = get_reasonable_range_limits(start_value)
        self.set_minimum(limits[0])
        self.set_maximum(limits[1])
        self.set_value(start_value)

    def set_minimum(self, value):
        self.slider.setMinimum(value * 100)

    def set_maximum(self, value):
        self.slider.setMaximum(value * 100)

    def get_value(self):
        return self.slider.value() / 100

    def set_value(self, value):
        factored = value * 100
        if factored > self.slider.maximum():
            slider.setMaximum(factored)
        self.slider.setValue(factored)

    def on_slider_changed(self, val):
        text = "%.2f" % self.get_value()
        if str(self.value_edit.text()) != text:
            self.value_edit.setText(text)
        self.emit_update()

    def on_box_changed(self):
        text = self.value_edit.text()
        try:
            value = float(text)
        except ValueError as ve:
            logger.error('Could not convert argument to float %s', text)
            return
        self.set_value(value)


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
            maybe_widget = self.create_prop_widgets(selected.target_obj)
            if maybe_widget is not None:
                selected.prop_widget = maybe_widget
                self.layout().addWidget(selected.prop_widget)
            else:
                return


    def create_prop_widgets(obj):
        # Add property-widget children if supported class
        if type(obj) not in supported_classes:
            return None
        scroll_area = QScrollArea()
        container_widget = QWidget()
        scroll_area.setWidget(container_widget)
        container_widget.setLayout( QVBoxLayout() )
        for propname, factory in property_2_widget_factory.iteritems():
            if hasattr(obj, 'get_' + propname):
                container_widget.layout().addWidget(factory(obj))
            else:
                continue
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(400)
        return scroll_area
    #     return container_widget


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
    layout, lineedit = _textedit(text, getter())
    obj_widget = QFrame()
    obj_widget.setLayout(layout)
    def update(text):
        setter(text)
        redraw_canvas_through_object(obj)

    lineedit.textChanged.connect(update)
    return obj_widget


def slider_for_object(obj, text, min, max, prop=None, getter=None, setter=None):
    getter, setter = deduce_getter_setter(obj, text, prop, getter, setter)
    obj_widget, slider = new_slider(text)

    def update(value):
        setter(value / 100)
        redraw_canvas_through_object(obj)
    slider.setValue(getter() * 100)
    slider.setMinimum(min * 100)
    slider.setMaximum(max * 100)
    slider.valueChanged.connect(update)

    return obj_widget



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

