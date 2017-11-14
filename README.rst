HiperCAM Python Driver
===================================

``hcam_drivers`` provides Python tools for interfacing with the HiperCAM high-speed
camera. ``hcam_drivers`` is written in Python and is based on TKinter. It should be
compatible with Python2 and Python3.

Installation
------------

The software is written as much as possible to make use of core Python
components. The third-party requirements are:

- My own `hcam_widgets <https://github.com/HiPERCAM/hcam_widgets/>`_ package;

- `astropy <http://astropy.org/>`_, a package for astronomical calculations;

- `pyserial <http://pyserial.sourceforge.net/>`_ for talking to serial ports;

- `tornado <http://www.tornadoweb.org/en/stable/>`_, used for the various servers which allow communicationbetween the GUI and the instrument

- `pyaml <https://pypi.python.org/pypi/pyaml/>`_ and `configobj <http://configobj.readthedocs.io/en/latest/configobj.html/>`_ for loading config files and

- `pymodbus <https://github.com/riptideio/pymodbus>`_ (Python 2) or `pymodbus3 <https://pypi.python.org/pypi/pymodbus3/1.0.0>`_ (Python 3) for talking to the flow-rate monitor.


Usually, installing with pip will handle these dependencies for you, so installation is a simple matter of typing::

 pip install hcam_drivers

or if you don't have root access::

 pip install --prefix=my_own_installation_directory hcam_drivers

For more information, see:

* `The documentation <http://hcam-drivers.readthedocs.io/en/latest/>`_
* `This packages' Github code repository <https://github.com/HiPERCAM/hcam_drivers>`_

