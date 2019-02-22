import serial
import threading
import signal
import time
from functools import partial
from contextlib import contextmanager

from astropy import units as u


class NoKeyboardInterrupt:
    """
    Context manager to ignore Keyboard interrupt for lifetime of context

    Interuppt is triggered upon exit. If called in a thread, does nothing.
    """
    def __enter__(self):
        try:
            self.signal_received = False
            self.old_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self.handler)
            self.threaded = False
        except ValueError:
            self.threaded = True

    def handler(self, signal, frame):
        self.signal_received = (signal, frame)

    def __exit__(self, type, value, traceback):
        if not self.threaded:
            signal.signal(signal.SIGINT, self.old_handler)
            if self.signal_received:
                self.old_handler(*self.signal_received)
        else:
            pass


class NewportError(Exception):
    '''
    Class to represent errors from the controller

    Errors come in the form (code, timestamp, MESSAGE).
    e.g 0, 451322, NO ERROR DETECTED
    '''
    def __init__(self, string):
        self._string = string
        code, ts, msg = string.split(',')
        if len(code) == 3:
            self.axis = int(code[0])
            self.code = int(code[1:])
        else:
            self.axis = None
            self.code = code
        self.timestamp = int(ts.strip())  # number of 400us intervals since reset
        self.message = msg.strip()

    def __str__(self):
        msg = 'newport error code {}'.format(self.code)
        if self.axis is not None:
            msg += ' on axis ' + self.axis
        return '{} ({})'.format(msg, self.message)


class AxisProperty:
    """
    A descriptor for access to a property of a NewportESP301Axis

    For example, one might wish to get or set the acceleration of a motor
    stage. There is a fair amount of boiler-plate code involved in getting
    or setting this property, but all that differs between them is the command
    code used and the units of the property.

    This is a perfect use of a Python descriptor
    """
    def __init__(self, code, units=u.dimensionless_unscaled,
                 relative_units=True, errcheck=True):
        """
        Parameters
        ----------
        code : string
            command code used to get or set property, e.g QS for microstep
        units : ```~astropy.units.Quantity```
            the units of the property, e.g ```~astropy.unit.A``` for current.
            see also `relative_units`.
        relative_units : bool
            units are in terms of Axis base units.

            Some properties are always returned in terms of the Axis' base units.
            For example,  the velocity is returned in 'units'/sec, where 'units' can
            be set on the controller axis. If `relative_units` is `True`, the property
            units are given by the controller base units multiplied by the `unit` of the
            property.
        errcheck : bool
            check for errors on get/set
        """
        self.code = code
        self.units = units
        self.relative_units = relative_units
        self.errcheck = errcheck

    def __get__(self, instance, cls):
        if instance is None:
            # called from class itself
            return self
        else:
            # called from class instance
            val = instance._cmd(self.code + '?', errcheck=self.errcheck)
            if self.relative_units:
                units = instance.units * self.units
            else:
                units = self.units
            return val * units

    def __set__(self, instance, value):
        # if we are passed a float or int, assume correct units and create quantity
        if not isinstance(value, u.Quantity):
            value = value * self.units * instance.units if self.relative_units else value * self.units

        # get value in correct units
        value = value.to_value(self.units * instance.units if self.relative_units else self.units)

        # set value
        instance._cmd(self.code, params=(value,), errcheck=self.errcheck)


class IntegerAxisProperty(AxisProperty):
    """
    An axis property that must be integer.
    """
    def __init__(self, code, errcheck=True):
        super(IntegerAxisProperty, self).__init__(code,
                                                  units=u.dimensionless_unscaled,
                                                  relative_units=False,
                                                  errcheck=errcheck)

    def __get__(self, instance, cls):
        value = super(IntegerAxisProperty, self).__get__(instance, cls)
        return int(value)

    def __set__(self, instance, value):
        super(IntegerAxisProperty, self).__set__(instance, int(value))


class NewportESP301:
    """
    Controller for ESP301 Motion Controller over Serial Interface.

    The controller itself has some limited functionality, but mostly this class serves
    as a container for a list of NewportESP301Axis objects, which directly control stages
    attached to each axis. For example

    >>> esp = NewportESP301('/dev/ttyUSB0')
    >>> esp.axis[0].home()

    Axes are numbered starting from zero, following Python standards, but in the controller
    they are labelled from 1, so `esp.axis[0]` refers to axis 1 as described in the manual.
    """
    def __init__(self, port, baudrate=19200):
        """
        Parameters
        -----------
        port : string
            Serial port
        baudrate : int, default=19200
            baud rate for serial port
        """
        self.lock = threading.Lock()
        self.dev = serial.Serial(port=port, baudrate=baudrate, bytesize=8, timeout=1,
                                 parity='N', rtscts=1)
        self._execute_immediately = True  # either collect commands into a list, or send one-by-one
        self._command_list = []  # list of commands to send together
        self.axis = [NewportESP301Axis(self, i) for i in range(3)]

    def __del__(self):
        self.ser.close()

    def _execute(self, cmd, errcheck):
        """
        Write string to device
        """
        response = None

        with self.lock:
            with NoKeyboardInterrupt():
                if not cmd.endswith('\r'):
                    cmd += '\r'
                self.ser.write(cmd)
                if '?' in cmd:
                    response = self.ser.readline().strip()

                if errcheck:
                    self.ser.write('TB?\r')
                    error_string = self.ser.readline().strip()
                    if not error_string.startswith('0'):
                        raise NewportError(error_string)

        return response

    def _cmd(self, cmd, params=tuple(), target=None, errcheck=True):
        """
        Here we wrap low-level read/write commands to allow specifying different axis and error checking

        Write to device.

        Parameters
        -----------
        cmd : string
            commands to send to device.
        params : iterable
            parameters for command, eg. position for move
        target : int or NewportESP301Axis, default None
            The destination axis. If none, msg is sent to controller
        errcheck : bool
            If true, the device is checked for errors after command is sent
            Note that error-checking is disabled in program mode, so ```errcheck```
            must be `False` in program mode
        """

        if isinstance(target, NewportESP301Axis):
            target = target.axis_idx

        raw_cmd = "{target}{cmd}{params}".format(
            target=target if target is not None else "",
            cmd=cmd.upper(),
            params=",".join(map(str, params))
        )

        response = None
        if self._execute_immediately:
            response = self._execute(raw_cmd, errcheck)
        else:
            self._command_list.append(raw_cmd)

        return response

    def reset(self):
        """
        Perform a hardware reset.

        Only effective if the watchdog timier is enabled by physical jumpers. See the users guide
        for more information
        """
        self._cmd("RS", errcheck=False)

    def abort_all_axes(self):
        self._cmd('AB')

    def stop_all_axes(self):
        """
        Stops motion on all axes, with programmed decceleration rate
        """
        self._cmd('ST')

    @property
    def version(self):
        return self.cmd('VE?')

    @contextmanager
    def define_program(self, program_id):
        """
        Erases existing program with given ID and records commands within this context to new program

        Parameters
        ----------
        program_id : int
            Label for new program

        Usage
        -----
        >>> controller = NewportESP301('/dev/ttyS0')
        >>> with controller.define_program(10):
        ...        controller.axis[0].move(0.001, absolute=False)
        ...        controller.axis[1].move(20, absolute=True)
        ...
        >>> controller.run_program(10)
        """
        if program_id not in range(1, 101):
            raise ValueError('program ID must be in range 1 to 100 (inclusive')

        # erase old program and enter programming mode
        self._cmd('XX', target=program_id)
        try:
            self._cmd('EP', target=program_id)
            yield
        finally:
            self._cmd('QP')

    @contextmanager
    def execute_bulk_commands(self, errcheck=True):
        """
        Context manager to send mutliple commands in a single message to controller.

        Note that it is not currently possible to receive the controllers response.

        Parameters
        -----------
        errcheck : bool
            Check for errors after each command

        Usage
        -------
        >>> controller = NewportESP301('/dev/ttyS0')
        >>> with controller.execute_bulk_command():
        ...     controller.axis[0].move(0.001, absolute=False)
        ...     controller.axis[1].move(20, absolute=True)
        ...
        """
        self._execute_immediately = False
        yield
        command_string = ';'.join(self._command_list)
        self._bulk_query_resp = self.execute(command_string, errcheck)
        self._command_list = []
        self._execute_immediately = True

    def run_program(self, program_id):
        """
        Run a previously defined program

        Program must be defined using ```NewportESP301.define_program```.

        Parameters
        ----------
        program_id : int
            ID number of previously defined program
        """
        if program_id not in range(1, 101):
            raise ValueError('program ID must be in range 1 to 100 (inclusive')

        self._cmd("EX", target=program_id)


class NewportESP301Axis:
    """
    Communication class for access to a single axis of an ESP301 controller.
    """

    # TODO: make it work when trying to use units of encoder count and motor step
    _unit_dict = {
        0: u.def_unit('encoder count', u.dimensionless_unscaled),
        1: u.def_unit('motor step', u.dimensionless_unscaled),
        2: u.mm,
        3: u.micrometer,
        4: u.imperial.inch,
        5: u.def_unit('milliinch', u.imperial.inch / 1000),
        6: u.def_unit('microinch', u.imperial.inch / 1000000),
        7: u.deg,
        8: u.def_unit('gradian', 9*u.deg/10),
        9: u.rad,
        10: u.milliradian,
        11: u.microradian
    }

    acceleration = AxisProperty('AC', units=1/u.s**2)
    deceleration = AxisProperty('AG', units=1/u.s**2)
    estop_deceleration = AxisProperty('AE', units=1/u.s**2)
    max_acceleration = AxisProperty('AU', units=1/u.s**2)
    max_deceleration = AxisProperty('AU', units=1/u.s**2)
    jerk = AxisProperty('JK', units=1/u.s**3)
    velocity = AxisProperty('VA', units=1/u.s)
    max_velocity = AxisProperty('VU', units=1/u.s)
    max_base_velocity = AxisProperty('VB', units=1/u.s)  # for stepper motors only
    jog_high_velocity = AxisProperty('JH', units=1/u.s)
    jog_low_velocity = AxisProperty('JL', units=1/u.s)
    homing_velocity = AxisProperty('OH', units=1/u.s)
    position = AxisProperty('TP')
    desired_position = AxisProperty('DP')
    desired_velocity = AxisProperty('DV', units=1/u.s)
    home_position = AxisProperty('DH')
    left_limit = AxisProperty('SL')
    right_limit = AxisProperty('SR')
    error_threshold = AxisProperty('FE')
    current = AxisProperty('QI', units=u.A, relative_units=False)
    voltage = AxisProperty('QV', units=u.V, relative_units=False)
    motor_type = IntegerAxisProperty('QM')
    position_display_resolution = IntegerAxisProperty('FP')  # 0--7, num. dec. places except 7=scientific notation
    # 1: trapezoidal, 2: s-curve, 3: jog, 4: slave to master's desired position
    # 5: slave to masters actual position, 6: slave to masters velocity
    trajectory_mode = IntegerAxisProperty('TJ')
    microstep_factor = IntegerAxisProperty('QS')
    accel_feedforward_gain = AxisProperty('AF', units=u.dimensionless_unscaled, relative_units=False)
    proportional_gain = AxisProperty('KP', units=u.dimensionless_unscaled, relative_units=False)
    derivative_gain = AxisProperty('KD', units=u.dimensionless_unscaled, relative_units=False)
    integral_gain = AxisProperty('KI', units=u.dimensionless_unscaled, relative_units=False)
    integral_gain_saturation = AxisProperty('KS',
                                            units=u.dimensionless_unscaled,
                                            relative_units=False)

    def __init__(self, controller, axis_idx):
        if not isinstance(controller, NewportESP301):
            raise ValueError('controller must be an instance of NewportESP301')

        self.controller = controller
        self.axis_idx = axis_idx
        self._units = NewportESP301Axis._unit_dict[self._get_units()]
        # make a copy of the controller command function, with this axis index hard-wired
        self._cmd = partial(self._controller._cmd, target=self.axis_idx)

    @property
    def motion_complete(self):
        """
        True if all motion commands complete.
        """
        return bool(int(self._cmd("MD?")))

    # UNIT control. First private functions for talking to axis
    def _get_units(self):
        return int(self._cmd('SN?'))

    def _set_units(self, new_units):
        return self._cmd('SN', params=[int(new_units)])

    # and a utility function to lookup unit dictionary given an astropy unit
    def _get_unit_num(self, quantity):
        """
        Gets the newport integer label for a given unit
        """
        for num, quant in self._unit_dict.items():
            if quant == quantity:
                return num

        raise KeyError('{} is not a valid unit for NewportESP301Axis'.format(quantity))

    # now public property for axis through astropy units
    @property
    def units(self):
        """
        Units of axis as an ```~astropy.units.Quantity``` object.
        """
        return self._units

    @units.setter
    def units(self, newval):
        if isinstance(newval, int):
            self._units = NewportError._unit_dict[newval]
        elif isinstance(newval, u.Quantity):
            self._units = newval
            newval = self._get_unit_num(newval)
        self._set_units(newval)

    def home(self, search_mode=1, errcheck=True):
        """
        Move device to home.

        Parameters
        ----------
        search_mode : int
            0 : search by zero position count
            1 : search for home and index signals (default)
            2 : search only for home signal
            3 : search for positive limit signal
            4 : search for negative limit signal
            5 : seach for positive limit and index signals
            6 : search for negative limit and index signals
        """
        self._cmd('OR', params=[search_mode], errcheck=errcheck)

    def move(self, position, absolute=True, wait=False, block=False):
        """
        Move to or by a specified position.

        Parameters
        ----------
        position : float or ```~astropy.units.Quantity```
            The position to move to (if absolute) or amount to move by
            if relative. If a float is provided, we assume the position
            is given in the current controller units.
        absolute : bool
            If `False`, position is a relative offset from current position
        wait : bool
            If `True`, function returns immediately, but axis is instructed
            not to execute other commands until move is finished.
        block : bool
            IF `True`, function will not return until move is complete.
        """
        if not isinstance(position, u.Quantity):
            position = position * self.units
        position = position.to_value(self.units)

        cmd = 'PA' if absolute else 'PR'
        self._cmd(cmd, params=[position])
        if wait:
            self.wait_for_position(position)
        if block:
            time.sleep(0.01)
            done = self.motion_complete
            while not done:
                done = self.motion_complete
                time.sleep(0.01)

    def wait_for_position(self, position):
        """
        Wait for axis to reach given position before executing other commands.

        Following this call, other commands can be sent to the controller, but they
        will not be executed until the specified position is reached. Most useful
        in bulk command mode or programming mode.

        Parameters
        ----------
        position : float or ```~astropy.units.Quantity```
            The position to wait for. If a float is provided, we assume the position
            is given in the current controller units.
        """
        if not isinstance(position, u.Quantity):
            position = position * self.units
        position = position.to_value(self.units)
        self._cmd('WP', params=[position])

    def wait_for_stop(self):
        """
        Waits for axis to stop before executing other commands.

        Following this call, other commands can be sent to the controller, but they
        will not be executed until the axis has stopped. Most useful
        in bulk command mode or programming mode.
        """
        self._cmd('WS')

    def abort_motion(self):
        """
        Stops motion immediately
        """
        self._cmd('AB')

    def stop_motion(self):
        """
        Stops motion with programmed decceleration.
        """
        self._cmd('ST')

    def move_to_hardware_limit(self):
        """
        Move to hardware travel limit
        """
        self._cmd('MT')

    def move_indefinitely(self):
        """
        Move until a stop request is received
        """
        self._cmd('MV')

    def power_on(self):
        """
        Turns on motor axis
        """
        self._cmd("MO")

    def power_off(self):
        """
        Turns off motor axis
        """
        self._cmd("MF")
