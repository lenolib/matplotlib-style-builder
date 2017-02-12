from __future__ import print_function, division, unicode_literals

import os
import sys
import re

from collections import OrderedDict
from operator import itemgetter
from itertools import chain

# 3rd-party library imports
import yaml


# Matplotlib and Qt imports
import matplotlib
import matplotlib as mpl

from matplotlib.figure import Figure
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.qt_compat import QtWidgets, QtCore, QtGui, is_pyqt5

if is_pyqt5():
    from PyQt5.QtCore import pyqtSignal, Qt 
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg \
                                                            as FigureCanvas
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT \
                                                            as NavigationToolbar
else:
    from PyQt4.QtCore import pyqtSignal, Qt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg \
                                                            as FigureCanvas
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT \
                                                            as NavigationToolbar


# Project imports
from param_widgets import ComboboxParam, TextParam, SliderParam, ColorParam


# Logging
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
    "{} ('{}')".format(v, k): k for (k, v) in MarkerStyle.markers.items()
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



class ParamTree(QtWidgets.QWidget):
    def __init__(self, plot_callback=None):
        super(ParamTree, self).__init__()
        self.setMinimumSize(600, 400)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.tw = QtWidgets.QTreeWidget(self)
        self.tw.setMinimumWidth(100)
        self.layout().addWidget(self.tw, stretch=2)
        self.show()
        self.changed = {}
        self.plot_callback = plot_callback
        self.fig_widget = QtWidgets.QWidget()
        self.fig_widget.setMinimumSize(600, 400)
        self.fig_widget.setLayout(QtWidgets.QVBoxLayout())
        self.fig_widget.show()
        self.prop_frame = QtWidgets.QFrame()
        self.prop_frame.setLayout( QtWidgets.QVBoxLayout() )
        self.prop_frame.layout().addStretch()
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidget(self.prop_frame)
        self.scroll_area.setWidgetResizable(True)
        self.layout().addWidget(self.scroll_area, stretch=10)
        self.prop_widgets = {}
        with open('rcParams.yaml') as fh:
            self.categorized_params = yaml.safe_load(fh)
        self.params = dict(chain.from_iterable(
            [subdict.items() for subdict in self.categorized_params.values()]
        ))
        self.currently_displayed = []

    def build_tree(self):
        for category, pdict in sorted(self.categorized_params.items()):
            top_item = QtWidgets.QTreeWidgetItem([category])
            self.tw.addTopLevelItem(top_item)
        self.tw.itemSelectionChanged.connect(self.tree_item_selected)
        axes_idx = sorted(self.categorized_params).index('axes')
        self.tw.setCurrentIndex(
            self.tw.model().index(axes_idx, 0)
        )
        self.plot_with_changed()

    def params_matching(self, substr=None, regex=None):
        if regex is None:
            assert substr is not None
            regex = '.*{}.*'.format(re.escape(substr))
        logger.debug('Matching params to "%s"', regex)
        compiled = re.compile(regex)
        matching = [p for p in self.params.keys() if compiled.search(p)]

        return matching

    def display_list(self, params):
        self.hide_all_current_params()
        logger.debug('Displaying %s', params)
        for param in params[::-1]:  # Reverse because inserting at top
            assert param in self.params
            if param not in self.prop_widgets:
                self.prop_widgets[param] = self.widget_from_prop(
                    param,
                    self.params[param]
                )
            # Inserting to keep spacer at bottom
            self.prop_frame.layout().insertWidget(0, self.prop_widgets[param])
            self.prop_widgets[param].show()
        self.currently_displayed = [self.prop_widgets[x] for x in params]

    def hide_all_current_params(self):
        # TODO should probably use a formlayout and properly remove / add
        # widgets in order to have control of order
        for widg in self.currently_displayed:
            widg.hide()

    def tree_item_selected(self):
        selected = self.tw.selectedItems()
        logger.debug('Selected %s', selected)
        if len(selected) > 1:
            logger.debug('multiple items selected - no action')
            return
        else:
            selected_str = str(selected[0].text(0))
            matching = self.params_matching(
                # Matches 'sup', 'sub.sub', but not 'superduper'
                regex='^{}(\.?$|\.\w.*$)'.format(re.escape(selected_str))
            )
            self.display_list(matching)

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

    def widget_from_prop(self, name, prop):
        try:
            widget = self.construct_widget(name, prop)
        except Exception:
            logger.exception('%s %s', name, prop)
            raise
        if prop.get('help'):
            help_label = QtWidgets.QLabel('<b>Help:</b> ' + prop['help'])
            help_label.setMinimumWidth(200)
            help_label.setWordWrap(True)
            widget.layout().addWidget(help_label, stretch=2)
        button = QtWidgets.QPushButton(name)
        button.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                             QtWidgets.QSizePolicy.Maximum)
        widget.layout().insertWidget(0, button)
        button.clicked.connect(widget.reset_value)
        widget.sig_param_updated.connect(self.value_updated)
        if hasattr(widget.layout, 'addStretch'):
            widget.layout().addStretch()

        return widget

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


class Tree(QtWidgets.QWidget):
    def __init__(self):
        super(Tree, self).__init__()
        self.tw = QTreeWidget()
        self.last_selected = None
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.tw)
        self.show()

    def new_tree(self, obj):
        def add_top_level_item(tree_widget, item_obj, name):
            top_item = QtWidgets.QtWidgets.QTreeWidget()
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
        scroll_area = QtWidgets.QScrollArea()
        container_widget = QtWidgets.QWidget()
        scroll_area.setWidget(container_widget)
        container_widget.setLayout( QtWidgets.QVBoxLayout() )
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
        tree_item.treeWidget().setItemWidget(
            tree_item,
            0,
            QtWidgets.QLabel(text)
        )
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
            child_item = QtWidgets.QTreeWidgetItem()
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
            child_item = QtWidgets.QTreeWidgetItem()
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
        child_item = QtWidgets.QTreeWidgetItem()
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


def main():
    interactive = True
    if interactive:
        shell = get_ipython_if_any()
        if shell and not shell._inputhook.__module__.endswith('.qt'):
            shell.enable_gui('qt')
            logger.info("Enabled 'qt' gui in current ipython shell")
    maybe_existing_app = QtWidgets.QApplication.instance()
    app = maybe_existing_app or QtWidgets.QApplication(sys.argv)
    from matplotlib.backends.qt_compat import QtGui
    QtGui.qApp = app
    pt = test()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
