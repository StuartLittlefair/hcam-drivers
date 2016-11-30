# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
hcam-drivers is a GUI interface for running the HiperCAM high-speed
camera. The main user-facing tool is the hdriver.py script which runs
the GUI.

The package follows the following general structure. Widgets are defined as
classes. All widgets have a ``toplevel`` argument in the constructor, which
is the main window widget. This top level widget has attributes for e.g. window parameters.
As a result, all widgets have access to the same properties through their ``toplevel``
attribute, which allows the widgets to interact with each other.
"""

# Affiliated packages may add whatever they like to this file, but
# should keep this content at the top.
# ----------------------------------------------------------------------------
from ._astropy_init import *
# ----------------------------------------------------------------------------

# For egg_info test builds to pass, put package imports here.
if not _ASTROPY_SETUP_:
    from .example_mod import *
