from __future__ import division, print_function

from setuptools import setup

VERSION = '0.1.0'

import importlib

def raises_importerror(module):
    try:
        importlib.import_module(module)
        return False
    except ImportError:
        return True


def check_if_installed(module, only_if=None, advice='', raise_=False):
    """
    :param module: str, module to try to import or raise if not present
    :param only_if: bool-callback, only raise if true.
    :param advice: str, how to satisfy requirement
    :param raise_: bool, raise or just print warning
    """
    if raises_importerror(module):
        if only_if and only_if():
            # We're good, hopefully the requirement will be satisfied
            # after installation
            return
        txt = "Missing extra dependency '{}'. {}".format(module, advice)
        if raise_:
            raise ImportError(txt)
        else:
            print('WARNING: %s' %txt)
    else:
        print("{} installed - OK!".format(module))


pre_dependencies = [
    {
        'module': 'PyQt4',
        'advice': "Try e.g. 'apt-get install python-qt4'",
    },
    {
        'module': 'PyQt5',
        # If PyQt4 is importable, we don't raise
        'only_if': lambda: raises_importerror('PyQt4'),
        'advice': "Try e.g. 'pip3 install pyqt5'",
    },
    {
        'module': 'matplotlib.backends.backend_qt4agg',
        'only_if': lambda: raises_importerror('matplotlib') \
                and raises_importerror('matplotlib.backends.backend_qt4agg'),
        'advice': 'Try reinstalling matplotlib',
    },
    {
        'module': 'matplotlib.backends.backend_qt5agg',
        'only_if': lambda: raises_importerror('matplotlib') \
                and raises_importerror('matplotlib.backends.backend_qt4agg'),
        'advice': 'Try reinstalling matplotlib',
    },
]

from setuptools.command.install import install
from setuptools.command.develop import develop

class PreInstallHook(install):
    def run(self):
        [check_if_installed(**dep_dict) for dep_dict in pre_dependencies]
        install.run(self)


class PreDevelopHook(develop):
    def run(self):
        [check_if_installed(**dep_dict) for dep_dict in pre_dependencies]
        develop.run(self)


setup(
    name="mpl_style_builder",
    version=VERSION,
    description='Tool for producing matplotlib rc-param collections (styles) '
    			'interactively',
    url='https://github.com/lenolib/matplotlib-style-builder',
    author='Lennart Liberg',
    license='GPL-3.0',
    packages=[
        'mpl_style_builder'
    ],
    install_requires=[
        'matplotlib>=1.5.0', # maybe higher required TODO: test
    ],
    extras_require={
    },
    cmdclass={
        'install': PreInstallHook, # TODO verify behaviour
        'develop': PreDevelopHook, # TODO verify behaviour
    },
    entry_points={
        'console_scripts': [
            'mpl-style-builder=mpl_style_builder.main:main',
        ],
    },
)
