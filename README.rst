HiperCAM Python Driver
===================================

.. image:: http://img.shields.io/badge/powered%20by-AstroPy-orange.svg?style=flat
    :target: http://www.astropy.org
    :alt: Powered by Astropy Badge

``hcam_drivers`` provides Python tools for interfacing with the HiperCAM high-speed
camera. ``hcam_drivers`` is written in Python and is based on TKinter. It should be
compatible with Python2 and Python3. 

Installation
------------

The software is written as much as possible to make use of core Python
components. The third-party requirements are `astropy <http://astropy.org/>`_, a package 
for astronomical calculations, and `pyserial <http://pyserial.sourceforge.net/>`_ for 
talking to serial ports.

Once you have installed these, install with the usual::

 python setup.py install

or if you don't have root access::

 python setup.py install --prefix=my_own_installation_directory

For more information, see:

* `The documentation <http://hcam-drivers.readthedocs.io/en/latest/>`_
* `This packages' Github code repository <https://github.com/StuartLittlefair/hcam_drivers>`_

Status reports for developers
-----------------------------

.. image:: https://travis-ci.org/astropy/package-template.svg
    :target: https://travis-ci.org/StuartLittlefair/hcam-drivers
    :alt: Travis Status
