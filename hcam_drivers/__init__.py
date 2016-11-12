# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
hcam-drivers is a GUI interface for running the HiperCAM high-speed
camera. The main user-facing tool is the hdriver.py script which runs
the GUI.

The package follows the general structure first adopted by T. Marsh
for the ULTRACAM/SPEC GUIs, which is is to group related buttons and information 
fields into discrete widgets, which translate into equivalent classes at the code level,
e.g. trm.drivers.drivers.Astroframe. The compartmentalisation suggested by
this is rather illusory as there is typically a need to interact between such
widgets. One way to do this would have been with callbacks, but in the end I
decided it was much easier to use a set of globals. Many of the classes therefore
really serve just to loosely group functions associated with them.

"""

# Affiliated packages may add whatever they like to this file, but
# should keep this content at the top.
# ----------------------------------------------------------------------------
from ._astropy_init import *
# ----------------------------------------------------------------------------

# For egg_info test builds to pass, put package imports here.
if not _ASTROPY_SETUP_:
    from .example_mod import *
