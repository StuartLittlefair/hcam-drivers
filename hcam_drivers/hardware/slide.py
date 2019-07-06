#!/usr/bin/env python

"""
Class to talk to the focal plane slide

Written by Stu.
"""
from __future__ import (print_function, division, absolute_import)
import struct
import six
import socket
import threading

# internal imports
from hcam_widgets.widgets import GuiLogger, IntegerEntry
from hcam_widgets.misc import get_hardware_value, set_hardware_value
from hcam_widgets.tkutils import get_root

if not six.PY3:
    import Tkinter as tk
else:
    import tkinter as tk


class SlideError(Exception):
    pass


# number of bytes to transmit & recieve
PACKET_SIZE = 6

# command numbers
RESET = 0
HOME = 1
MOVE_ABSOLUTE = 20
MOVE_RELATIVE = 21
STOP = 23
RESTORE = 36
SET_MODE = 40
RETURN_SETTING = 53
POSITION = 60
NULL = 0

# error return from slide
ERROR = 255

# unit number, may depend upon how device is connected to the port
UNIT = 1

PERIPHERAL_ID = 0
POTENTIOM_OFF = 8
POTENTIOM_ON = 0

TRUE = 1
FALSE = 0

# the next define ranges for the movement in terms of
# microsteps, millimetres and pixels
MIN_MS = 0
MAX_MS = 1664000
MM_PER_MS = 0.000078
MIN_MM = MM_PER_MS*MIN_MS
MAX_MM = MM_PER_MS*MAX_MS

# Next numbers set the limits in pixel numbers. They are telescope dependent.
# WHT/HIPERCAM Numbers, Oct 2017
# 429.85589 MS per PIX
# GTC/HIPERCAM Numbers, Feb 2018
# 424.8903 MS per PIX

# TNT values March 2014 -- present
MIN_PX = 2760.2
MAX_PX = -1155.3

# Standard pixel positions for unblocking and blocking the CCD
UNBLOCK_POS = 1100.
BLOCK_POS = -100.

# the slide starts moving taking time MAX_STEP_TIME and accelerates to
# MIN_STEP_TIME (in seconds/steps) at a rate of STEP_TIME_ACCN
# (secs/step/step) These parameters are used to estimate the time taken to
# make a move along with the number of microsteps/step
MAX_STEP_TIME = 0.0048
MIN_STEP_TIME = 0.0025
STEP_TIME_ACCN = 0.00005
MS_PER_STEP = 64

# MAX_TIMEOUT is set by the time taken to move the slide from one end to the
# other MIN_TIMEOUT is used as a lower limt on all timeouts (seconds)
MIN_TIMEOUT = 5
MAX_TIMEOUT = 70


class Slide(object):

    def __init__(self, log=None, host='192.168.1.3', port=10001):
        """
        Creates a Slide. Arguments::

         log  : not used, argument still in API for backwards compatibility
         port : port device representing the slide

        """
        self.port = port
        self.host = host
        self.default_timeout = MIN_TIMEOUT
        # thread lock for threadsafe operations
        self._lock = threading.Lock()
        # open connection on object creation
        try:
            self.connect()
        except ConnectionRefusedError:
            self.sock = None

    def __del__(self):
        # must close connection on object deletion
        self.close()

    def connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        self.sock = s

    def close(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None

    def _sendRecv(self, byteArr, timeout):
        if self.sock is None:
            try:
                self.connect()
            except ConnectionRefusedError:
                raise SlideError('not connected')

        # only one thread at a time talks to the slide
        with self._lock:
            try:
                self.sock.settimeout(self.default_timeout)
                self.sock.send(byteArr)
            except Exception as e:
                raise SlideError('failed to send bytes to slide' + str(e))
            self.sock.settimeout(timeout)
            msg = self.sock.recv(6)
        return bytearray(msg)

    def _decodeCommandData(self, byteArr):
        return struct.unpack('<L', byteArr[2:])[0]

    def _encodeCommandData(self, int):
        return bytearray(struct.pack('<L', int))

    def _encodeByteArr(self, intArr):
        if len(intArr) != 6:
            raise SlideError('must send 6 bytes to slide: cannot send ' +
                             repr(intArr))
        return bytearray(intArr)

    def compute_timeout(self, nmicrostep):
        nstep = abs(nmicrostep)/MS_PER_STEP
        nacc = (MAX_STEP_TIME - MIN_STEP_TIME)/STEP_TIME_ACCN
        if nacc > nstep:
            time_estimate = (MAX_STEP_TIME - STEP_TIME_ACCN * nstep/2)*nstep
        else:
            time_estimate = (MAX_STEP_TIME + MIN_STEP_TIME)*nacc/2 + \
                MIN_STEP_TIME*(nstep-nacc)

        timeout = time_estimate+2
        timeout = timeout if timeout > MIN_TIMEOUT else MIN_TIMEOUT
        timeout = timeout if timeout < MAX_TIMEOUT else MAX_TIMEOUT
        return timeout

    def _getPosition(self):
        """
        returns current position of the slide in microsteps
        """
        if not self._hasBeenHomed():
            raise SlideError('position of slide is undefined until slide homed')
        byteArr = self._encodeByteArr([UNIT, POSITION, NULL, NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        pos = self._decodeCommandData(byteArr)
        return pos

    def _hasBeenHomed(self):
        """
        returns true if the slide has been homed and has a calibrated
        position
        """
        byteArr = self._encodeByteArr([UNIT, RETURN_SETTING,
                                       SET_MODE, NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        if byteArr[1] == ERROR:
            raise SlideError('Error trying to get the setting byte')

        # if 7th bit is set, we have been homed
        if byteArr[2] & 128:
            return True
        else:
            return False

    def _move_absolute(self, nstep, timeout=None):
        """
        move to a defined position in microsteps
        """
        if nstep < MIN_MS or nstep > MAX_MS:
            raise SlideError("Attempting to set position = %d ms," +
                             " which is out of range %d to %d" % (nstep, MIN_MS, MAX_MS))
        if not timeout:
            timeout, _ = self.time_absolute(nstep)

        # encode command bytes into bytearray
        byteArr = self._encodeCommandData(nstep)

        # add bytes to define instruction at start of array
        byteArr.insert(0, MOVE_ABSOLUTE)
        byteArr.insert(0, UNIT)
        byteArr = self._sendRecv(byteArr, timeout)

    def _move_relative(self, nstep, timeout=None):
        """
        move by nstep microsteps relative to the current position
        """
        # if this raises an error, so be it
        start_pos = self._getPosition()
        attempt_pos = start_pos+nstep
        if attempt_pos < MIN_MS or attempt_pos > MAX_MS:
            raise SlideError("Attempting to set position = %d ms," +
                             " which is out of range %d to %d" % (nstep, MIN_MS, MAX_MS))
        if not timeout:
            timeout = self.compute_timeout(nstep)

        # encode command bytes into bytearray
        byteArr = self._encodeCommandData(nstep)

        # add bytes to define instruction at start of array
        byteArr.insert(0, MOVE_RELATIVE)
        byteArr.insert(0, UNIT)
        byteArr = self._sendRecv(byteArr, self.default_timeout)

    def _convert_to_microstep(self, amount, units):
        """"
        Converts amount to number of microsteps
        """
        if units.upper() not in ['MS', 'PX', 'MM']:
            raise SlideError('unsupported units %s: only PX,' +
                             ' MM or MS allowed' % units)

        if units.upper() == 'MS':
            nstep = int(amount)
        elif units.upper() == 'PX':
            nstep = MIN_MS + int((MAX_MS-MIN_MS) *
                                 (amount-MIN_PX) / (MAX_PX-MIN_PX) + 0.5)
        elif units.upper() == 'MS':
            nstep = MIN_MS + int((MAX_MS-MIN_MS) *
                                 (amount-MIN_MM) / (MAX_MM-MIN_MM) + 0.5)
        return nstep

    def time_absolute(self, nstep, units='ms'):
        """
        Returns estimate of time to carry out a move to absolute value nstep
        Have to separate this from because of threading issues.
        """
        start_pos = self._getPosition()
        end = self._convert_to_microstep(nstep, units)
        return self.compute_timeout(end-start_pos), None

    def time_home(self):
        """
        Returns estimate of time to carry out the home command. Have to separate
        this from home itself because of threading issues.
        """
        if self._hasBeenHomed():
            # if this throws an exception, then something is bad, so don't catch
            start_pos = self._getPosition()
            return self.compute_timeout(start_pos), None
        else:
            return MAX_TIMEOUT, 'position undefined: setting max timeout for home'

    def home(self, timeout=None):
        """
        move the slide to the home position. This is needed after a power on
        to calibrate the slide
        """
        if not timeout:
            timeout = self.time_home()

        byteArr = self._encodeByteArr([UNIT, HOME, NULL, NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        if byteArr[1] == ERROR:
            raise SlideError('Error occurred setting to the home position')
        return None, 'Slide returned to home position (click "position" to confirm)'

    def reset(self):
        """
        carry out the reset command, equivalent to turning the slide off and
        on again. The position of the slide will be lost and a home will be
        needed
        """
        byteArr = self._encodeByteArr([UNIT, RESET, NULL, NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        return 'reset completed'

    def restore(self):
        """
        carry out the restore command. restores the device to factory settings
        very useful if the device does not appear to function correctly
        """
        byteArr = self._encodeByteArr([UNIT, RESTORE, PERIPHERAL_ID,
                                       NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        return 'finished restore'

    def disable(self):
        """
        carry out the disable command. disables the potentiometer preventing
        manual adjustment of the device
        """
        byteArr = self._encodeByteArr([UNIT, SET_MODE, POTENTIOM_OFF,
                                       NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        return 'manual adjustment disabled'

    def enable(self):
        """
        carry out the enable command. enables the potentiometer allowing
        manual adjustment of the device
        """
        byteArr = self._encodeByteArr([UNIT, SET_MODE, POTENTIOM_ON,
                                       NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        return 'manual adjustment enabled'

    def stop(self):
        """stop the slide"""
        byteArr = self._encodeByteArr([UNIT, STOP, NULL, NULL, NULL, NULL])
        byteArr = self._sendRecv(byteArr, self.default_timeout)
        if byteArr[1] == ERROR:
            raise SlideError('Error stopping the slide')

        return None, 'slide stopped at {}'.format(self.report_position())

    def move_relative(self, amount, units, timeout=None):
        """
        move the slide by a relative amount.

        Available units are:
        MS - microsteps
        PX - pixels
        MM - millimeters
        """
        nstep = self._convert_to_microstep(amount, units)
        self._move_relative(nstep, timeout)
        msg = 'Moving slide by {} {} (click "position" to confirm")'.format(
            str(amount), units
        )
        return None, msg

    def move_absolute(self, amount, units, timeout=None):
        '''move the slide to an absolute position.
        available units are:
        MS - microsteps
        PX - pixels
        MM - millimeters
        '''
        nstep = self._convert_to_microstep(amount, units)
        self._move_absolute(nstep, timeout)
        msg = 'Moving slide to {} {} (click "position" to confirm")'.format(
            str(amount), units
        )
        return None, msg

    def return_position(self):
        """
        Returns position in microsteps, mm and pixels. Returns
        (ms,mm,px)
        """
        pos_ms = self._getPosition()
        pos_mm = MIN_MM + (MAX_MM-MIN_MM)*(pos_ms-MIN_MS)/(MAX_MS-MIN_MS)
        pos_px = MIN_PX + (MAX_PX-MIN_PX)*(pos_ms-MIN_MS)/(MAX_MS-MIN_MS)
        return (pos_ms, pos_mm, pos_px), None

    def report_position(self):
        """
        Reports position in microsteps, mm and pixels. Returns
        (ms,mm,px)
        """
        (pos_ms, pos_mm, pos_px), msg = self.return_position()
        return 'Current position = {0:6.1f} pixels ({1:.1f} mm, {2:d} ms)'.format(
            pos_px, pos_mm, pos_ms
        )


class FocalPlaneSlide(tk.LabelFrame):
    """
    Self-contained widget to deal with the focal plane slide
    """

    def __init__(self, master):
        """
        master  : containing widget
        """
        tk.LabelFrame.__init__(
            self, master, text='Focal plane slide', padx=10, pady=4)

        # Top for table of buttons
        top = tk.Frame(self)

        # Define the buttons
        width = 8
        self.home = tk.Button(top, fg='black', text='home', width=width,
                              command=lambda: self.action('home'))

        self.block = tk.Button(top, fg='black', text='block', width=width,
                               command=lambda: self.action('block'))

        self.unblock = tk.Button(top, fg='black', text='unblock', width=width,
                                 command=lambda: self.action('unblock'))

        self.gval = IntegerEntry(top, UNBLOCK_POS, None, True, width=4)

        self.goto = tk.Button(top, fg='black', text='goto', width=width,
                              command=lambda: self.action('goto',
                                                          self.gval.value()))

        self.position = tk.Button(top, fg='black', text='position', width=width,
                                  command=lambda: self.action('position'))

        self.reset = tk.Button(top, fg='black', text='reset', width=width,
                               command=lambda: self.action('reset'))

        self.stop = tk.Button(top, fg='black', text='stop', width=width,
                              command=lambda: self.action('stop'))

        self.enable = tk.Button(top, fg='black', text='enable', width=width,
                                command=lambda: self.action('enable'))

        self.disable = tk.Button(top, fg='black', text='disable', width=width,
                                 command=lambda: self.action('disable'))

        self.restore = tk.Button(top, fg='black', text='restore', width=width,
                                 command=lambda: self.action('restore'))

        # arrange the permanent ones
        self.home.grid(row=0, column=0)
        self.block.grid(row=0, column=1)
        self.unblock.grid(row=0, column=2)
        self.goto.grid(row=1, column=0)
        self.gval.grid(row=1, column=1)
        self.position.grid(row=1, column=2)

        # set others according to expertlevel
        self.setExpertLevel()

        top.pack(pady=2)

        # region to log slide command results
        self.log = GuiLogger('SLD', self, 5, 53)
        self.log.pack(pady=2)

        # Queue for slide messages
        self.running_future = None
        self.thread = None

        # Finish off
        self.where = 'UNDEF'

    def setExpertLevel(self):
        """
        Modifies widget according to expertise level, which in this
        case is just matter of hiding or revealing the LED option
        and changing the lower limit on the exposure button.
        """
        g = get_root(self).globals
        level = g.cpars['expert_level']

        if level == 0:
            self.reset.grid_forget()
            self.enable.grid_forget()
            self.disable.grid_forget()
            self.restore.grid_forget()
            self.stop.grid_forget()
        else:
            self.stop.grid(row=2, column=0)
            self.disable.grid(row=2, column=1)
            self.enable.grid(row=2, column=2)
            self.reset.grid(row=3, column=0)
            self.restore.grid(row=3, column=1)

    def startSlideCommand(self, command):
        """
        Start running a slide command in the background
        """
        if self.running_future is not None:
            self.log.warn('Slide command already running, aborted')
            return

        self.running_future = command()
        self.after(100, self.checkSlideCommand)

    def checkSlideCommand(self):
        if self.running_future and not self.running_future.ready:
            self.after(100, self.checkSlideCommand)
            return

        try:
            value, msg = self.running_future.value
        except TypeError:
            msg = self.running_future.value
        except Exception as error:
            self.log.warn('Error in Slide thread: {}'.format(error))
            self.log.warn('You may want to try again; the slide is unreliable\n' +
                          'in its error reporting. Try "position" for example')
        else:
            self.log.info(msg)

        self.running_future = None

    def action(self, *comm):
        """
        Send a command to the focal plane slide
        """
        g = get_root(self).globals
        if not g.cpars['focal_plane_slide_on']:
            self.log.warn('Focal plane slide access is OFF; see settings.')
            return

        self.log.info('Executing command: ' +
                      ' '.join([str(it) for it in comm]))

        if comm[0] == 'home':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'home', background=True)
                return result

        elif comm[0] == 'unblock':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'position',
                                            UNBLOCK_POS, background=True)
                return result

        elif comm[0] == 'block':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'position',
                                            BLOCK_POS, background=True)
                return result

        elif comm[0] == 'position':
            def command():
                result = get_hardware_value(g.cpars, 'slide', 'position', background=True)
                return result

        elif comm[0] == 'reset':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'reset', background=True)
                return result

        elif comm[0] == 'restore':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'restore', background=True)
                return result

        elif comm[0] == 'enable':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'enable', background=True)
                return result

        elif comm[0] == 'disable':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'disable', background=True)
                return result

        elif comm[0] == 'stop':
            def command():
                result = set_hardware_value(g.cpars, 'slide', 'stop', background=True)
                return result

        elif comm[0] == 'goto':
            if comm[1] is not None:
                def command():
                    result = set_hardware_value(
                        g.cpars, 'slide', 'position', comm[1], background=True
                    )
                    return result
            else:
                self.log.warn('You must enter an integer pixel position' +
                              ' for the mask first')
                return
        else:
            self.log.warn('Command = ' + str(comm) +
                          ' not implemented yet.')
            return

        self.where = comm[0]
        self.startSlideCommand(command)
