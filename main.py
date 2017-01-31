from __future__ import print_function, division

import os
import sys

from collections import OrderedDict
from operator import itemgetter

import yaml

import matplotlib
import matplotlib as mpl
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.backend_bases import key_press_handler

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
    QApplication,
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

from param_widgets import ComboboxParam, TextParam, SliderParam, ColorParam



import logging
if not logging.getLogger().handlers:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s %(levelname)-6s [%(name)s]: %(message)s'
    )
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)



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
        ax = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)
        ret = ax.plot(np.arange(9)**2, label='myline')
        ax=fig.axes[0]
#         ax.grid(True)
        ax.legend()
        ax.set_title('The graph title')
        ax.set_xlabel('the xlabel')
        series.plot(ax=ax2)

    pt = ParamTree(my_plot)
    pt.build_tree()
    return pt



class ParamTree(QWidget):
    def __init__(self, plot_callback=None):
        super(ParamTree, self).__init__()
        self.setMinimumSize(600, 400)
        self.setLayout(QHBoxLayout())
        self.tw = QTreeWidget(self)
        self.tw.setMinimumWidth(100)
        self.last_selected = None
        self.layout().addWidget(self.tw, stretch=2)
        self.show()
        self.changed = {}
        self.plot_callback = plot_callback
        self.fig_widget = QWidget()
        self.fig_widget.setMinimumSize(600, 400)
        self.fig_widget.setLayout(QVBoxLayout())
        self.fig_widget.show()
        self.prop_widgets = {}

    def build_tree(self):
        with open('rcParams.yaml') as fh:
            self.params = yaml.safe_load(fh)

        for category, pdict in sorted(self.params.items()):
            top_item = QTreeWidgetItem()
            self.tw.addTopLevelItem(top_item)
            prop_widget = self.create_prop_widgets(pdict)
            scroll_area = QScrollArea()
            scroll_area.setWidget(prop_widget)
            scroll_area.setWidgetResizable(True)
            top_item.treeWidget().setItemWidget(top_item, 0, QLabel(category))
            scroll_area.hide()
            self.layout().addWidget(scroll_area, stretch=10)
            top_item.prop_widget = prop_widget
            top_item.scroll_area = scroll_area
            self.prop_widgets[category] = prop_widget

        self.tw.itemSelectionChanged.connect(self.tree_item_selected)
        axes_idx = sorted(self.params).index('axes')
        self.tw.setCurrentIndex(
            self.tw.model().index(axes_idx, 0)
        )
        self.plot_with_changed()

    def tree_item_selected(self):
        if hasattr(self.last_selected, 'prop_widget'):
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
            selected.scroll_area.show()
        else:
            raise Exception('no attr')

    def plot_with_changed(self):
        with matplotlib.rc_context(self.changed):
            logger.debug('Updating plot')
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
                widget = ComboboxParam(name, prop)
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
            widget = ComboboxParam(name, prop)
        elif prop['type'] == 'colorstring':
            widget = ColorParam(name, prop)

        return widget

    def create_prop_widgets(self, props):
        container_widget = QFrame()
        formlayout = QFormLayout()
        container_widget.setLayout(formlayout) 
        formlayout.setVerticalSpacing(0)
        formlayout.setFormAlignment(Qt.AlignLeft)
        for name, prop in sorted(props.items()):
            try:
                widget = self.construct_widget(name, prop)
            except Exception:
                logger.exception('%s %s', name, prop)
                raise
            if prop.get('help'):
                help_label = QLabel('<b>Help:</b> ' + prop['help'])
                help_label.setMinimumWidth(200)
                help_label.setWordWrap(True)
                widget.layout().addWidget(help_label, stretch=2)
            widget.sig_param_updated.connect(self.value_updated)
            if hasattr(widget.layout, 'addStretch'):
                widget.layout().addStretch()
            
            formlayout.addRow(name, widget)

        return container_widget


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


def get_ipython_if_any():
    try:
        from IPython import get_ipython
    except ImportError:
        return None

    return get_ipython()


if __name__ == '__main__':
    interactive = True
    if interactive:
        shell = get_ipython_if_any()
        if shell and not shell._inputhook.__module__.endswith('.qt'):
            shell.enable_gui('qt')
            logger.info("Enabled 'qt' gui in current ipython shell")
    maybe_existing_app = QApplication.instance()
    app = maybe_existing_app or QApplication(sys.argv)
    QtGui.qApp = app
    pt = test()
    sys.exit(app.exec_())


