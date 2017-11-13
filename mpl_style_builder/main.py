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
import matplotlib.pyplot

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
    from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg \
                                                            as FigureCanvas
    from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT \
                                                            as NavigationToolbar


# Project imports
from mpl_style_builder.param_widgets import (
    ComboboxParam,
    TextParam,
    SliderParam,
    ColorParam,
)


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

from datetime import datetime

def default_sample_plot(fig):
    yvals = [0, 100,  10, 100,  10,  10]
    xvals = list(map(
        datetime.utcfromtimestamp,
        [ 0,  30,  31,  45,  46, 300]
    ))
    ax = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)
    ret = ax.plot([y**2 for y in range(9)],
                  label='myline')
    ax=fig.axes[0]
#     ax.grid(True)
    ax.legend()
    ax.set_title('The graph title')
    ax.set_xlabel('the xlabel')
    ax2.plot(xvals, yvals)


def QString2pyunicode(qs):
    if not isinstance(qs, str):
        return str(qs.toAscii()).decode('utf8')
    else:
        return qs


class StyleBuilderMainWidget(QtWidgets.QWidget):
    def __init__(self, plot_callback=None):
        super(StyleBuilderMainWidget, self).__init__()
        self.setMinimumSize(600, 400)
        self.setLayout(QtWidgets.QVBoxLayout())

        self.top = QtWidgets.QWidget()
        self.top.setLayout( QtWidgets.QHBoxLayout() )
        self.layout().addWidget(self.top)

        self.top.layout().addWidget(QtWidgets.QLabel('Filter:'))
        self.filtration_field = QtWidgets.QLineEdit()
        self.top.layout().addWidget(self.filtration_field)
        self.filtration_field.textChanged.connect(self.filtration_changed)

        self.reset_all_button = QtWidgets.QPushButton('Reset all')
        self.top.layout().addWidget(self.reset_all_button)
        self.reset_all_button.clicked.connect(self.reset_all)

        self.show_changed_button = QtWidgets.QPushButton('Show changed')
        self.top.layout().addWidget(self.show_changed_button)
        self.show_changed_button.clicked.connect(
            lambda: self.display_list(sorted(self.changed))
        )

        self.mplstyle_combobox = QtWidgets.QComboBox()
        self.top.layout().addWidget(self.mplstyle_combobox)
        self.mplstyle_combobox.currentIndexChanged.connect(
            lambda _dummy: self.load_mplstyle(
                str(self.mplstyle_combobox.currentText())
            )
        )
        self.repopulate_stylelist()

        self.save_button = QtWidgets.QPushButton('Save new')
        self.top.layout().addWidget(self.save_button)
        self.save_button.clicked.connect(self.save_new_style)

        self.lower_frame = QtWidgets.QFrame()
        self.lower_frame.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.lower_frame)

        self.tw = QtWidgets.QTreeWidget(self)
        self.tw.model().setHeaderData(0, QtCore.Qt.Horizontal, 'Category')
        self.tw.setMinimumWidth(100)
        self.lower_frame.layout().addWidget(self.tw, stretch=2)

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
        self.lower_frame.layout().addWidget(self.scroll_area, stretch=10)

        self.plot_callback = plot_callback
        self.prop_widgets = {}
        self.prevent_figure_update = False
        rc_yaml_path = os.path.join(os.path.dirname(__file__), 'rcParams.yaml')
        with open(rc_yaml_path) as fh:
            self.categorized_params = yaml.safe_load(fh)
        self.params = dict(chain.from_iterable(
            [subdict.items() for subdict in self.categorized_params.values()]
        ))
        self.currently_displayed = []
        self.changed = {}

        self.show()

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

    def filtration_changed(self, text):
        spaced_separated = QString2pyunicode(text).split(' ')
        if not spaced_separated:
            return
        matching_first = self.params_matching(substr=spaced_separated[0])
        filtered_final = []
        for item in matching_first:
            if all(tok in item for tok in spaced_separated[1:]):
                filtered_final.append(item)
            else:
                continue
        self.display_list(
            sorted(filtered_final)
        )

    def repopulate_stylelist(self):
        current_choice = self.mplstyle_combobox.currentText()
        self.mplstyle_combobox.clear()
        mpl.pyplot.style.reload_library()
        items = ['<Load mplstyle>'] + mpl.pyplot.style.available
        try:
            current_idx = items.index(str(current_choice))
        except ValueError:
            current_idx = 0
        self.mplstyle_combobox.addItems(items)
        self.mplstyle_combobox.setCurrentIndex(current_idx)

    def load_mplstyle(self, name):
        rcparams = mpl.pyplot.style.library.get(name)
        if rcparams is None:
            logger.debug('mplstyle not found %s', name)
            return
        any_unrecognized = set(rcparams) - set(self.params)
        if any_unrecognized:
            logger.error('Unrecognized params in mplstyle %s: %s',
                          name,
                          any_unrecognized)
            return
        self.display_list(list(rcparams))
        self.prevent_figure_update = True  # FIXME this should be a lock
        for param, value in rcparams.items():
            logger.debug('Loaded from style %s: (%s: %s)', name, param, value)
            self.prop_widgets[param].set_value(value)
        self.prevent_figure_update = False
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
        for idx in range(self.prop_frame.layout().count() - 1): # sub -1 b/c spacer
            child = self.prop_frame.layout().takeAt(0)
            child.widget().hide()

    def tree_item_selected(self):
        selected = self.tw.selectedItems()
        logger.debug('Selected %s', selected)
        if len(selected) > 1:
            logger.debug('multiple items selected - no action')
            return
        else:
            selected_str = str(selected[0].text(0))
            matching = self.params_matching(
                # Matches 'sup', 'sup.sub', but not 'superduper'
                regex='^{}(\.?$|\.\w.*$)'.format(re.escape(selected_str))
            )
            self.display_list(matching)

    def plot_with_changed(self):
        if self.prevent_figure_update:  # FIXME this should be a lock
            return
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

    def _create_user_stylelib_directory(self):
        user_mpl_dir = os.path.join(
            str(QtCore.QDir.home().path()),
            '.config/matplotlib'
        )
        stylelib_dir = os.path.join(user_mpl_dir, 'stylelib')
        # Only create stylelib dir if does not exists and matplotlib dir found
        if not os.path.exists(stylelib_dir) and os.path.exists(user_mpl_dir):
            logger.debug('Creating stylelib directory: %s', stylelib_dir)
            os.mkdir(stylelib_dir)

    def save_new_style(self):
        if not self.changed:
            logger.debug('Nothing changed, nothing to save')
            return
        self._create_user_stylelib_directory()
        filepath = QtWidgets.QFileDialog.getSaveFileName(
            caption='Save new mplstyle',
            directory=os.path.join(
                str(QtCore.QDir.home().path()),
                '.config/matplotlib/stylelib'
            ),
            filter=".mplstyle files (*.mplstyle)"
        )
        if not filepath:
            logging.debug('No filepath chosen. Aborting save')
        else:
            filepath = str(filepath)
        if not filepath.endswith('.mplstyle'):
            filepath = filepath + '.mplstyle'
        lines = []
        for param, value in self.changed.items():
            if value and isinstance(value, str) and value.startswith('#'):
                value = value[1:]
            elif isinstance(value, list):
                if self.params[param]['list_type'] == 'integer':
                    value = map(int, value)
                value = ', '.join(map(str, value))
            lines.append('{}: {}'.format(param, value))

        with open(filepath, 'w') as fh:
            fh.write('\n'.join(lines))

        self.repopulate_stylelist()

    def reset_all(self):
        self.prevent_figure_update = True
        for param in list(self.changed):
            self.reset_param(param)
        self.prevent_figure_update = False
        self.plot_with_changed()

    def reset_param(self, param):
        self.prop_widgets[param].reset_value()
        if param in self.changed:
            self.changed.pop(param)

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
        button.clicked.connect(lambda: self.reset_param(name))
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
            widget = TextParam(name, prop)
        elif prop['type'] == 'bool':
            widget = ComboboxParam(name, prop)
        elif prop['type'] == 'colorstring':
            widget = ColorParam(name, prop)

        return widget


def get_ipython_if_any():
    try:
        from IPython import get_ipython
    except ImportError:
        return None

    return get_ipython()


class MplStyleBuilder(object):
    def __init__(self, plot_callback=None, call_exec=False, interactive=True):
        if interactive:
            shell = get_ipython_if_any()
            if shell and not shell._inputhook.__module__.endswith('.qt'):
                shell.enable_gui('qt')
                logger.info("Enabled 'qt' gui in current ipython shell")
        maybe_existing_app = QtWidgets.QApplication.instance()
        self.app = maybe_existing_app or QtWidgets.QApplication(sys.argv)
        from matplotlib.backends.qt_compat import QtGui
        QtGui.qApp = self.app
        if plot_callback is None:
            plot_callback = default_sample_plot
        self.builder = StyleBuilderMainWidget(plot_callback)
        self.builder.build_tree()
        if call_exec:
            sys.exit(self.app.exec_())


def main():
    style_builder = MplStyleBuilder(call_exec=True, interactive=False)
    return style_builder


if __name__ == '__main__':
    style_builder = main()
